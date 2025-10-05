#Parser.src/services/cache_service.py

class CacheService:
    def __init__(self):
        self.redis = redis.asyncio.from_url(settings.REDIS_URL)
        
    @cache(ttl=3600)
    async def get_company_info(self, ticker: str):
        # Кэшируем информацию о компаниях
        cache_key = f"company:{ticker}"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Если нет в кэше - загружаем
        data = await self.moex_api.get_security(ticker)
        await self.redis.setex(
            cache_key, 3600, json.dumps(data)
        )
        return data
    
    @cache(ttl=300)
    async def get_trending_news(self, limit: int = 10):
        # Кэшируем популярные новости
        return await self.news_repo.get_trending(limit)