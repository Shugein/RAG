from transformers import pipeline

class SentimentAnalyzer:
    def __init__(self):
        # Используем предобученную модель для русского языка
        self.model = pipeline(
            "sentiment-analysis",
            model="blanchefort/rubert-base-cased-sentiment"
        )
    
    async def analyze_news(self, news: News) -> dict:
        result = self.model(news.text_plain[:512])
        
        return {
            "sentiment": result[0]["label"],  # POSITIVE/NEGATIVE/NEUTRAL
            "score": result[0]["score"],
            "market_impact": self._estimate_market_impact(result)
        }
    
    def _estimate_market_impact(self, sentiment_result):
        # Оцениваем потенциальное влияние на рынок
        if sentiment_result["label"] == "NEGATIVE" and sentiment_result["score"] > 0.8:
            return "HIGH_NEGATIVE"
            # ... другая логика