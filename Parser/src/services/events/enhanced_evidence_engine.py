import logging
import math
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from src.core.models import Event, News, Entity, EventImportance
from src.graph_models import GraphService

logger = logging.getLogger(__name__)


class EnhancedEvidenceEngine:
    """
    Расширенный алгоритм поиска Evidence Events
    Находит события, которые усиливают причинно-следственные связи
    """
    
    def __init__(self, session: AsyncSession, graph_service: GraphService):
        self.session = session
        self.graph = graph_service
        
        # Конфигурация алгоритмов
        self.evidence_weights = {
            "temporal_proximity": 0.3,      # Близость по времени
            "semantic_relevance": 0.3,      # Семантическая релевантность
            "entity_overlap": 0.25,        # Пересечение сущностей
            "source_trust": 0.1,           # Доверие к источнику
            "importance_score": 0.05        # Важность события
        }
        
        # Статистики
        self.stats = {
            "evidence_search_attempts": 0,
            "evidence_events_found": 0,
            "high_quality_evidence": 0,
            "total_algorithms_executed": 0
        }
    
    async def find_enhanced_evidence_events(
        self,
        cause_event: Event,
        effect_event: Event,
        max_evidence_count: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Найти Evidence Events между причиной и следствием используя расширенные алгоритмы
        
        Args:
            cause_event: Событие-причина
            effect_event: Событие-следствие
            max_evidence_count: Максимальное количество Evidence Events
            
        Returns:
            List[Dict]: Список Evidence Events с оценками релевантности
        """
        logger.info(f"Finding enhanced evidence for causal link: {cause_event.event_type} -> {effect_event.event_type}")
        
        self.stats["evidence_search_attempts"] += 1
        
        # Фильтруем события во временном окне между причиной и следствием
        time_window_start = cause_event.ts
        time_window_end = effect_event.ts
        
        # Расширяем окно поиска на ±2 часа для лучшего покрытия
        search_start = time_window_start - timedelta(hours=2)
        search_end = time_window_end + timedelta(hours=2)
        
        # Получаем все события в окне поиска
        candidate_events = await self._get_candidate_events(
            search_start, 
            search_end,
            exclude_ids=[cause_event.id, effect_event.id]
        )
        
        evidence_scores = []
        
        for candidate in candidate_events:
            # Выполняем множественные алгоритмы оценки
            score_data = await self._calculate_evidence_score(
                candidate, cause_event, effect_event
            )
            
            if score_data['total_weighted_score'] > 0.3:  # Порог релевантности
                evidence_scores.append(score_data)
        
        # Сортируем по общей оценке релевантности
        evidence_scores.sort(key=lambda x: x['total_weighted_score'], reverse=True)
        
        # Выбираем топ Evidence Events
        top_evidence = evidence_scores[:max_evidence_count]
        
        self.stats["evidence_events_found"] += len(top_evidence)
        self.stats["high_quality_evidence"] += len([
            e for e in top_evidence if e['total_weighted_score'] > 0.7
        ])
        
        logger.info(f"Found {len(top_evidence)} evidence events (avg score: {sum(e['total_weighted_score'] for e in top_evidence) / max(len(top_evidence), 1):.3f})")
        
        return top_evidence
    
    async def _get_candidate_events(
        self,
        search_start: datetime,
        search_end: datetime,
        exclude_ids: List[str]
    ) -> List[Event]:
        """Получить все события-кандидаты в установленном временном окне"""
        
        result = await self.session.execute(
            select(Event)
            .where(
                and_(
                    Event.ts >= search_start,
                    Event.ts <= search_end,
                    Event.id.notin_([str(id_) for id_ in exclude_ids])
                )
            )
            .order_by(Event.ts)
        )
        
        return result.scalars().all()
    
    async def _calculate_evidence_score(
        self,
        evidence_event: Event,
        cause_event: Event,
        effect_event: Event
    ) -> Dict[str, Any]:
        """Рассчитать комплексную оценку релевантности Evidence Event"""
        
        scores = {}
        total_weighted_score = 0.0
        
        # 1. Временная близость
        temporal_score = await self._calculate_temporal_proximity(
            evidence_event, cause_event, effect_event
        )
        scores['temporal_proximity'] = temporal_score
        total_weighted_score += temporal_score * self.evidence_weights["temporal_proximity"]
        
        # 2. Семантическая релевантность
        semantic_score = await self._calculate_semantic_relevance(
            evidence_event, cause_event, effect_event
        )
        scores['semantic_relevance'] = semantic_score
        total_weighted_score += semantic_score * self.evidence_weights["semantic_relevance"]
        
        # 3. Пересечение сущностей
        entity_score = await self._calculate_entity_overlap(
            evidence_event, cause_event, effect_event
        )
        scores['entity_overlap'] = entity_score
        total_weighted_score += entity_score * self.evidence_weights["entity_overlap"]
        
        # 4. Доверие к источнику
        source_score = await self._calculate_source_trust(
            evidence_event
        )
        scores['source_trust'] = source_score
        total_weighted_score += source_score * self.evidence_weights["source_trust"]
        
        # 5. Важность события
        importance_score = await self._calculate_importance_score(
            evidence_event
        )
        scores['importance_score'] = importance_score
        total_weighted_score += importance_score * self.evidence_weights["importance_score"]
        
        # Получаем дополнительный контекст из Neo4j графа
        graph_context = await self._analyze_graph_context(
            evidence_event, cause_event, effect_event
        )
        
        return {
            'evidence_event': {
                'id': str(evidence_event.id),
                'type': evidence_event.event_type,
                'title': evidence_event.title,
                'timestamp': evidence_event.ts.isoformat()
            },
            'evidence_scores': scores,
            'total_weighted_score': total_weighted_score,
            'graph_context': graph_context,
            'evidence_type': self._classify_evidence_type(
                evidence_event, cause_event, effect_event
            ),
            'confidence': 'high' if total_weighted_score > 0.8 else 'medium' if total_weighted_score > 0.5 else 'low'
        }
    
    async def _calculate_temporal_proximity(
        self,
        evidence_event: Event,
        cause_event: Event,
        effect_event: Event
    ) -> float:
        """Рассчитать оценку временной близости"""
        
        # Проверяем, находится ли событие между причиной и следствием
        if not (cause_event.ts < evidence_event.ts < effect_event.ts):
            return 0.0
        
        # Чем ближе к центру временного промежутка, тем выше оценка
        time_interval = (effect_event.ts - cause_event.ts).total_seconds()
        if time_interval <= 0:
            return 0.0
        
        # Позиция события в интервале
        position_from_start = (evidence_event.ts - cause_event.ts).total_seconds()
        relative_position = position_from_start / time_interval
        
        # Гауссова функция для оценки: лучше события ближе к центру
        sigma = 4.0  # Ширина кривой
        temporal_score = math.exp(-((relative_position - 0.5) ** 2) / (2 * sigma ** 2))
        
        return min(1.0, temporal_score * 1.5)  # Нормализация
    
    async def _calculate_semantic_relevance(
        self,
        evidence_event: Event,
        cause_event: Event,
        effect_event: Event
    ) -> float:
        """Рассчитать семантическую релевантность"""
        
        # Словарь семантических связей между типами событий
        semantic_connections = self._get_semantic_connections()
        
        # Проверяем прямые связи
        evidence_type = evidence_event.event_type.lower()
        cause_type = cause_event.event_type.lower()
        effect_type = effect_event.event_type.lower()
        
        score = 0.0
        
        # Прямая связь с причиной
        if evidence_type in semantic_connections.get(cause_type, []):
            score += 0.6
        
        # Прямая связь со следствием
        if evidence_type in semantic_connections.get(effect_type, []):
            score += 0.6
        
        # Транзитивная связь: evidence -> cause или effect -> evidence
        if (evidence_type in semantic_connections.get(cause_type, []) or
            effect_type in semantic_connections.get(evidence_type, [])):
            score += 0.4
        
        # Анализ ключевых слов в названии и атрибутах
        word_relevance = self._analyze_keyword_relevance(
            evidence_event, cause_event, effect_event
        )
        score += word_relevance * 0.3
        
        return min(1.0, score)
    
    def _get_semantic_connections(self) -> Dict[str, List[str]]:
        """Получить словарь семантических связей между типами событий"""
        return {
            'sanctions': ['trade_restrictions', 'banking_limitations', 'market_drop', 'currency_decline'],
            'rate_hike': ['banking_positive', 'bond_yield_up', 'currency_strength', 'market_reaction'],
            'earnings': ['guidance_update', 'dividend_change', 'stock_movement', 'analyst_update'],
            'merger': ['regulatory_approval', 'shareholder_vote', 'staff_changes', 'financial_details'],
            'market_drop': ['volatility_spike', 'liquidity_issues', 'panic_selling', 'circuit_breakers'],
            'volatility_spike': ['panic_selling', 'liquidity_issues', 'margin_calls'],
            'trade_restrictions': ['supply_disruption', 'price_changes', 'company_challenges'],
            'banking_limitations': ['credit_crunch', 'liquidity_issues', 'financial_stress']
        }
    
    def _analyze_keyword_relevance(
        self,
        evidence_event: Event,
        cause_event: Event,
        effect_event: Event
    ) -> float:
        """Анализ релевантности по ключевым словам"""
        
        # Извлекаем ключевые слова из событий
        evidence_words = set(self._extract_keywords_from_event(evidence_event))
        cause_words = set(self._extract_keywords_from_event(cause_event))
        effect_words = set(self._extract_keywords_from_event(effect_event))
        
        score = 0.0
        
        # Пересечение с причиной
        cause_overlap = len(evidence_words & cause_words)
        if cause_words:
            score += (cause_overlap / len(cause_words)) * 0.5
        
        # Пересечение со следствием
        effect_overlap = len(evidence_words & effect_words)
        if effect_words:
            score += (effect_overlap / len(effect_words)) * 0.5
        
        return min(1.0, score)
    
    def _extract_keywords_from_event(self, event: Event) -> List[str]:
        """Извлечь ключевые слова из события"""
        
        # Извлекаем ключевые слова из названия
        title_words = self._extract_words_from_text(event.title)
        
        # Добавляем типы компаний/фирм из атрибутов
        attr_words = []
        if event.attrs:
            companies = event.attrs.get('companies', [])
            if isinstance(event.attrs.get('companies', []), list):
                attr_words.extend([c.lower() for c in companies])
        
        return title_words + attr_words
    
    def _extract_words_from_text(self, text: str) -> List[str]:
        """Извлечь слова из текста (простая реализация)"""
        
        if not text:
            return []
        
        # Удаляем знаки препинания и приводится к нижнему регистру
        import re
        words = re.findall(r'\b[А-Яа-я]+\b', text.lower())
        
        # Фильтруем короткие слова
        return [w for w in words if len(w) > 3]
    
    async def _calculate_entity_overlap(
        self,
        evidence_event: Event,
        cause_event: Event,
        effect_event: Event
    ) -> float:
        """Рассчитать пересечение сущностей между событиями"""
        
        # Получаем сущности для каждого события
        evidence_entities = await self._get_event_entities(evidence_event)
        cause_entities = await self._get_event_entities(cause_event)
        effect_entities = await self._get_event_entities(effect_event)
        
        if not evidence_entities:
            return 0.0
        
        # Рассчитываем пересечения
        cause_overlap = len(set(evidence_entities) & set(cause_entities))
        effect_overlap = len(set(evidence_entities) & set(effect_entities))
        
        # Нормализуем по общему количеству сущностей
        max_entities = max(len(cause_entities), len(effect_entities))
        if max_entities == 0:
            return 0.0
        
        entity_score = (cause_overlap + effect_overlap) / max_entities
        return min(1.0, entity_score)
    
    async def _get_event_entities(self, event: Event) -> List[str]:
        """Получить список сущностей для события"""
        
        result = await self.session.execute(
            select(Entity)
            .where(Entity.news_id == event.news_id)
        )
        
        entities = result.scalars().all()
        return [e.text.lower() for e in entities]
    
    async def _calculate_source_trust(self, evidence_event: Event) -> float:
        """Рассчитать доверие к источнику события"""
        
        # Получаем информацию о источнике
        result = await self.session.execute(
            select(News.source_id, News.title)
            .where(News.id == evidence_event.news_id)
        )
        
        news_info = result.fetchone()
        if not news_info:
            return 0.5  # Среднее доверие по умолчанию
        
        # Простая логика определения доверия
        title = news_info.title.lower()
        
        trust_score = 0.5  # Базовое доверие
        
        # Повышаем доверие для известных источников
        trusted_keywords = ['медиазона', 'блоггер', 'коммерсантъ', 'meduza', 'tass', 'рбк']
        if any(keyword in title for keyword in trusted_keywords):
            trust_score = 0.8
        
        # Понижаем доверие для сомнительных источников
        suspicious_keywords = ['инсайдер', 'утечка', 'неофициально', 'слухи']
        if any(keyword in title for keyword in suspicious_keywords):
            trust_score = 0.3
        
        return trust_score
    
    async def _calculate_importance_score(self, evidence_event: Event) -> float:
        """Получить оценку важности события"""
        
        # Получаем последний расчет важности
        importance_obj = await self.session.execute(
            select(EventImportance)
            .where(EventImportance.event_id == evidence_event.id)
            .order_by(EventImportance.created_at.desc())
            .limit(1)
        )
        
        importance_obj = importance_obj.scalar_one_or_none()
        
        if importance_obj:
            return importance_obj.importance_score
        else:
            # Если не рассчитана важность, используем базовую оценку
            return 0.6
    
    async def _analyze_graph_context(
        self,
        evidence_event: Event,
        cause_event: Event,
        effect_event: Event
    ) -> Dict[str, Any]:
        """Анализировать контекст в графе Neo4j"""
        
        try:
            # Получаем связи из графа
            evidence_context = await self.graph.get_event_context(str(evidence_event.id))
            cause_context = await self.graph.get_event_context(str(cause_event.id))
            effect_context = await self.graph.get_event_context(str(effect_event.id))
            
            return {
                'evidence_connections': {
                    'inbound_causes': len(evidence_context.get('causes', [])) if evidence_context else 0,
                    'outbound_causes': len(evidence_context.get('impacts', [])) if evidence_context else 0
                },
                'graph_position': 'connector' if (
                    evidence_context and 
                    evidence_context.get('causes') and 
                    evidence_context.get('impacts')
                ) else 'leaf',
                'cluster_info': {
                    'evidence_cluster': len(evidence_context.get('cluster', {}).get('events', [])) if evidence_context else 0,
                    'shared_neighbors': 0  # TODO: Реализовать поиск общих соседей
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing graph context: {e}")
            return {'error': str(e)}
    
    def _classify_evidence_type(
        self,
        evidence_event: Event,
        cause_event: Event,
        effect_event: Event
    ) -> str:
        """Классифицировать тип Evidence Event"""
        
        # Определяем позицию события во временной последовательности
        if cause_event.ts < evidence_event.ts < effect_event.ts:
            if 'market' in evidence_event.event_type.lower() or 'volatility' in evidence_event.event_type.lower():
                return 'market_mediator'
            elif 'regulatory' in evidence_event.event_type.lower():
                return 'regulatory_factor'
            else:
                return 'causal_mediator'
        else:
            return 'additional_context'
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистики алгоритма Evidence Events"""
        return {
            'evidence_engine_stats': self.stats,
            'algorithm_weights': self.evidence_weights,
            'status': 'operational'
        }
