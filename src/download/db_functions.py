# import chromadb
# from chromadb.config import Settings
# from langchain_chroma import Chroma
# from langchain_huggingface import HuggingFaceEmbeddings

# # HTTP-клиент к серверу
# client = chromadb.HttpClient(host="localhost", port=8000, settings=Settings())

# # Эмбеддер (любой совместимый)
# emb = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")

# # LangChain-обёртка, указываем client (а не persist_directory)
# vectorstore = Chroma(
#     collection_name="docs",
#     client=client,
#     embedding_function=emb,
# )

# # Добавление документов
# from langchain_core.documents import Document
# docs = [Document(page_content="третий текст", metadata={"source": "c.txt"})]
# vectorstore.add_documents(docs)

# # Запрос
# hits = vectorstore.similarity_search("поисковый запрос", k=5)
# print(hits[0].page_content)


# from Parser.src.data import downloader_functions as d_f
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
    # Используем GPU-ускоренный векторайзер из Docker контейнера
    vector_config=[
        Configure.Vectors.text2vec_transformers(
            name="title_vector",
            source_properties=["title"],
            pooling_strategy="masked_mean",           # пример параметра
            inference_url="http://text2vec-transformers:8080"  # если несколько контейнеров
        )
    ],
)

client.close()
print("Weaviate connection closed.")