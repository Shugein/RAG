import re
import uuid
import tqdm
import nltk
import json
import os
from nltk.stem import WordNetLemmatizer
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
from src.system.entity_recognition import CachedFinanceNERExtractor

nltk.download('wordnet')

# Загружаем API ключ
load_dotenv()
API_KEY = os.environ.get('API_KEY_2')

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

# Загрузка данных из JSON файла
def load_news_from_json(json_path="parser/test_news.json"):
    """
    Загружает новости из JSON файла.

    Параметры:
    - json_path: путь к JSON файлу

    Возвращает:
    - список словарей с новостями
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

# Загружаем данные из JSON
ds = load_news_from_json()

### === Preparing data === ###
documents = [
    Document(
        page_content=row['text'],
        metadata={
            "title": row["title"],
            'timestamp': row['timestamp'],
            'url': row['url'],
            'source': row['source'],
            'clear_txt': row['text']
        },
    )
    for row in ds
]

def prepare_weaviate_data(documents, chunk_size=800, chunk_overlap=200, extract_entities=True):
    """
    Подготавливает данные для загрузки в Weaviate с поддержкой гибридного поиска.

    Параметры:
    - documents: список Document объектов с текстом и метаданными
    - chunk_size: размер чанка для векторизации
    - chunk_overlap: перекрытие между чанками
    - extract_entities: извлекать ли сущности через NER (параллельно)

    Возвращает:
    - список Document объектов с лемматизированным текстом и метаданными
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    weaviate_data = []

    # Инициализируем экстрактор сущностей если нужно
    extractor = None
    all_entities = []

    if extract_entities and API_KEY:
        extractor = CachedFinanceNERExtractor(
            api_key=API_KEY,
            enable_caching=True
        )
        print(f"Инициализирован экстрактор сущностей: {extractor.model}")

        # ПАРАЛЛЕЛЬНОЕ извлечение сущностей для всех документов сразу
        print(f"Извлечение сущностей параллельно для {len(documents)} документов...")
        news_texts = [doc.page_content for doc in documents]
        all_entities = extractor.extract_entities_batch(news_texts, verbose=False, parallel=True)
        print(f"✓ Извлечение завершено!")

    for doc_idx, doc in enumerate(tqdm.tqdm(documents, desc="Creating chunks")):
        parent_doc_id = str(uuid.uuid4())
        original_text = doc.page_content
        cleaned_text = clean_text(original_text)

        # Получаем уже извлеченные сущности для этого документа
        entities = all_entities[doc_idx] if all_entities else None

        if entities:
            print(f"  Документ {doc_idx + 1}: компаний={len(entities.companies)}, персон={len(entities.people)}, рынков={len(entities.markets)}")

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
                    "timestamp": doc.metadata.get("timestamp", ""),
                    "url": doc.metadata.get("url", ""),
                    "source": doc.metadata.get("source", ""),
                    "entities": entities,  # Добавляем извлеченные сущности
                    "publication_date": entities.publication_date if entities else "",
                    "hotness": 0.5,  # Дефолтное значение hotness
                }
            )

            weaviate_data.append(chunk_document)

    # Выводим статистику если использовали экстрактор
    if extractor:
        extractor.print_stats()

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

weaviate_data = prepare_weaviate_data(documents, extract_entities=True)

print(f"\nПодготовлено {len(weaviate_data)} чанков для загрузки в Weaviate")
print("Пример данных:")
if weaviate_data:
    example = weaviate_data[0]
    print(f"ID: {example.metadata['id']}")
    print(f"Текст для векторизации: {example.page_content[:100]}...")
    print(f"Метаданные: title={example.metadata['title']}, source={example.metadata['source']}, url={example.metadata['url']}, timestamp={example.metadata['timestamp']}, parent_doc_id={example.metadata['parent_doc_id']}")
    if example.metadata.get('entities'):
        entities = example.metadata['entities']
        print(f"Сущности: компаний={len(entities.companies)}, персон={len(entities.people)}, рынков={len(entities.markets)}")