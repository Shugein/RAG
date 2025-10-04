"""
Пайплайн загрузки, обработки и индексации новостей в векторную БД
Использует локальную модель для извлечения сущностей и Weaviate для хранения
"""
import time
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import tqdm

import weaviate
import weaviate.classes.config as wc
from weaviate.classes.config import Configure
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.system.entity_recognition_local import LocalFinanceNERExtractor, ExtractedEntities


@dataclass
class NewsDocument:
    """Структура новостного документа"""
    text: str
    title: str
    url: str
    source: str
    timestamp: int
    entities: Optional[ExtractedEntities] = None


class NewsIndexingPipeline:
    """
    Пайплайн индексации новостей:
    1. Получение данных через API
    2. Извлечение сущностей локальной моделью
    3. Чанкование текста
    4. Сохранение в Weaviate
    """

    def __init__(
        self,
        weaviate_host: str = "localhost",
        weaviate_port: int = 8080,
        collection_name: str = "NewsChunks",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        batch_size: int = 32,
        use_entity_extraction: bool = True,
    ):
        """
        Параметры:
        - weaviate_host: хост Weaviate
        - weaviate_port: порт Weaviate
        - collection_name: название коллекции
        - chunk_size: размер чанка
        - chunk_overlap: перекрытие чанков
        - batch_size: размер батча для вставки
        - use_entity_extraction: использовать ли извлечение сущностей
        """
        self.weaviate_host = weaviate_host
        self.weaviate_port = weaviate_port
        self.collection_name = collection_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.batch_size = batch_size
        self.use_entity_extraction = use_entity_extraction

        # Клиент Weaviate
        self.client = None
        self.collection = None

        # Экстрактор сущностей
        self.entity_extractor = None

        # Сплиттер текста
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        # Статистика
        self.stats = {
            "total_documents": 0,
            "total_chunks": 0,
            "total_time": 0.0,
            "entity_extraction_time": 0.0,
            "indexing_time": 0.0,
        }

    def connect_weaviate(self):
        """Подключение к Weaviate"""
        print(f"🔌 Подключение к Weaviate ({self.weaviate_host}:{self.weaviate_port})...")

        self.client = weaviate.connect_to_local(
            host=self.weaviate_host,
            port=self.weaviate_port
        )

        if not self.client.is_ready():
            raise ConnectionError("Weaviate не готов")

        print("✅ Подключено к Weaviate")

    def initialize_collection(self, recreate: bool = False):
        """
        Инициализация коллекции в Weaviate

        Параметры:
        - recreate: если True, пересоздает коллекцию (удаляет существующую)
        """
        if not self.client:
            self.connect_weaviate()

        # Удаляем коллекцию если нужно
        if recreate and self.client.collections.exists(self.collection_name):
            print(f"🗑️  Удаление существующей коллекции {self.collection_name}...")
            self.client.collections.delete(self.collection_name)

        # Создаем коллекцию если не существует
        if not self.client.collections.exists(self.collection_name):
            print(f"📦 Создание коллекции {self.collection_name}...")

            properties = [
                # Текстовые поля
                wc.Property(name="original_text", data_type=wc.DataType.TEXT, skip_vectorization=False),
                wc.Property(name="text_for_bm25", data_type=wc.DataType.TEXT, skip_vectorization=True),

                # Метаданные чанка
                wc.Property(name="chunk_index", data_type=wc.DataType.INT),

                # Метаданные документа
                wc.Property(name="parent_doc_id", data_type=wc.DataType.TEXT, skip_vectorization=True),
                wc.Property(name="parent_doc_text", data_type=wc.DataType.TEXT, skip_vectorization=True),
                wc.Property(name="title", data_type=wc.DataType.TEXT, skip_vectorization=True),
                wc.Property(name="url", data_type=wc.DataType.TEXT, skip_vectorization=True),
                wc.Property(name="source", data_type=wc.DataType.TEXT, skip_vectorization=True),
                wc.Property(name="timestamp", data_type=wc.DataType.INT, skip_vectorization=True),
            ]

            # Добавляем поля для сущностей если включено
            if self.use_entity_extraction:
                properties.extend([
                    # Сущности (JSON строки)
                    wc.Property(name="entities_json", data_type=wc.DataType.TEXT, skip_vectorization=True),

                    # Отдельные поля для фильтрации
                    wc.Property(name="companies", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
                    wc.Property(name="people", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
                    wc.Property(name="markets", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
                ])

            self.collection = self.client.collections.create(
                name=self.collection_name,
                vectorizer_config=Configure.Vectorizer.text2vec_transformers(
                    vectorize_collection_name=False
                ),
                reranker_config=Configure.Reranker.transformers(),
                properties=properties,
            )

            print(f"✅ Коллекция {self.collection_name} создана")
        else:
            self.collection = self.client.collections.get(self.collection_name)
            print(f"✅ Используется существующая коллекция {self.collection_name}")

    def initialize_entity_extractor(self):
        """Инициализация экстрактора сущностей"""
        if not self.use_entity_extraction:
            print("⚠️  Извлечение сущностей отключено")
            return

        print("🔧 Инициализация экстрактора сущностей...")
        self.entity_extractor = LocalFinanceNERExtractor(
            model_name="unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
            device="cuda",
            batch_size=10
        )
        print("✅ Экстрактор сущностей инициализирован")

    def extract_entities_batch(self, news_list: List[NewsDocument]) -> List[NewsDocument]:
        """
        Извлечение сущностей из батча новостей

        Параметры:
        - news_list: список новостных документов

        Возвращает:
        - список документов с извлеченными сущностями
        """
        if not self.use_entity_extraction or not self.entity_extractor:
            return news_list

        print(f"🔍 Извлечение сущностей из {len(news_list)} новостей...")
        start_time = time.time()

        # Извлекаем тексты
        texts = [news.text for news in news_list]

        # Batch обработка
        entities_list = self.entity_extractor.extract_entities_batch(texts, verbose=False)

        # Добавляем сущности к документам
        for i, entities in enumerate(entities_list):
            news_list[i].entities = entities

        elapsed = time.time() - start_time
        self.stats["entity_extraction_time"] += elapsed

        success_count = sum(1 for news in news_list if news.entities is not None)
        print(f"✅ Извлечено сущностей: {success_count}/{len(news_list)} ({elapsed:.2f}s)")

        return news_list

    def prepare_chunks(self, news: NewsDocument) -> List[Dict[str, Any]]:
        """
        Подготовка чанков из новости

        Параметры:
        - news: новостной документ

        Возвращает:
        - список чанков с метаданными
        """
        parent_doc_id = str(uuid.uuid4())
        chunks = self.text_splitter.split_text(news.text)

        prepared_chunks = []

        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())

            # Базовые свойства
            properties = {
                "original_text": chunk_text,
                "text_for_bm25": chunk_text.lower(),  # Для BM25 поиска
                "chunk_index": chunk_idx,
                "parent_doc_id": parent_doc_id,
                "parent_doc_text": news.text,
                "title": news.title,
                "url": news.url,
                "source": news.source,
                "timestamp": news.timestamp,
            }

            # Добавляем сущности если есть
            if self.use_entity_extraction and news.entities:
                entities = news.entities

                # Сохраняем JSON
                properties["entities_json"] = entities.model_dump_json()

                # Массивы для фильтрации
                properties["companies"] = [c.name for c in entities.companies]
                properties["people"] = [p.name for p in entities.people]
                properties["markets"] = [m.name for m in entities.markets]

            prepared_chunks.append({
                "id": chunk_id,
                "properties": properties
            })

        return prepared_chunks

    def index_documents(self, news_list: List[NewsDocument], show_progress: bool = True):
        """
        Индексация документов в Weaviate

        Параметры:
        - news_list: список новостных документов
        - show_progress: показывать ли прогресс-бар
        """
        if not self.collection:
            self.initialize_collection()

        print(f"\n📥 Индексация {len(news_list)} новостей...")
        start_time = time.time()

        # Подготовка чанков
        all_chunks = []
        for news in tqdm.tqdm(news_list, desc="Подготовка чанков", disable=not show_progress):
            chunks = self.prepare_chunks(news)
            all_chunks.extend(chunks)

        print(f"📦 Подготовлено {len(all_chunks)} чанков")

        # Batch вставка
        with self.collection.batch.fixed_size(batch_size=self.batch_size) as batch:
            for chunk in tqdm.tqdm(all_chunks, desc="Индексация", disable=not show_progress):
                batch.add_object(
                    properties=chunk["properties"],
                    uuid=chunk["id"]
                )

                if batch.number_errors > 50:
                    print(f"⚠️  Остановка из-за большого количества ошибок: {batch.number_errors}")
                    break

        elapsed = time.time() - start_time
        self.stats["indexing_time"] += elapsed
        self.stats["total_documents"] += len(news_list)
        self.stats["total_chunks"] += len(all_chunks)

        print(f"✅ Индексация завершена за {elapsed:.2f}s")
        print(f"   Ошибок: {batch.number_errors}")

    def process_and_index(
        self,
        news_list: List[NewsDocument],
        extract_entities: bool = True,
        show_progress: bool = True
    ):
        """
        Полный пайплайн: извлечение сущностей + индексация

        Параметры:
        - news_list: список новостных документов
        - extract_entities: извлекать ли сущности
        - show_progress: показывать ли прогресс
        """
        print(f"\n{'='*60}")
        print(f"🚀 ЗАПУСК ПАЙПЛАЙНА ИНДЕКСАЦИИ")
        print(f"{'='*60}")
        print(f"Новостей: {len(news_list)}")
        print(f"Извлечение сущностей: {'Да' if extract_entities and self.use_entity_extraction else 'Нет'}")
        print(f"{'='*60}\n")

        start_time = time.time()

        # Шаг 1: Извлечение сущностей
        if extract_entities and self.use_entity_extraction:
            news_list = self.extract_entities_batch(news_list)

        # Шаг 2: Индексация
        self.index_documents(news_list, show_progress=show_progress)

        # Статистика
        total_time = time.time() - start_time
        self.stats["total_time"] += total_time

        print(f"\n{'='*60}")
        print("✅ ПАЙПЛАЙН ЗАВЕРШЕН")
        print(f"{'='*60}")
        print(f"Всего времени: {total_time:.2f}s")
        print(f"  - Извлечение сущностей: {self.stats['entity_extraction_time']:.2f}s")
        print(f"  - Индексация: {self.stats['indexing_time']:.2f}s")
        print(f"Обработано документов: {len(news_list)}")
        print(f"Создано чанков: {self.stats['total_chunks']}")
        print(f"{'='*60}\n")

    def get_collection_stats(self) -> Dict[str, Any]:
        """Получение статистики коллекции"""
        if not self.collection:
            return {}

        total_count = self.collection.aggregate.over_all().total_count

        return {
            "collection_name": self.collection_name,
            "total_objects": total_count,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }

    def close(self):
        """Закрытие соединения"""
        if self.client:
            self.client.close()
            print("🔌 Соединение с Weaviate закрыто")


# ===== ПРИМЕР ИСПОЛЬЗОВАНИЯ =====
def main():
    """Пример использования пайплайна"""

    # Создаем пайплайн
    pipeline = NewsIndexingPipeline(
        collection_name="NewsChunks",
        chunk_size=500,
        chunk_overlap=100,
        use_entity_extraction=True,
    )

    # Подключаемся к Weaviate
    pipeline.connect_weaviate()

    # Инициализируем коллекцию (пересоздать = False)
    pipeline.initialize_collection(recreate=False)

    # Инициализируем экстрактор сущностей
    pipeline.initialize_entity_extractor()

    # Примеры новостей (обычно загружаются через API)
    sample_news = [
        NewsDocument(
            text="""Акции Сбербанка выросли на 3.2% после публикации отчетности.
            Чистая прибыль составила 389 млрд рублей. Глава Сбербанка Герман Греф
            заявил о планах увеличить дивиденды.""",
            title="Сбербанк показал рост прибыли",
            url="https://example.com/news/1",
            source="РБК",
            timestamp=1704067200  # 2024-01-01
        ),
        NewsDocument(
            text="""Индекс ММВБ закрылся на отметке 3245 пунктов (+1.5%).
            На фоне роста цен на нефть выросли акции Лукойла (+2.1%) и Роснефти (+1.8%).""",
            title="Российский рынок акций вырос",
            url="https://example.com/news/2",
            source="Интерфакс",
            timestamp=1704153600
        ),
        NewsDocument(
            text="""ЦБ РФ повысил ключевую ставку до 16%. Аналитики ВТБ Капитал
            ожидают замедления инфляции в следующем квартале.""",
            title="ЦБ повысил ключевую ставку",
            url="https://example.com/news/3",
            source="ТАСС",
            timestamp=1704240000
        ),
    ]

    # Запускаем пайплайн
    pipeline.process_and_index(sample_news)

    # Статистика коллекции
    stats = pipeline.get_collection_stats()
    print("\n📊 Статистика коллекции:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    # Закрываем соединение
    pipeline.close()


if __name__ == "__main__":
    main()
