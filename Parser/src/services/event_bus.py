# Вместо прямых вызовов - использовать события через RabbitMQ
# src/services/event_bus.py

class EventBus:
    """Централизованная шина событий"""
    
    async def publish(self, event_type: str, payload: dict):
        # Публикуем в соответствующую очередь
        routing_key = event_type.replace(".", "_")
        await self.channel.default_exchange.publish(
            Message(body=json.dumps(payload)),
            routing_key=f"events.{routing_key}"
        )
    
    async def subscribe(self, event_pattern: str, handler: Callable):
        # Подписываемся на события
        queue = await self.channel.declare_queue(auto_delete=True)
        await queue.bind(exchange, routing_key=event_pattern)
        await queue.consume(handler)

# Использование:
# Parser -> публикует "news.raw"
# Enricher -> слушает "news.raw", публикует "news.enriched"
# Notifier -> слушает "news.enriched", отправляет уведомления