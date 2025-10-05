#Parser.src/services/events/event_extractor.py
"""
Event Extractor - извлечение событий из AI-extracted сущностей
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from Parser.src.core.models import News, Event

logger = logging.getLogger(__name__)


class EventExtractor:
    """
    Извлекает события из новостей на основе AI-extracted сущностей
    Использует причинно-следственные маркеры из ТЗ (раздел 11)
    """

    # Лексикон причинно-следственных маркеров (из ТЗ раздел 11)
    CAUSAL_MARKERS_RU = {
        # События по типам
        "sanctions": [
            "санкции", "санкц", "ограничени", "запрет", "включить в список",
            "задержать", "наложить штраф", "инициировать расследование"
        ],
        "rate_hike": [
            "ключевая ставка", "повысил ставку", "рост ставки", "повышение ставки",
            "цб повысил", "центральный банк повысил"
        ],
        "rate_cut": [
            "снижение ставки", "снизил ставку", "понижение ставки",
            "ставка снижена", "снижена ставка"
        ],
        "earnings": [
            "прибыль", "выручка", "отчетность", "результаты", "финансовые результаты",
            "квартальная отчетность", "годовая отчетность"
        ],
        "earnings_miss": ["убыток", "снижение прибыли", "падение прибыли"],
        "earnings_beat": ["рост прибыли", "увеличение прибыли", "рекордная прибыль"],
        "guidance": ["прогноз", "ожидания", "планы", "намерен", "планирует"],
        "guidance_cut": ["снизил прогноз", "ухудшил прогноз", "пересмотрел прогноз"],
        "m&a": ["слияние", "поглощение", "сделка", "приобрет", "купил долю", "m&a"],
        "default": ["дефолт", "банкротство", "невыплата", "технический дефолт"],
        "dividends": ["дивиденды", "дивиденд", "выплата дивидендов"],
        "dividend_cut": ["сократил дивиденды", "снизил дивиденды"],
        "buyback": ["обратный выкуп", "байбэк", "buyback"],
        "ipo": ["ipo", "размещение", "первичное размещение"],
        "regulatory": [
            "регулятор", "регулирование", "закон", "законопроект",
            "постановление", "указ", "антимонопольн"
        ],
        "legal": ["суд", "судебн", "иск", "арбитраж", "судебное решение"],
        "management_change": [
            "новый директор", "смена руководства", "назначен", "ушел в отставку",
            "покинул пост", "сменил директор"
        ],
        "supply_chain": [
            "цепочка поставок", "поставк", "логистик", "транспорт", "перебои",
            "задержка поставок"
        ],
        "production": ["производство", "выпуск", "мощност", "завод"],
        "accident": ["авария", "инцидент", "катастроф", "чп"],
        "strike": ["забастовка", "протест", "остановка работы"],
    }

    CAUSAL_MARKERS_EN = {
        "sanctions": ["sanctions", "restrict", "ban", "embargo"],
        "rate_hike": ["rate hike", "raised rate", "increased rate"],
        "earnings": ["earnings", "revenue", "profit", "results"],
        "guidance": ["guidance", "forecast", "outlook"],
        "m&a": ["merger", "acquisition", "m&a", "takeover"],
    }

    def __init__(self):
        """Инициализация экстрактора"""
        # Компилируем регулярки для быстрого поиска
        self._compiled_patterns = {}
        for event_type, markers in self.CAUSAL_MARKERS_RU.items():
            pattern = "|".join(re.escape(m) for m in markers)
            self._compiled_patterns[event_type] = re.compile(pattern, re.IGNORECASE)

    def extract_events_from_news(
        self,
        news: News,
        ai_extracted: Any
    ) -> List[Event]:
        """
        Извлекает события из новости на основе AI extraction

        Args:
            news: Объект новости
            ai_extracted: Результат AI extraction (ExtractedEntities)

        Returns:
            Список извлечённых событий
        """
        events = []

        # Определяем тип события по маркерам в тексте
        full_text = f"{news.title} {news.text_plain or ''}".lower()
        event_types = self._detect_event_types(full_text)

        if not event_types:
            # Если маркеров нет, используем общий тип "news"
            event_types = ["news_general"]

        # Для каждого типа создаём событие
        for event_type in event_types:
            # Формируем атрибуты события из AI extraction
            attrs = {
                "companies": [c.name for c in ai_extracted.companies],
                "tickers": [c.ticker for c in ai_extracted.companies if c.ticker],
                "people": [
                    {
                        "name": p.name,
                        "position": p.position,
                        "company": p.company
                    }
                    for p in ai_extracted.people
                ],
                "markets": [
                    {
                        "name": m.name,
                        "type": m.type,
                        "value": m.value,
                        "change": m.change
                    }
                    for m in ai_extracted.markets
                ],
                "financial_metrics": [
                    {
                        "metric_type": fm.metric_type,
                        "value": fm.value,
                        "company": fm.company
                    }
                    for fm in ai_extracted.financial_metrics
                ]
            }

            # Определяем, является ли это якорным событием
            is_anchor = self._is_anchor_event(event_type, attrs)

            # Создаём событие
            event = Event(
                id=uuid4(),
                news_id=news.id,
                event_type=event_type,
                title=news.title,
                ts=news.published_at,
                attrs=attrs,
                is_anchor=is_anchor,
                confidence=self._calculate_confidence(event_type, full_text)
            )

            events.append(event)
            logger.info(
                f"Extracted event {event_type} from news {news.id} "
                f"(companies: {len(attrs['companies'])}, anchor: {is_anchor})"
            )

        return events

    def _detect_event_types(self, text: str) -> List[str]:
        """
        Определяет типы событий по маркерам в тексте

        Args:
            text: Текст новости (lowercase)

        Returns:
            Список типов событий
        """
        detected_types = []

        for event_type, pattern in self._compiled_patterns.items():
            if pattern.search(text):
                detected_types.append(event_type)

        # Сортируем по приоритету (более специфичные первыми)
        priority = {
            "sanctions": 10,
            "rate_hike": 9,
            "rate_cut": 9,
            "earnings_miss": 8,
            "earnings_beat": 8,
            "earnings": 7,
            "default": 9,
            "m&a": 8,
            "ipo": 8,
        }

        detected_types.sort(key=lambda t: priority.get(t, 5), reverse=True)

        # Возвращаем максимум 2 типа
        return detected_types[:2]

    def _is_anchor_event(self, event_type: str, attrs: Dict[str, Any]) -> bool:
        """
        Определяет, является ли событие якорным (AnchorEvent)

        Якорные события - важные события, которые часто являются причиной других

        Args:
            event_type: Тип события
            attrs: Атрибуты события

        Returns:
            True если якорное
        """
        # Якорные типы событий (из domain priors ТЗ раздел 9)
        anchor_types = {
            "sanctions",
            "rate_hike",
            "rate_cut",
            "earnings_miss",
            "earnings_beat",
            "default",
            "regulatory",
            "m&a",
            "ipo",
        }

        if event_type in anchor_types:
            return True

        # Дополнительные критерии:
        # - Упоминает крупные компании (>= 2)
        if len(attrs.get("companies", [])) >= 2:
            return True

        # - Есть финансовые метрики (прибыль, убытки, дивиденды)
        if len(attrs.get("financial_metrics", [])) >= 1:
            return True

        return False

    def _calculate_confidence(self, event_type: str, text: str) -> float:
        """
        Рассчитывает уверенность в извлечении события

        Args:
            event_type: Тип события
            text: Текст новости

        Returns:
            Confidence [0, 1]
        """
        # Базовая уверенность
        confidence = 0.7

        # Если нашли несколько маркеров одного типа - повышаем
        if event_type in self._compiled_patterns:
            matches = len(self._compiled_patterns[event_type].findall(text))
            confidence += min(matches * 0.1, 0.2)

        # Ограничиваем [0.5, 0.95]
        return max(0.5, min(confidence, 0.95))
