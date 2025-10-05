#!/usr/bin/env python3
"""
Enhanced CEG Demo Script - демонстрация новых возможностей CEG системы
Показывает работу Importance Score и Watchers (L0/L1/L2)
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Добавляем пути
sys.path.insert(0, str(Path(__file__).parent))

from Parser.src.core.database import init_db, close_db, get_db_session
from Parser.src.core.models import News, Event
from Parser.src.services.events.ceg_realtime_service import CEGRealtimeService
from Parser.src.services.events.importance_calculator import ImportanceScoreCalculator
from Parser.src.services.events.watchers import WatchersSystem
from Parser.src.graph_models import GraphService
from Parser.src.core.config import settings
from Parser.src.utils.logging import setup_logging

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)


class EnhancedCEGDemo:
    """
    Демонстрационный класс для Enhanced CEG с Importance Score и Watchers
    """
    
    def __init__(self):
        self.ceg_service = None
        self.graph_service = None
        self.session = None
    
    async def initialize(self):
        """Инициализация компонентов системы"""
        logger.info("🚀 Initializing Enhanced CEG Demo...")
        
        # Инициализация БД
        await init_db()
        
        # Получаем сессию БД
        async with get_db_session() as session:
            self.session = session
            
            # Инициализируем Neo4j
            self.graph_service = GraphService()
            await self.graph_service.verify_connection()
            
            # Создаем CEG сервис с включенными watcher'ами
            self.ceg_service = CEGRealtimeService(
                session=session,
                graph_service=self.graph_service,
                lookback_window=30,
                enable_watchers=True  # Включаем watcher'ы!
            )
            
            logger.info("✅ Components initialized successfully")
    
    async def demo_importance_score_calculation(self):
        """Демонстрация расчета Importance Score"""
        logger.info("\n📊 Demonstrating Importance Score Calculation...")
        
        # Получаем случайные события из БД для демонстрации
        from sqlalchemy import select
        result = await self.session.execute(
            select(Event)
            .order_by(Event.created_at.desc())
            .limit(5)
        )
        events = result.scalars().all()
        
        if not events:
            logger.warning("No events found in database for demo")
            return
        
        # Создаем калькулятор важности
        importance_calc = ImportanceScoreCalculator(self.session, self.graph_service)
        
        importance_results = []
        
        for event in events:
            logger.info(f"📈 Calculating importance for event: {event.event_type}")
            
            # Рассчитываем важность
            importance_data = await importance_calc.calculate_importance_score(event)
            
            importance_results.append({
                'event': {
                    'id': str(event.id),
                    'type': event.event_type,
                    'title': event.title,
                    'timestamp': event.ts.isoformat(),
                    'is_anchor': event.is_anchor
                },
                'importance': importance_data
            })
            
            # Красивый вывод
            score = importance_data['importance_score']
            novelty = importance_data['novelty']
            burst = importance_data['burst']
            credibility = importance_data['credibility']
            breadth = importance_data['breadth']
            price_impact = importance_data['price_impact']
            
            print(f"\n🎯 Event: {event.event_type}")
            print(f"   📍 Title: {event.title[:60]}...")
            print(f"   🏆 Total Importance: {score:.3f}")
            print(f"   🆕 Novelty: {novelty:.3f} | 💥 Burst: {burst:.3f}")
            print(f"   ✅ Credibility: {credibility:.3f} | 🌐 Breadth: {breadth:.3f}")
            print(f"   💰 Price Impact: {price_impact:.3f}")
        
        # Показываем топ событий по важности
        sorted_results = sorted(importance_results, key=lambda x: x['importance']['importance_score'], reverse=True)
        
        print(f"\n🏅 Top Events by Importance:")
        for i, result in enumerate(sorted_results[:3], 1):
            event_info = result['event']
            importance = result['importance']
            print(f"{i}. {event_info['type']}: {importance['importance_score']:.3f} (\"{event_info['title'][:40]}...\")")
        
        return importance_results
    
    async def demo_watchers_system(self):
        """Демонстрация системы Watchers (L0/L1/L2)"""
        logger.info("\n👁️ Demonstrating Watchers System...")
        
        if not self.ceg_service.watchers_system:
            logger.error("Watchers system not initialized")
            return
        
        # Получаем события для тестирования
        from sqlalchemy import select
        result = await self.session.execute(
            select(Event)
            .where(Event.event_type.in_(['sanctions', 'rate_hike', 'earnings']))
            .order_by(Event.created_at.desc())
            .limit(10)
        )
        events = result.scalars().all()
        
        if not events:
            logger.warning("No suitable events found for watchers demo")
            return
        
        print(f"\n📡 Testing {len(events)} events against L0/L1/L2 watchers...")
        
        watcher_results = []
        
        for event in events:
            logger.info(f"🔍 Checking event: {event.event_type}")
            
            # Проверяем событие watcher'ами
            watch_results = await self.ceg_service.watchers_system.check_event(event)
            
            watcher_results.append({
                'event': {
                    'id': str(event.id),
                    'type': event.event_type,
                    'title': event.title[:60] + "..."
                },
                'watchers': watch_results
            })
            
            total_triggers = watch_results['summary']['total_triggers']
            levels_triggered = watch_results['summary']['levels_triggered']
            
            if total_triggers > 0:
                print(f"\n🚨 Event TRIGGERED {total_triggers} watcher(s) on levels: {', '.join(levels_triggered)}")
                
                # Показываем детали срабатывания
                for level_result in watch_results['level_results'].values():
                    triggered_watches = level_result.get('triggered_watches', [])
                    if triggered_watches:
                        for watch in triggered_watches:
                            print(f"   📌 Rule: {watch['rule_name']}")
                            context = watch.get('context', {})
                            importance = context.get('importance_score', 0)
                            print(f"      Importance: {importance:.3f} | Priority: HIGH")
        
        # Статистика watcher'ов
        watcher_stats = self.ceg_service.watchers_system.get_statistics()
        
        print(f"\n📊 Watchers Statistics:")
        print(f"   Total events checked: {watcher_stats['system_statistics']['total_events_checked']}")
        print(f"   Active watches: {watcher_stats['total_active_watches']}")
        
        # Показываем статистику по уровням
        watcher_stats_by_level = watcher_stats['watcher_statistics']
        for level, stats in watcher_stats_by_level.items():
            triggers = stats['statistics'].get('triggers_found', 0)
            print(f"   {level} Level: {triggers} triggers")
        
        return watcher_results
    
    async def demo_integration_scenario(self):
        """Демонстрация интеграционного сценария"""
        logger.info("\n🔄 Demonstrating Integration Scenario...")
        
        # Создаем тестовую новость с AI extraction результатом
        mock_news = type('MockNews', (), {
            'id': 'demo-news-' + datetime.now().strftime('%Y%m%d%H%M%S'),
            'title': 'ЦБ РФ повысил ключевую ставку до 20%',
            'text_plain': 'Центральный банк России объявил о повышении ключевой ставки на 2 процентных пункта до 20% годовое. Это решение принято в связи с ухудшением макроэкономической ситуации.',
            'published_at': datetime.utcnow(),
            'is_ad': False
        })()
        
        mock_ai_extracted = {
            'entities': [
                {'text': 'ЦБ РФ', 'type': 'ORG', 'norm': 'Central Bank of Russia'},
                {'text': '20%', 'type': 'PCT', 'norm': {'value': 20.0, 'currency': 'yearly'}},
                {'text': 'ключевая ставка', 'type': 'FIN_TERM', 'norm': 'key_rate'}
            ],
            'companies': ['ЦБ РФ'],
            'metrics': [{'type': 'rate_change', 'value': 2.0, 'period': 'percentage_points'}]
        }
        
        print(f"📰 Processing mock news: \"{mock_news.title}\"")
        
        # Процессим новость через расширенный CEG
        ceg_result = await self.ceg_service.process_news(mock_news, mock_ai_extracted)
        
        events_created = len(ceg_result.get('events', []))
        causal_links = len(ceg_result.get('causal_links', []))
        impacts_calculated = len(ceg_result.get('impacts', []))
        retroactive_links = ceg_result.get('retroactive_links', 0)
        
        print(f"\n⚡ CEG Processing Results:")
        print(f"   📊 Events created: {events_created}")
        print(f"   🕸️ Causal links: {causal_links}")
        print(f"   💰 Market impacts: {impacts_calculated}")
        print(f"   🔄 Retroactive links: {retroactive_links}")
        
        # Статистика с важностью и watcher'ами
        final_stats = self.ceg_service.get_stats()
        print(f"\n📈 Enhanced Stats:")
        print(f"   📊 Importance calculated: {final_stats.get('importance_calculated', 0)}")
        print(f"   👁️ Watchers triggered: {final_stats.get('watchers_triggered', 0)}")
        print(f"   📊 Total events: {final_stats.get('events_created', 0)}")
        print(f"   📰 News processed: {final_stats.get('news_processed', 0)}")
        
        return ceg_result
    
    async def demo_api_endpoints(self):
        """Демонстрация новых API endpoints"""
        logger.info("\n🌐 Summarizing new API endpoints...")
        
        print(f"\n🚀 New Enhanced CEG API Endpoints:")
        
        print(f"\n📊 Importance Score Endpoints:")
        print(f"   GET /importance/events/{{event_id}} - Get event importance")
        print(f"   GET /importance/events?min_importance=0.7 - List events by importance")
        print(f"   GET /importance/summary?period_hours=24 - Importance statistics")
        print(f"   GET /importance/analytics/trends - Importance trends over time")
        print(f"   GET /importance/analytics/distribution - Importance distribution")
        
        print(f"\n👁️ Watchers System Endpoints:")
        print(f"   GET /watchers/active?watch_level=L0 - Active watchers")
        print(f"   GET /watchers/predictions?status=pending - Event predictions")
        print(f"   GET /watchers/statistics?period_hours=24 - Watchers stats")
        print(f"   GET /watchers/rules - Available watch rules")
        print(f"   GET /watchers/alerts/recent?priority=high - Recent alerts")
        print(f"   POST /watchers/cleanup-expired - Cleanup expired watchers")
        
        print(f"\n🔌 Existing CEG Endpoints (Enhanced):")
        print(f"   GET /ceg/events - Events with importance scores")
        print(f"   GET /ceg/stats - Statistics including watchers")
        print(f"   GET /ceg/anchor-events - Anchor events with importance")
        print(f"   GET /ceg/events/{{id}}/causal-context - Enhanced causal context")
    
    async def run_demo(self):
        """Запуск полной демонстрации"""
        logger.info("🎭 Starting Enhanced CEG Demo...")
        
        try:
            await self.initialize()
            
            # Детальная демонстрация Importance Score
            importance_results = await self.demo_importance_score_calculation()
            
            # Демонстрация Watchers
            watcher_results = await self.demo_watchers_system()
            
            # Интеграционный сценарий
            integration_result = await self.demo_integration_scenario()
            
            # Обзор API endpoints
            await self.demo_api_endpoints()
            
            print(f"\n🎉 Enhanced CEG Demo completed successfully!")
            print(f"\n📝 Demo Summary:")
            print(f"   ✅ Importance Score calculations: {len(importance_results)} events")
            print(f"   ✅ Watchers system tests: {len(watcher_results)} events")
            print(f"   ✅ Integration scenario: {"PASSED" if integration_result else "FAILED"}")
            print(f"   ✅ API endpoints: 12 new endpoints available")
            
            logger.info("Demo completed successfully")
            
        except Exception as e:
            logger.error(f"Demo failed with error: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Очистка ресурсов"""
        if self.graph_service:
            await self.graph_service.close()
        
        await close_db()
        logger.info("Cleanup completed")


async def main():
    """Главная функция демо"""
    demo = EnhancedCEGDemo()
    await demo.run_demo()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        sys.exit(1)
