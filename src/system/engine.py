"""
RAG Pipeline Engine
Основной модуль для поиска и генерации ответов
"""
import logging
import time
from typing import List, Dict, Any
import weaviate

from src.system import search, llm

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

    def search(self, query: str, limit: int = 10, rerank_limit: int = 3, use_parent_docs: bool = True) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов с реренкингом

        Args:
            query: Поисковый запрос
            limit: Количество результатов для первичного поиска
            rerank_limit: Количество результатов после реренкинга
            use_parent_docs: Использовать полные родительские документы вместо чанков

        Returns:
            Список документов с метаданными
        """
        logger.info(f"Searching for: '{query}' (parent_docs: {use_parent_docs})")
        start_time = time.time()

        results = search.hybrid_search_with_rerank(
            self.collection,
            query=query,
            limit=limit,
            rerank_limit=rerank_limit,
            use_parent_docs=use_parent_docs
        )

        search_time = time.time() - start_time
        doc_type = "parent documents" if use_parent_docs else "chunks"
        logger.info(f"Search completed in {search_time:.2f}s, found {len(results)} {doc_type}")

        return results

    def generate_answer(self, query: str, context_docs: List[Dict[str, Any]], reasoning_level: str = "low") -> str:
        """
        Генерация ответа на основе найденных документов

        Args:
            query: Исходный вопрос пользователя
            context_docs: Найденные документы
            reasoning_level: Уровень рассуждений ('low', 'medium', 'high')

        Returns:
            Сгенерированный ответ
        """
        logger.info("Generating answer with LLM...")
        start_time = time.time()

        # Формируем контекст из документов
        context_parts = []
        for i, doc in enumerate(context_docs, 1):
            context_parts.append(
                f"Документ {i} (источник: {doc['source']}):\n{doc['text'][:500]}..."
            )

        context = "\n\n".join(context_parts)

        # Формируем промпт
        prompt = f"""На основе следующих документов ответь на вопрос пользователя.

КОНТЕКСТ:
{context}

ВОПРОС: {query}

ОТВЕТ (используй только информацию из контекста, если информации недостаточно - так и скажи):"""

        # Генерируем ответ
        answer = llm.generate_llm_response(prompt, reasoning_level=reasoning_level)

        gen_time = time.time() - start_time
        logger.info(f"Answer generated in {gen_time:.2f}s")

        return answer

    def query(self, user_query: str, search_limit: int = 10, rerank_limit: int = 3, reasoning_level: str = "low", use_parent_docs: bool = True) -> Dict[str, Any]:
        """
        Полный RAG пайплайн: поиск + генерация ответа

        Args:
            user_query: Вопрос пользователя
            search_limit: Количество результатов для первичного поиска
            rerank_limit: Количество результатов после реренкинга
            reasoning_level: Уровень рассуждений LLM
            use_parent_docs: Использовать полные родительские документы

        Returns:
            Dict с ответом и метаданными
        """
        logger.info(f"Processing query: '{user_query}' (parent_docs: {use_parent_docs})")
        pipeline_start = time.time()

        # Поиск
        search_results = self.search(user_query, limit=search_limit, rerank_limit=rerank_limit, use_parent_docs=use_parent_docs)

        # Генерация ответа
        answer = self.generate_answer(user_query, search_results, reasoning_level=reasoning_level)

        pipeline_time = time.time() - pipeline_start

        result = {
            'query': user_query,
            'answer': answer,
            'documents': search_results,
            'metadata': {
                'total_time': pipeline_time,
                'num_documents': len(search_results),
                'vectorizer': 'sergeyzh/BERTA',
                'reranker': 'BAAI/bge-reranker-v2-m3',
                'llm_model': 'openai/gpt-oss-20b:free',
                'use_parent_docs': use_parent_docs
            }
        }

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
        test_query = "Стоимость акций Газпрома"

        print(f"\n{'='*80}")
        print(f"RAG PIPELINE TEST")
        print(f"{'='*80}")
        print(f"\nQuery: {test_query}\n")

        # Выполнение запроса
        result = rag.query(
            user_query=test_query,
            search_limit=10,
            rerank_limit=3,
            reasoning_level="low"
        )

        # Вывод результатов
        print(f"\n{'='*80}")
        print(f"ANSWER:")
        print(f"{'='*80}")
        print(result['answer'])

        print(f"\n{'='*80}")
        print(f"DOCUMENTS USED:")
        print(f"{'='*80}")
        for i, doc in enumerate(result['documents'], 1):
            print(f"\n{i}. {doc['title']}")
            print(f"   Rerank Score: {doc['rerank_score']:.4f}")
            print(f"   Source: {doc['source']}")

        print(f"\n{'='*80}")
        print(f"METADATA:")
        print(f"{'='*80}")
        for key, value in result['metadata'].items():
            print(f"   {key}: {value}")

    finally:
        rag.close()