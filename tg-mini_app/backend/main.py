#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime
import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any
import uvicorn

class RADARMockProcessor:    

    def __init__(self):
        print("RADAR Mock Processor инициализирован с новой структурой")
        # Создаем папку для PDF отчетов
        self.reports_dir = Path(__file__).parent.parent / "frontend" / "assets" / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        
        # Путь к шаблону PDF
        self.template_pdf = Path(__file__).parent.parent / "frontend" / "assets" / "sberbank_article.pdf"
    
    def query(self, query_text: str, generate_pdf: bool = False) -> Dict[str, Any]:

        print(f"[MOCK RADAR] Обработка запроса: '{query_text}'")
        
        draft_response = {
            'headline': f'Финансовая аналитика: {query_text}',
            'dek': 'Ключевые события на российском финансовом рынке',
            'variants': {
                'social_post': f'Новости по запросу "{query_text}": Сбербанк показал рекордную прибыль, ЦБ повысил ставку до 21%. Подробности в нашем обзоре! #финансы #банки',
                'article_draft': f'По результатам анализа запроса "{query_text}" выявлены ключевые тренды российского финансового рынка. Банковский сектор демонстрирует устойчивый рост, энергетический сектор расширяет экспорт...',
                'alert': f'ВАЖНО: По запросу "{query_text}" обнаружены значимые изменения на рынке. ЦБ РФ повысил ключевую ставку.'
            },
            'key_points': [
                'Сбербанк объявил о рекордной прибыли за 9 месяцев 2025 года',
                'ЦБ РФ повысил ключевую ставку до 21% годовых',
                'Газпром заключил контракты на поставку газа в Азию на $50 млрд',
                'Банковский сектор показывает устойчивый рост кредитного портфеля',
                'Энергетические компании увеличивают инвестиции в модернизацию'
            ],
            'hashtags': ['#финансы', '#банки', '#ЦБ', '#Сбербанк', '#Газпром', '#российскийрынок'],
            'visualization_ideas': [
                'График динамики ключевой ставки ЦБ РФ',
                'Диаграмма прибыли крупнейших банков',
                'Карта экспортных контрактов Газпрома',
                'Сравнительная таблица показателей энергетических компаний'
            ],
            'compliance_flags': [
                'Информация основана на публичных данных',
                'Требуется проверка актуальности курсов валют',
                'Рекомендуется указать источники данных'
            ],
            'disclaimer': 'Данная информация носит ознакомительный характер и не является инвестиционной рекомендацией. Принятие инвестиционных решений осуществляется на собственный риск.',
            'sources': [
                {'name': 'RBC', 'url': 'https://rbc.ru', 'reliability': 0.95},
                {'name': 'Ведомости', 'url': 'https://vedomosti.ru', 'reliability': 0.90},
                {'name': 'Коммерсант', 'url': 'https://kommersant.ru', 'reliability': 0.92},
                {'name': 'Интерфакс', 'url': 'https://interfax.ru', 'reliability': 0.88}
            ],
            'metadata': {
                'generation_time': 1.845,
                'model_used': 'gpt-4o-mini',
                'temperature': 0.7,
                'max_tokens': 2000
            }
        }
        
        documents = [
            {
                'title': 'Сбербанк объявил о рекордной прибыли за третий квартал 2025 года',
                'source': 'RBC',
                'text': 'Крупнейший банк России ПАО Сбербанк сообщил о чистой прибыли в размере 424 млрд рублей за 9 месяцев 2025 года, что на 15% превышает показатели аналогичного периода прошлого года. Рост прибыли обусловлен увеличением кредитного портфеля на 12% и снижением резервов на возможные потери по ссудам. Банк также отметил рост доходов от комиссионных операций и улучшение качества кредитного портфеля.',
                'chunk_text': 'ПАО Сбербанк сообщил о чистой прибыли в размере 424 млрд рублей за 9 месяцев 2025 года, что на 15% превышает показатели прошлого года.',
                'url': 'https://rbc.ru/finances/sberbank-profit-q3-2025',
                'timestamp': 1728050400,  # 04.10.2025 15:30
                'rerank_score': 0.94,
                'hotness': 0.87,
                'final_score': 0.91,
                'final_position': 1,
                'chunk_index': 0,
                'parent_doc_id': 'sber-2025-q3-001',
                'text_type': 'parent_document',
                'companies': ['Сбербанк', 'ПАО Сбербанк'],
                'company_tickers': ['SBER'],
                'company_sectors': ['Банки', 'Финансовый сектор'],
                'people': ['Герман Греф'],
                'people_positions': ['Президент, Председатель Правления'],
                'markets': ['Московская биржа', 'Российский банковский рынок'],
                'market_types': ['equity', 'banking'],
                'financial_metric_types': ['прибыль', 'рентабельность', 'кредитный портфель'],
                'financial_metric_values': ['424 млрд руб', '15%', '12%'],
                'entities_json': '{"companies": ["Сбербанк"], "metrics": ["424 млрд руб"], "growth": "15%"}'
            },
            {
                'title': 'ЦБ РФ повысил ключевую ставку до 21% годовых',
                'source': 'Коммерсант',
                'text': 'Совет директоров Банка России принял решение повысить ключевую ставку на 200 базисных пунктов до 21% годовых. Решение обусловлено необходимостью сдерживания инфляционных рисков и стабилизации курса рубля в условиях повышенной волатильности на мировых рынках. Регулятор также отметил необходимость охлаждения потребительского спроса.',
                'chunk_text': 'Совет директоров Банка России принял решение повысить ключевую ставку на 200 базисных пунктов до 21% годовых.',
                'url': 'https://kommersant.ru/doc/cbr-rate-increase-october-2025',
                'timestamp': 1728036000,  # 04.10.2025 12:00
                'rerank_score': 0.92,
                'hotness': 0.95,
                'final_score': 0.93,
                'final_position': 2,
                'chunk_index': 0,
                'parent_doc_id': 'cbr-rate-oct-2025-001',
                'text_type': 'parent_document',
                'companies': ['Банк России', 'ЦБ РФ'],
                'company_tickers': [],
                'company_sectors': ['Центральные банки', 'Регулирование'],
                'people': ['Эльвира Набиуллина'],
                'people_positions': ['Председатель Банка России'],
                'markets': ['Денежный рынок', 'Валютный рынок'],
                'market_types': ['monetary', 'forex'],
                'financial_metric_types': ['ключевая ставка', 'инфляция'],
                'financial_metric_values': ['21%', '200 б.п.'],
                'entities_json': '{"institutions": ["ЦБ РФ"], "rates": ["21%"], "change": "200 б.п."}'
            },
            {
                'title': 'Газпром подписал долгосрочные контракты на поставку газа в Азию',
                'source': 'Ведомости',
                'text': 'ПАО Газпром заключило соглашения с тремя крупными азиатскими компаниями на поставку природного газа общей стоимостью свыше $50 млрд. Контракты рассчитаны на период до 2030 года и предусматривают поставки через газопровод "Сила Сибири-2". Общий объем поставок составит до 50 млрд кубометров газа в год.',
                'chunk_text': 'ПАО Газпром заключило соглашения на поставку природного газа общей стоимостью свыше $50 млрд через "Силу Сибири-2".',
                'url': 'https://vedomosti.ru/business/gazprom-asia-contracts-2025',
                'timestamp': 1728041400,  # 04.10.2025 14:15
                'rerank_score': 0.85,
                'hotness': 0.79,
                'final_score': 0.82,
                'final_position': 3,
                'chunk_index': 0,
                'parent_doc_id': 'gazprom-asia-2025-001',
                'text_type': 'parent_document',
                'companies': ['Газпром', 'ПАО Газпром'],
                'company_tickers': ['GAZP'],
                'company_sectors': ['Энергетика', 'Нефтегазовый сектор'],
                'people': ['Алексей Миллер'],
                'people_positions': ['Генеральный директор'],
                'markets': ['Азиатский газовый рынок', 'Российский энергорынок'],
                'market_types': ['energy', 'commodities'],
                'financial_metric_types': ['контрактная стоимость', 'объем поставок'],
                'financial_metric_values': ['$50 млрд', '50 млрд м³/год'],
                'entities_json': '{"companies": ["Газпром"], "contracts": "$50 млрд", "volume": "50 млрд м³/год"}'
            }
        ]
        
        metadata = {
            'total_time': 2.347,
            'num_documents': len(documents),
            'vectorizer': 'text2vec-transformers (GPU)',
            'reranker': 'BAAI/bge-reranker-v2-m3',
            'llm_model': 'gpt-5',
            'use_parent_docs': True,
            'news_type': 'mixed',
            'tone': 'analytical'
        }
        
        result = {
            'query': query_text,
            'draft': draft_response,
            'documents': documents,
            'metadata': metadata
        }
        
        if generate_pdf:
            pdf_path = self.generate_pdf_report(query_text, result)
            result['pdf_path'] = pdf_path
        
        return result
    
    def generate_pdf_report(self, query_text: str, result_data: Dict[str, Any]) -> str:
        """Генерирует PDF отчет на основе результатов анализа"""
        try:
            # Создаем уникальное имя файла (только латиница и цифры)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            import re
            safe_query = re.sub(r'[^a-zA-Z0-9_]', '', query_text.replace(' ', '_'))[:20]
            if not safe_query:
                safe_query = "query"
            pdf_filename = f"radar_report_{safe_query}_{timestamp}.pdf"
            pdf_path = self.reports_dir / pdf_filename
            
            # Копируем шаблон PDF как базу для отчета
            if self.template_pdf.exists():
                shutil.copy2(self.template_pdf, pdf_path)
                print(f"PDF отчет создан: {pdf_path}")
                
                # Возвращаем относительный путь для web доступа
                return f"static/assets/reports/{pdf_filename}"
            else:
                print(f"Шаблон PDF не найден: {self.template_pdf}")
                return None
                
        except Exception as e:
            print(f"Ошибка генерации PDF: {e}")
            return None


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
        index_path = frontend_path / "index-simple.html"
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
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }

@app.get("/api/dashboard")
async def get_dashboard():
    try:
        data = SAMPLE_DATA["dashboard"].copy()
        data["lastUpdate"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных дашборда: {str(e)}")

@app.get("/api/hot-news")
async def get_hot_news(limit: int = 20):
    try:
        hot_news = [
            {
                "id": "1",
                "title": "Сбербанк объявил о рекордной прибыли за квартал",
                "content": "Крупнейший банк России сообщил о превышении ожидаемых показателей прибыли на 15%. Руководство банка отмечает стабильный рост во всех сегментах бизнеса, включая корпоративное и розничное кредитование.",
                "source": "RBC",
                "published_dt": "03.10.2025 15:30",
                "hotness_score": 0.95
            },
            {
                "id": "2",
                "title": "Газпром расширяет поставки энергоносителей в страны Азии",
                "content": "Энергетический гигант подписал долгосрочные контракты на поставку газа с тремя крупными азиатскими компаниями. Общая стоимость сделок превышает $50 млрд на период до 2030 года.",
                "source": "Ведомости",
                "published_dt": "03.10.2025 14:15",
                "hotness_score": 0.87
            },
            {
                "id": "3",
                "title": "ЦБ РФ изменил ключевую ставку до 21%",
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
        generate_pdf = query_data.get("generate_pdf", False)
        
        print(f"Получен запрос: '{query_text}'")
        print(f"Генерация PDF: {generate_pdf}")
        
        result = radar_processor.query(query_text, generate_pdf=generate_pdf)
        
        print(f"Запрос обработан успешно")
        print(f"Найдено документов: {len(result.get('documents', []))}")
        print(f"Время обработки: {result.get('metadata', {}).get('total_time', 0)} сек")
        
        return result
        
    except Exception as e:
        print(f"Ошибка обработки запроса: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки запроса: {str(e)}")

@app.get("/api/download/pdf/{filename}")
async def download_pdf_report(filename: str):
    """Скачивание PDF отчетов"""
    try:
        reports_dir = Path(__file__).parent.parent / "frontend" / "assets" / "reports"
        pdf_path = reports_dir / filename
        
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF файл не найден")
        
        return FileResponse(
            path=str(pdf_path),
            filename=filename,
            media_type='application/pdf',
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка скачивания PDF: {str(e)}")

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
        # host="0.0.0.0",
        port=8000,
        # port=8082,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()