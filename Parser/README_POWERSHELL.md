# News Aggregator - PowerShell Setup Guide

## 🚀 Быстрый старт

### Предварительные требования

1. **Python 3.10+** - [Скачать с python.org](https://www.python.org/downloads/)
2. **Docker Desktop** - [Скачать с docker.com](https://www.docker.com/products/docker-desktop/)
3. **PowerShell 5.1+** (включен в Windows 10/11)

### Установка

1. **Клонируйте репозиторий:**
   ```powershell
   git clone <repository-url>
   cd Hakaton
   ```

2. **Запустите установку:**
   ```powershell
   .\setup.ps1
   ```

3. **Настройте переменные окружения:**
   - Откройте файл `.env`
   - Добавьте ваши Telegram API ключи:
     ```
     TELETHON_API_ID=your_api_id
     TELETHON_API_HASH=your_api_hash
     TELETHON_PHONE=+79999999999
     ```
   - Для AI анализа добавьте OpenAI API ключ (опционально):
     ```
     API_KEY_2=your_openai_api_key
     # или
     OPENAI_API_KEY=your_openai_api_key
     ```

4. **Установите AI зависимости (для CEG парсера):**
   ```powershell
   # Активируйте виртуальное окружение
   .\venv\Scripts\Activate.ps1
   
   # Установите AI библиотеки
   pip install transformers torch accelerate
   ```

## 🏃‍♂️ Запуск проекта

### 🚀 CEG Parser с AI анализом (НОВОЕ!)

Запускает улучшенный парсер с CEG анализом и AI:

```powershell
.\start_ceg_parser.ps1
```

**Возможности CEG парсера:**
- 🧠 AI-анализ новостей (OpenAI GPT или локальный Qwen3-4B)
- 📡 Парсинг Telegram источников
- 🌐 Парсинг HTML источников (Forbes, Interfax, E-disclosure, MOEX)
- 🕸️ Создание графа связей в Neo4j
- 🔗 CEG анализ причинных связей
- 📊 Batch обработка с детальными JSON ответами
- 🔮 Предсказания будущих событий

**Режимы работы:**
```powershell
# Все источники (Telegram + HTML)
.\start_ceg_parser.ps1

# Только Telegram
.\start_ceg_parser.ps1 -TelegramOnly

# Только HTML
.\start_ceg_parser.ps1 -HTMLOnly
```

### Режим разработки (рекомендуется)

Запускает сервисы локально с возможностью отладки:

```powershell
.\start_dev.ps1
```

Этот скрипт:
- ✅ Запускает инфраструктуру (PostgreSQL, RabbitMQ, Redis)
- ✅ Запускает API сервер в отдельном окне
- ✅ Запускает Telegram парсер в отдельном окне  
- ✅ Запускает Outbox Relay в отдельном окне

### Полный режим (Docker)

Запускает все сервисы в Docker контейнерах:

```powershell
.\start_full.ps1
```

## 🛑 Остановка сервисов

### Остановка режима разработки:
```powershell
.\stop_dev.ps1
```

### Остановка полного режима:
```powershell
.\stop_full.ps1
```

## 📊 Мониторинг

### Проверка здоровья системы:
```powershell
.\check_health.ps1
```

### Просмотр логов:
```powershell
# Все сервисы
.\view_logs.ps1

# Конкретный сервис
.\view_logs.ps1 -Service api -Lines 100
.\view_logs.ps1 -Service telegram -Lines 50
.\view_logs.ps1 -Service postgres -Lines 20
```

## 🌐 Доступные сервисы

После запуска будут доступны:

| Сервис | URL | Описание |
|--------|-----|----------|
| **API Server** | http://localhost:8000 | Основной REST API |
| **API Docs** | http://localhost:8000/docs | Swagger документация |
| **RabbitMQ Management** | http://localhost:15672 | Управление очередями (admin/admin123) |
| **Neo4j Browser** | http://localhost:7474 | Граф база данных (neo4j/password123) |

## 🔧 Полезные команды

### Работа с базой данных:
```powershell
# Создание миграции
alembic revision --autogenerate -m "Description"

# Применение миграций
alembic upgrade head

# Откат миграции
alembic downgrade -1
```

### Загрузка источников:
```powershell
# Активация виртуального окружения
.\venv\Scripts\Activate.ps1

# Загрузка источников
python scripts\load_sources.py
```

### Тестирование:
```powershell
# Запуск тестов
python -m pytest tests/

# Тест MOEX автопоиска
python scripts\test_moex_auto_search.py
```

## 🐛 Решение проблем

### Проблема: PowerShell не может выполнить скрипты
```powershell
# Разрешить выполнение скриптов (запустите от администратора)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Проблема: Docker не запускается
- Убедитесь, что Docker Desktop запущен
- Проверьте, что WSL2 включен (если используется)

### Проблема: Порты заняты
```powershell
# Проверить какие процессы используют порты
netstat -ano | findstr :8000
netstat -ano | findstr :5432
netstat -ano | findstr :5672

# Остановить процесс по PID
taskkill /PID <PID> /F
```

### Проблема: База данных не подключается
```powershell
# Проверить статус PostgreSQL
docker logs news-postgres

# Перезапустить PostgreSQL
docker restart news-postgres
```

### Проблема: CEG парсер не запускается
```powershell
# Ошибка "No module named 'transformers'"
.\venv\Scripts\Activate.ps1
pip install transformers torch accelerate

# Ошибка "No API key found"
# Добавьте в .env файл:
# API_KEY_2=your_openai_api_key

# Ошибка синтаксиса в entity_recognition.py
# Убедитесь, что исправлены все синтаксические ошибки
```

### Проблема: AI модель не загружается
```powershell
# Для локальной модели Qwen3-4B
# Убедитесь, что у вас достаточно RAM (минимум 8GB)
# При первом запуске модель будет скачана автоматически

# Для OpenAI API
# Проверьте API ключ и интернет соединение
# Убедитесь, что у вас есть кредиты на API
```

## 📁 Структура проекта

```
Hakaton/
├──Parser.src/                    # Исходный код
│   ├── api/               # REST API
│   ├── core/              # Основные компоненты
│   ├── services/          # Бизнес-логика
│   └── utils/             # Утилиты
├── scripts/               # Скрипты запуска
├── docker/                # Docker конфигурации
├── config/                # Конфигурационные файлы
├── migrations/            # Миграции БД
├── tests/                 # Тесты
├── setup.ps1             # Установка
├── start_dev.ps1         # Запуск dev режима
├── start_full.ps1        # Запуск полного режима
├── stop_dev.ps1          # Остановка dev режима
├── stop_full.ps1         # Остановка полного режима
├── check_health.ps1      # Проверка здоровья
└── view_logs.ps1         # Просмотр логов
```

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи: `.\view_logs.ps1`
2. Проверьте здоровье системы: `.\check_health.ps1`
3. Перезапустите сервисы: `.\stop_dev.ps1` → `.\start_dev.ps1`
4. Обратитесь к разработчикам с логами ошибок
