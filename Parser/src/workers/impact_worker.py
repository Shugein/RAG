"""
Воркер для расчета влияния новостей
Слушает топик news.norm и публикует в news.scored
"""

import asyncio
import json
import logging
from datetime import datetime

import aio_pika
from aio_pika import IncomingMessage

from Parser.src.services.impact_calculator import ImpactCalculator
from Parser.src.graph_models import GraphService

logger = logging.getLogger(__name__)


class ImpactWorker:
    """
    Воркер оценки влияния новостей на рынок
    Часть конвейера: news.norm -> impact calculation -> news.scored
    """
    
    def __init__(self):
        self.rabbit_connection = None
        self.channel = None
        self.queue = None
        self.graph = None
        self.impact_calc = None
        self.running = False
    
    async def start(self):
        """Запуск воркера"""
        try:
            # Инициализация сервисов
            await self._init_services()
            
            # Подписка на очередь
            await self._setup_consumer()
            
            self.running = True
            logger.info("Impact worker started")
            
            # Держим воркер активным
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to start impact worker: {e}")
            raise
    
    async def _init_services(self):
        """Инициализация сервисов"""
        
        # RabbitMQ
        self.rabbit_connection = await aio_pika.connect_robust(
            settings.RABBITMQ_URL
        )
        self.channel = await self.rabbit_connection.channel()
        await self.channel.set_qos(prefetch_count=1)
        
        # График
        self.graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Калькулятор влияния
        from Parser.src.services.market_data_service import MarketDataService
        market_data = MarketDataService()
        self.impact_calc = ImpactCalculator(market_data)
    
    async def _setup_consumer(self):
        """Настройка consumer для news.norm"""
        
        # Объявляем exchange
        exchange = await self.channel.declare_exchange(
            "radar.news",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Создаем очередь
        self.queue = await self.channel.declare_queue(
            "impact_calculation",
            durable=True
        )
        
        # Привязываем к топику news.norm.*
        await self.queue.bind(exchange, routing_key="news.norm.*")
        
        # Начинаем консьюмить
        await self.queue.consume(self._process_message)
    
    async def _process_message(self, message: IncomingMessage):
        """Обработка сообщения из очереди"""
        
        async with message.process():
            try:
                # Парсим событие
                event = json.loads(message.body.decode())
                
                logger.info(f"Processing impact for news {event['id']}")
                
                # Получаем компании из события
                companies = event.get("extracted_companies", [])
                
                if not companies:
                    logger.debug(f"No companies found in news {event['id']}")
                    # Публикуем без оценки влияния
                    await self._publish_scored(event, [])
                    return
                
                # Рассчитываем влияние для каждой компании
                impacts = []
                for company in companies:
                    affects, no_impact = await self.impact_calc.calculate_impact(
                        datetime.fromisoformat(event["published_at"]),
                        company["id"],
                        company.get("instrument_type", "equity")
                    )
                    
                    if affects and not no_impact:
                        # Сохраняем в граф
                        await self.graph.link_news_to_company(
                            event["id"],
                            company["id"],
                            affects
                        )
                        
                        impacts.append({
                            "company_id": company["id"],
                            "ticker": company.get("ticker"),
                            "weight": affects.weight,
                            "window": affects.window,
                            "method": affects.method
                        })
                        
                        # Распространяем по корреляциям
                        if abs(affects.weight) > 0.3:  # Значимое влияние
                            spread_results = await self.graph.spread_impact(
                                event["id"],
                                company["id"],
                                max_depth=2
                            )
                            
                            for spread_company_id, spread_weight in spread_results:
                                impacts.append({
                                    "company_id": spread_company_id,
                                    "weight": spread_weight,
                                    "window": "60m",
                                    "method": "correlation_spread"
                                })
                
                # Публикуем результат
                await self._publish_scored(event, impacts)
                
                logger.info(f"Impact calculated for news {event['id']}: {len(impacts)} companies affected")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                # В продакшене - отправка в DLQ
    
    async def _publish_scored(self, event: Dict, impacts: List[Dict]):
        """Публикация оцененной новости"""
        
        scored_event = {
            **event,
            "impacts": impacts,
            "impact_calculated_at": datetime.utcnow().isoformat(),
            "has_market_impact": len(impacts) > 0
        }
        
        # Публикуем в news.scored
        exchange = await self.channel.get_exchange("radar.news")
        
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(scored_event, ensure_ascii=False).encode(),
                content_type="application/json",
                delivery_mode=2
            ),
            routing_key="news.scored"
        )