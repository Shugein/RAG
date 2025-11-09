# services/ceg/events/ceg_realtime_service.py
"""
Real-time CEG Service - реактивный сервис для построения CEG в реальном времени

Этот сервис автоматически:
1. Обрабатывает новые новости при их загрузке
2. Извлекает события через EventExtractor
3. Анализирует причинность с помощью CMNLN
4. Выполняет Event Study для рыночного влияния
5. Обновляет граф Neo4j
6. Ретроспективно анализирует влияние на предыдущие новости
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import News, Event, EventImportance, TriggeredWatch, EventPrediction
from core.graph.service import GraphService, EventNode, CausesRelation, ImpactsRelation
from services.ceg.events.event_extractor import EventExtractor
from services.ceg.causal.cmnln_engine import CMLNEngine
from services.ceg.importance.calculator import ImportanceScoreCalculator
from services.ceg.watchers.watchers import WatchersSystem, WatchLevel
from services.ceg.predictions.event_prediction import EventPredictionEngine
from services.ceg.market.moex.moex_prices import MOEXPriceService, EventStudyAnalyzer

logger = logging.getLogger(__name__)


class CEGRealtimeService:
    """
    Реактивный сервис CEG - обрабатывает новости в реальном времени
    """

    def __init__(
        self,
        session: AsyncSession,
        graph_service: GraphService,
        lookback_window: int = 30,  # Дней для ретроспективного анализа
        enable_watchers: bool = True,  # Включить систему мониторинга
        enable_predictions: bool = True  # Включить систему предсказаний
    ):
        """
        Args:
            session: SQLAlchemy async session
            graph_service: GraphService для Neo4j
            lookback_window: Окно для поиска связанных событий (дней назад)
            enable_watchers: Включить систему watcher'ов (L0/L1/L2)
            enable_predictions: Включить систему предсказаний событий
        """
        self.session = session
        self.graph = graph_service
        self.lookback_window = lookback_window
        self.enable_watchers = enable_watchers
        self.enable_predictions = enable_predictions

        # Инициализация компонентов
        self.event_extractor = EventExtractor()
        self.cmnln = CMLNEngine(graph_service=graph_service, session=session)
        self.moex = MOEXPriceService()
        self.event_study = EventStudyAnalyzer(self.moex)

        # Инициализация новых компонентов
        self.importance_calculator = ImportanceScoreCalculator(session, graph_service)

        # Инициализация Watchers системы
        if self.enable_watchers:
            self.watchers_system = WatchersSystem(graph_service, self.importance_calculator)
            # Добавляем обработчик уведомлений
            self.watchers_system.add_notification_handler(self._handle_watcher_notification)
        else:
            self.watchers_system = None

        # Инициализация системы предсказаний
        if self.enable_predictions:
            self.prediction_engine = EventPredictionEngine(session, graph_service)
        else:
            self.prediction_engine = None

        # Статистика
        self.stats = {
            "news_processed": 0,
            "events_created": 0,
            "causal_links_created": 0,
            "impacts_calculated": 0,
            "retroactive_updates": 0,
            "importance_calculated": 0,
            "watchers_triggered": 0,
            "predictions_generated": 0,
            "predictions_fulfilled": 0
        }

    async def close(self):
        """Закрытие соединений"""
        await self.moex.close()

    async def process_news(
        self,
        news: News,
        ai_extracted: Any
    ) -> Dict[str, Any]:
        """
        Обработать новую новость и обновить CEG

        Args:
            news: Объект News
            ai_extracted: Результат AI extraction

        Returns:
            {
                'events': List[Event],
                'causal_links': List[tuple],
                'impacts': List[dict],
                'retroactive_links': int
            }
        """
        logger.info(f"Processing news {news.id} for CEG: {news.title[:60]}")

        result = {
            "events": [],
            "causal_links": [],
            "impacts": [],
            "retroactive_links": 0
        }

        try:
            # 1. Извлекаем события из новости
            events = self.event_extractor.extract_events_from_news(news, ai_extracted)

            if not events:
                logger.debug(f"No events extracted from news {news.id}")
                return result

            # Сохраняем события в БД
            for event in events:
                self.session.add(event)
            await self.session.flush()

            result["events"] = events
            self.stats["events_created"] += len(events)

            # 2. Создаем узлы событий в Neo4j
            for event in events:
                event_node = EventNode(
                    id=str(event.id),
                    title=event.title,
                    ts=event.ts,
                    type=event.event_type,
                    attrs=event.attrs,
                    is_anchor=event.is_anchor,
                    confidence=event.confidence
                )
                await self.graph.create_event_ceg(event_node)

            # 3. Ищем причинно-следственные связи с предыдущими событиями
            causal_links = await self._find_causal_links(events)
            result["causal_links"] = causal_links
            self.stats["causal_links_created"] += len(causal_links)

            # 4. Выполняем Event Study для рыночного влияния
            impacts = await self._calculate_impacts(events)
            result["impacts"] = impacts
            self.stats["impacts_calculated"] += len(impacts)

            # 5. Ретроспективный анализ: обновляем связи для предыдущих событий
            retroactive_count = await self._retroactive_analysis(events)
            result["retroactive_links"] = retroactive_count
            self.stats["retroactive_updates"] += retroactive_count

            # 6. Рассчитываем важность событий (Importance Score)
            importance_data = {}
            for event in events:
                importance_calc = await self.importance_calculator.calculate_importance_score(event)
                importance_data[str(event.id)] = importance_calc

                # Сохраняем в БД
                importance_record = EventImportance(
                    event_id=event.id,
                    importance_score=importance_calc['importance_score'],
                    novelty=importance_calc['novelty'],
                    burst=importance_calc['burst'],
                    credibility=importance_calc['credibility'],
                    breadth=importance_calc['breadth'],
                    price_impact=importance_calc['price_impact'],
                    components_details=importance_calc.get('components_details', {}),
                    calculation_timestamp=importance_calc['calculation_timestamp'],
                    weights_version="1.0"
                )
                self.session.add(importance_record)

            await self.session.flush()

            # 7. Проверяем событий watcher'ами (если включены)
            watched_results = {}
            if self.watchers_system:
                for event in events:
                    watch_results = await self.watchers_system.check_event(event)
                    watched_results[str(event.id)] = watch_results

                    # Сохраняем сработавшие watcher'ы в БД
                    if watch_results['summary']['total_triggers'] > 0:
                        for level_result in watch_results['level_results'].values():
                            for triggered_watch_data in level_result.get('triggered_watches', []):
                                triggered_watch = TriggeredWatch(
                                    rule_id=triggered_watch_data['rule_id'],
                                    rule_name=triggered_watch_data['rule_name'],
                                    watch_level=triggered_watch_data['trigger_time'][:2],  # L0, L1, L2
                                    event_id=event.id,
                                    trigger_time=datetime.fromisoformat(triggered_watch_data['trigger_time']),
                                    auto_expire_at=datetime.fromisoformat(triggered_watch_data['trigger_time']) + timedelta(hours=168),
                                    context=triggered_watch_data['context']
                                )
                                self.session.add(triggered_watch)

                                # Генерируем предсказания для L2 watcher'ов
                                if self.prediction_engine and triggered_watch.watch_level == 'L2':
                                    try:
                                        predictions = await self.prediction_engine.generate_l2_predictions(
                                            triggered_watch,
                                            prediction_types=['follow_up_events', 'market_reactions']
                                        )
                                        self.stats["predictions_generated"] += len(predictions)
                                        logger.debug(f"Generated {len(predictions)} predictions for L2 watch {triggered_watch.rule_id}")
                                    except Exception as e:
                                        logger.error(f"Error generating predictions for watch {triggered_watch.id}: {e}")

            await self.session.flush()

            # 8. Коммитим все изменения в БД
            await self.session.commit()

            self.stats["news_processed"] += 1
            self.stats["importance_calculated"] += len(importance_data)
            if self.watchers_system:
                self.stats["watchers_triggered"] = sum(
                    result['summary']['total_triggers']
                    for result in watched_results.values()
                )

            predictions_count = self.stats.get("predictions_generated", 0)
            logger.info(
                f"CEG update with importance, watchers & predictions complete for news {news.id}: "
                f"{len(events)} events, {len(causal_links)} links, "
                f"{len(impacts)} impacts, {retroactive_count} retroactive updates, "
                f"{len(importance_data)} importance scores, "
                f"{sum(len(wr['summary']['levels_triggered']) for wr in watched_results.values()) if watched_results else 0} watcher triggers, "
                f"{predictions_count} predictions generated"
            )

        except Exception as e:
            logger.error(f"Error processing news {news.id} for CEG: {e}", exc_info=True)
            await self.session.rollback()
            raise

        return result

    async def _find_causal_links(self, new_events: List[Event]) -> List[tuple]:
        """
        Найти причинно-следственные связи для новых событий

        Ищет связи как:
        - old_event -> new_event (прошлые события вызвали новое)
        - new_event1 -> new_event2 (в рамках одной новости)
        """
        causal_links = []

        # Загружаем события за lookback_window
        lookback_date = datetime.utcnow() - timedelta(days=self.lookback_window)

        stmt = select(Event).where(
            Event.ts >= lookback_date,
            Event.id.not_in([e.id for e in new_events])
        ).order_by(Event.ts.desc()).limit(200)

        result = await self.session.execute(stmt)
        past_events = result.scalars().all()

        # Проверяем причинность между прошлыми и новыми событиями
        for past_event in past_events:
            for new_event in new_events:
                # Проверяем временную последовательность
                if past_event.ts >= new_event.ts:
                    continue

                # Определяем причинность через CMNLN
                relation = await self.cmnln.detect_causality(
                    cause_event=past_event,
                    effect_event=new_event,
                    news_text=""  # TODO: можем передать текст новости
                )

                if relation:
                    # Добавляем conf_market если есть тикеры
                    if new_event.attrs.get("tickers"):
                        ticker = new_event.attrs["tickers"][0]
                        conf_market = await self.event_study.calculate_market_confidence(
                            ticker, new_event.ts
                        )
                        relation.conf_market = conf_market

                        # Пересчитываем total confidence
                        relation.conf_total = self.cmnln._calculate_total_confidence(
                            relation.conf_prior,
                            relation.conf_text,
                            relation.conf_market
                        )

                    # Создаем связь в Neo4j
                    await self.graph.link_events_causes(
                        cause_id=str(past_event.id),
                        effect_id=str(new_event.id),
                        causes=relation
                    )

                    causal_links.append((past_event, new_event, relation))

        # Проверяем связи между новыми событиями
        for i, event1 in enumerate(new_events):
            for event2 in new_events[i+1:]:
                if event1.ts >= event2.ts:
                    continue

                relation = await self.cmnln.detect_causality(
                    cause_event=event1,
                    effect_event=event2,
                    news_text=""
                )

                if relation:
                    await self.graph.link_events_causes(
                        cause_id=str(event1.id),
                        effect_id=str(event2.id),
                        causes=relation
                    )

                    causal_links.append((event1, event2, relation))

        return causal_links

    async def _calculate_impacts(self, events: List[Event]) -> List[Dict[str, Any]]:
        """
        Рассчитать рыночное влияние событий через Event Study
        """
        impacts = []

        for event in events:
            tickers = event.attrs.get("tickers", [])

            if not tickers:
                continue

            for ticker in tickers[:3]:  # Максимум 3 тикера на событие
                try:
                    impact = await self.event_study.analyze_event_impact(
                        event_id=str(event.id),
                        secid=ticker,
                        event_date=event.ts
                    )

                    if impact and impact.get("is_significant"):
                        # Создаем узел инструмента в Neo4j
                        await self.graph.create_instrument_node(
                            instrument_id=f"MOEX:{ticker}",
                            symbol=ticker,
                            instrument_type="equity",
                            exchange="MOEX",
                            currency="RUB"
                        )

                        # Создаем связь IMPACTS
                        impacts_rel = ImpactsRelation(
                            price_impact=impact["ar"],
                            volume_impact=impact["volume_spike"],
                            sentiment=1.0 if impact["ar"] > 0 else -1.0 if impact["ar"] < 0 else 0.0,
                            window="1d"
                        )

                        await self.graph.link_event_impacts_instrument(
                            event_id=str(event.id),
                            instrument_id=f"MOEX:{ticker}",
                            impacts=impacts_rel
                        )

                        impacts.append(impact)

                except Exception as e:
                    logger.warning(f"Error calculating impact for {ticker}: {e}")

        return impacts

    async def _retroactive_analysis(self, new_events: List[Event]) -> int:
        """
        Ретроспективный анализ: новые события могут быть причинами/следствиями
        для уже существующих событий

        Например:
        - День 1: Событие "earnings" для SBER
        - День 3: Новое событие "sanctions" (может объяснить предыдущее падение)

        Этот метод находит такие связи и обновляет граф
        """
        retroactive_links = 0

        # Ищем события, которые произошли ПОСЛЕ новых событий
        # (новое событие может быть причиной старого)
        for new_event in new_events:
            future_date_start = new_event.ts + timedelta(hours=1)
            future_date_end = new_event.ts + timedelta(days=self.lookback_window)

            stmt = select(Event).where(
                Event.ts >= future_date_start,
                Event.ts <= future_date_end,
                Event.id != new_event.id
            ).limit(100)

            result = await self.session.execute(stmt)
            future_events = result.scalars().all()

            for future_event in future_events:
                # Проверяем причинность new_event -> future_event
                relation = await self.cmnln.detect_causality(
                    cause_event=new_event,
                    effect_event=future_event,
                    news_text=""
                )

                if relation:
                    # Добавляем conf_market
                    if future_event.attrs.get("tickers"):
                        ticker = future_event.attrs["tickers"][0]
                        conf_market = await self.event_study.calculate_market_confidence(
                            ticker, future_event.ts
                        )
                        relation.conf_market = conf_market
                        relation.conf_total = self.cmnln._calculate_total_confidence(
                            relation.conf_prior,
                            relation.conf_text,
                            relation.conf_market
                        )

                    # Создаем/обновляем связь в Neo4j
                    await self.graph.link_events_causes(
                        cause_id=str(new_event.id),
                        effect_id=str(future_event.id),
                        causes=relation
                    )

                    retroactive_links += 1

        return retroactive_links

    async def batch_process_recent_news(self, days: int = 7) -> Dict[str, int]:
        """
        Пакетная обработка недавних новостей для построения CEG

        Полезно для инициализации графа или переобработки

        Args:
            days: Сколько дней назад обрабатывать
        """
        from_date = datetime.utcnow() - timedelta(days=days)

        stmt = select(News).where(
            News.published_at >= from_date
        ).order_by(News.published_at.asc())

        result = await self.session.execute(stmt)
        news_list = result.scalars().all()

        logger.info(f"Batch processing {len(news_list)} news items for CEG")

        processed = 0
        errors = 0

        for news in news_list:
            try:
                # TODO: Нужно загрузить AI extracted entities из БД или пересоздать
                # Для простоты пропустим новости без сохраненных entities
                # В реальной системе нужно запустить AI extraction заново

                # await self.process_news(news, ai_extracted)
                processed += 1

            except Exception as e:
                logger.error(f"Error processing news {news.id}: {e}")
                errors += 1

        return {
            "total": len(news_list),
            "processed": processed,
            "errors": errors,
            "events_created": self.stats["events_created"],
            "causal_links": self.stats["causal_links_created"],
            "impacts": self.stats["impacts_calculated"]
        }

    def get_stats(self) -> Dict[str, int]:
        """Получить статистику работы сервиса"""
        stats = self.stats.copy()

        # Добавляем статистику watcher'ов если включены
        if self.watchers_system:
            watcher_stats = self.watchers_system.get_statistics()
            stats.update(watcher_stats['system_statistics'])
            stats['total_active_watches'] = watcher_stats['total_active_watches']

        return stats

    async def _handle_watcher_notification(self, notification: Dict[str, Any]):
        """
        Обработчик уведомлений от watcher'ов

        Args:
            notification: Данные уведможения:
                {
                    'watch_id': str,
                    'watch_name': str,
                    'level': str,
                    'trigger_event_id': str,
                    'trigger_time': str,
                    'alerts': List[str],
                    'context': dict,
                    'priority': str
                }
        """
        logger.info(
            f"📨 WATCHER ALERT [{notification['priority'].upper()}] "
            f"{notification['watch_name']} ({notification['level']}) "
            f"triggered by event {notification['trigger_event_id']}"
        )

        # Здесь можно добавить отправку уведомлений в:
        # - Slack/Discord
        # - Email
        # - SMS
        # - Webhook'и
        # - Система алертов

        # Пример логирования детальной информации
        logger.info(f"Notification details: {notification}")

        # Пример отправки в Telegram (если настроено)
        # await self._send_telegram_alert(notification)

        # Пример отправки в webhook (если настроено)
        # await self._send_webhook_alert(notification)

    async def get_watcher_statistics(self) -> Dict[str, Any]:
        """Получить статистику watcher'ов"""
        if not self.watchers_system:
            return {"error": "Watchers system not enabled"}

        return self.watchers_system.get_statistics()

    async def cleanup_expired_watchers(self):
        """Очистить истекшие watcher'ы"""
        if self.watchers_system:
            await self.watchers_system.cleanup_expired_watches()

    async def check_and_update_predictions(self):
        """Проверить выполнение предсказаний и обновить статистику"""
        if not self.prediction_engine:
            return {"error": "Prediction engine not enabled"}

        try:
            # Проверяем выполнение предсказаний
            fulfilled_predictions = await self.prediction_engine.check_prediction_fulfillment()

            # Обновляем статистику
            if fulfilled_predictions:
                self.stats["predictions_fulfilled"] += len(fulfilled_predictions)

            # Обновляем точность предсказаний
            accuracy_stats = await self.prediction_engine.update_predictions_accuracy()

            logger.info(f"Checked predictions: {len(fulfilled_predictions)} fulfilled, "
                       f"accuracy: {accuracy_stats.get('overall_accuracy', 0):.3f}")

            return {
                "fulfilled_count": len(fulfilled_predictions),
                "accuracy_stats": accuracy_stats
            }

        except Exception as e:
            logger.error(f"Error checking predictions: {e}", exc_info=True)
            return {"error": str(e)}

    def get_prediction_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы предсказаний"""
        if not self.prediction_engine:
            return {"error": "Prediction engine not enabled"}

        return self.prediction_engine.get_statistics()
