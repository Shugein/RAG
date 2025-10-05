import logging
import math
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from Parser.src.core.models import Event, EventImportance
from Parser.src.graph_models import GraphService

logger = logging.getLogger(__name__)


class ChainDirection(Enum):
    """Направление поиска причинных цепочек"""
    FORWARD = "forward"  # От причины к следствию
    BACKWARD = "backward"  # От следствия к причине
    BIDIRECTIONAL = "bidirectional"  # В обе стороны


@dataclass
class CausalNode:
    """Узел в причинной цепочке"""
    event_id: str
    event_type: str
    title: str
    timestamp: datetime
    depth: int
    sources: List[str]  # Источники связей
    confidence: float
    path_from_root: List[str]  # Путь от корня
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type,
            'title': self.title,
            'timestamp': self.timestamp.isoformat(),
            'depth': self.depth,
            'sources': self.sources,
            'confidence': self.confidence,
            'path_from_root': self.path_from_root
        }


@dataclass
class CausalChainLink:
    """Связь между событиями в цепочке"""
    from_event_id: str
    to_event_id: str
    relationship_type: str  # "causes", "impacts", "evidence"
    confidence: float
    time_lag_seconds: int
    link_context: Dict[str, Any]


class CausalChainsEngine:
    """
    Движок для построения многоуровневых причинных цепочек
    Использует BFS для поиска связей до максимальной глубины
    """
    
    def __init__(self, session: AsyncSession, graph_service: GraphService):
        self.session = session
        self.graph = graph_service
        
        # Конфигурация алгоритма
        self.default_max_depth = 3
        self.min_confidence_threshold = 0.3
        self.temporal_constraints = {
            'max_time_window_hours': 168,  # 7 дней
            'min_time_delay_minutes': 5,   # Минимальная задержка между событиями
            'max_time_delay_hours': 72     # Максимальная задержка между событиями
        }
        
        # Статистики
        self.stats = {
            'chains_discovered': 0,
            'total_nodes_found': 0,
            'average_chain_length': 0.0,
            'max_depth_reached': 0,
            'high_confidence_links': 0
        }
        
        # Кеш для оптимизации
        self._event_cache: Dict[str, Event] = {}
        self._importance_cache: Dict[str, float] = {}
    
    async def discover_causal_chains(
        self,
        root_event_id: str,
        direction: ChainDirection = ChainDirection.BIDIRECTIONAL,
        max_depth: Optional[int] = None,
        min_confidence: Optional[float] = None,
        time_window_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Обнаружить причинные цепочки для корневого события
        
        Args:
            root_event_id: ID корневого события
            direction: Направление поиска цепочек
            max_depth: Максимальная глубина поиска
            min_confidence: Минимальная уверенность в связях
            time_window_hours: Временное окно для поиска событий
            
        Returns:
            Словарь с найденными цепочками и метаданными
        """
        max_depth = max_depth or self.default_max_depth
        min_confidence = min_confidence or self.min_confidence_threshold
        time_window_hours = time_window_hours or self.temporal_constraints['max_time_window_hours']
        
        logger.info(f"Discovering causal chains from {root_event_id} "
                   f"(direction: {direction.value}, max_depth: {max_depth})")
        
        # Получаем корневое событие
        root_event = await self._get_event_by_id(root_event_id)
        if not root_event:
            return {"error": f"Root event {root_event_id} not found"}
        
        discovered_chains = []
        
        if direction in [ChainDirection.FORWARD, ChainDirection.BIDIRECTIONAL]:
            # Поиск цепочек от причины к следствиям
            forward_chains = await self._discover_chains_direction(
                root_event, 'forward', max_depth, min_confidence, time_window_hours
            )
            discovered_chains.extend(forward_chains)
        
        if direction in [ChainDirection.BACKWARD, ChainDirection.BIDIRECTIONAL]:
            # Поиск цепочек от следствия к причинам
            backward_chains = await self._discover_chains_direction(
                root_event, 'backward', max_depth, min_confidence, time_window_hours
            )
            discovered_chains.extend(backward_chains)
        
        # Анализируем и ранжируем цепочки
        analysis_result = self._analyze_discovered_chains(discovered_chains, root_event)
        
        self.stats['chains_discovered'] += len(discovered_chains)
        self.stats['total_nodes_found'] += sum(len(chain['nodes']) for chain in discovered_chains)
        
        logger.info(f"Discovered {len(discovered_chains)} causal chains "
                   f"with {analysis_result['total_unique_nodes']} unique nodes")
        
        return {
            'root_event': {
                'id': str(root_event.id),
                'type': root_event.event_type,
                'title': root_event.title,
                'timestamp': root_event.ts.isoformat()
            },
            'discovery_params': {
                'direction': direction.value,
                'max_depth': max_depth,
                'min_confidence': min_confidence,
                'time_window_hours': time_window_hours
            },
            'chains': discovered_chains,
            'analysis': analysis_result,
            'statistics': self._calculate_statistics(discovered_chains),
            'discovery_timestamp': datetime.utcnow().isoformat()
        }
    
    async def _discover_chains_direction(
        self,
        root_event: Event,
        direction: str,
        max_depth: int,
        min_confidence: float,
        time_window_hours: int
    ) -> List[Dict[str, Any]]:
        """Обнаружить цепочки в одном направлении"""
        
        discovered_chains = []
        
        # BFS очередь: (node, current_depth, path)
        queue = deque([(str(root_event.id), 0, [str(root_event.id)])])
        visited_nodes = set()
        
        # Ограничения по времени
        time_window_start = root_event.ts - timedelta(hours=time_window_hours/2)
        time_window_end = root_event.ts + timedelta(hours=time_window_hours/2)
        
        while queue and len(discovered_chains) < 100:  # Лимит цепочек
            current_node_id, current_depth, current_path = queue.popleft()
            
            if current_depth >= max_depth:
                continue
            
            if current_node_id in visited_nodes:
                continue
            
            visited_nodes.add(current_node_id)
            
            # Получаем событие
            current_event = await self._get_event_by_id(current_node_id)
            if not current_event:
                continue
            
            # Ищем связанные события
            linked_events = await self._find_connected_events(
                current_event, direction, time_window_start, time_window_end
            )
            
            for linked_event in linked_events:
                linked_id = str(linked_event['event_id'])
                
                # Проверяем ограничения
                if not self._satisfies_temporal_constraints(current_event, linked_event):
                    continue
                
                if linked_event.get('confidence', 0) < min_confidence:
                    continue
                
                # Новая цепочка
                new_path = current_path + [linked_id]
                new_depth = current_depth + 1
                
                # Создаем узел цепочки
                chain_node = CausalNode(
                    event_id=linked_id,
                    event_type=linked_event['event_type'],
                    title=linked_event['title'],
                    timestamp=linked_event['timestamp'],
                    depth=new_depth,
                    sources=[linked_event.get('source', 'unknown')],
                    confidence=linked_event.get('confidence', 0),
                    path_from_root=new_path.copy()
                )
                
                # Создаем связь
                chain_link = CausalChainLink(
                    from_event_id=current_node_id,
                    to_event_id=linked_id,
                    relationship_type=linked_event.get('relationship_type', 'unknown'),
                    confidence=linked_event.get('confidence', 0),
                    time_lag_seconds=int((linked_event['timestamp'] - current_event.ts).total_seconds()),
                    link_context={
                        'evidence_count': linked_event.get('evidence_count', 0),
                        'connection_strength': linked_event.get('connection_strength', 0)
                    }
                )
                
                # Проверяем, не создает ли это зацикливание
                if linked_id not in current_path:
                    discovered_chains.append({
                        'chain_id': f"{root_event.id}_{len(discovered_chains)}",
                        'direction': direction,
                        'nodes': [chain_node],
                        'links': [chain_link],
                        'total_depth': new_depth,
                        'average_confidence': chain_node.confidence,
                        'path': new_path
                    })
                    
                    # Добавляем продолжение цепочки в очередь
                    if new_depth < max_depth:
                        queue.append((linked_id, new_depth, new_path.copy()))
        
        return discovered_chains
    
    async def _find_connected_events(
        self,
        base_event: Event,
        direction: str,
        time_window_start: datetime,
        time_window_end: datetime
    ) -> List[Dict[str, Any]]:
        """Найти события, связанные с базовым событием"""
        
        connected_events = []
        
        try:
            # Получаем связи из Neo4j графа
            graph_context = await self.graph.get_event_context(str(base_event.id))
            
            if not graph_context:
                return connected_events
            
            # В зависимости от направления ищем причины или следствия
            connections = []
            if direction == 'forward':
                connections = graph_context.get('impacts', [])
                relationship_type = 'impacts'
            elif direction == 'backward':
                connections = graph_context.get('causes', [])
                relationship_type = 'causes'
            else:
                connections = (
                    graph_context.get('causes', []) + 
                    graph_context.get('impacts', [])
                )
                relationship_type = 'mixed'
            
            for connection_data in connections:
                event_id = connection_data.get('event_id')
                if not event_id:
                    continue
                
                # Получаем полную информацию о событии
                event_result = await self.session.execute(
                    select(Event)
                    .where(Event.id == event_id)
                    .and_(Event.ts >= time_window_start)
                    .and_(Event.ts <= time_window_end)
                )
                
                linked_event = event_result.scalar_one_or_none()
                if not linked_event:
                    continue
                
                # Рассчитываем уверенность в связи
                confidence = await self._calculate_link_confidence(
                    base_event, linked_event, connection_data
                )
                
                connected_events.append({
                    'event_id': str(linked_event.id),
                    'event_type': linked_event.event_type,
                    'title': linked_event.title,
                    'timestamp': linked_event.ts,
                    'relationship_type': relationship_type,
                    'confidence': confidence,
                    'evidence_count': len(connection_data.get('evidence_events', [])),
                    'connection_strength': connection_data.get('strength', 0),
                    'source': 'neo4j_graph'
                })
        
        except Exception as e:
            logger.error(f"Error finding connected events: {e}")
        
        return connected_events
    
    async def _calculate_link_confidence(
        self,
        event1: Event,
        event2: Event,
        connection_data: Dict[str, Any]
    ) -> float:
        """Рассчитать уверенность в связи между событиями"""
        
        base_confidence = connection_data.get('confidence', 0.5)
        
        # Корректировки на основе временной близости
        time_diff = abs((event2.ts - event1.ts).total_seconds())
        time_factor = self._calculate_time_factor(time_diff)
        
        # Корректировки на основе важности событий
        importance_factor = await self._calculate_importance_factor(event1, event2)
        
        # Корректировки на основе количества Evidence Events
        evidence_factor = min(1.0, connection_data.get('evidence_count', 0) / 3.0)
        
        # Итоговая уверенность
        final_confidence = (
            base_confidence * 0.4 +
            time_factor * 0.25 +
            importance_factor * 0.2 +
            evidence_factor * 0.15
        )
        
        return max(0.0, min(1.0, final_confidence))
    
    def _calculate_time_factor(self, time_diff_seconds: int) -> float:
        """Рассчитать фактор на основе временной близости"""
        
        # Оптимальное время связи - от 30 минут до 4 часов
        min_delay = self.temporal_constraints['min_time_delay_minutes'] * 60
        max_delay = self.temporal_constraints['max_time_delay_hours'] * 3600
        optimal_delay = 2 * 3600  # 2 часа
        
        if min_delay <= time_diff_seconds <= max_delay:
            # Нормальное распределение вокруг оптимального времени
            sigma = max_delay / 2
            factor = math.exp(-((time_diff_seconds - optimal_delay) ** 2) / (2 * sigma ** 2))
            return max(0.3, factor)
        else:
            return 0.3  # Минимальный фактор для событий вне оптимального окна
    
    async def _calculate_importance_factor(self, event1: Event, event2: Event) -> float:
        """Рассчитать фактор на основе важности событий"""
        
        # Получаем важность событий
        importance1 = await self._get_event_importance(event1.id)
        importance2 = await self._get_event_importance(event2.id)
        
        # Чем выше важность обоих событий, тем больше фактор
        importance_product = importance1 * importance2
        
        return min(1.0, importance_product * 2)  # Масштабирование
    
    async def _get_event_importance(self, event_id: str) -> float:
        """Получить важность события из кеша или БД"""
        
        if event_id in self._importance_cache:
            return self._importance_cache[event_id]
        
        result = await self.session.execute(
            select(EventImportance.importance_score)
            .where(EventImportance.event_id == event_id)
            .order_by(EventImportance.created_at.desc())
            .limit(1)
        )
        
        importance_score = result.scalar_one_or_none() or 0.5
        self._importance_cache[event_id] = importance_score
        
        return importance_score
    
    async def _get_event_by_id(self, event_id: str) -> Optional[Event]:
        """Получить событие из кеша или БД"""
        
        if event_id in self._event_cache:
            return self._event_cache[event_id]
        
        result = await self.session.execute(
            select(Event).where(Event.id == event_id)
        )
        
        event = result.scalar_one_or_none()
        if event:
            self._event_cache[event_id] = event
        
        return event
    
    def _satisfies_temporal_constraints(
        self,
        event1: Event,
        event2: Dict[str, Any]
    ) -> bool:
        """Проверить соответствие временным ограничениям"""
        
        time_diff = abs((event2['timestamp'] - event1.ts).total_seconds())
        
        min_delay = self.temporal_constraints['min_time_delay_minutes'] * 60
        max_delay = self.temporal_constraints['max_time_delay_hours'] * 3600
        
        return min_delay <= time_diff <= max_delay
    
    def _analyze_discovered_chains(
        self,
        chains: List[Dict[str, Any]],
        root_event: Event
    ) -> Dict[str, Any]:
        """Анализ обнаруженных цепочек"""
        
        if not chains:
            return {'total_unique_nodes': 0, 'average_depth': 0, 'strongest_chain': None}
        
        # Собираем уникальные узлы
        unique_nodes = set()
        node_depths = []
        chain_confidences = []
        
        for chain in chains:
            unique_nodes.update(node['event_id'] for node in chain['nodes'])
            node_depths.extend(node['depth'] for node in chain['nodes'])
            chain_confidences.append(chain.get('average_confidence', 0))
        
        # Находим самую сильную цепочку
        strongest_chain = max(chains, key=lambda c: c.get('average_confidence', 0)) if chains else None
        
        return {
            'total_unique_nodes': len(unique_nodes),
            'total_chains': len(chains),
            'average_depth': sum(node_depths) / len(node_depths) if node_depths else 0,
            'average_confidence': sum(chain_confidences) / len(chain_confidences) if chain_confidences else 0,
            'strongest_chain': strongest_chain['chain_id'] if strongest_chain else None,
            'depth_distribution': self._calculate_depth_distribution(chains),
            'confidence_bands': self._calculate_confidence_bands(chain_confidences)
        }
    
    def _calculate_depth_distribution(self, chains: List[Dict[str, Any]]) -> Dict[int, int]:
        """Рассчитать распределение по глубинам"""
        depth_dist = defaultdict(int)
        
        for chain in chains:
            depth_dist[chain['total_depth']] += 1
        
        return dict(depth_dist)
    
    def _calculate_confidence_bands(self, confidences: List[float]) -> Dict[str, int]:
        """Рассчитать распределение по диапазонам уверенности"""
        bands = {'high': 0, 'medium': 0, 'low': 0}
        
        for conf in confidences:
            if conf >= 0.7:
                bands['high'] += 1
            elif conf >= 0.4:
                bands['medium'] += 1
            else:
                bands['low'] += 1
        
        return bands
    
    def _calculate_statistics(self, chains: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Рассчитать статистики для обнаруженных цепочек"""
        
        if not chains:
            return {'total_chains': 0, 'total_nodes': 0, 'average_length': 0}
        
        total_nodes = sum(len(chain['nodes']) for chain in chains)
        average_length = total_nodes / len(chains)
        
        return {
            'total_chains': len(chains),
            'total_nodes': total_nodes,
            'average_length': average_length,
            'longest_chain': max((len(chain['nodes']) for chain in chains), default=0),
            'shortest_chain': min((len(chain['nodes']) for chain in chains), default=0)
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистики движка причинных цепочек"""
        
        avg_length = 0
        if self.stats['chains_discovered'] > 0:
            avg_length = self.stats['total_nodes_found'] / self.stats['chains_discovered']
        
        return {
            'causal_chains_stats': {
                **self.stats,
                'average_chain_length': avg_length
            },
            'algorithm_config': {
                'default_max_depth': self.default_max_depth,
                'min_confidence_threshold': self.min_confidence_threshold,
                'temporal_constraints': self.temporal_constraints
            },
            'cache_info': {
                'cached_events': len(self._event_cache),
                'cached_importances': len(self._importance_cache)
            },
            'status': 'operational'
        }
