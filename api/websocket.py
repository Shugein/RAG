class NotificationService:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {}
        self.user_subscriptions: Dict[str, List[str]] = {}
    
    async def subscribe_user(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.connections[user_id] = websocket
        
        # Подписываем на интересующие тикеры/темы
        subscriptions = await self.get_user_subscriptions(user_id)
        self.user_subscriptions[user_id] = subscriptions
    
    async def notify_relevant_users(self, news: News, enrichment: dict):
        # Определяем, кому интересна эта новость
        relevant_users = []
        
        # По тикерам
        for company in enrichment.get("companies", []):
            users = await self.get_ticker_subscribers(company["secid"])
            relevant_users.extend(users)
        
        # По темам
        for topic in enrichment.get("topics", []):
            users = await self.get_topic_subscribers(topic["topic"])
            relevant_users.extend(users)
        
        # Отправляем уведомления
        for user_id in set(relevant_users):
            if user_id in self.connections:
                await self.send_notification(
                    user_id,
                    {
                        "type": "new_news",
                        "news": news.to_dict(),
                        "importance": self.calculate_importance(news, user_id)
                    }
                )