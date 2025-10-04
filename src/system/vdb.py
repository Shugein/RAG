from src.download import downloader_functions as d_f
import tqdm

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

# Подключение к локальному серверу Weaviate (http://localhost:8080 по умолчанию)
client = weaviate.connect_to_local()
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
        # Основные текстовые поля (original_text будет векторизироваться автоматически)
        wc.Property(name="text_for_bm25", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="original_text", data_type=wc.DataType.TEXT, skip_vectorization=False),

        # Метаданные чанка
        wc.Property(name="chunk_index", data_type=wc.DataType.INT),

        # Метаданные родительского документа
        wc.Property(name="parent_doc_id", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="parent_doc_text", data_type=wc.DataType.TEXT, skip_vectorization=True),

        # Метаданные новости
        wc.Property(name="title", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="timestamp", data_type=wc.DataType.INT, skip_vectorization=True),
        wc.Property(name="url", data_type=wc.DataType.TEXT, skip_vectorization=True),
        wc.Property(name="source", data_type=wc.DataType.TEXT, skip_vectorization=True),
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
        batch.add_object(
            properties={
                "text_for_bm25": doc.metadata["text_for_bm25"],
                "original_text": doc.page_content,  # Это поле будет автоматически векторизировано
                "chunk_index": doc.metadata["chunk_index"],
                "parent_doc_id": doc.metadata["parent_doc_id"],
                "parent_doc_text": doc.metadata["parent_doc_text"],
                "title": doc.metadata["title"],
                "timestamp": doc.metadata["timestamp"],
                "url": doc.metadata["url"],
                "source": doc.metadata["source"],
            },
            uuid=doc.metadata["id"]
        )

        if batch.number_errors > 50:
            print(f"Batch import stopped due to excessive errors at document {i}")
            break

print(f"Batch completed with {batch.number_errors} errors")



print("Data insertion completed!")
print("Total objects in collection:", collection.aggregate.over_all().total_count)

