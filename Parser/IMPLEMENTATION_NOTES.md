# Заметки по реализации пустых файлов

## ✅ Созданные файлы

### 1. `src/services/enricher/ner_extractor.py`
**Статус:** ✅ Реализован

**Описание:** 
- Класс `NERExtractor` для извлечения именованных сущностей
- Поддержка Natasha (по умолчанию) - оптимизирована для русского языка, Python 3.12+
- Поддержка DeepPavlov BERT для мультиязычного NER (требует Python 3.9-3.11)
- Fallback на rule-based извлечение, если ML-модели недоступны

**Функционал:**
- ✅ Извлечение организаций (ORG), персон (PERSON), локаций (LOC) через Natasha/DeepPavlov
- ✅ Извлечение дат (DATE) - поддержка разных форматов
- ✅ Извлечение денежных сумм (MONEY) - с валютой и масштабом (млн, млрд)
- ✅ Извлечение процентов (PCT) - с базисом сравнения (YoY, QoQ, etc.)
- ✅ Финансовые метрики (AMOUNT) - суммы с единицами измерения
- ✅ Отчетные периоды (PERIOD) - 1П2025, Q3 2024, 9М2025

**Зависимости:**
```bash
# Рекомендуемый вариант для Python 3.12+ (уже установлен):
pip install natasha razdel slovnet

# Альтернатива для Python 3.9-3.11:
pip install deeppavlov
python -m deeppavlov install ner_multi_bert
```

**Режимы работы:**
- С Natasha (по умолчанию): `NERExtractor()` или `NERExtractor(backend="natasha")`
- С DeepPavlov: `NERExtractor(backend="deeppavlov")` - требует Python 3.9-3.11
- Только финансовые метрики: `NERExtractor(use_ml_ner=False)` - без ML-моделей

---

### 2. `src/services/outbox/publisher.py`
**Статус:** ✅ Реализован

**Описание:**
- Класс `EventPublisher` - создание событий в outbox таблице
- Класс `RabbitMQPublisher` - прямая публикация в RabbitMQ

**Функционал:**
- ✅ `publish_news_created()` - событие создания новости
- ✅ `publish_news_updated()` - событие обновления
- ✅ `publish_enrichment_completed()` - событие завершения обогащения
- ✅ Retry логика с exponential backoff
- ✅ At-least-once delivery через Transactional Outbox
- ✅ Persistent сообщения в RabbitMQ

**Зависимости:**
```bash
pip install aio-pika>=9.0.0
```

---

### 3. `src/services/outbox/relay.py`
**Статус:** ✅ Реализован

**Описание:**
- Класс `OutboxRelay` - основной relay сервис
- Класс `OutboxRelayHealthCheck` - проверка здоровья

**Функционал:**
- ✅ Polling таблицы outbox для pending событий
- ✅ Публикация событий в RabbitMQ
- ✅ Retry логика с exponential backoff (60s * 2^(retry_count-1))
- ✅ Обработка событий батчами
- ✅ Автоматическая очистка старых событий
- ✅ Статистика и health check

**Настройки (через config):**
- `OUTBOX_POLL_INTERVAL` - интервал polling (по умолчанию: 5 сек)
- `OUTBOX_BATCH_SIZE` - размер батча (по умолчанию: 100)
- `OUTBOX_MAX_RETRIES` - макс. попытки (по умолчанию: 3)
- `OUTBOX_RETRY_DELAY` - базовая задержка retry (по умолчанию: 60 сек)
- `OUTBOX_KEEP_DAYS` - сколько дней хранить отправленные (по умолчанию: 7)

---

### 4. `scripts/start_outbox_relay.py`
**Статус:** ✅ Реализован

**Описание:**
- Скрипт запуска Outbox Relay сервиса
- Обработка сигналов (SIGINT, SIGTERM)
- Периодическая очистка старых событий

**Запуск:**
```bash
python scripts/start_outbox_relay.py
```

**Требования:**
- Настроенная `RABBITMQ_URL` в .env
- Настроенная `DATABASE_URL` в .env

---

## 📦 Требования к requirements.txt

Добавьте следующие зависимости:

```txt
# Для NER Extractor (опционально, но рекомендуется)
deeppavlov>=1.7.0

# Для Outbox Publisher/Relay (обязательно)
aio-pika>=9.0.0
```

Полная установка:
```bash
# Основные зависимости
pip install -r requirements.txt

# DeepPavlov BERT для NER (опционально)
pip install deeppavlov
python -m deeppavlov install ner_multi_bert
```

---

## 🔧 Настройка в src/core/config.py

Добавьте следующие настройки в класс `Settings`:

```python
# Outbox Relay настройки
OUTBOX_POLL_INTERVAL: int = 5  # секунды
OUTBOX_BATCH_SIZE: int = 100
OUTBOX_MAX_RETRIES: int = 3
OUTBOX_RETRY_DELAY: int = 60  # секунды
OUTBOX_KEEP_DAYS: int = 7

# RabbitMQ настройки
RABBITMQ_URL: str
RABBITMQ_EXCHANGE: str = "news_events"

# NER настройки
USE_DEEPPAVLOV_NER: bool = False  # Включить если установлен DeepPavlov
```

---

## 🚀 Использование

### NERExtractor

```python
from src.services.enricher.ner_extractor import NERExtractor

# С DeepPavlov (если установлен)
extractor = NERExtractor(use_deeppavlov=True)

# Без DeepPavlov (только rule-based)
extractor = NERExtractor(use_deeppavlov=False)

# Извлечение сущностей
text = "Газпром увеличил прибыль на 15% до 500 млрд рублей в 1П2025"
entities = extractor.extract_entities(text)

for entity in entities:
    print(f"{entity.type}: {entity.text} -> {entity.normalized}")
```

### EventPublisher

```python
from src.services.outbox.publisher import EventPublisher

async with get_db_session() as session:
    publisher = EventPublisher(session)
    
    # Публикация события
    await publisher.publish_news_created(news, enrichment_data)
    
    # Не забудьте commit!
    await session.commit()
```

### Запуск Outbox Relay

```bash
# Как отдельный процесс
python scripts/start_outbox_relay.py

# Или через Docker
docker-compose up outbox-relay
```

---

## 📊 Мониторинг

### Проверка статистики outbox

```python
from src.services.outbox.relay import OutboxRelay

relay = OutboxRelay()
stats = await relay.get_statistics()

print(stats)
# {
#   'by_status': {'pending': 10, 'sent': 1000, 'failed': 5},
#   'permanently_failed': 2,
#   'total': 1015
# }
```

### Health Check

```python
from src.services.outbox.relay import OutboxRelayHealthCheck

health = OutboxRelayHealthCheck(relay)
is_healthy = await health.is_healthy()
status = await health.get_status()
```

---

## ⚠️ Важные замечания

1. **NERExtractor** может работать без DeepPavlov, но функционал будет ограничен
2. **EventPublisher** только создает записи в outbox, фактическая публикация через OutboxRelay
3. **OutboxRelay** должен быть запущен как отдельный процесс/сервис
4. Все события публикуются с `delivery_mode=PERSISTENT` для надежности
5. Exponential backoff предотвращает перегрузку при ошибках

---

## 🐛 Troubleshooting

### DeepPavlov не устанавливается
```bash
# Используйте без DeepPavlov
extractor = NERExtractor(use_deeppavlov=False)
```

### RabbitMQ connection refused
```bash
# Проверьте что RabbitMQ запущен
docker-compose up -d rabbitmq

# Проверьте RABBITMQ_URL в .env
echo $RABBITMQ_URL
```

### Outbox события не публикуются
```bash
# 1. Проверьте что relay запущен
ps aux | grep outbox_relay

# 2. Проверьте логи
tail -f logs/outbox_relay.log

# 3. Проверьте статистику
python -c "from src.services.outbox.relay import OutboxRelay; import asyncio; relay = OutboxRelay(); print(asyncio.run(relay.get_statistics()))"
```

---

**Создано:** 2025-10-03  
**Автор:** AI Assistant  
**Версия:** 1.0

