# RAG System with Streamlit Interface

Система поиска и генерации ответов (RAG) с веб-интерфейсом на Streamlit.

## 🚀 Быстрый старт

### 1. Запуск Docker контейнеров

```bash
docker compose up -d
```

Проверьте статус:
```bash
docker compose ps
```

Должны быть запущены:
- `berta-transformers` (порт 8081) - векторизация
- `bge-reranker` (порт 8082) - реренкинг
- `weaviate` (порт 8080) - векторная БД

### 2. Создание коллекции (если еще не создана)

```bash
python -m src.system.vdb
```

### 3. Запуск Streamlit приложения

```bash
streamlit run app.py
```

Приложение откроется в браузере по адресу: http://localhost:8501

## 📋 Тестирование через CLI

Протестировать RAG пайплайн без Streamlit:

```bash
python -m src.system.engine
```

## 🎯 Возможности интерфейса

### Основные функции:
- 💬 **Ввод вопросов** с примерами запросов
- 🔍 **Hybrid поиск** (BM25 + векторный)
- 🎯 **Реренкинг** с BAAI/bge-reranker-v2-m3
- 📖 **Parent Document Retrieval** - возврат полных документов вместо чанков
- 🔄 **Дедупликация** - автоматическое удаление дубликатов родительских документов
- 🤖 **Генерация ответов** через LLM
- 📊 **Визуализация** изменения scores
- 📈 **Статистика** в реальном времени
- 📜 **История запросов**

### Настройки:
- Количество результатов поиска (5-20)
- Результатов после реренкинга (1-10)
- Уровень рассуждений LLM (low/medium/high)
- **Использовать полные документы** (вкл/выкл)

### Визуализация:
- Сравнение Hybrid Score vs Rerank Score
- Изменение позиций документов
- График bar chart для scores
- Детали каждого документа

## 🛠️ Архитектура

```
User Query
    ↓
Hybrid Search (BM25 + Vector)  ← BERTA embeddings
    ↓
Top 10 chunks
    ↓
Reranking  ← BGE-Reranker-v2-m3
    ↓
Top 3 reranked chunks
    ↓
Parent Document Retrieval  ← Получение полных документов
    ↓
Deduplication  ← Удаление дубликатов parent documents
    ↓
Top 3 unique parent documents
    ↓
LLM Generation  ← OpenRouter GPT
    ↓
Final Answer
```

### 📖 Parent Document Retrieval

**Проблема:** Чанки содержат фрагменты документов, что может приводить к потере контекста.

**Решение:**
1. Поиск находит релевантные **чанки**
2. Reranker оценивает чанки
3. **Parent Document Retrieval** заменяет чанки на полные родительские документы
4. **Дедупликация** удаляет повторяющиеся документы
5. LLM получает полный контекст

**Пример:**
- Найдено: chunk #3, chunk #7, chunk #5
- Parent docs: doc_A (из chunk #3), doc_A (из chunk #7), doc_B (из chunk #5)
- После дедупликации: doc_A, doc_B, **doc_C** (следующий по релевантности)
- Итого: 3 уникальных полных документа вместо фрагментов

## 📦 Модели

- **Векторизация**: `sergeyzh/BERTA` (на GPU)
- **Реренкинг**: `BAAI/bge-reranker-v2-m3` (на GPU)
- **LLM**: `openai/gpt-oss-20b:free` (через OpenRouter)

## 🔧 Переменные окружения

Создайте файл `.env`:

```env
API_KEY=your_openrouter_api_key
```

## 📊 Пример использования

1. Откройте Streamlit интерфейс
2. Введите вопрос или выберите пример
3. Нажмите "Найти ответ"
4. Изучите:
   - Ответ модели
   - Использованные документы
   - Scores до и после реренкинга
   - Визуализацию изменений

## 🐛 Troubleshooting

### Ошибка подключения к Weaviate
```bash
# Проверьте статус контейнеров
docker compose ps

# Перезапустите если нужно
docker compose restart
```

### Reranker не работает
```bash
# Проверьте логи
docker compose logs bge-reranker
```

### LLM не отвечает
- Проверьте наличие API_KEY в .env
- Проверьте баланс на OpenRouter

## 📝 Логи

Логи RAG пайплайна выводятся в консоль при запуске через CLI или в Streamlit терминал.

Уровни логирования:
- INFO: Основные события (подключения, запросы)
- WARNING: Предупреждения
- ERROR: Ошибки

## 🔄 Обновление данных

Для обновления коллекции:
```bash
python -m src.system.vdb
```

⚠️ Внимание: это удалит существующую коллекцию и создаст новую!
