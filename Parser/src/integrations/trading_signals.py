class TradingSignalGenerator:
    async def generate_signals(self, news: News, enrichment: dict):
        """Генерация торговых сигналов на основе новостей"""
        
        signals = []
        
        for company in enrichment["companies"]:
            sentiment = enrichment.get("sentiment", {})
            
            if sentiment.get("label") == "NEGATIVE" and sentiment.get("score") > 0.9:
                signals.append({
                    "ticker": company["secid"],
                    "action": "SELL",
                    "confidence": sentiment["score"],
                    "reason": f"Negative news: {news.title[:100]}"
                })
            
            # Проверяем ключевые слова
            if any(word in news.text_plain.lower() for word in ["банкрот", "дефолт", "арест"]):
                signals.append({
                    "ticker": company["secid"],
                    "action": "URGENT_SELL",
                    "confidence": 0.95,
                    "reason": "Critical negative event detected"
                })
        
        # Отправляем в trading систему
        for signal in signals:
            await self.send_to_trading_platform(signal)
        
        return signals

