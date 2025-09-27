import unsloth
# need test for torch and cuda

import torch
if torch.cuda.is_available():
    device = torch.device("cuda")
elif torch.backends.mps.is_available():
    # Apple Silicon
    device = torch.device("mps")
else:
    device = torch.device("cpu")
print("using device", device)


import numpy as np
import uuid
from tqdm.auto import tqdm
from groq import Groq
import pandas as pd
import csv
pd.set_option('display.max_colwidth', 2000)
import os

import chromadb
from sentence_transformers import SentenceTransformer
from chromadb.utils import embedding_functions
from chromadb import  Documents, EmbeddingFunction, Embeddings

from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_core.documents.base import Document

from langchain.text_splitter import RecursiveCharacterTextSplitter, CharacterTextSplitter

import json
import tempfile

from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, AutoConfig, pipeline

import requests
from bs4 import BeautifulSoup
# from googlesearch import search
import re

import nltk


from nltk.stem import WordNetLemmatizer
from tqdm import tqdm


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

def extract_main_content(html_content):
    """
    Извлекает основной текст из HTML-контента с помощью BeautifulSoup.

    Параметры:
    - html_content (str): HTML-код страницы.

    Возвращает:
    - text (str): Извлеченный и очищенный текст.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Удаляем все скрипты и стили
    for script_or_style in soup(['script', 'style', 'noscript']):
        script_or_style.decompose()

    # Пытаемся найти тег <article>, если он есть
    article = soup.find('article')
    if article:
        text = article.get_text(separator='\n')
    else:
        # Если <article> нет, выбираем наиболее содержательный <div>
        divs = soup.find_all('div')
        max_text = ''
        max_length = 0
        for div in divs:
            div_text = div.get_text(separator='\n').strip()
            div_length = len(div_text)
            if div_length > max_length:
                max_length = div_length
                max_text = div_text
        text = max_text

    # Дополнительная очистка текста
    clean_main_text = clean_text(text)

    return clean_main_text

def internet_search(query, k):
    """
    Выполняет поиск в интернете с помощью Google,
    загружает контент первых k ссылок и обрабатывает его с использованием Text Splitters из langchain.

    Параметры:
    - query (str): Поисковой запрос.
    - k (int): Количество ссылок для обработки.

    Возвращает:
    - result_array (list): Список, содержащий по 2 чанка с каждой ссылки.
    """
    # Выполнение поискового запроса
    links = search(query, lang='ru', num_results=k)
    result_array = []

    for idx, link in enumerate(links):
        try:
            print(f"Обрабатывается ссылка {idx+1}/{k}: {link}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/58.0.3029.110 Safari/537.3"
            }
            response = requests.get(link, headers=headers, timeout=10)
            response.raise_for_status()
            html_content = response.text

            # Извлечение основного текста
            clean_main_text = extract_main_content(html_content)

            if not clean_main_text:
                print(f"На странице {link} не найден основной текст.")
                continue

            # Разбиение текста на чанки
            text_splitter = RecursiveCharacterTextSplitter(
                separator='\n',
                chunk_size=1000,
                chunk_overlap=100
            )
            chunks = text_splitter.split_text(clean_main_text)

            # Берем только первые 2 чанка
            first_two_chunks = chunks[:2]

            result_array.append(clean_main_text)

        except requests.exceptions.RequestException as e:
            print(f"Ошибка при загрузке {link}: {e}")
        except Exception as e:
            print(f"Ошибка при обработке контента с {link}: {e}")

    return result_array

def groq_apr_request(
    topic: str,
    goal: int,
    input_text: str,
    sys_prompt: str,
    temperature: float = 0.5,
    top_p: float = 0.9,
    # repetition_penalty=1.2,
    max_tokens: int = 8192,
    table_file: str = "llama_test"
):
    """
    Отправляет запрос в модель LLM и записывает результат в CSV-файл.

    :param topic: Тема (например, 'Технологии', 'Здоровье' и т.д.).
    :param prompt: Промпт или формулировка запроса к модели.
    :param input_text: Текст инпута, который передаётся модели.
    :param temperature: Параметр Temperature в OpenAI API (степень креативности).
    :param top_p: Параметр top_p в OpenAI API (контроль вывода самых вероятных токенов).
    :param max_tokens: Максимальное число токенов в ответе.
    :param table_file: Путь к CSV-файлу, в который записывается результат.
    """

    chat_completion = client.chat.completions.create(
        # Подготовка сообщений для ChatCompletion (формат OpenAI Chat API)
        messages = [
            {
                "role": "system",
                "content": sys_prompt.format(input_text=input_text)
            },
            # {
            #     "role": "user",
            #     "content": input_text
            # }
        ],
        model="llama-3.3-70b-versatile",
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        # repetition_penalty=repetition_penalty,
        stream=False,
    )

    # Извлекаем текст ответа
    output_text = chat_completion.choices[0].message.content

    # Подсчитываем длины
    input_length = len(input_text.split())
    output_length = len(output_text.split())

    # Подготовим запись (строку) для CSV
    row = {
        "Тема": topic,
        "Цель": goal,
        "Температура": temperature,
        "Системный промпт": sys_prompt.format(input_text=input_text),
        "Длина Инпута (слов)": input_length,
        "Текст Инпута": input_text,
        "Длина Аутпута (слов)": output_length,
        "Текст Аутпута": output_text,
    }

    # Если файл не существует, создадим его с заголовками
    file_exists = os.path.exists(table_file)
    with open(table_file, mode="a", newline="", encoding="utf-8") as csvfile:
        fieldnames = list(row.keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        # Запишем строку в таблицу
        writer.writerow(row)

    # Возвращаем результат генерации (на случай, если нужно использовать дальше)
    return output_text

#### ========== data filtration ========== ####
df = pd.read_csv("/content/drive/MyDrive/Работа/data/lenta_ru_news_2022_2023_cut.csv")

# Создаём копию для безопасной обработки
df_clean = df.copy()

# Удаляем NaN значения в колонке 'text'
df_clean = df_clean.dropna(subset=['text'])

# Приводим все значения колонки к строковому типу
df_clean['text'] = df_clean['text'].astype(str)
df_clean['title'] = df_clean['title'].astype(str)

# Объединяем строки из колонок 'text1' и 'text2' через пробел
df_clean['combined'] = df_clean['title'] + '. ' + df_clean['text']

# Убираем лишние пробелы в объединённой строке
df_clean['combined'] = df_clean['combined'].str.strip()

# Удаляем пустые строки и строки, содержащие только пробелы
df_clean = df_clean[df_clean['combined'].str.strip() != '']

# Удаляем дубликаты по колонке 'text'
df_clean = df_clean.drop_duplicates(subset=['combined'])

print(f"Очистка завершена. Осталось строк: {len(df_clean)}")


#### ========== ChromaDB with SentenceTransformer ========== ####
# Инициализация HuggingFaceEmbeddings
embeddings_fun = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-large",
    model_kwargs = {'device': torch.device(device)})

print("GPU memory allocated after loading embedding model: %fGB" % (torch.cuda.memory_allocated() / 2**30))

db = Chroma(
    persist_directory="/content/drive/MyDrive/Работа/data/db_test",
    embedding_function=embeddings_fun
)

print('Amount of texts in DB before adding:', db._collection.count())

#===== Data clening for ChromaDB =====#

nltk.download('wordnet')

texts = df_clean['combined'].tolist()
texts[:5]

def lemmatize_corpus(texts):
    clean_texts = []

    for text in tqdm(texts):

        lemm_text = [WordNetLemmatizer().lemmatize(w) for w in text.lower().split()]
        clean_texts.append(" ".join(lemm_text))

    return clean_texts


clean_texts = lemmatize_corpus(texts)
print(clean_texts)

all_ids = [str(uuid.uuid4()) for _ in range(0, len(clean_texts))]

file_path = '/content/drive/MyDrive/Работа/data/all_ids.txt'

with open(file_path, 'w') as f:
    for id in all_ids:
        f.write(id + "\n")


#===== Adding texts to ChromaDB in batches =====#
# Определите размер батча
batch_size = 140

# Добавление документов по батчам
for i in tqdm(range(0, len(clean_texts), batch_size), desc="Добавление батчами"):
    batch_texts = clean_texts[i:i+batch_size]
    batch_ids = all_ids[i:i+batch_size]

    db.add_texts(
        ids=batch_ids,
        texts=batch_texts,
    )

print(db._collection.peek()['documents'][:5])
print('Amount of texts in DB after adding:', db._collection.count())

def semantic_search_with_score(db, query, limit=3):
    """
    Выполняет семантический поиск и возвращает уникальные документы с их оценками.

    :param db: Объект базы данных, поддерживающий similarity_search_with_score.
    :param query: Строка запроса.
    :param limit: Максимальное количество уникальных документов для возврата.
    :return: Кортеж из двух списков: документов и их оценок.
    """
    # Запрашиваем больше результатов, чтобы компенсировать возможные дубликаты
    over_fetch_limit = limit * 2
    results = db._collection.similarity_search_with_score(query, k=limit)

    seen = set()
    unique_docs = []
    unique_scores = []

    for doc, score in results:
        content = doc.page_content.strip()
        if content not in seen:
            seen.add(content)
            unique_docs.append(content)
            unique_scores.append(score)
            if len(unique_docs) >= limit:
                break

    return unique_docs, unique_scores

#===== Reranker =====#
# Инициализация модели для ранжирования
from transformers import BertTokenizer, BertForSequenceClassification, AutoModelForSequenceClassification

# Инициализация токенизатора и модели для ранжирования
tokenizer_reranker = BertTokenizer.from_pretrained("nlpaueb/legal-bert-base-uncased")
model_reranker = BertForSequenceClassification.from_pretrained("nlpaueb/legal-bert-base-uncased").to(device)

model_reranker.eval()

def rerank_and_filter(query, documents, top_n=3, threshold=0.3):
    # Реранкинг документов
    inputs = tokenizer_reranker([query]*len(documents), documents, return_tensors='pt', truncation=True, padding=True)
    with torch.no_grad():
        outputs = model_reranker(**inputs)
    scores = torch.softmax(outputs.logits, dim=1)[:,1].tolist()

    ranked_docs = sorted(zip(documents, scores), key=lambda x: x[1])

    # Выбор документов ниже порога
    filtered_docs = [doc for doc, score in ranked_docs if score <= threshold]

    # Если отфильтрованных документов меньше top_n, дополняем их топ-N
    if len(filtered_docs) < top_n:
        filtered_docs = [doc for doc, score in ranked_docs[:top_n]]

    rearranged_docs_topn = filtered_docs[:top_n]
    rearranged_docs = [rearranged_docs_topn[1]] + rearranged_docs_topn[2:2+(top_n-2)] + [rearranged_docs_topn[0]]
    return rearranged_docs, rearranged_docs_topn



#### ========== local LLM ========== ####

from unsloth import FastLanguageModel
print("GPU memory allocated: %fGB" % (torch.cuda.memory_allocated() / 2**30))

model_name='unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit'
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = model_name,
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit=True
)


FastLanguageModel.for_inference(model)

sys_prompt = '''Вы — полезный новостной ассистент. Пожалуйста, предоставьте прямой и краткий ответ на следующий вопрос, основываясь на представленных статьях. Не давайте никаких дополнительных пояснений.

Вопрос: {input}

Ответ:'''

# Определение шаблона промпта
prompt_template = PromptTemplate(
    input_variables=["input"],
    template=sys_prompt,
)

import langchain
from langchain import ConversationChain, LLMChain, PromptTemplate
from langchain.memory import ConversationBufferMemory
from langchain.llms import HuggingFacePipeline

pipe = pipeline(
    "text-generation",
    tokenizer=tokenizer,
    model=model,
    do_sample=True,
    temperature=0.5,
    top_p=0.9,
    # early_stopping=True,
    # num_beams=2,
    # pad_token_id=tokenizer.eos_token_id
    max_new_tokens=256,
    torch_dtype=torch.float16,
    truncation=True,
    padding=True,
    repetition_penalty=1.2,
    return_full_text=False,
    # streamer = text_streamer,
)

llm = HuggingFacePipeline(pipeline=pipe)

chain = LLMChain(
    llm=llm,
    prompt=prompt_template,
)

chain.invoke('Сколько цветов у радуги')


# Список вопросов, сформированных на основе представленных текстов
questions = [
    "1. Какие особенности эпидемического распространения оспы обезьян по сравнению с COVID-19 выделила Наталья Пшеничная?",
    "2. Как эмбарго на импорт российской нефти, согласованное странами ЕС, может изменить мировой энергетический порядок?",
    "3. Какую роль, по мнению российского посла по особым поручениям МИД Григория Машкова, должен сыграть международный диалог по контролю над ракетами?",
    "4. Какое значение имеет присоединение «ВымпелКома» к национальному инклюзивному договору для масштабирования усилий государства и бизнеса?",
    "5. Какие меры по профилактике заражения оспой обезьян предложил Павел Волчков?",
    "6. Какие ключевые отличия между авианосцем «Адмирал Кузнецов» и американскими атомными авианосцами отмечаются в публикации?",
    "7. Какова суть плана Польши и Украины по конфискации российских финансовых активов за рубежом?",
    "8. Какие аргументы приводит спикер Госдумы Вячеслав Володин относительно намерений США использовать Украину в своих интересах?",
    "9. Какие изменения для владельцев недвижимости и порядок узаконивания перепланировки предусматриваются новым законом с начала 2024 года?",
    "10. Как изменение минимального размера оплаты труда (МРОТ) с 1 января 2024 года отразится на доходах работников и социальных выплатах?"
]

# Список ответов, соответствующих сформированным вопросам
ideal_answers  = [
    "Ответ 1: Оспа обезьян характеризуется более высокой летальностью, чем COVID-19, но имеет значительно меньшую контагиозность, поскольку для инфицирования требуется тесный и длительный контакт. Наиболее уязвимыми группами являются дети и взрослые с иммунодефицитом.",
    "Ответ 2: Эмбарго на импорт российской нефти может привести к глобальной перестройке энергетического рынка – ослабить экономические позиции России, а альтернативные поставщики (например, Саудовская Аравия) получат возможность существенно увеличить свои доходы. Рост цен на нефть негативно отразится на экономике многих стран, вынуждая ЕС искать нефть у менее удобных поставщиков.",
    "Ответ 3: По мнению Григория Машкова, международный диалог по контролю над ракетами необходим для создания эффективной системы контроля, поскольку текущие механизмы (например, Режим контроля за ракетными технологиями и Гаагский кодекс поведения) не обеспечивают достаточной координации и не вызывают должного внимания на глобальном уровне.",
    "Ответ 4: Присоединение «ВымпелКома» к национальному инклюзивному договору позволяет масштабировать усилия государства и бизнеса по созданию новых подходов в поддержке равных прав и возможностей, особенно посредством технологий связи, что способствует улучшению качества жизни людей с ограниченными возможностями.",
    "Ответ 5: Павел Волчков рекомендует ограничить контакты с незнакомыми людьми, применять меры предосторожности при половом общении (например, использовать защиту и проводить анализы у партнёров) и придерживаться карантинных мер, поскольку заражение оспой обезьян требует длительного тесного контакта.",
    "Ответ 6: «Адмирал Кузнецов» – стареющий российский авианосец, предназначенный для поддержки береговых оборонительных операций, тогда как американские атомные авианосцы создаются для проекции силы за рубежом и могут находиться в открытом море значительно дольше, что отражает различия в стратегических возможностях.",
    "Ответ 7: План предполагает легальную конфискацию российских финансовых активов за рубежом для создания фонда, который будет использоваться для восстановления и перестройки Украины, затрагивая как активы российских олигархов, так и имущество Российской Федерации, находящееся в зарубежных банках.",
    "Ответ 8: Спикер Госдумы Вячеслав Володин утверждает, что США стремятся использовать Украину как «колонию» для извлечения ресурсов, что может привести к хаосу и гуманитарным катастрофам, подобным тем, что наблюдались в других странах, где проводилась «демократия по американскому образцу».",
    "Ответ 9: Новый закон требует от владельцев недвижимости узаконивать проведённые перепланировки или возвращать помещения в исходное состояние, предусматривая значительные штрафы для частных лиц и юридических лиц, что может привести к финансовым потерям и усилению контроля над изменениями в жилых помещениях.",
    "Ответ 10: Повышение МРОТ на 18,5% с 1 января 2024 года приведёт к увеличению минимальных зарплат, что улучшит доходы работников. Поскольку МРОТ используется для расчёта социальных выплат (например, пособий, отпускных, больничных), это изменение также повлияет на их размер, повышая общий уровень социальных выплат."
]

def gen_final_answer(
        query: str,
        limit: int,
        rerank_limit: int
):
    top_docs = semantic_search_with_score(db, query, limit=limit)[0]
    info = rerank_and_filter(query, top_docs, rerank_limit)
    prompt = f''''Ответь на вопрос пользователя {query}, используя данную информацию:
    {info}'''

    return chain.invoke(prompt)['text']

results = []
pd.set_option('display.max_colwidth', 2000)
print(semantic_search_with_score(db, 'Какие особенности эпидемического распространения оспы обезьян по сравнению с COVID-19 выделила Наталья Пшеничная?', 10))

res = chain.invoke('Сколько цветов у радуги')['text']


def generate_and_collect_results(questions, ideal_answers, limit=15, rerank_limit=3):

    for question, ideal in zip(questions, ideal_answers):
        # Генерация ответа для данного вопроса
        generated_answer = gen_final_answer(query=question, limit=limit, rerank_limit=rerank_limit)
        results.append({
            "Вопрос": question,
            "Ответ": generated_answer,
            "Идеальный ответ": ideal
        })
    df = pd.DataFrame(results)
    return df

df_results = generate_and_collect_results(questions, ideal_answers)
df_results.head()