# 🤖 RADAR Finance Telegram Mini App

**Интеллектуальный финансовый помощник в формате Telegram Mini App**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue.svg)](https://core.telegram.org/bots/api)

## 📋 Описание

RADAR Finance Mini App — современное веб-приложение, интегрированное с Telegram, которое предоставляет доступ к финансовой аналитике и новостям российского рынка с использованием технологий RAG и машинного обучения.

### ✨ Основные возможности

- 🔍 **Умный поиск** - поиск и анализ финансовых новостей по запросам на естественном языке
- 📊 **Готовые статьи** - генерация готовых аналитических материалов с ключевыми тезисами
- 🎯 **Персонализированные ответы** - анализ релевантности и ранжирование документов
- 💹 **Мультисекторальный охват** - банки, энергетика, IT, металлургия и другие отрасли
- ⚡ **Быстрый отклик** - время обработки запросов менее 3 секунд

## 🏗️ Архитектура

```
tg-mini_app/
├── 🚀 backend/               # FastAPI сервер
│   ├── main.py              # Основной API с RADAR интеграцией
│   └── requirements.txt     # Зависимости
├── 🎨 frontend/             # Клиентская часть
│   ├── index-clean.html     # Главный интерфейс
│   ├── css/                # Стили
│   └── js/                 # JavaScript логика
└── 📁 config/              # Конфигурация
```

## 🚀 Быстрый старт

### 1. Установка и запуск

```bash
# Установка зависимостей
cd backend
pip install -r requirements.txt

# Запуск сервера
python main.py
```

### 2. Настройка Telegram Bot

```bash
# 1. Создайте бота через @BotFather
/newbot

# 2. Создайте Mini App
/newapp
# App name: RADAR Finance
# Web App URL: https://yourdomain.com

# 3. Настройте кнопку меню
/setmenubutton
# Button text: 📊 RADAR Finance
```

## 🔌 API

### POST `/api/process_query`

Основной endpoint для обработки пользовательских запросов с новой структурой от Сергея.

**Request:**
```json
{
    "query": "новости Сбербанка за сегодня",
    "generate_pdf": false
}
```

**Response:**
```json
{
    "query": "новости Сбербанка за сегодня",
    "draft": {
        "headline": "Финансовая аналитика: новости Сбербанка",
        "dek": "Ключевые события на российском финансовом рынке",
        "variants": {
            "social_post": "🔥 Новости по запросу...",
            "article_draft": "По результатам анализа...",
            "alert": "⚠️ ВАЖНО: обнаружены значимые изменения..."
        },
        "key_points": [
            "Сбербанк объявил о рекордной прибыли за 9 месяцев 2025 года",
            "ЦБ РФ повысил ключевую ставку до 21% годовых"
        ],
        "hashtags": ["#финансы", "#банки", "#Сбербанк"],
        "disclaimer": "Информация носит ознакомительный характер..."
    },
    "documents": [
        {
            "title": "Сбербанк объявил о рекордной прибыли",
            "source": "RBC",
            "text": "Полный текст новости...",
            "chunk_text": "Релевантный фрагмент...",
            "url": "https://rbc.ru/news...",
            "timestamp": 1728050400,
            "rerank_score": 0.94,
            "hotness": 0.87,
            "final_score": 0.91,
            "final_position": 1,
            "companies": ["Сбербанк", "ПАО Сбербанк"],
            "company_tickers": ["SBER"],
            "people": ["Герман Греф"],
            "financial_metric_values": ["424 млрд руб", "15%"]
        }
    ],
    "metadata": {
        "total_time": 2.347,
        "num_documents": 3,
        "vectorizer": "text2vec-transformers (GPU)",
        "reranker": "BAAI/bge-reranker-v2-m3",
        "llm_model": "gpt-5",
        "use_parent_docs": true
    }
}
```

## 🎨 Frontend

Минималистичный интерфейс с расширенным отображением:
- Готовые статьи с ключевыми тезисами и вариантами текстов
- Отображение компаний, персон и финансовых метрик
- Показатели hotness и reranking score
- Адаптивный дизайн для мобильных устройств

## 🚢 Развертывание

### Heroku
```bash
heroku create your-radar-app
git push heroku main
```

### ngrok (для тестирования)
```bash
ngrok http 8000
# Обновите URL в BotFather
```

## 📊 Технологии

- **Backend:** Python 3.8+, FastAPI, uvicorn
- **Frontend:** Vanilla JS, Tailwind CSS, Telegram WebApp SDK
- **ML:** text2vec-transformers (GPU), BAAI/bge-reranker-v2-m3
- **Data:** RBC, Ведомости, Коммерсант, MOEX, E-disclosure API

## 🔧 Интеграция реальной RADAR функции

Для подключения настоящей RADAR функции:

```python
# Замените в backend/main.py:
from your_radar_module import query as real_radar_query

# В endpoint process_radar_query:
result = real_radar_query(query_text, generate_pdf=generate_pdf)
```

Структура `result` уже соответствует требованиям Сергея - никаких изменений во frontend не потребуется.

---

**🚀 Готово к использованию! Финансовая аналитика нового поколения в Telegram.**