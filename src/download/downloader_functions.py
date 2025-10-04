from datasets import load_dataset
import re
import uuid
import tqdm
import nltk
from nltk.stem import WordNetLemmatizer
from langchain_core.documents import Document 

from langchain_text_splitters import RecursiveCharacterTextSplitter

nltk.download('wordnet')

#### ========== Helper functions ========== ####
def clean_text(text):
    """
    Очищает текст от лишних символов и повторений.

    Параметры:
    - text (str): Исходный текст.

    Возвращает:
    - clean_text (str): Очищенный текст.
    """
    # Удаляем лишние пробелы и переносы строк
    text = re.sub(r'\s+', ' ', text)

    # Удаляем оставшиеся многократные пробелы после удаления шаблонов
    text = re.sub(r'\s+', ' ', text)

    return text.strip()

def lemmatize_corpus(texts):
    clean_texts = []

    for text in tqdm.tqdm(texts):

        lemm_text = [WordNetLemmatizer().lemmatize(w) for w in text.lower().split()]
        clean_texts.append(" ".join(lemm_text))

    return clean_texts

ds = load_dataset("IlyaGusev/ru_news", split="train").shuffle(seed=7).select(range(5000))
docs = [r["text"] for r in ds if "text" in r and r["text"]]

## // TODO metadata seacrh by time, title and source + adding url 

### === Preapering data === ###
# only text
# // TODO fix in one data pipe

documents = [
    Document(
        page_content=row['text'],                 
        metadata={"title": row["title"],
                   'time': row['timestamp'],
                     'url': row['url'],
                       'source': row['source'],
                         'clear_txt': row['text']},
    )
    for row in ds
]

def prepare_weaviate_data(documents, chunk_size=500, chunk_overlap=100):
    """
    Подготавливает данные для загрузки в Weaviate с поддержкой гибридного поиска.

    Параметры:
    - documents: список Document объектов с текстом и метаданными
    - chunk_size: размер чанка для векторизации
    - chunk_overlap: перекрытие между чанками

    Возвращает:
    - список Document объектов с лемматизированным текстом и метаданными
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    weaviate_data = []

    for doc_idx, doc in enumerate(documents):
        parent_doc_id = str(uuid.uuid4())
        original_text = doc.page_content
        cleaned_text = clean_text(original_text)

        chunks = splitter.split_text(cleaned_text or "")

        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())

            lemmatized_chunk = lemmatize_text(chunk_text)

            chunk_document = Document(
                page_content=lemmatized_chunk,
                metadata={
                    "id": chunk_id,
                    "parent_doc_id": parent_doc_id,
                    "parent_doc_text": original_text,
                    "text_for_bm25": lemmatized_chunk,
                    "original_text": chunk_text,
                    "chunk_index": chunk_idx,
                    "title": doc.metadata.get("title", ""),
                    "timestamp": doc.metadata.get("time", ""),
                    "url": doc.metadata.get("url", ""),
                    "source": doc.metadata.get("source", ""),

                }
            )

            weaviate_data.append(chunk_document)

    return weaviate_data

def lemmatize_text(text):
    """
    Лемматизирует отдельный текст.

    Параметры:
    - text (str): Исходный текст

    Возвращает:
    - lemmatized_text (str): Лемматизированный текст
    """
    lemmatizer = WordNetLemmatizer()
    lemmatized_words = [lemmatizer.lemmatize(w) for w in text.lower().split()]
    return " ".join(lemmatized_words)

weaviate_data = prepare_weaviate_data(documents)

print(f"Подготовлено {len(weaviate_data)} чанков для загрузки в Weaviate")
print("Пример данных:")
if weaviate_data:
    example = weaviate_data[0]
    print(f"ID: {example.metadata['id']}")
    print(f"Текст для векторизации: {example.page_content[:100]}...")
    print(f"Метаданные: title={example.metadata['title']}, source={example.metadata['source']}, url={example.metadata['url']}, timestamp={example.metadata['timestamp']}, parent_doc_id={example.metadata['parent_doc_id']}")