#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RADAR Finance Mini App - Backend API Server
FastAPI сервер для обслуживания Mini App и API endpoints с заглушкой RADAR функции
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime
import os
import json
from pathlib import Path
from typing import Dict, Any
import uvicorn

class RADARMockProcessor:    
    def __init__(self):
        self.mock_news_data = [
            {
                "id": "1",
                "title": "🏦 Сбербанк объявил о рекордной прибыли за третий квартал",
                "content": "Крупнейший банк России сообщил о чистой прибыли в размере 424 млрд рублей за 9 месяцев 2025 года, что на 15% превышает показатели прошлого года. Рост обусловлен увеличением кредитного портфеля и снижением резервов на возможные потери.",
                "source": "RBC",
                "published_dt": "04.10.2025 15:30",
                "estimated_importance": 0.95,
                "sector": "banks",
                "url": "https://example.com/news1"
            },
            {
                "id": "2", 
                "title": "⚡ Газпром подписал долгосрочные контракты на поставку газа в Азию",
                "content": "ПАО 'Газпром' заключило соглашения с тремя крупными азиатскими компаниями на поставку природного газа общей стоимостью свыше $50 млрд. Контракты рассчитаны на период до 2030 года и предусматривают поставки через 'Силу Сибири-2'.",
                "source": "Ведомости",
                "published_dt": "04.10.2025 14:15",
                "estimated_importance": 0.87,
                "sector": "energy",
                "url": "https://example.com/news2"
            },
            {
                "id": "3",
                "title": "💰 ЦБ РФ повысил ключевую ставку до 21% годовых",
                "content": "Совет директоров Банка России принял решение повысить ключевую ставку на 200 базисных пунктов до 21% годовых. Решение обусловлено необходимостью сдерживания инфляционных рисков и стабилизации курса рубля.",
                "source": "Коммерсант",
                "published_dt": "04.10.2025 12:00",
                "estimated_importance": 0.92,
                "sector": "macroeconomics",
                "url": "https://example.com/news3"
            },
            {
                "id": "4",
                "title": "🔄 ВТБ запустил новую программу ипотечного кредитования",
                "content": "Банк ВТБ анонсировал запуск льготной ипотечной программы с процентной ставкой от 12% годовых для покупки жилья в новостройках. Программа действует до конца 2025 года.",
                "source": "РБК",
                "published_dt": "04.10.2025 11:45",
                "estimated_importance": 0.71,
                "sector": "banks",
                "url": "https://example.com/news4"
            },
            {
                "id": "5",
                "title": "🏭 Лукойл увеличил инвестиции в переработку на 25%",
                "content": "Нефтяная компания 'Лукойл' объявила об увеличении капиталовложений в модернизацию нефтеперерабатывающих заводов. Общий объем инвестиций в 2025 году составит 180 млрд рублей.",
                "source": "Интерфакс",
                "published_dt": "04.10.2025 10:20",
                "estimated_importance": 0.78,
                "sector": "energy",
                "url": "https://example.com/news5"
            },
            {
                "id": "6",
                "title": "📱 МТС запускает 5G сеть в 15 регионах России",
                "content": "Телекоммуникационная компания МТС объявила о развертывании сетей пятого поколения в 15 крупнейших регионах России. Инвестиции в проект составят 45 млрд рублей.",
                "source": "Ведомости",
                "published_dt": "04.10.2025 09:15",
                "estimated_importance": 0.68,
                "sector": "telecom",
                "url": "https://example.com/news6"
            }
        ]
        
        self.mock_edisclosure_data = [
            {
                "id": "e1",
                "company_info": {"name": "ПАО Сбербанк"},
                "event_description": "Выплата промежуточных дивидендов",
                "date": "03.10.2025",
                "full_content": "Совет директоров ПАО Сбербанк принял решение о выплате промежуточных дивидендов в размере 22 рублей на акцию. Дата закрытия реестра: 15.10.2025.",
                "sector": "banks"
            },
            {
                "id": "e2", 
                "company_info": {"name": "ПАО Газпром"},
                "event_description": "Изменения в составе Правления",
                "date": "02.10.2025",
                "full_content": "В состав Правления ПАО Газпром включен новый член - заместитель генерального директора по стратегическому развитию.",
                "sector": "energy"
            }
        ]
    
    def process_user_query(self, query_text: str, query_type: str = "general", sector: str = "all") -> Dict[str, Any]:
        print(f"[MOCK] Обработка запроса: '{query_text}'")
        print(f"[MOCK] Тип: {query_type}, Сектор: {sector}")
        
        filtered_news = self._filter_by_sector(self.mock_news_data, sector)
        filtered_edisclosure = self._filter_by_sector(self.mock_edisclosure_data, sector)
        
        if query_type == "draft":
            results = self._generate_draft(filtered_news, filtered_edisclosure, sector)
        elif query_type == "hot":
            results = self._get_hot_news(filtered_news, filtered_edisclosure, sector)
        elif query_type == "analytics":
            results = self._generate_analytics(filtered_news, filtered_edisclosure, sector)
        else:
            results = self._general_search(filtered_news, filtered_edisclosure, query_text, sector)
        
        response = {
            "status": "success",
            "query": {
                "text": query_text,
                "type": query_type,
                "sector": sector,
                "processed_at": datetime.now().isoformat()
            },
            "statistics": {
                "total_sources": len(set([item.get('source') for item in filtered_news if item.get('source')])),
                "total_news": len(filtered_news),
                "total_edisclosure": len(filtered_edisclosure),
                "processing_time_ms": 250
            },
            "results": results,
            "visualization": {
                "charts": self._generate_charts_data(filtered_news, sector),
                "timeline": self._generate_timeline(filtered_news),
                "sectors_breakdown": self._get_sectors_breakdown(filtered_news)
            }
        }
        return response
    
    def _filter_by_sector(self, data, sector):
        """Фильтрует данные по сектору"""
        if sector == "all":
            return data
            
        sector_mapping = {
            "banking": "banks",
            "banks": "banks", 
            "energy": "energy",
            "tech": "telecom",
            "it": "telecom"
        }
        
        target_sector = sector_mapping.get(sector, sector)
        return [item for item in data if item.get('sector') == target_sector]
    
    def _generate_draft(self, news_data, edisclosure_data, sector):
        hot_news = sorted(news_data, key=lambda x: float(x.get('estimated_importance', 0)), reverse=True)[:5]
        
        return {
            "title": f"Аналитический черновик: {sector}",
            "summary": f"Краткая сводка по сектору {sector} на основе {len(news_data)} новостей и {len(edisclosure_data)} корпоративных событий",
            "key_points": [
                f"Обнаружено {len(hot_news)} важных событий с высоким рейтингом",
                f"Зафиксировано {len(edisclosure_data)} корпоративных событий", 
                f"Проанализировано {len(set([n.get('source') for n in news_data]))} источников",
                "Рекомендуется особое внимание к изменениям ключевой ставки ЦБ",
                "Банковский сектор показывает устойчивый рост прибыли"
            ],
            "hot_news": [
                {
                    "id": news.get('id'),
                    "title": news.get('title', ''),
                    "source": news.get('source', ''),
                    "importance": float(news.get('estimated_importance', 0)),
                    "date": news.get('published_dt', ''),
                    "summary": news.get('content', '')[:200] + "..."
                }
                for news in hot_news
            ],
            "corporate_events": [
                {
                    "id": event.get('id'),
                    "company": event.get('company_info', {}).get('name', 'Неизвестная компания'),
                    "event_type": event.get('event_description', ''),
                    "date": event.get('date', ''),
                    "summary": event.get('full_content', '')[:150] + "..." if event.get('full_content') else ''
                }
                for event in edisclosure_data
            ],
            "recommendations": [
                f"Особое внимание стоит уделить событиям в секторе {sector}",
                "Рекомендуется мониторить изменения процентной политики ЦБ",
                "Следует отслеживать корпоративные действия крупнейших игроков рынка",
                "Важно учитывать влияние геополитических факторов на отрасль"
            ]
        }
    
    def _get_hot_news(self, news_data, edisclosure_data, sector):
        """Возвращает горячие новости"""
        hot_news = sorted(news_data, key=lambda x: float(x.get('estimated_importance', 0)), reverse=True)
        
        return {
            "title": f"Горячие новости: {sector}",
            "total_found": len(hot_news),
            "news": [
                {
                    "id": news.get('id'),
                    "title": news.get('title', ''),
                    "content": news.get('content', '')[:300] + "...",
                    "source": news.get('source', ''),
                    "hotness_score": float(news.get('estimated_importance', 0)),
                    "published_dt": news.get('published_dt', ''),
                    "url": news.get('url', ''),
                    "sector": sector,
                    "tags": self._extract_tags(news.get('title', '') + ' ' + news.get('content', ''))
                }
                for news in hot_news
            ]
        }
    
    def _generate_analytics(self, news_data, edisclosure_data, sector):
        sources_count = {}
        for news in news_data:
            source = news.get('source', 'unknown')
            sources_count[source] = sources_count.get(source, 0) + 1
        
        return {
            "title": f"Аналитический отчет: {sector}",
            "period": "За последние 24 часа",
            "metrics": {
                "total_news": len(news_data),
                "total_sources": len(sources_count),
                "avg_importance": sum(float(n.get('estimated_importance', 0)) for n in news_data) / len(news_data) if news_data else 0,
                "total_edisclosure": len(edisclosure_data)
            },
            "sources_breakdown": [
                {"source": source, "count": count, "percentage": round(count/len(news_data)*100, 1)}
                for source, count in sorted(sources_count.items(), key=lambda x: x[1], reverse=True)
            ],
            "timeline": [
                {"date": "04.10.2025", "count": len(news_data)},
                {"date": "03.10.2025", "count": max(1, len(news_data) - 2)},
                {"date": "02.10.2025", "count": max(1, len(news_data) - 3)}
            ],
            "top_news": [
                {
                    "title": news.get('title', ''),
                    "importance": float(news.get('estimated_importance', 0)),
                    "source": news.get('source', ''),
                    "date": news.get('published_dt', '')
                }
                for news in sorted(news_data, key=lambda x: float(x.get('estimated_importance', 0)), reverse=True)[:10]
            ]
        }
    
    def _general_search(self, news_data, edisclosure_data, query, sector):
        query_words = query.lower().split()
        
        relevant_news = []
        for news in news_data:
            title = news.get('title', '').lower()
            content = news.get('content', '').lower()
            
            relevance = 0
            for word in query_words:
                if word in title:
                    relevance += 2
                if word in content:
                    relevance += 1
            
            if relevance > 0:
                news_copy = news.copy()
                news_copy['relevance'] = relevance
                relevant_news.append(news_copy)
        
        relevant_news.sort(key=lambda x: x['relevance'], reverse=True)
        
        return {
            "title": f"Результаты поиска: '{query}'",
            "query": query,
            "sector": sector,
            "total_found": len(relevant_news),
            "results": [
                {
                    "id": news.get('id'),
                    "title": news.get('title', ''),
                    "content": news.get('content', '')[:250] + "...",
                    "source": news.get('source', ''),
                    "relevance": news.get('relevance', 0),
                    "importance": float(news.get('estimated_importance', 0)),
                    "published_dt": news.get('published_dt', ''),
                    "highlights": news.get('title', '')  # Упрощенная подсветка
                }
                for news in relevant_news
            ]
        }
    
    def _extract_tags(self, text):
        common_tags = ['банки', 'энергетика', 'финансы', 'политика', 'рынок', 'экономика', 'прибыль', 'дивиденды']
        text_lower = text.lower()
        found_tags = [tag for tag in common_tags if tag in text_lower]
        return found_tags[:3]
    
    def _generate_charts_data(self, news_data, sector):
        sources = {}
        for news in news_data:
            source = news.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        return {
            "sources_pie": {
                "labels": list(sources.keys()),
                "data": list(sources.values()),
                "colors": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40"]
            }
        }
    
    def _generate_timeline(self, news_data):
        return [
            {"date": "04.10.2025", "count": len(news_data)},
            {"date": "03.10.2025", "count": max(1, len(news_data) - 1)},
            {"date": "02.10.2025", "count": max(1, len(news_data) - 2)}
        ]
    
    def _get_sectors_breakdown(self, news_data):
        sectors = {"Банки": 0, "Энергетика": 0, "Телеком": 0, "Другое": 0}
        
        for news in news_data:
            sector = news.get('sector', 'other')
            if sector == 'banks':
                sectors["Банки"] += 1
            elif sector == 'energy':
                sectors["Энергетика"] += 1
            elif sector == 'telecom':
                sectors["Телеком"] += 1
            else:
                sectors["Другое"] += 1
        
        return sectors

radar_processor = RADARMockProcessor()

app = FastAPI(
    title="RADAR Finance Mini App API",
    description="API для Telegram Mini App системы финансовой аналитики RADAR",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    
    @app.get("/")
    async def serve_index():
        index_path = frontend_path / "index-clean.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        fallback_path = frontend_path / "index.html"
        if fallback_path.exists():
            return FileResponse(str(fallback_path))
        return {"message": "Frontend не найден"}
    
    @app.get("/js/{filename}")
    async def serve_js(filename: str):
        js_path = frontend_path / "js" / filename
        if js_path.exists():
            return FileResponse(str(js_path), media_type="application/javascript")
        raise HTTPException(status_code=404, detail="File not found")

SAMPLE_DATA = {
    "dashboard": {
        "totalNews": 1507,
        "hotNewsToday": 12,
        "totalSources": 6,
        "lastUpdate": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "topNews": [
            {
                "id": "1",
                "title": "Сбербанк объявил о рекордной прибыли",
                "source": "RBC",
                "hotness_score": 0.95,
                "published_dt": "03.10.2025"
            },
            {
                "id": "2",
                "title": "Газпром расширяет поставки в Азию",
                "source": "Ведомости",
                "hotness_score": 0.87,
                "published_dt": "03.10.2025"
            }
        ]
    }
}


@app.get("/api/health")
async def health_check():
    """Проверка здоровья API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/api/dashboard")
async def get_dashboard():
    """Получить данные дашборда"""
    try:
        data = SAMPLE_DATA["dashboard"].copy()
        data["lastUpdate"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных дашборда: {str(e)}")

@app.get("/api/hot-news")
async def get_hot_news(limit: int = 20):
    """Получить горячие новости"""
    try:
        hot_news = [
            {
                "id": "1",
                "title": "🏦 Сбербанк объявил о рекордной прибыли за квартал",
                "content": "Крупнейший банк России сообщил о превышении ожидаемых показателей прибыли на 15%. Руководство банка отмечает стабильный рост во всех сегментах бизнеса, включая корпоративное и розничное кредитование.",
                "source": "RBC",
                "published_dt": "03.10.2025 15:30",
                "hotness_score": 0.95
            },
            {
                "id": "2",
                "title": "🏭 Газпром расширяет поставки энергоносителей в страны Азии",
                "content": "Энергетический гигант подписал долгосрочные контракты на поставку газа с тремя крупными азиатскими компаниями. Общая стоимость сделок превышает $50 млрд на период до 2030 года.",
                "source": "Ведомости",
                "published_dt": "03.10.2025 14:15",
                "hotness_score": 0.87
            },
            {
                "id": "3",
                "title": "💰 ЦБ РФ изменил ключевую ставку до 21%",
                "content": "Центральный банк России принял решение о повышении ключевой ставки на 200 базисных пунктов в ответ на усиливающиеся инфляционные риски.",
                "source": "Коммерсант",
                "published_dt": "03.10.2025 12:00",
                "hotness_score": 0.83
            }
        ]
        
        return {"news": hot_news[:limit]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения горячих новостей: {str(e)}")

@app.get("/api/search") 
async def search_news(q: str, limit: int = 20):
    """Поиск новостей"""
    try:
        if not q:
            raise HTTPException(status_code=400, detail="Параметр поиска 'q' обязателен")
        
        results = [
            {
                "id": "1",
                "title": f"Результат поиска по запросу '{q}'",
                "content": f"Найденный контент, содержащий '{q}' в тексте новости...",
                "source": "RBC",
                "published_dt": "02.10.2025",
                "relevance": 0.9
            }
        ]
        
        return {
            "query": q,
            "results": results[:limit],
            "total": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка поиска: {str(e)}")

@app.get("/api/statistics")
async def get_statistics():
    try:
        return {
            "sources": {
                "RBC": 118,
                "Ведомости": 281,
                "Коммерсант": 69,
                "MOEX": 45,
                "Интерфакс": 94,
                "E-disclosure": 150
            },
            "dates": {
                "today": 12,
                "week": 89,
                "month": 456
            },
            "companies": {
                "Сбербанк": 23,
                "Газпром": 18,
                "Лукойл": 15,
                "ВТБ": 12,
                "Роснефть": 10
            },
            "categories": {
                "Банковский сектор": 95,
                "Энергетика": 87,
                "Металлургия": 43,
                "Телекоммуникации": 35
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

@app.get("/api/e-disclosure/news")
async def get_edisclosure_news(limit: int = 20):
    try:
        return {
            "news": [
                {
                    "id": "1",
                    "title": "Корпоративное событие - выплата дивидендов",
                    "company": "ПАО Сбербанк",
                    "date": "03.10.2025",
                    "content": "Совет директоров ПАО Сбербанк принял решение о выплате промежуточных дивидендов...",
                    "event_type": "dividend_payment"
                },
                {
                    "id": "2", 
                    "title": "Существенный факт - изменение в руководстве",
                    "company": "ПАО Газпром",
                    "date": "03.10.2025",
                    "content": "В составе Правления ПАО Газпром произошли изменения...",
                    "event_type": "management_change"
                }
            ][:limit]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения E-disclosure новостей: {str(e)}")

@app.get("/api/e-disclosure/messages")
async def get_edisclosure_messages(limit: int = 20):
    try:
        return {
            "messages": [
                {
                    "id": "1",
                    "company": "ПАО Сбербанк",
                    "event_type": "Выплата дивидендов",
                    "date": "03.10.2025 15:30",
                    "content": "Полное содержание корпоративного события о выплате дивидендов...",
                    "full_content": "Детальная информация о размере дивидендов, датах выплат и реестрах акционеров..."
                },
                {
                    "id": "2",
                    "company": "ПАО Газпром", 
                    "event_type": "Собрание акционеров",
                    "date": "03.10.2025 14:15",
                    "content": "Уведомление о проведении внеочередного собрания акционеров...",
                    "full_content": "Повестка дня, порядок участия, список документов для ознакомления..."
                }
            ][:limit]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения E-disclosure сообщений: {str(e)}")

@app.post("/api/process_query")
async def process_radar_query(query_data: dict):
    try:
        query_text = query_data.get("query", "Тестовый запрос")
        
        print(f"Получен запрос: '{query_text}'")
        
        result = {
            'query': query_text,
            'answer': 'Согласно представленной информации, найдены релевантные данные по вашему запросу в финансовой сфере.',
            'documents': [
                {
                    'title': 'Сбербанк показал рекордную прибыль',
                    'source': 'RBC',
                    'text': 'Сбербанк объявил о рекордной прибыли за третий квартал 2025 года. Чистая прибыль банка составила 350 млрд рублей.',
                    'chunk_text': 'Сбербанк объявил о рекордной прибыли за третий квартал 2025 года. Чистая прибыль банка составила 350 млрд рублей.',
                    'url': 'https://example.com/news/sberbank',
                    'timestamp': 1728000000,
                    'hybrid_score': 0.89,
                    'rerank_score': 0.89,
                    'original_position': 1,
                    'new_position': 1,
                    'chunk_index': 0,
                    'parent_doc_id': 'sber-001',
                    'text_type': 'parent_document'
                },
                {
                    'title': 'ЦБ РФ повысил ключевую ставку',
                    'source': 'Коммерсант',
                    'text': 'Центральный банк России принял решение повысить ключевую ставку до 21% годовых в ответ на инфляционные риски.',
                    'chunk_text': 'Центральный банк России принял решение повысить ключевую ставку до 21% годовых в ответ на инфляционные риски.',  
                    'url': 'https://example.com/news/cbr',
                    'timestamp': 1727950000,
                    'hybrid_score': 0.76,
                    'rerank_score': 0.76,
                    'original_position': 2,
                    'new_position': 2,
                    'chunk_index': 0,
                    'parent_doc_id': 'cbr-001',
                    'text_type': 'parent_document'
                },
                {
                    'title': 'Газпром заключил новые контракты',
                    'source': 'Ведомости',
                    'text': 'Газпром подписал долгосрочные контракты на поставку газа в страны Азии общей стоимостью 45 млрд долларов.',
                    'chunk_text': 'Газпром подписал долгосрочные контракты на поставку газа в страны Азии общей стоимостью 45 млрд долларов.',
                    'url': 'https://example.com/news/gazprom',
                    'timestamp': 1727900000,
                    'hybrid_score': 0.68,
                    'rerank_score': 0.68,
                    'original_position': 3,
                    'new_position': 3,
                    'chunk_index': 0,
                    'parent_doc_id': 'gaz-001',
                    'text_type': 'parent_document'
                }
            ],
            'metadata': {
                'total_time': 2.3,
                'num_documents': 3,
                'vectorizer': 'sergeyzh/BERTA',
                'reranker': 'BAAI/bge-reranker-v2-m3',
                'llm_model': 'openai/gpt-4',
                'use_parent_docs': True
            }
        }
        
        print(f"Запрос обработан успешно")
        return result
        
    except Exception as e:
        print(f"Ошибка обработки запроса: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса: {str(e)}")

@app.get("/api/sectors")
async def get_available_sectors():
    return {
        "sectors": [
            {"id": "all", "name": "Все сектора", "emoji": "🌐", "description": "Все доступные новости"},
            {"id": "banking", "name": "Банки", "emoji": "🏦", "description": "Банковский сектор"},
            {"id": "energy", "name": "Энергетика", "emoji": "⚡", "description": "Энергетический сектор"},
            {"id": "tech", "name": "IT/Технологии", "emoji": "💻", "description": "IT и телекоммуникации"},
            {"id": "metals", "name": "Металлургия", "emoji": "🏭", "description": "Металлургическая отрасль"},
            {"id": "retail", "name": "Ритейл", "emoji": "🛒", "description": "Розничная торговля"},
        ]
    }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик ошибок"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Произошла внутренняя ошибка сервера",
            "details": str(exc) if app.debug else None
        }
    )

def main():
    """Запуск сервера"""
    print("Запуск RADAR Finance Mini App API Server")
    print("=" * 50)
    print("Frontend: http://127.0.0.1:8000")
    print("API: http://127.0.0.1:8000/api/")
    print("Health: http://127.0.0.1:8000/api/health")
    print("Docs: http://127.0.0.1:8000/docs")
    print("Process Query: http://127.0.0.1:8000/api/process_query")
    print("=" * 50)
    print("RADAR функция готова к работе (MOCK режим)")
    print("Используйте новый интерфейс в браузере!")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()