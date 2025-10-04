# src/services/ml/news_clustering.py

from sentence_transformers import SentenceTransformer
from sklearn.cluster import DBSCAN
import numpy as np

class NewsClusterer:
    def __init__(self):
        self.model = SentenceTransformer('cointegrated/rubert-tiny2')
        
    async def find_similar_news(self, news: News, threshold: float = 0.8):
        # Векторизируем новость
        news_embedding = self.model.encode(news.title + " " + news.text_plain[:500])
        
        # Получаем embeddings последних новостей из БД
        recent_news = await self.get_recent_news_embeddings()
        
        # Находим похожие через косинусное сходство
        similarities = cosine_similarity([news_embedding], recent_news)
        similar_indices = np.where(similarities[0] > threshold)[0]
        
        return {
            "is_duplicate": len(similar_indices) > 0,
            "similar_news_ids": similar_indices.tolist(),
            "max_similarity": float(similarities[0].max())
        }
    
    async def cluster_daily_news(self):
        # Кластеризуем новости за день для выявления главных тем
        embeddings = await self.get_today_embeddings()
        
        clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
        clusters = clustering.fit_predict(embeddings)
        
        return self.extract_cluster_topics(clusters)