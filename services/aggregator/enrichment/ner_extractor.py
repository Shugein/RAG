#Parser.src/services/enricher/ner_extractor.py
"""
Извлечение именованных сущностей (NER) с использованием DeepPavlov BERT
Поддерживает мультиязычное извлечение организаций, персон, локаций, дат, денежных сумм
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """Извлеченная сущность"""
    type: str  # ORG, PERSON, LOC, DATE, MONEY, PCT, AMOUNT, etc.
    text: str  # Оригинальный текст
    normalized: Optional[Dict[str, Any]] = None  # Нормализованное значение
    start: int = 0  # Позиция начала в тексте
    end: int = 0  # Позиция конца в тексте
    confidence: float = 1.0  # Уверенность в извлечении


class NERExtractor:
    """
    Класс для извлечения именованных сущностей из текста
    
    Поддерживаемые бэкенды:
    - Natasha (по умолчанию) - оптимизирована для русского языка, Python 3.12+
    - DeepPavlov BERT - мультиязычный NER (требует Python 3.9-3.11)
    
    + дополнительные регулярные выражения для финансовых метрик
    """
    
    def __init__(self, use_ml_ner: bool = True, backend: str = "natasha"):
        """
        Инициализация NER экстрактора
        
        Args:
            use_ml_ner: Использовать ли ML-модель для NER (требует установки)
            backend: Бэкенд для NER - "natasha" (рекомендуется для русского) или "deeppavlov"
        """
        self.use_ml_ner = use_ml_ner
        self.backend = backend
        self.ner_model = None
        self.natasha_ner = None
        
        # Паттерны для финансовых метрик
        self._init_financial_patterns()
        
        # Инициализация NER модели (если доступна)
        if use_ml_ner:
            try:
                if backend == "natasha":
                    self._init_natasha_model()
                elif backend == "deeppavlov":
                    self._init_deeppavlov_model()
                else:
                    logger.warning(f"Unknown backend: {backend}. Falling back to rule-based extraction only")
                    self.use_ml_ner = False
            except Exception as e:
                logger.warning(f"Failed to initialize {backend} model: {e}")
                logger.warning("Falling back to rule-based extraction only")
                self.use_ml_ner = False
    
    def _init_natasha_model(self):
        """Инициализация Natasha NER модели (оптимизирована для русского языка)"""
        try:
            from natasha import (
                Segmenter,
                MorphVocab,
                NewsEmbedding,
                NewsNERTagger,
                NamesExtractor,
                Doc
            )
            
            # Инициализация компонентов Natasha
            self.natasha_ner = {
                'segmenter': Segmenter(),
                'morph_vocab': MorphVocab(),
                'emb': NewsEmbedding(),
                'ner_tagger': NewsNERTagger(NewsEmbedding()),
                'names_extractor': NamesExtractor(MorphVocab()),
                'doc_class': Doc
            }
            logger.info("Natasha NER model initialized successfully")
            
        except ImportError:
            logger.error(
                "Natasha not installed. Install with: "
                "pip install natasha razdel slovnet"
            )
            raise
        except Exception as e:
            logger.error(f"Error initializing Natasha model: {e}")
            raise
    
    def _init_deeppavlov_model(self):
        """Инициализация DeepPavlov BERT NER модели"""
        try:
            from deeppavlov import build_model
            
            # Используем мультиязычную BERT модель для NER
            # Модель поддерживает русский и английский
            self.ner_model = build_model('ner_multi_bert', download=True)
            logger.info("DeepPavlov NER model initialized successfully")
            
        except ImportError:
            logger.error(
                "DeepPavlov not installed. Install with: "
                "pip install deeppavlov && python -m deeppavlov install ner_multi_bert"
            )
            raise
        except Exception as e:
            logger.error(f"Error initializing DeepPavlov model: {e}")
            raise
    
    def _init_financial_patterns(self):
        """Инициализация регулярных выражений для финансовых метрик"""
        
        # Денежные суммы (123 млн руб, $45.6M, 100 тыс. долларов)
        self.money_pattern = re.compile(
            r'(?P<amount>[\d\s,.]+)\s*'
            r'(?P<scale>млрд|млн|тыс\.?|миллиард|миллион|тысяч|billion|million|thousand|B|M|K)?\s*'
            r'(?P<currency>руб\.?|рубл|долл|€|₽|\$|USD|EUR|RUB)',
            re.IGNORECASE | re.UNICODE
        )
        
        # Проценты (45%, 12.5 процентов, +3.2% YoY)
        self.percent_pattern = re.compile(
            r'(?P<sign>[+-])?'
            r'(?P<value>[\d,.]+)\s*'
            r'(?P<unit>%|процент|п\.?п\.?|pp|б\.?п\.?|bps?)\s*'
            r'(?P<basis>YoY|QoQ|MoM|г/г|кв/кв|м/м)?',
            re.IGNORECASE
        )
        
        # Количественные показатели (1000 тонн, 500 баррелей, 200 МВт)
        self.amount_pattern = re.compile(
            r'(?P<amount>[\d\s,.]+)\s*'
            r'(?P<scale>млрд|млн|тыс\.?)?'
            r'\s*(?P<unit>тонн|баррел|куб\.?м|МВт|ГВт|кВт|штук?|единиц)',
            re.IGNORECASE | re.UNICODE
        )
        
        # Периоды отчетности (1П2025, Q3 2024, 9М2025, FY2024)
        self.period_pattern = re.compile(
            r'(?P<period>(?:1П|2П|[1-4]Q|Q[1-4]|[1-9]М|FY|ГОД)\s*[\-\s]?\s*20\d{2})',
            re.IGNORECASE
        )
        
        # Даты (15 января 2025, 2025-01-15, 15.01.2025)
        self.date_pattern = re.compile(
            r'(?P<date>'
            r'(?:\d{1,2}[\s\-/.]\d{1,2}[\s\-/.]\d{2,4})|'  # 15.01.2025
            r'(?:\d{4}[\s\-/.]\d{1,2}[\s\-/.]\d{1,2})|'     # 2025-01-15
            r'(?:\d{1,2}\s+(?:янв|фев|мар|апр|мая|июн|июл|авг|сен|окт|ноя|дек)\w*\s+\d{4})'  # 15 января 2025
            r')',
            re.IGNORECASE | re.UNICODE
        )
    
    def extract_entities(self, text: str) -> List[ExtractedEntity]:
        """
        Извлечение всех сущностей из текста
        
        Args:
            text: Текст для анализа
            
        Returns:
            Список извлеченных сущностей
        """
        entities = []
        
        # 1. Извлечение с помощью ML-модели (если доступна)
        if self.use_ml_ner:
            try:
                if self.backend == "natasha" and self.natasha_ner:
                    entities.extend(self._extract_with_natasha(text))
                elif self.backend == "deeppavlov" and self.ner_model:
                    entities.extend(self._extract_with_deeppavlov(text))
            except Exception as e:
                logger.error(f"{self.backend} extraction failed: {e}")
        
        # 2. Извлечение финансовых метрик с помощью регулярных выражений
        entities.extend(self._extract_money(text))
        entities.extend(self._extract_percentages(text))
        entities.extend(self._extract_amounts(text))
        entities.extend(self._extract_periods(text))
        entities.extend(self._extract_dates(text))
        
        # 3. Удаление дубликатов и сортировка по позиции
        entities = self._deduplicate_entities(entities)
        entities.sort(key=lambda e: e.start)
        
        return entities
    
    def _extract_with_deeppavlov(self, text: str) -> List[ExtractedEntity]:
        """
        Извлечение сущностей с помощью DeepPavlov BERT
        
        Поддерживаемые типы:
        - PER (PERSON): персоны
        - ORG: организации
        - LOC: локации
        """
        entities = []
        
        try:
            # DeepPavlov возвращает: (tokens, tags)
            # tags в формате BIO: B-PER, I-PER, B-ORG, I-ORG, B-LOC, I-LOC, O
            result = self.ner_model([text])
            
            if not result or len(result) < 2:
                return entities
            
            tokens_list = result[0][0]  # Список токенов
            tags_list = result[1][0]    # Список тегов
            
            current_entity = None
            current_tokens = []
            current_tag = None
            start_pos = 0
            
            for token, tag in zip(tokens_list, tags_list):
                # Ищем позицию токена в тексте
                token_start = text.find(token, start_pos)
                if token_start == -1:
                    continue
                
                token_end = token_start + len(token)
                
                if tag.startswith('B-'):
                    # Начало новой сущности
                    if current_entity:
                        # Сохраняем предыдущую
                        entities.append(current_entity)
                    
                    entity_type = tag[2:]  # Убираем 'B-'
                    current_entity = ExtractedEntity(
                        type=entity_type,
                        text=token,
                        start=token_start,
                        end=token_end,
                        confidence=0.9
                    )
                    current_tokens = [token]
                    current_tag = entity_type
                    
                elif tag.startswith('I-') and current_entity:
                    # Продолжение текущей сущности
                    entity_type = tag[2:]
                    if entity_type == current_tag:
                        current_tokens.append(token)
                        current_entity.text = ' '.join(current_tokens)
                        current_entity.end = token_end
                    
                else:
                    # O - не сущность
                    if current_entity:
                        entities.append(current_entity)
                        current_entity = None
                        current_tokens = []
                        current_tag = None
                
                start_pos = token_end
            
            # Не забываем последнюю сущность
            if current_entity:
                entities.append(current_entity)
        
        except Exception as e:
            logger.error(f"Error in DeepPavlov extraction: {e}")
        
        return entities
    
    def _extract_with_natasha(self, text: str) -> List[ExtractedEntity]:
        """
        Извлечение сущностей с помощью Natasha (оптимизирована для русского)
        
        Поддерживаемые типы:
        - PER (PERSON): персоны
        - ORG: организации
        - LOC: локации
        """
        entities = []
        
        try:
            # Создаем документ и применяем NER
            Doc = self.natasha_ner['doc_class']
            segmenter = self.natasha_ner['segmenter']
            ner_tagger = self.natasha_ner['ner_tagger']
            
            doc = Doc(text)
            doc.segment(segmenter)
            doc.tag_ner(ner_tagger)
            
            # Извлекаем сущности
            for span in doc.spans:
                # Natasha использует типы: PER, LOC, ORG
                entity_type = span.type
                
                # Нормализация типа для совместимости
                if entity_type == 'PER':
                    entity_type = 'PERSON'
                
                entities.append(ExtractedEntity(
                    type=entity_type,
                    text=span.text,
                    start=span.start,
                    end=span.stop,
                    confidence=0.9
                ))
        
        except Exception as e:
            logger.error(f"Error in Natasha extraction: {e}")
        
        return entities
    
    def _extract_money(self, text: str) -> List[ExtractedEntity]:
        """Извлечение денежных сумм"""
        entities = []
        
        for match in self.money_pattern.finditer(text):
            try:
                amount_str = match.group('amount').replace(' ', '').replace(',', '.')
                amount = float(amount_str)
                
                scale = match.group('scale')
                if scale:
                    scale_lower = scale.lower()
                    if scale_lower in ['млрд', 'миллиард', 'billion', 'b']:
                        amount *= 1_000_000_000
                    elif scale_lower in ['млн', 'миллион', 'million', 'm']:
                        amount *= 1_000_000
                    elif scale_lower in ['тыс', 'тысяч', 'thousand', 'k']:
                        amount *= 1_000
                
                currency = match.group('currency')
                # Нормализация валюты
                currency_map = {
                    'руб': 'RUB', 'рубл': 'RUB', '₽': 'RUB',
                    'долл': 'USD', '$': 'USD',
                    '€': 'EUR'
                }
                currency_code = currency_map.get(currency.lower().rstrip('.'), currency.upper())
                
                entities.append(ExtractedEntity(
                    type='MONEY',
                    text=match.group(0),
                    normalized={
                        'amount': amount,
                        'currency': currency_code
                    },
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95
                ))
            except (ValueError, AttributeError) as e:
                logger.debug(f"Failed to parse money: {match.group(0)} - {e}")
                continue
        
        return entities
    
    def _extract_percentages(self, text: str) -> List[ExtractedEntity]:
        """Извлечение процентов"""
        entities = []
        
        for match in self.percent_pattern.finditer(text):
            try:
                value_str = match.group('value').replace(',', '.')
                value = float(value_str)
                
                sign = match.group('sign')
                if sign == '-':
                    value = -value
                
                unit = match.group('unit')
                basis = match.group('basis')
                
                # Преобразование в базисные пункты если нужно
                is_bps = unit.lower() in ['б.п', 'бп', 'bp', 'bps']
                
                entities.append(ExtractedEntity(
                    type='PCT',
                    text=match.group(0),
                    normalized={
                        'value': value,
                        'is_basis_points': is_bps,
                        'comparison_basis': basis if basis else None
                    },
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95
                ))
            except (ValueError, AttributeError) as e:
                logger.debug(f"Failed to parse percentage: {match.group(0)} - {e}")
                continue
        
        return entities
    
    def _extract_amounts(self, text: str) -> List[ExtractedEntity]:
        """Извлечение количественных показателей с единицами"""
        entities = []
        
        for match in self.amount_pattern.finditer(text):
            try:
                amount_str = match.group('amount').replace(' ', '').replace(',', '.')
                amount = float(amount_str)
                
                scale = match.group('scale')
                if scale:
                    scale_lower = scale.lower()
                    if scale_lower in ['млрд']:
                        amount *= 1_000_000_000
                    elif scale_lower in ['млн']:
                        amount *= 1_000_000
                    elif scale_lower in ['тыс']:
                        amount *= 1_000
                
                unit = match.group('unit')
                
                entities.append(ExtractedEntity(
                    type='AMOUNT',
                    text=match.group(0),
                    normalized={
                        'value': amount,
                        'unit': unit
                    },
                    start=match.start(),
                    end=match.end(),
                    confidence=0.9
                ))
            except (ValueError, AttributeError) as e:
                logger.debug(f"Failed to parse amount: {match.group(0)} - {e}")
                continue
        
        return entities
    
    def _extract_periods(self, text: str) -> List[ExtractedEntity]:
        """Извлечение отчетных периодов"""
        entities = []
        
        for match in self.period_pattern.finditer(text):
            period_text = match.group('period')
            
            entities.append(ExtractedEntity(
                type='PERIOD',
                text=match.group(0),
                normalized={'period': period_text.replace(' ', '').replace('-', '')},
                start=match.start(),
                end=match.end(),
                confidence=0.95
            ))
        
        return entities
    
    def _extract_dates(self, text: str) -> List[ExtractedEntity]:
        """Извлечение дат"""
        entities = []
        
        for match in self.date_pattern.finditer(text):
            date_text = match.group('date')
            
            entities.append(ExtractedEntity(
                type='DATE',
                text=match.group(0),
                normalized={'date_string': date_text},
                start=match.start(),
                end=match.end(),
                confidence=0.85
            ))
        
        return entities
    
    def _deduplicate_entities(self, entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
        """
        Удаление дубликатов сущностей
        Если две сущности пересекаются, оставляем ту, у которой выше confidence
        """
        if not entities:
            return []
        
        # Сортируем по позиции начала
        sorted_entities = sorted(entities, key=lambda e: e.start)
        
        result = []
        for entity in sorted_entities:
            # Проверяем пересечение с уже добавленными
            overlap = False
            for existing in result:
                if self._entities_overlap(entity, existing):
                    # Если пересекаются, оставляем с большей уверенностью
                    if entity.confidence > existing.confidence:
                        result.remove(existing)
                        result.append(entity)
                    overlap = True
                    break
            
            if not overlap:
                result.append(entity)
        
        return result
    
    def _entities_overlap(self, e1: ExtractedEntity, e2: ExtractedEntity) -> bool:
        """Проверка пересечения двух сущностей"""
        return not (e1.end <= e2.start or e2.end <= e1.start)

