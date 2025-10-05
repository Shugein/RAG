# 🤖 RADAR Finance Telegram Mini App

**Интеллектуальный финансовый помощник в формате Telegram Mini App**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Telegram Bot API](https://img.shields.io/badge/Telegram-Bot%20API-blue.svg)](https://core.telegram.org/bots/api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 Описание

RADAR Finance Mini App — это современное веб-приложение, интегрированное с Telegram, которое предоставляет пользователям доступ к финансовой аналитике и новостям российского рынка. Приложение использует передовые технологии для анализа финансовых данных и предоставления персонализированных рекомендаций.

### ✨ Основные возможности

- 🔍 **Умный поиск финансовых новостей** - поиск и анализ новостей по ключевым словам
- 📊 **Анализ E-Disclosure сообщений** - мониторинг корпоративных событий и уведомлений
- 🎯 **Персонализированные рекомендации** - анализ трендов и важности событий
- 💹 **Мультисекторальный анализ** - охват банков, энергетики, телекома и других отраслей
- ⚡ **Быстрый отклик** - оптимизированный интерфейс с минимальным временем загрузки
- 📱 **Адаптивный дизайн** - полная совместимость с мобильными устройствами

## 🏗️ Архитектура проекта

│   ├── requirements.txt       # Python зависимости
│   └── .env.example          # Пример переменных окружения
├── 🎨 frontend/               # Клиентская часть
│   ├── index-clean.html      # Основной интерфейс (упрощенный)
│   ├── index.html            # Полный интерфейс
│   ├── css/                  # Стили приложения
│   │   └── styles.css
│   ├── js/                   # JavaScript логика
│   │   ├── simple-app.js     # Упрощенная версия
│   │   └── app.js           # Полная версия
│   └── assets/              # Статические ресурсы
├── 📁 config/                # Конфигурационные файлы
├── 📚 docs/                  # Документация
└── 🧪 example_json_answer.txt # Пример API ответа
```

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.8 или выше
- Telegram Bot Token
- Git

### 1. Установка зависимостей

```bash
# Перейдите в папку backend
cd backend

# Установите зависимости
pip install -r requirements.txt
```

### 2. Настройка конфигурации

Отредактируйте файл `backend/config.py` с вашими настройками:

```python
# Основные настройки
api_host: str = "127.0.0.1"
api_port: int = 8000
telegram_bot_token: Optional[str] = "YOUR_BOT_TOKEN_HERE"
```

### 3. Запуск приложения

```bash
# Запуск backend сервера
cd backend
python main.py

# Сервер будет доступен по адресу: http://localhost:8000
```

### 4. Настройка Telegram Mini App

1. Создайте бота через [@BotFather](https://t.me/botfather)
2. Получите Bot Token и добавьте в config.py
3. Настройте Mini App в BotFather:
   ```
   /newapp
   @your_bot_username
   App name: RADAR Finance
   Description: Финансовая аналитика RADAR
   Photo: (загрузите иконку)
   Web App URL: https://yourdomain.com
   ```
4. Настройте кнопку меню:
   ```
   /setmenubutton
   @your_bot_username
   Button text: 📊 RADAR Finance
   Web App URL: https://yourdomain.com
   ```

## � API Endpoints

### POST `/api/process_query`

Основной endpoint для обработки пользовательских запросов.

**Request Body:**
```json
{
    "query": "новости Сбербанка за сегодня"
}
```

**Response:**
```json
{
    "query": "новости Сбербанка за сегодня",
    "answer": "Найдено 5 новостей о Сбербанке за сегодня...",
    "documents": [
        {
            "title": "Сбербанк объявил о рекордной прибыли",
            "source": "RBC",
            "text": "Полный текст новости...",
            "chunk_text": "Релевантный фрагмент...",
            "url": "https://example.com/news1",
            "timestamp": "2025-10-04T15:30:00",
            "scores": {
                "retrieval_score": 0.95,
                "rerank_score": 0.87
            },
            "positions": [1],
            "chunk_id": "chunk_1",
            "document_id": "doc_1"
        }
    ],
    "metadata": {
        "total_time": 1.234,
        "num_documents": 5,
        "vectorizer": "sentence-transformers",
        "reranker": "cross-encoder",
        "llm_model": "gpt-3.5-turbo",
        "use_parent_docs": true
    }
}
```

### GET `/health`

Проверка состояния сервера.

### GET `/`

Главная страница приложения.

## 🎨 Frontend

### Основные компоненты

#### 1. Упрощенный интерфейс (`index-clean.html`)
- Минималистичный дизайн с фокусом на функциональность
- Только поле ввода запроса и кнопка отправки
- Оптимизирован для мобильных устройств
- **Рекомендуется для использования**

#### 2. Полный интерфейс (`index.html`)
- Расширенные возможности (в разработке)
- Дополнительные настройки поиска

### Технологии Frontend

- **Framework:** Tailwind CSS 3.0+
- **Шрифты:** Inter (Google Fonts)
- **JavaScript:** Vanilla ES6+
- **Telegram WebApp SDK:** Официальный SDK

### Цветовая схема

- Primary: `#1e40af` (radar-primary)
- Secondary: `#3b82f6` (radar-secondary)  
- Accent: `#10b981` (radar-accent)
- Дизайн: Glassmorphism эффекты

## 🔌 Интеграция с Telegram

### WebApp API

```javascript
// Инициализация Telegram WebApp
window.Telegram.WebApp.ready();
window.Telegram.WebApp.expand();

// Получение данных пользователя
const user = window.Telegram.WebApp.initDataUnsafe?.user;
```

### Безопасность

- CORS настройки для Telegram домена
- Валидация запросов от Telegram

## 🧪 Тестирование

### Локальное тестирование

```bash
# Запуск сервера
cd backend
python main.py

# Откройте в браузере: http://localhost:8000
```

### Тестирование с Telegram

1. Используйте ngrok для публичного URL:
```bash
ngrok http 8000
```

2. Обновите URL в настройках бота
3. Откройте Mini App в Telegram

### Mock данные

Приложение включает систему mock-данных с реалистичными финансовыми новостями для тестирования без подключения к реальной RADAR системе.

## 📊 Производительность

### Оптимизации

- **Асинхронность:** FastAPI с uvicorn
- **Кэширование:** Настроено в config.py (cache_ttl: 300s)
- **Компрессия:** Статические файлы
- **CDN:** Tailwind CSS и шрифты загружаются из CDN

### Метрики

- Время отклика API: < 200ms
- Время загрузки интерфейса: < 1s
- Поддержка множественных пользователей

## 🚢 Быстрое развертывание

### Heroku (рекомендуется)

```bash
# Установите Heroku CLI
# Создайте приложение
heroku create your-radar-app

# Установите переменные окружения  
heroku config:set TELEGRAM_BOT_TOKEN=your_token

# Деплой
git push heroku main
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "backend/main.py"]
```

## 🔧 Конфигурация

### Основные настройки (`backend/config.py`)

```python
class Settings(BaseSettings):
    # Приложение
    app_name: str = "RADAR Finance Mini App"
    version: str = "1.0.0"
    debug: bool = False
    
    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    
    # Telegram
    telegram_bot_token: Optional[str] = None
    
    # Производительность
    default_news_limit: int = 20
    max_news_limit: int = 100
    cache_ttl: int = 300
```

## 🐛 Часто встречающиеся проблемы

### 1. Mini App не открывается в Telegram
- Проверьте HTTPS сертификат
- Убедитесь, что URL правильно настроен в BotFather
- Проверьте CORS настройки

### 2. API возвращает ошибки
- Проверьте logs сервера: `python main.py`
- Убедитесь, что порт 8000 не занят
- Проверьте формат запросов к API

### 3. Стили не загружаются
- Проверьте подключение к интернету (Tailwind CSS загружается из CDN)
- Убедитесь, что статические файлы доступны

## 🤝 Разработка

### Добавление новых функций

1. **Новый API endpoint:**
```python
@app.post("/api/new-feature")
async def new_feature(request: dict):
    # Ваша логика
    return {"result": "success"}
```

2. **Обновление frontend:**
- Добавьте функции в `frontend/js/simple-app.js`
- Обновите HTML в `frontend/index-clean.html`

### Mock → Real RADAR Integration

Чтобы подключить реальную RADAR функцию:

1. Замените `RADARMockProcessor` в `backend/main.py`
2. Импортируйте вашу RADAR функцию
3. Обновите `process_radar_query()` endpoint

```python
# Замените mock на реальную функцию
from your_radar_module import process_radar_query as real_radar_query

@app.post("/api/process_query")
async def process_query(request: dict):
    result = await real_radar_query(request["query"])
    return result
```

## � Дополнительные ресурсы

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Telegram WebApp API](https://core.telegram.org/bots/webapps)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Tailwind CSS](https://tailwindcss.com/docs)

## 📞 Поддержка

При возникновении проблем:

1. Проверьте логи сервера
2. Убедитесь в правильности конфигурации
3. Протестируйте API endpoints через браузер
4. Проверьте настройки Telegram бота

---

**🚀 Готово к запуску! Финансовая аналитика в Telegram Mini App формате.**