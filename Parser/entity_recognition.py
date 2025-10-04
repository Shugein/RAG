#!/usr/bin/env python3
"""
🚀 AI-POWERED FINANCE NER EXTRACTOR

Замена классического NER (Natasha) на современную ИИ-систему извлечения финансовых событий.


- Новейшие модели (GPT-5/GPT-4o-mini/Qwen3-4B)
- Понимание сложных финансовых контекстов
- Высокая точность извлечения сущностей

 
- Prompt Caching: экономия до 90% на токенах
- Parallel Processing: обработка в реальном времени
- Batch Processing: массивная обработка массивов


- Финансовый глоссарий: компании, индексы, термины
- CEG система: события, якорные события, цепочки причин
- Russian Finance: оптимизация для русских финансовых текстов


- is_advertisement: фильтрация рекламы
- content_types: финансовые, политические, юридические, природные бедствия  
- События: санкции, ставки ЦБ, результаты компаний
- Без якорности в NER - вычисляется отдельно

- Совместимость с существующей системой Natasha

Использование:
1. Быстрое извлечение финансовых сущностей из новостей
2. Batch обработка массивов новостей в JSON формате
3. Интеграция с CEG системой для анализа влияния
4. Фильтрация рекламного контента
5. Классификация типов контента
"""

import os
import json
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field, validator
import os
import json
from dotenv import load_dotenv
import httpx
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
load_dotenv()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
OPENAI_API_KEY = os.environ.get('API_KEY_2')

# ===== PYDANTIC МОДЕЛИ =====
class Person(BaseModel):
    name: str = Field(description="Имя человека")
    position: Optional[str] = Field(None, description="Должность")
    company: Optional[str] = Field(None, description="Компания")

class Company(BaseModel):
    name: str = Field(description="Название компании")
    ticker: Optional[str] = Field(None, description="Тикер")
    sector: Optional[str] = Field(None, description="Сектор")

class Market(BaseModel):
    name: str = Field(description="Название рынка")
    type: str = Field(description="Тип")
    value: Optional[float] = Field(None, description="Значение")
    change: Optional[str] = Field(None, description="Изменение")

class FinancialMetric(BaseModel):
    metric_type: str = Field(description="Тип показателя")
    value: str = Field(description="Значение")
    company: Optional[str] = Field(None, description="Компания")

class ExtractedEntities(BaseModel):
    publication_date: Optional[str] = Field(None, description="Дата")
    people: List[Person] = Field(default_factory=list)
    companies: List[Company] = Field(default_factory=list)
    markets: List[Market] = Field(default_factory=list)
    financial_metrics: List[FinancialMetric] = Field(default_factory=list)
    
    # Дополнительные поля для CEG системы
    sector: Optional[str] = Field(None, description="Отрасль")
    country: Optional[str] = Field(None, description="Страна") 
    event_types: List[str] = Field(default_factory=list, description="Типы событий")
    event: Optional[str] = Field(None, description="Описание события")
    
    # Фильтры и категоризация
    is_advertisement: bool = Field(False, description="Реклама?")
    content_types: List[str] = Field(default_factory=list, description="Типы контента")
    
    # Метаданные обработки
    confidence_score: float = Field(0.8, description="Уверенность")
    language: str = Field("ru", description="Язык")
    requires_market_data: bool = Field(False, description="Нужны рыночные данные?")
    urgency_level: str = Field("normal", description="Срочность")

class BatchExtractedEntities(BaseModel):
    """Модель для batch-обработки"""
    news_items: List[ExtractedEntities] = Field(default_factory=list)
    total_processed: int = 0
    batch_id: Optional[str] = None

# ===== ГЛОССАРИЙ =====
class RussianFinanceGlossary:
    def __init__(self):
        self.companies = {
            "ГАЗПРОМ": {"full_name": "ПАО Газпром", "ticker": "GAZP", "sector": "Нефть и газ"},
            "СБЕРБАНК": {"full_name": "ПАО Сбербанк", "ticker": "SBER", "sector": "Финансы"},
            "ЛУКОЙЛ": {"full_name": "ПАО ЛУКОЙЛ", "ticker": "LKOH", "sector": "Нефть и газ"},
            "НОРНИКЕЛЬ": {"full_name": "ГМК Норильский никель", "ticker": "GMKN", "sector": "Металлургия"},
        }
        
        self.event_types = {
            "sanctions": ["санкции", "санкц", "ограничени", "запрет"],
            "rate_hike": ["ключевая ставка", "повысил ставку", "рост ставки"],
            "earnings": ["прибыль", "выручка", "отчетность", "результаты"],
        }
        
        self.content_types = {
            "financial": ["финансы", "банк", "акции", "валют", "курс"],
            "political": ["политик", "правительство", "президент", "минтра", "власть"],
            "legal": ["закон", "суд", "право", "иск", "вердикт"],
            "natural_disaster": ["пожар", "наводнение", "землетрясение", "стихийное"],
        }
        
        self.advertisement_markers = [
            "реклама", "промо", "акция", "скидка", "купи", 
            "инвестиционн", "консультант", "брокер", "подписывайт", "@"
        ]
    
    def get_glossary_text(self) -> str:
        """Возвращает глоссарий"""
        text = "# ФИНАНСОВЫЙ ГЛОССАРИЙ\n\n"
        
        text += "## Компании:\n"
        for abbr, info in self.companies.items():
            text += f"- {abbr}: {info['full_name']} (Тикер: {info['ticker']})\n"
        
        text += "\n## Типы событий:\n"
        for event_type, keywords in self.event_types.items():
            text += f"- {event_type}: {', '.join(keywords[:3])}\n"
        
        text += "\n## Типы контента:\n"
        for content_type, keywords in self.content_types.items():
            text += f"- {content_type}: {', '.join(keywords[:3])}\n"
        
        return text

# ===== ОСНОВНОЙ НЕР =====
class CachedFinanceNERExtractor:
    """ИИ-извлекатель с поддержкой prompt caching"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", enable_caching: bool = True):
        self.api_key = api_key
        self.model = model
        self.enable_caching = enable_caching
        self.base_url = "https://api.openai.com/v1"
        self.glossary = RussianFinanceGlossary()
        
        # Prompt инструкции
        self.base_instructions = """Ты эксперт анализа финансовых новостей. Извлеки JSON с полями:
          "publication_date": "дата или null",
          "people": [{"name": "ФИО", "position": "должность", "company": "компания"}],
          "companies": [{"name": "название", "ticker": "тикер", "sector": "отрасль"}],
          "markets": [{"name": "название", "type": "тип", "value": число, "change": "изменение"}],
          "financial_metrics": [{"metric_type": "тип", "value": "строка", "company": "компания"}],
          "sector": "основная отрасль или null",
          "country": "страна или null",
          "event_types": ["типы событий"],
          "event": "описание события или null",
          "is_advertisement": "true если реклама",
          "content_types": ["financial", "political", "legal", "natural_disaster"], 
          "confidence_score": "уверенность 0-1",
          "language": "ru или en",
          "requires_market_data": "true если нужны рыночные данные",
          "urgency_level": "low/normal/high/critical"

ПРАВИЛА:
1. Используй глоссарий
2. is_advertisement = true если содержит рекламу
3. content_types: financial/пolitical/legal/natural_disaster
4. Для requires_market_data ставь true если влияет на цены
5. Якорность НЕ определяй - будет вычисляться отдельно"""

        self.batch_instructions = """Обработай массив новостей и верни в формате:
          "news_items": [массив с теми же полями],
          "total_processed": "число",
          "batch_id": "идентификатор или null"

Максимум 50 новостей за раз."""

    async def extract_entities_async(self, news_text: str) -> ExtractedEntities:
        """Асинхронное извлечение одной новости"""
        messages = [
            {"role": "system", "content": f"{self.base_instructions}\n\n{self.glossary.get_glossary_text()}\n\nТекст новости:"},
            {"role": "user", "content": news_text}
        ]
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4000,
            "cache_override": "auto" if self.enable_caching else "disable"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
        
        response.raise_for_status()
        json_response = response.json()
        
        content = json_response['choices'][0]['message']['content']
        return ExtractedEntities.parse_raw(content)

    def extract_entities_json_batch(self, news_list: List[str], news_metadata: List[Dict[str, Any]] = None, verbose: bool = False) -> Dict[str, Any]:
        """Batch обработка JSON массива новостей"""
        
        if len(news_list) > 50:
            # Обрабатываем по частям
            chunk_size = 25
            results = []
            for i in range(0, len(news_list), chunk_size):
                chunk = news_list[i:i + chunk_size]
                chunk_meta = news_metadata[i:i + chunk_size] if news_meta else []
                chunk_result = self._process_batch_chunk(chunk, chunk_meta)
                results.extend(chunk_result.get('news_items', []))
            
            return {
                "news_items": results,
                "total_processed": len(results),
                "batch_id": None
            }
        
        return self._process_batch_chunk(news_list, news_metadata or [])
    
    def _process_batch_chunk(self, news_list: List[str], metadata_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обрабатывает chunk новостей"""
        
        # Формируем массив для обработки
        news_array = []
        for i, news_text in enumerate(news_list):
            news_item = {"text": news_text}
            if i < len(metadata_list):
                news_item.update(metadata_list[i])
            news_array.append(news_item)
        
        messages = [
            {"role": "system", "content": f"{self.batch_instructions}\n\n{self.glossary.get_glossary_text()}"},
            {"role": "user", "content": f"Обработай:\n{json.dumps(news_array, ensure_ascii=False, indent=2)}"}
        ]
        
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 8000,
            "cache_override": "auto" if self.enable_caching else "disable"
        }
        
        response = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        
        try:
            batch_result = BatchExtractedEntities.parse_raw(response.json()['choices'][0]['message']['content'])
            return batch_result.dict()
        except Exception as e:
            return {
                "news_items": [],
                "total_processed": 0,
                "batch_id": None,
                "error": str(e)
            }

# ===== СОВМЕСТИМОСТЬ =====
class CompatibilityWrapper:
    """Совместимость с старой системой Natasha"""
    
    def __init__(self, extractor: CachedFinanceNERExtractor):
        self.extractor = extractor
        
    async def extract_entities(self, text: str, news_meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """Извлекает в формате совместимом с Natasha"""
        try:
            extracted = await self.extractor.extract_entities_async(text)
            
            result = {
                'matches': [],
                'norm': {},
                'fact': {},
                'meta': news_meta or {}
            }
            
            # Компании как ORG
            for company in extracted.companies:
                result['matches'].append({
                    'fact': company.dict(),
                    'span': [0, len(company.name)],
                    'type': 'ORG'
                })
            
            # Финансовые метрики как AMOUNT
            for metric in extracted.financial_metrics:
                result['matches'].append({
                    'fact': {'type': metric.metric_type, 'value': metric.value},
                    'span': [0, len(metric.value)],
                    'type': 'AMOUNT'
                })
            
            # Новые метаданные
            if extracted.event_types:
                result['meta']['event_types'] = extracted.event_types
            if extracted.sector:
                result['meta']['sector'] = extracted.sector
            if extracted.country:
                result['meta']['country'] = extracted.country
            if extracted.content_types:
                result['meta']['content_types'] = extracted.content_types
            
            result['meta']['is_advertisement'] = extracted.is_advertisement
            result['meta']['requires_market_data'] = extracted.requires_market_data
            result['meta']['urgency_level'] = extracted.urgency_level
            
            return result
            
        except Exception as e:
            return {
                'matches': [],
                'norm': {},
                'fact': {},
                'meta': news_meta or {},
                'error': str(e)
            }

# ===== TEСТ =====
async def main():
    """Тестирование нового NER"""
    
    API_KEY = os.environ.get('API_KEY_2')
    if not API_KEY:
        print("❌ API_KEY не найден")
        return
    
    extractor = CachedFinanceNERExtractor(api_key=API_KEY, enable_caching=True)
    
    # Тест 1: Одна новость
    news_text = """
    ЦБ РФ сохранил ключевую ставку на уровне 7.5%. 
    Сбербанк показал рост прибыли на 25% до 180 млрд рублей.
    """
    
    print("🚀 Тест новой NER системы")
    print("="*50)
    
    extracted = await extractor.extract_entities_async(news_text)
    print(f"Компании: {[c.name for c in extracted.companies]}")
    print(f"События: {extracted.event_types}")
    print(f"Фильтр рекламы: {'ДА' if extracted.is_advertisement else 'НЕТ'}")
    print(f"Контент: {extracted.content_types}")
    print(f"НЕ ЯКОРНОЕ: Убрана проверка якорности")
    
    # Тест 2: Batch обработка
    batch_news = [
        "ЦБ РФ повысил ставку до 16%",
        "Сбербанк показал рост прибыли на 30%", 
        "Купите акции! Скидка на консультации! Подписывайтесь!",
        "Землетрясение в Японии нарушило поставки"
    ]
    
    print("\n" + "="*50)
    print("📊 БАТЧ ОБРАБОТКА")
    
    batch_result = extractor.extract_entities_json_batch(batch_news, verbose=True)
    print(f"Обработано: {batch_result['total_processed']}/{len(batch_news)}")
    
    for i, item in enumerate(batch_result['news_items']):
        if item:
            print(f"Новость {i+1}: события={item.get('event_types', [])}, "
                  f"реклама={'ДА' if item.get('is_advertisement', False) else 'НЕТ'}, "
                  f"контент={item['content_types']}")
    
    print("\n✅ Тест завершен")

if __name__ == "__main__":
    asyncio.run(main())
