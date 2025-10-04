import os
import asyncio
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv
import time


# ===== МОДЕЛИ ДАННЫХ =====
class Person(BaseModel):
    name: str = Field(description="ФИО или имя персоны")
    position: Optional[str] = Field(None, description="Должность")
    company: Optional[str] = Field(None, description="Компания")


class Company(BaseModel):
    name: str = Field(description="Название компании")
    ticker: Optional[str] = Field(None, description="Тикер акций")
    sector: Optional[str] = Field(None, description="Отрасль")


class Market(BaseModel):
    name: str = Field(description="Название рынка/биржи/индекса")
    type: str = Field(description="Тип: 'биржа', 'индекс', 'валюта', 'товар'")
    value: Optional[float] = Field(None, description="Значение/котировка")
    change: Optional[str] = Field(None, description="Изменение")


class FinancialMetric(BaseModel):
    metric_type: str = Field(description="Тип показателя")
    value: str = Field(description="Значение с единицами")
    company: Optional[str] = Field(None, description="Компания")


class ExtractedEntities(BaseModel):
    publication_date: Optional[str] = Field(None, description="Дата YYYY-MM-DD")
    people: List[Person] = Field(default_factory=list)
    companies: List[Company] = Field(default_factory=list)
    markets: List[Market] = Field(default_factory=list)
    financial_metrics: List[FinancialMetric] = Field(default_factory=list)


# ===== ГЛОССАРИЙ =====
class RussianFinanceGlossary:
    def __init__(self):
        self.companies = {
            "ГАЗПРОМ": {"full_name": "ПАО Газпром", "ticker": "GAZP", "sector": "Нефть и газ"},
            "ЛУКОЙЛ": {"full_name": "ПАО ЛУКОЙЛ", "ticker": "LKOH", "sector": "Нефть и газ"},
            "СБЕРБАНК": {"full_name": "ПАО Сбербанк", "ticker": "SBER", "sector": "Финансы"},
            "СБЕР": {"full_name": "ПАО Сбербанк", "ticker": "SBER", "sector": "Финансы"},
            "ВТБ": {"full_name": "Банк ВТБ", "ticker": "VTBR", "sector": "Финансы"},
            "ЯНДЕКС": {"full_name": "Яндекс", "ticker": "YNDX", "sector": "Технологии"},
            "НОРНИКЕЛЬ": {"full_name": "ГМК Норильский никель", "ticker": "GMKN", "sector": "Металлургия"},
            "РОСНЕФТЬ": {"full_name": "ПАО Роснефть", "ticker": "ROSN", "sector": "Нефть и газ"},
            "НОВАТЭК": {"full_name": "ПАО НОВАТЭК", "ticker": "NVTK", "sector": "Нефть и газ"},
            "МАГНИТ": {"full_name": "ПАО Магнит", "ticker": "MGNT", "sector": "Ритейл"},
            "X5": {"full_name": "X5 Retail Group", "ticker": "FIVE", "sector": "Ритейл"},
            "ОЗОН": {"full_name": "Ozon Holdings", "ticker": "OZON", "sector": "E-commerce"},
            "МТС": {"full_name": "ПАО МТС", "ticker": "MTSS", "sector": "Телеком"},
            "МЕГАФОН": {"full_name": "ПАО МегаФон", "ticker": "MFON", "sector": "Телеком"},
        }
        
        self.indices = {
            "ММВБ": {"full_name": "Индекс Московской биржи", "type": "индекс"},
            "IMOEX": {"full_name": "Индекс Московской биржи", "type": "индекс"},
            "РТС": {"full_name": "Индекс РТС", "type": "индекс"},
            "RTSI": {"full_name": "Индекс РТС", "type": "индекс"},
        }
        
        self.markets = {
            "MOEX": {"full_name": "Московская биржа", "type": "биржа"},
            "МОСБИРЖА": {"full_name": "Московская биржа", "type": "биржа"},
            "СПБ": {"full_name": "Санкт-Петербургская биржа", "type": "биржа"},
        }
        
        self.terms = {
            "ЦБ": "Центральный банк",
            "ЦБ РФ": "Центральный банк РФ",
            "ФРС": "Федеральная резервная система США",
            "ВВП": "Валовой внутренний продукт",
            "ИПЦ": "Индекс потребительских цен",
        }
    
    def get_glossary_text(self) -> str:
        """Возвращает глоссарий в текстовом формате для кэширования"""
        text = "# ФИНАНСОВЫЙ ГЛОССАРИЙ\n\n"
        
        text += "## Компании:\n"
        for abbr, info in self.companies.items():
            text += f"- {abbr}: {info['full_name']} (Тикер: {info['ticker']}, Сектор: {info['sector']})\n"
        
        text += "\n## Индексы:\n"
        for abbr, info in self.indices.items():
            text += f"- {abbr}: {info['full_name']}\n"
        
        text += "\n## Биржи:\n"
        for abbr, info in self.markets.items():
            text += f"- {abbr}: {info['full_name']}\n"
        
        text += "\n## Термины:\n"
        for abbr, full in self.terms.items():
            text += f"- {abbr}: {full}\n"
        
        return text


# ===== КЛИЕНТ С PROMPT CACHING =====
class CachedFinanceNERExtractor:
    """
    Экстрактор с поддержкой prompt caching для экономии до 90% на входных токенах
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5-nano-2025-08-07",  # Изменен дефолт на GPT-4o-mini для OpenAI
        enable_caching: bool = True
    ):
        self.api_key = api_key
        self.model = model
        self.enable_caching = enable_caching
        self.base_url = "https://api.openai.com/v1"
        self.glossary = RussianFinanceGlossary()
        
        # Статистика для отслеживания экономии
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0
        }
    
    def extract_entities(self, news_text: str, news_date: Optional[str] = None, verbose: bool = False) -> ExtractedEntities:
        """Извлекает сущности с использованием prompt caching

        GPT-5 автоматически кэширует промпты >1024 токенов (самый длинный префикс)
        Кэш очищается через 5-10 минут неактивности
        """

        messages = self._build_cached_messages(news_text, news_date)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
        }

        # GPT-5 не поддерживает кастомный temperature (только дефолт 1.0)
        if "gpt-4" in self.model:
            payload["temperature"] = 0.1

        # Для GPT-5 используем простой JSON mode (не schema-based)
        # т.к. GPT-5 требует additionalProperties: false во всех объектах схемы
        if "gpt-5" in self.model:
            payload["response_format"] = {"type": "json_object"}
        elif "gpt-4" in self.model:
            # GPT-4 поддерживает structured outputs
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "financial_entities",
                    "strict": True,
                    "schema": ExtractedEntities.model_json_schema()
                }
            }

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Выводим детали ошибки для отладки
            if verbose:
                print(f"   Детали ошибки: {e.response.text}")
            raise

        result = response.json()

        # Обновляем статистику
        self._update_stats(result)

        content = result["choices"][0]["message"]["content"]

        # Убираем markdown обертку если есть (```json ... ```)
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        if verbose:
            print(f"\n{'='*60}")
            print("СЫРОЙ ОТВЕТ МОДЕЛИ:")
            print(content)
            print(f"{'='*60}\n")

        entities = ExtractedEntities.model_validate_json(content)

        return entities

    async def extract_entities_async(self, news_text: str, news_date: Optional[str] = None, verbose: bool = False) -> ExtractedEntities:
        """Асинхронная версия extract_entities для параллельной обработки"""

        messages = self._build_cached_messages(news_text, news_date)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
        }

        if "gpt-4" in self.model:
            payload["temperature"] = 0.1

        if "gpt-5" in self.model:
            payload["response_format"] = {"type": "json_object"}
        elif "gpt-4" in self.model:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "financial_entities",
                    "strict": True,
                    "schema": ExtractedEntities.model_json_schema()
                }
            }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if verbose:
                    print(f"   Детали ошибки: {e.response.text}")
                raise

        result = response.json()
        self._update_stats(result)

        content = result["choices"][0]["message"]["content"]

        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        if verbose:
            print(f"\n{'='*60}")
            print("СЫРОЙ ОТВЕТ МОДЕЛИ:")
            print(content)
            print(f"{'='*60}\n")

        entities = ExtractedEntities.model_validate_json(content)
        return entities

    async def extract_entities_batch_async(self, news_list: List[str], verbose: bool = False) -> List[Optional[ExtractedEntities]]:
        """Асинхронная параллельная обработка списка новостей

        Обрабатывает все новости параллельно для максимальной скорости
        """
        tasks = [self.extract_entities_async(news, verbose=verbose) for news in news_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Обрабатываем результаты и ошибки
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                if verbose:
                    print(f"Ошибка обработки новости {i+1}: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)

        return processed_results

    def extract_entities_batch(self, news_list: List[str], verbose: bool = False, parallel: bool = True) -> List[Optional[ExtractedEntities]]:
        """Обрабатывает список новостей с опцией параллельной обработки

        Args:
            news_list: Список новостей для обработки
            verbose: Детальный вывод
            parallel: Использовать параллельную обработку (быстрее)
        """
        if parallel:
            return asyncio.run(self.extract_entities_batch_async(news_list, verbose=verbose))
        else:
            # Последовательная обработка
            results = []
            for i, news in enumerate(news_list):
                try:
                    entity = self.extract_entities(news, verbose=verbose)
                    results.append(entity)
                except Exception as e:
                    if verbose:
                        print(f"Ошибка обработки новости {i+1}: {e}")
                    results.append(None)
            return results
    
    def _build_cached_messages(self, news_text: str, news_date: Optional[str]) -> List[Dict[str, Any]]:
        """
        Строит messages с поддержкой кэширования.
        
        КЛЮЧЕВАЯ ИДЕЯ: Помечаем статичные части (инструкции + глоссарий) для кэширования.
        Динамическая часть (новость) идет отдельно и не кэшируется.
        
        Поддержка разных моделей:
        - Claude (Anthropic): explicit cache_control с "ephemeral"
        - GPT (OpenAI): автоматический кэш (просто размещаем в начале)
        - Gemini: implicit cache (размещаем в начале, min 1024 tokens)
        - DeepSeek: автоматический кэш
        """
        
        # Часть 1: Базовые инструкции (кэшируются)
        base_instructions = """Ты - эксперт по анализу финансовых новостей на русском языке.

Твоя задача: извлечь из новости структурированную информацию в JSON формате со следующими полями:
{
  "publication_date": "YYYY-MM-DD или null",
  "people": [{"name": "ФИО", "position": "должность или null", "company": "компания или null"}],
  "companies": [{"name": "название", "ticker": "тикер или null", "sector": "отрасль или null"}],
  "markets": [{"name": "название", "type": "биржа/индекс/валюта/товар", "value": число или null, "change": "изменение или null"}],
  "financial_metrics": [{"metric_type": "тип показателя", "value": "значение с единицами (строка)", "company": "компания или null"}]
}

ВАЖНО:
- Используй глоссарий ниже для правильной интерпретации сокращений
- Будь точным, не добавляй информацию которой нет в тексте
- Точно следуй структуре JSON схемы выше
- Все значения metric_type и value должны быть строками"""
        
        # Часть 2: Глоссарий (кэшируется)
        glossary_text = self.glossary.get_glossary_text()
        
        messages = []

        # Для OpenAI - просто размещаем в начале
        # OpenAI автоматически кэширует префиксы промптов
        messages.append({
            "role": "system",
            "content": base_instructions + "\n\n" + glossary_text
        })
        
        # Часть 3: Новость (НЕ кэшируется - меняется каждый раз)
        user_content = f"Проанализируй финансовую новость:\n\n{news_text}"
        if news_date:
            user_content += f"\n\nДата публикации: {news_date}"
        
        messages.append({
            "role": "user",
            "content": user_content
        })
        
        return messages
    
    def _update_stats(self, result: Dict[str, Any]):
        """Обновляет статистику использования и кэширования"""
        self.stats["total_requests"] += 1
        
        usage = result.get("usage", {})

        # Для OpenAI
        prompt_tokens = usage.get("prompt_tokens", 0)
        # OpenAI возвращает cached_tokens в prompt_tokens_details (для поддерживаемых моделей)
        cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        
        self.stats["input_tokens"] += prompt_tokens
        self.stats["cached_tokens"] += cached_tokens
        self.stats["output_tokens"] += completion_tokens
        
        if cached_tokens > 0:
            self.stats["cache_hits"] += 1
        
        # Расчет стоимости для OpenAI моделей
        # Цены актуальны на август 2025
        cost = 0
        regular_input = prompt_tokens - cached_tokens

        if "gpt-5-nano" in self.model:
            cost += (regular_input / 1_000_000) * 0.050  # Input
            cost += (cached_tokens / 1_000_000) * 0.025  # Cached input (50% cheaper)
            cost += (completion_tokens / 1_000_000) * 0.400  # Output
        elif "gpt-4o-mini" in self.model:
            cost += (regular_input / 1_000_000) * 0.150  # Input
            cost += (cached_tokens / 1_000_000) * 0.075  # Cached input (50% cheaper)
            cost += (completion_tokens / 1_000_000) * 0.600  # Output
        elif "gpt-4o" in self.model:
            cost += (regular_input / 1_000_000) * 2.50  # Input
            cost += (cached_tokens / 1_000_000) * 1.25  # Cached input (50% cheaper)
            cost += (completion_tokens / 1_000_000) * 10.0  # Output
        elif "gpt-4-turbo" in self.model:
            cost += (regular_input / 1_000_000) * 10.0  # Input
            cost += (cached_tokens / 1_000_000) * 5.0  # Cached input (50% cheaper)
            cost += (completion_tokens / 1_000_000) * 30.0  # Output
        else:
            # Дефолтные цены для неизвестных моделей (GPT-5 Nano)
            cost += (regular_input / 1_000_000) * 0.050
            cost += (cached_tokens / 1_000_000) * 0.025
            cost += (completion_tokens / 1_000_000) * 0.400
        
        self.stats["total_cost"] += cost
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Возвращает статистику использования"""
        if self.stats["total_requests"] == 0:
            return {
                **self.stats,
                "cache_hit_rate_percent": 0,
                "token_savings_percent": 0,
                "estimated_savings_usd": 0,
                "avg_cost_per_request": 0
            }

        cache_hit_rate = (self.stats["cache_hits"] / self.stats["total_requests"]) * 100
        
        # Расчет экономии
        total_input = self.stats["input_tokens"]
        if total_input > 0:
            savings_percent = (self.stats["cached_tokens"] / total_input) * 100
        else:
            savings_percent = 0
        
        # Примерная экономия в деньгах (для Claude 3.5 Sonnet)
        cost_without_cache = (self.stats["input_tokens"] / 1_000_000) * 3.0
        actual_cache_cost = (self.stats["cached_tokens"] / 1_000_000) * 0.30
        regular_cost = ((self.stats["input_tokens"] - self.stats["cached_tokens"]) / 1_000_000) * 3.0
        money_saved = cost_without_cache - (actual_cache_cost + regular_cost)
        
        return {
            **self.stats,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "token_savings_percent": round(savings_percent, 2),
            "estimated_savings_usd": round(money_saved, 4),
            "avg_cost_per_request": round(self.stats["total_cost"] / self.stats["total_requests"], 6)
        }
    
    def print_stats(self):
        """Выводит статистику обработки"""
        stats = self.get_stats_summary()

        print("\n" + "="*60)
        print("📊 СТАТИСТИКА ОБРАБОТКИ")
        print("="*60)
        print(f"Всего запросов: {stats['total_requests']}")
        print(f"Input токенов: {stats['input_tokens']:,}")
        print(f"Output токенов: {stats['output_tokens']:,}")
        print(f"Общая стоимость: ${stats['total_cost']:.4f}")
        print("="*60)


# ===== ПРИМЕР ИСПОЛЬЗОВАНИЯ =====
def main():

# Загружаем переменные окружения
    load_dotenv()
    API_KEY = os.environ.get('API_KEY_2')
    print("API_KEY loaded:", bool(API_KEY))

    # Инициализация с дефолтной моделью (gpt-4o-mini)
    extractor = CachedFinanceNERExtractor(
        api_key=API_KEY,
        enable_caching=True
    )
    
    # Примеры новостей
    news_samples = [
        """Акции Сбербанка выросли на 3.2% после публикации отчетности. 
        Чистая прибыль составила 389 млрд рублей. Глава Сбербанка Герман Греф 
        заявил о планах увеличить дивиденды.""",
        
        """Индекс ММВБ закрылся на отметке 3245 пунктов (+1.5%). 
        На фоне роста цен на нефть выросли акции Лукойла (+2.1%) и Роснефти (+1.8%).""",
        
        """ЦБ РФ повысил ключевую ставку до 16%. Аналитики ВТБ Капитал 
        ожидают замедления инфляции в следующем квартале.""",
        
        """Яндекс представил квартальную отчетность. Выручка составила 
        150 млрд рублей (+18% год к году). Акции выросли на 5%.""",
        
        """Газпром объявил о рекордных дивидендах в размере 52 рублей на акцию. 
        Аналитики повысили целевую цену до 250 рублей."""
    ]
    
    print("🚀 Начинаем ПАРАЛЛЕЛЬНУЮ обработку новостей с GPT-5...\n")
    print(f"Модель: {extractor.model}")
    print(f"Кэширование: GPT-5 автоматически кэширует промпты >1024 токенов")
    print(f"Обработка: Асинхронная (все запросы параллельно)\n")

    # Обрабатываем новости с детальным выводом
    VERBOSE = False  # Отключить детальный вывод для скорости

    print(f"⏱️  Начало обработки {len(news_samples)} новостей...")
    start_time = time.time()

    # ПАРАЛЛЕЛЬНАЯ обработка всех новостей сразу
    results = extractor.extract_entities_batch(news_samples, verbose=VERBOSE, parallel=True)

    elapsed = time.time() - start_time
    print(f"✅ Завершено за {elapsed:.2f} секунд ({elapsed/len(news_samples):.2f} сек/новость)\n")

    # Выводим результаты
    for i, (news, entities) in enumerate(zip(news_samples, results), 1):
        print(f"\n{'='*70}")
        print(f"📰 НОВОСТЬ {i}/{len(news_samples)}")
        print(f"{'='*70}")
        print(f"ТЕКСТ:\n{news}\n")

        if entities is None:
            print(f"   ✗ ОШИБКА: Не удалось обработать")
        else:
            print(f"✓ ИЗВЛЕЧЕНО:")
            print(f"  • Компаний: {len(entities.companies)}")
            for c in entities.companies:
                print(f"    - {c.name}" + (f" ({c.ticker})" if c.ticker else ""))
            print(f"  • Персон: {len(entities.people)}")
            for p in entities.people:
                print(f"    - {p.name}" + (f", {p.position}" if p.position else ""))
            print(f"  • Рынков: {len(entities.markets)}")
            for m in entities.markets:
                print(f"    - {m.name}: {m.value} ({m.change})" if m.value else f"    - {m.name}")
            print(f"  • Метрик: {len(entities.financial_metrics)}")
            for fm in entities.financial_metrics:
                print(f"    - {fm.metric_type}: {fm.value}")

    print(f"\n{'='*70}")
    
    # Выводим статистику
    extractor.print_stats()

    # Расчет стоимости для 1000 новостей
    stats = extractor.get_stats_summary()
    if stats['total_requests'] > 0:
        cost_per_news = stats['total_cost'] / stats['total_requests']
        cost_1000 = cost_per_news * 1000
        print(f"\n💰 СТОИМОСТЬ ОБРАБОТКИ 1000 НОВОСТЕЙ:")
        print(f"   Модель: {extractor.model}")
        print(f"   Стоимость: ${cost_1000:.2f}")


if __name__ == "__main__":
    main()