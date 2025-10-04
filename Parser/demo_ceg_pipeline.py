# demo_ceg_pipeline.py
"""
Demo CEG Pipeline - демонстрация работы Causal Event Graph

Пайплайн:
1. Загружает новости из БД
2. Извлекает события (EventExtractor)
3. Определяет причинность (CMNLN)
4. Анализирует рыночное влияние (Event Study)
5. Строит граф в Neo4j
6. Выводит результаты
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import List

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.models import News, Event
from src.core.config import settings
from src.services.events.event_extractor import EventExtractor
from src.services.events.cmnln_engine import CMLNEngine
from src.services.moex.moex_prices import MOEXPriceService, EventStudyAnalyzer
from src.graph_models import GraphService, EventNode, CausesRelation, ImpactsRelation

# Импорт AI extraction
from entity_recognition import CachedFinanceNERExtractor
from entity_recognition_local import LocalFinanceNERExtractor


async def main():
    """Основная функция демо-пайплайна"""
    print("=" * 80)
    print("CEG + CMNLN Demo Pipeline")
    print("=" * 80)

    # 1. Инициализация сервисов
    print("\n[1/6] Инициализация сервисов...")

    # Database
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Neo4j Graph Service
    graph = GraphService(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )

    # AI Extraction (используем локальный или API)
    use_local = os.getenv("USE_LOCAL_AI", "false").lower() == "true"
    if use_local:
        print("   Using Local Qwen3-4B for NER extraction")
        ai_ner = LocalFinanceNERExtractor(
            model_name="unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
            device="cuda",
            batch_size=5
        )
    else:
        print("   Using GPT-5 API for NER extraction")
        api_key = os.getenv("API_KEY_2") or os.getenv("OPENAI_API_KEY")
        ai_ner = CachedFinanceNERExtractor(
            api_key=api_key,
            model="gpt-4o-mini",
            enable_caching=True
        )

    # Event Extractor
    event_extractor = EventExtractor()

    # CMNLN Engine
    cmnln = CMLNEngine(graph_service=graph)

    # MOEX Price Service & Event Study
    moex = MOEXPriceService()
    event_study = EventStudyAnalyzer(moex)

    print("   ✓ Сервисы инициализированы")

    # 2. Загрузка новостей из БД
    print("\n[2/6] Загрузка новостей из БД...")

    async with async_session() as session:
        # Загружаем последние 50 новостей за последние 7 дней
        date_from = datetime.utcnow() - timedelta(days=7)
        stmt = select(News).where(
            News.published_at >= date_from
        ).order_by(News.published_at.desc()).limit(50)

        result = await session.execute(stmt)
        news_list = result.scalars().all()

    print(f"   ✓ Загружено {len(news_list)} новостей")

    # 3. Извлечение событий
    print("\n[3/6] Извлечение событий из новостей...")

    all_events = []

    for idx, news in enumerate(news_list[:10], 1):  # Ограничим 10 новостями для демо
        print(f"   [{idx}/10] Обработка: {news.title[:60]}...")

        # AI extraction
        full_text = f"{news.title}\n{news.text_plain or ''}"
        ai_extracted = ai_ner.extract_entities(full_text, verbose=False)

        # Event extraction
        events = event_extractor.extract_events_from_news(news, ai_extracted)

        # Сохраняем события в БД
        async with async_session() as session:
            for event in events:
                session.add(event)
            await session.commit()

        all_events.extend(events)

        if events:
            for event in events:
                print(f"       → Событие: {event.event_type} (anchor={event.is_anchor}, conf={event.confidence:.2f})")

    print(f"   ✓ Извлечено {len(all_events)} событий")

    # 4. Определение причинности (CMNLN)
    print("\n[4/6] Определение причинно-следственных связей...")

    causal_links = []

    # Ищем якорные события
    anchor_events = [e for e in all_events if e.is_anchor]
    print(f"   Найдено {len(anchor_events)} якорных событий")

    for anchor in anchor_events[:3]:  # Ограничим 3 якорями для демо
        print(f"   Анализ якоря: {anchor.event_type} - {anchor.title[:50]}...")

        links = await cmnln.build_causal_chain(anchor, all_events, max_depth=2)
        causal_links.extend(links)

        if links:
            for cause, effect, relation in links:
                print(f"       → CAUSES: {cause.event_type} → {effect.event_type} " +
                      f"(conf={relation.conf_total:.2f}, sign={relation.sign})")

    print(f"   ✓ Найдено {len(causal_links)} причинных связей")

    # 5. Анализ рыночного влияния (Event Study)
    print("\n[5/6] Анализ рыночного влияния событий...")

    impact_results = []

    for event in all_events[:5]:  # Ограничим 5 событиями
        tickers = event.attrs.get("tickers", [])

        if not tickers:
            continue

        ticker = tickers[0]  # Берем первый тикер
        print(f"   Event Study: {event.event_type} → {ticker}")

        try:
            impact = await event_study.analyze_event_impact(
                event_id=str(event.id),
                secid=ticker,
                event_date=event.ts
            )

            if impact:
                impact_results.append((event, impact))
                print(f"       → AR={impact['ar']:.4f}, CAR={impact['car']:.4f}, " +
                      f"Volume Spike={impact['volume_spike']:.2f}x, " +
                      f"Significant={impact['is_significant']}")
        except Exception as e:
            print(f"       ✗ Ошибка: {e}")

    print(f"   ✓ Проанализировано {len(impact_results)} событий")

    # 6. Построение графа в Neo4j
    print("\n[6/6] Построение CEG в Neo4j...")

    # Создаем узлы событий
    for event in all_events:
        event_node = EventNode(
            id=str(event.id),
            title=event.title,
            ts=event.ts,
            type=event.event_type,
            attrs=event.attrs,
            is_anchor=event.is_anchor,
            confidence=event.confidence
        )
        await graph.create_event_ceg(event_node)

    # Создаем причинные связи
    for cause, effect, relation in causal_links:
        await graph.link_events_causes(
            cause_id=str(cause.id),
            effect_id=str(effect.id),
            causes=relation
        )

    # Создаем связи IMPACTS с инструментами
    for event, impact in impact_results:
        tickers = event.attrs.get("tickers", [])
        if tickers:
            ticker = tickers[0]

            # Создаем узел инструмента если нужно
            await graph.create_instrument_node(
                instrument_id=f"MOEX:{ticker}",
                symbol=ticker,
                instrument_type="equity",
                exchange="MOEX",
                currency="RUB"
            )

            # Связываем событие с инструментом
            impacts = ImpactsRelation(
                price_impact=impact["ar"],
                volume_impact=impact["volume_spike"],
                sentiment=1.0 if impact["ar"] > 0 else -1.0 if impact["ar"] < 0 else 0.0,
                window="1d"
            )

            await graph.link_event_impacts_instrument(
                event_id=str(event.id),
                instrument_id=f"MOEX:{ticker}",
                impacts=impacts
            )

    print(f"   ✓ Граф построен: {len(all_events)} узлов, {len(causal_links)} связей CAUSES")

    # Вывод итогов
    print("\n" + "=" * 80)
    print("ИТОГИ ДЕМО-ПАЙПЛАЙНА")
    print("=" * 80)
    print(f"✓ Обработано новостей: {len(news_list[:10])}")
    print(f"✓ Извлечено событий: {len(all_events)}")
    print(f"✓ Якорных событий: {len(anchor_events)}")
    print(f"✓ Причинных связей: {len(causal_links)}")
    print(f"✓ Event Study анализов: {len(impact_results)}")
    print("\nCEG успешно построен в Neo4j!")
    print("Откройте Neo4j Browser: http://localhost:7474")
    print("Запрос для визуализации: MATCH (e:EventNode)-[r:CAUSES]->(e2) RETURN *")
    print("=" * 80)

    # Очистка
    await moex.close()
    await graph.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
