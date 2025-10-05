"""
RAG Pipeline Engine
Основной модуль для поиска и генерации ответов с интеграцией LLM_final
"""
import logging
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import weaviate

from src.system import search
from src.system.LLM_final.main import (
    generate_news_draft,
    DraftRequest,
    SourceItem,
    Instrument,
    Forecast,
    DraftResponse
)
from src.system.LLM_final.output import save_article_pdf
from src.system.entity_recognition import ExtractedEntities

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RAGPipeline:
    """RAG пайплайн для поиска и генерации ответов"""

    def __init__(self, collection_name: str = "NewsChunks"):
        """
        Инициализация RAG пайплайна

        Args:
            collection_name: Имя коллекции в Weaviate
        """
        self.collection_name = collection_name
        self.client = None
        self.collection = None

    def connect(self):
        """Подключение к Weaviate"""
        logger.info("Connecting to Weaviate...")
        self.client = weaviate.connect_to_local()

        if not self.client.is_ready():
            raise ConnectionError("Weaviate is not ready")

        self.collection = self.client.collections.use(self.collection_name)
        logger.info(f"Connected to collection: {self.collection_name}")

    def search(
        self,
        query: str,
        limit: int = 10,
        rerank_limit: int = 3,
        use_parent_docs: bool = True,
        hotness_weight: float = 0.3,
        alpha: float = 0.6
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов с реренкингом

        Args:
            query: Поисковый запрос
            limit: Количество результатов для первичного поиска
            rerank_limit: Количество результатов после реренкинга
            use_parent_docs: Использовать полные родительские документы вместо чанков
            hotness_weight: Вес hotness в финальном скоре (0.0-1.0)
            alpha: Баланс между векторным и BM25 поиском (0.0-1.0)

        Returns:
            Список документов с метаданными
        """
        logger.info(f"Searching for: '{query}' (parent_docs: {use_parent_docs}, alpha: {alpha})")
        start_time = time.time()

        results = search.hybrid_search_with_rerank(
            self.collection,
            query=query,
            limit=limit,
            rerank_limit=rerank_limit,
            use_parent_docs=use_parent_docs,
            hotness_weight=hotness_weight,
            alpha=alpha
        )

        search_time = time.time() - start_time
        doc_type = "parent documents" if use_parent_docs else "chunks"
        logger.info(f"Search completed in {search_time:.2f}s, found {len(results)} {doc_type}")

        return results

    def generate_article(
        self,
        query: str,
        context_docs: List[Dict[str, Any]],
        news_type: str = "industry_trend",
        tone: str = "explanatory",
        desired_outputs: List[str] = None
    ) -> DraftResponse:
        """
        Генерация статьи на основе найденных документов через LLM_final

        Args:
            query: Исходный вопрос/тема пользователя
            context_docs: Найденные документы с метаданными и сущностями
            news_type: Тип новости (earnings, guidance, macro, industry_trend, etc.)
            tone: Тональность (neutral, explanatory, urgent, etc.)
            desired_outputs: Форматы вывода (social_post, article_draft, alert, etc.)

        Returns:
            DraftResponse с готовыми текстами
        """
        logger.info("Generating article with LLM_final...")
        start_time = time.time()

        if desired_outputs is None:
            desired_outputs = ["social_post", "article_draft"]

        # Формируем данные из документов
        summary_parts = []
        sources = []
        all_text = []
        instruments = []
        all_companies = set()
        all_tickers = set()

        for doc in context_docs:
            # Собираем весь текст для body_text
            all_text.append(doc.get('text', ''))

            # Собираем источники
            if doc.get('url'):
                sources.append(SourceItem(
                    title=doc.get('title', 'Источник'),
                    url=doc['url']
                ))

            # Краткая выжимка для summary
            summary_parts.append(f"{doc.get('title', '')}: {doc.get('text', '')[:200]}")

        # Обрабатываем сущности из ПЕРВОГО документа (самого релевантного)
        if context_docs:
            first_doc = context_docs[0]

            # Извлекаем компании и тикеры из метаданных
            companies = first_doc.get('companies', [])
            company_tickers = first_doc.get('company_tickers', [])
            company_sectors = first_doc.get('company_sectors', [])

            # Формируем инструменты
            for i, company in enumerate(companies):
                ticker = company_tickers[i] if i < len(company_tickers) else None
                sector = company_sectors[i] if i < len(company_sectors) else None

                if ticker:
                    instruments.append(Instrument(
                        ticker=ticker,
                        name=company,
                        class_="equity",
                        exchange="MOEX",  # По умолчанию MOEX для российских компаний
                        currency="RUB",
                        country="RU"
                    ))

        # Формируем headline из query
        headline = query if len(query) < 100 else query[:97] + "..."

        # Формируем summary из первых документов
        summary = " | ".join(summary_parts[:2])
        if len(summary) > 300:
            summary = summary[:297] + "..."

        # Полный текст для body_text
        body_text = "\n\n".join(all_text)

        # Получаем hotness из первого документа
        hot_score = context_docs[0].get('hotness', 0.5) if context_docs else 0.5

        # Формируем запрос для LLM
        draft_request = DraftRequest(
            news_type=news_type,
            language="ru",
            audience="mixed",
            tone=tone,
            headline=headline,
            summary=summary,
            body_text=body_text,
            sources=sources,
            instruments=instruments,
            model_forecasts={},  # Можно добавить прогнозы если есть
            desired_outputs=desired_outputs,
            include_hashtags=True,
            include_disclaimer=True,
            include_visual_ideas=True,
            max_words_social=280,
            max_words_article=500,
            hot_score=hot_score
        )

        # Генерируем черновик
        draft = generate_news_draft(draft_request)

        gen_time = time.time() - start_time
        logger.info(f"Article generated in {gen_time:.2f}s")

        return draft

    def generate_pdf(
        self,
        draft: DraftResponse,
        output_path: str = "article.pdf"
    ) -> str:
        """
        Генерация PDF из DraftResponse

        Args:
            draft: DraftResponse объект с готовой статьей
            output_path: Путь для сохранения PDF

        Returns:
            Путь к сохраненному PDF файлу
        """
        logger.info(f"Generating PDF: {output_path}")
        start_time = time.time()

        # Конвертируем DraftResponse в dict для save_article_pdf
        draft_dict = draft.model_dump(by_alias=True)

        # Генерируем PDF
        pdf_path = save_article_pdf(draft_dict, output_path)

        gen_time = time.time() - start_time
        logger.info(f"PDF generated in {gen_time:.2f}s at {pdf_path}")

        return pdf_path

    def query(
        self,
        user_query: str,
        search_limit: int = 10,
        rerank_limit: int = 3,
        use_parent_docs: bool = True,
        news_type: str = "industry_trend",
        tone: str = "explanatory",
        desired_outputs: List[str] = None,
        generate_pdf: bool = False,
        pdf_path: str = "article.pdf"
    ) -> Dict[str, Any]:
        """
        Полный RAG пайплайн: поиск + генерация статьи + опциональный PDF

        Args:
            user_query: Вопрос/тема пользователя
            search_limit: Количество результатов для первичного поиска
            rerank_limit: Количество результатов после реренкинга
            use_parent_docs: Использовать полные родительские документы
            news_type: Тип новости для генерации
            tone: Тональность статьи
            desired_outputs: Форматы вывода
            generate_pdf: Генерировать PDF файл
            pdf_path: Путь для сохранения PDF

        Returns:
            Dict с статьей, метаданными и опциональным путем к PDF
        """
        logger.info(f"Processing query: '{user_query}' (parent_docs: {use_parent_docs})")
        pipeline_start = time.time()

        # Поиск
        search_results = self.search(
            user_query,
            limit=search_limit,
            rerank_limit=rerank_limit,
            use_parent_docs=use_parent_docs
        )

        # Генерация статьи
        draft = self.generate_article(
            user_query,
            search_results,
            news_type=news_type,
            tone=tone,
            desired_outputs=desired_outputs
        )

        pipeline_time = time.time() - pipeline_start

        result = {
            'query': user_query,
            'draft': draft,  # DraftResponse объект
            'documents': search_results,
            'metadata': {
                'total_time': pipeline_time,
                'num_documents': len(search_results),
                'vectorizer': 'text2vec-transformers (GPU)',
                'reranker': 'BAAI/bge-reranker-v2-m3',
                'llm_model': 'gpt-5',
                'use_parent_docs': use_parent_docs,
                'news_type': news_type,
                'tone': tone
            }
        }

        # Генерация PDF если запрошена
        if generate_pdf:
            pdf_file_path = self.generate_pdf(draft, pdf_path)
            result['pdf_path'] = pdf_file_path

        logger.info(f"Pipeline completed in {pipeline_time:.2f}s")
        return result

    def close(self):
        """Закрытие соединения с Weaviate"""
        if self.client:
            self.client.close()
            logger.info("Connection closed")


# CLI интерфейс для тестирования
if __name__ == "__main__":
    # Инициализация пайплайна
    rag = RAGPipeline()

    try:
        # Подключение
        rag.connect()

        # Тестовый запрос
        test_query = "Что известно о Сбербанке?"

        print(f"\n{'='*80}")
        print(f"RAG PIPELINE TEST - ARTICLE GENERATION")
        print(f"{'='*80}")
        print(f"\nQuery: {test_query}\n")

        # Выполнение запроса с генерацией PDF
        result = rag.query(
            user_query=test_query,
            search_limit=10,
            rerank_limit=3,
            use_parent_docs=True,
            news_type="industry_trend",
            tone="explanatory",
            desired_outputs=["social_post", "article_draft", "alert"],
            generate_pdf=False,
            pdf_path="sberbank_article.pdf"
        )

        # Вывод результатов
        draft = result['draft']

        print(f"\n{'='*80}")
        print(f"GENERATED ARTICLE:")
        print(f"{'='*80}")
        print(f"\nЗаголовок: {draft.headline}")
        print(f"Подзаголовок: {draft.dek}\n")

        print("Ключевые моменты:")
        for point in draft.key_points:
            print(f"  • {point}")

        print(f"\n--- Варианты текста ---")
        for variant_name, variant_text in draft.variants.items():
            print(f"\n[{variant_name.upper()}]:")
            print(variant_text[:300] + "..." if len(variant_text) > 300 else variant_text)

        if draft.hashtags:
            print(f"\nХэштеги: {' '.join(draft.hashtags)}")

        print(f"\n{'='*80}")
        print(f"DOCUMENTS USED:")
        print(f"{'='*80}")
        for i, doc in enumerate(result['documents'], 1):
            print(f"\n{i}. {doc['title']}")
            print(f"   Final Score: {doc['final_score']:.4f}")
            print(f"   Hotness: {doc['hotness']:.2f}")
            print(f"   Source: {doc['source']}")
            if doc.get('companies'):
                print(f"   Компании: {', '.join(doc['companies'])}")

        print(f"\n{'='*80}")
        print(f"METADATA:")
        print(f"{'='*80}")
        for key, value in result['metadata'].items():
            print(f"   {key}: {value}")

        # PDF
        if 'pdf_path' in result:
            print(f"\n{'='*80}")
            print(f"PDF GENERATED:")
            print(f"{'='*80}")
            print(f"   Path: {result['pdf_path']}")

    finally:
        rag.close()