from src.download import downloader_functions as d_f
from src.system.entity_recognition import ExtractedEntities
import tqdm
import json

import torch
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    device = torch.device("mps")
else:
    device = torch.device("cpu")
print("using device", device)

import weaviate
import weaviate.classes.config as wc
from weaviate.classes.config import Configure

# ========== Weaviate с GPU эмбеддингом через Docker ========== #

print("Using Weaviate with GPU-accelerated embeddings via Docker container")

# Подключение к локальному серверу Weaviate на порту 8083
client = weaviate.connect_to_local(port=8083, grpc_port=50051)
assert client.is_ready(), "Weaviate is not ready"

COLL_NAME = "NewsChunks"

# Удаляем коллекцию если она существует
if client.collections.exists(COLL_NAME):
    client.collections.delete(COLL_NAME)
    print(f"Deleted existing collection: {COLL_NAME}")

# Создаём новую коллекцию с расширенной схемой
collection = client.collections.create(
    name=COLL_NAME,
    vectorizer_config=Configure.Vectorizer.text2vec_transformers(
        vectorize_collection_name=False
    ),
    # Включаем reranker для коллекции
    reranker_config=Configure.Reranker.transformers(),
    properties=[
        # ===== ОСНОВНЫЕ ТЕКСТОВЫЕ ПОЛЯ =====
        wc.Property(name="text_for_bm25", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="original_text", data_type=wc.DataType.TEXT, skip_vectorization=False),

        # ===== МЕТАДАННЫЕ ЧАНКА =====
        wc.Property(name="chunk_index", data_type=wc.DataType.INT),

        # ===== МЕТАДАННЫЕ РОДИТЕЛЬСКОГО ДОКУМЕНТА =====
        wc.Property(name="parent_doc_id", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="parent_doc_text", data_type=wc.DataType.TEXT, skip_vectorization=True),

        # ===== БАЗОВЫЕ МЕТАДАННЫЕ НОВОСТИ =====
        wc.Property(name="title", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="timestamp", data_type=wc.DataType.INT, skip_vectorization=True),
        wc.Property(name="url", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="source", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="publication_date", data_type=wc.DataType.TEXT, skip_vectorization=True),

        # ===== HOTNESS SCORE =====
        # Оценка "горячести" новости от 0.0 до 1.0
        # Используется для ранжирования актуальных новостей
        wc.Property(name="hotness", data_type=wc.DataType.NUMBER, skip_vectorization=True),

        # ===== ИЗВЛЕЧЕННЫЕ СУЩНОСТИ (JSON) =====
        # Полный JSON с извлеченными сущностями
        wc.Property(name="entities_json", data_type=wc.DataType.TEXT, skip_vectorization=True),

        # ===== КОМПАНИИ (для фильтрации и поиска) =====
        wc.Property(name="companies", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
        wc.Property(name="company_tickers", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
        wc.Property(name="company_sectors", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),

        # ===== ПЕРСОНЫ (для фильтрации и поиска) =====
        wc.Property(name="people", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
        wc.Property(name="people_positions", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),

        # ===== РЫНКИ/БИРЖИ/ИНДЕКСЫ (для фильтрации и поиска) =====
        wc.Property(name="markets", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
        wc.Property(name="market_types", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),

        # ===== ФИНАНСОВЫЕ МЕТРИКИ =====
        wc.Property(name="financial_metric_types", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
        wc.Property(name="financial_metric_values", data_type=wc.DataType.TEXT_ARRAY, skip_vectorization=True),
    ],
)

print(f"Created collection: {COLL_NAME}")

# Подготавливаем данные из нашей функции
print("Preparing data from documents...")
weaviate_data = d_f.prepare_weaviate_data(d_f.documents)
print(f"Prepared {len(weaviate_data)} chunks for insertion")

# Загрузка данных с автоматической GPU векторизацией
print("Inserting data with automatic GPU vectorization...")

with collection.batch.fixed_size(batch_size=32) as batch:
    for i, doc in enumerate(tqdm.tqdm(weaviate_data, desc="Inserting documents")):
        # Weaviate автоматически векторизирует original_text с помощью GPU

        # Извлекаем entities из метаданных (если есть)
        entities = doc.metadata.get("entities")

        # Базовые свойства
        properties = {
            "text_for_bm25": doc.metadata["text_for_bm25"],
            "original_text": doc.page_content,
            "chunk_index": doc.metadata["chunk_index"],
            "parent_doc_id": doc.metadata["parent_doc_id"],
            "parent_doc_text": doc.metadata["parent_doc_text"],
            "title": doc.metadata["title"],
            "timestamp": doc.metadata["timestamp"],
            "url": doc.metadata["url"],
            "source": doc.metadata["source"],
            "publication_date": doc.metadata.get("publication_date", ""),

            # Hotness score из метаданных
            "hotness": doc.metadata.get("hotness", 0.5),
        }

        # Если есть entities - добавляем их
        if entities:
            properties["entities_json"] = entities.model_dump_json()
            properties["companies"] = [c.name for c in entities.companies]
            properties["company_tickers"] = [c.ticker for c in entities.companies if c.ticker]
            properties["company_sectors"] = [c.sector for c in entities.companies if c.sector]
            properties["people"] = [p.name for p in entities.people]
            properties["people_positions"] = [p.position for p in entities.people if p.position]
            properties["markets"] = [m.name for m in entities.markets]
            properties["market_types"] = [m.type for m in entities.markets]
            properties["financial_metric_types"] = [fm.metric_type for fm in entities.financial_metrics]
            properties["financial_metric_values"] = [fm.value for fm in entities.financial_metrics]
        else:
            # Пустые значения
            properties["entities_json"] = ""
            properties["companies"] = []
            properties["company_tickers"] = []
            properties["company_sectors"] = []
            properties["people"] = []
            properties["people_positions"] = []
            properties["markets"] = []
            properties["market_types"] = []
            properties["financial_metric_types"] = []
            properties["financial_metric_values"] = []

        batch.add_object(
            properties=properties,
            uuid=doc.metadata["id"]
        )

        if batch.number_errors > 50:
            print(f"Batch import stopped due to excessive errors at document {i}")
            break

print(f"Batch completed with {batch.number_errors} errors")



print("Data insertion completed!")
print("Total objects in collection:", collection.aggregate.over_all().total_count)

