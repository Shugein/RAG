#!/usr/bin/env python3
# scripts/test_neo4j_connection.py
"""
Скрипт для тестирования подключения к Neo4j
Поддерживает различные способы подключения
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.graph_models import GraphService, News, Company, NewsType, NewsSubtype


async def test_connection(uri: str, user: str, password: str, description: str):
    """Тест подключения к Neo4j"""
    print(f"\n🔌 Тестирование: {description}")
    print(f"   URI: {uri}")
    print(f"   User: {user}")
    
    try:
        graph = GraphService(uri=uri, user=user, password=password)
        
        # Тестируем подключение
        async with graph.driver.session() as session:
            result = await session.run("RETURN 'Hello Neo4j!' as message, datetime() as time")
            record = await result.single()
            print(f"   ✅ Подключение успешно!")
            print(f"   📝 Сообщение: {record['message']}")
            print(f"   ⏰ Время: {record['time']}")
            
            # Тестируем создание констрейнтов
            await graph.create_constraints()
            print(f"   ✅ Констрейнты созданы")
            
            return graph
            
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return None


async def create_demo_data(graph: GraphService):
    """Создание демо данных"""
    print("\n📊 Создание демо данных...")
    
    try:
        async with graph.driver.session() as session:
            # 1. Создаем новость
            news = News(
                id="demo_news_1",
                url="https://example.com/demo1",
                title="Сбербанк отчитался о рекордной прибыли",
                text="ПАО Сбербанк объявил о росте прибыли на 25% в третьем квартале 2024 года.",
                lang_orig="ru",
                lang_norm="ru",
                published_at=datetime.utcnow(),
                source="demo",
                news_type=NewsType.ONE_COMPANY,
                news_subtype=NewsSubtype.EARNINGS
            )
            
            await graph.upsert_news(news)
            print("   ✅ Новость создана")
            
            # 2. Создаем сектор
            await session.run("""
                MERGE (s:Sector {
                    id: "9010",
                    name: "Banks",
                    taxonomy: "ICB",
                    level: 2,
                    parent_id: "9000",
                    description: "Banking sector"
                })
            """)
            print("   ✅ Сектор создан")
            
            # 3. Создаем страну
            await session.run("""
                MERGE (c:Country {
                    code: "RU",
                    name: "Россия"
                })
            """)
            print("   ✅ Страна создана")
            
            # 4. Создаем компанию
            await session.run("""
                MERGE (comp:Company {
                    id: "sber",
                    name: "ПАО Сбербанк",
                    ticker: "SBER",
                    country_code: "RU"
                })
            """)
            print("   ✅ Компания создана")
            
            # 5. Создаем связи
            await session.run("""
                MATCH (n:News {id: "demo_news_1"})
                MATCH (s:Sector {id: "9010"})
                MATCH (c:Country {code: "RU"})
                MATCH (comp:Company {id: "sber"})
                MERGE (n)-[:ABOUT_SECTOR]->(s)
                MERGE (n)-[:ABOUT_COUNTRY]->(c)
                MERGE (n)-[:ABOUT]->(comp)
                MERGE (comp)-[:BELONGS_TO]->(s)
            """)
            print("   ✅ Связи созданы")
            
    except Exception as e:
        print(f"   ❌ Ошибка создания данных: {e}")


async def query_demo_data(graph: GraphService):
    """Запрос демо данных"""
    print("\n🔍 Запрос демо данных...")
    
    try:
        async with graph.driver.session() as session:
            # 1. Все новости
            print("\n📰 Новости:")
            result = await session.run("MATCH (n:News) RETURN n.id, n.title, n.news_type, n.news_subtype")
            async for record in result:
                print(f"   ID: {record['n.id']}")
                print(f"   Заголовок: {record['n.title']}")
                print(f"   Тип: {record['n.news_type']}")
                print(f"   Подтип: {record['n.news_subtype']}")
                print()
            
            # 2. Все секторы
            print("🏭 Секторы:")
            result = await session.run("MATCH (s:Sector) RETURN s.id, s.name, s.taxonomy, s.level")
            async for record in result:
                print(f"   ID: {record['s.id']}, Название: {record['s.name']}, Таксономия: {record['s.taxonomy']}, Уровень: {record['s.level']}")
            
            # 3. Все страны
            print("\n🌍 Страны:")
            result = await session.run("MATCH (c:Country) RETURN c.code, c.name")
            async for record in result:
                print(f"   Код: {record['c.code']}, Название: {record['c.name']}")
            
            # 4. Все компании
            print("\n🏢 Компании:")
            result = await session.run("MATCH (comp:Company) RETURN comp.id, comp.name, comp.ticker, comp.country_code")
            async for record in result:
                print(f"   ID: {record['comp.id']}, Название: {record['comp.name']}, Тикер: {record['comp.ticker']}, Страна: {record['comp.country_code']}")
            
            # 5. Связи
            print("\n🔗 Связи:")
            result = await session.run("""
                MATCH (n)-[r]->(m)
                RETURN labels(n)[0] as from_type, n.id as from_id, type(r) as relationship, labels(m)[0] as to_type, m.id as to_id
                ORDER BY from_type, relationship
            """)
            async for record in result:
                print(f"   {record['from_type']}({record['from_id']}) -[{record['relationship']}]-> {record['to_type']}({record['to_id']})")
            
    except Exception as e:
        print(f"   ❌ Ошибка запроса данных: {e}")


async def run_useful_queries(graph: GraphService):
    """Запуск полезных запросов"""
    print("\n🔍 Полезные запросы:")
    
    queries = [
        ("Статистика узлов", "MATCH (n) RETURN labels(n) as node_type, count(n) as count ORDER BY count DESC"),
        ("Статистика связей", "MATCH ()-[r]->() RETURN type(r) as relationship_type, count(r) as count ORDER BY count DESC"),
        ("Новости по секторам", "MATCH (n:News)-[:ABOUT_SECTOR]->(s:Sector) RETURN s.name as sector, count(n) as news_count ORDER BY news_count DESC"),
        ("Новости по странам", "MATCH (n:News)-[:ABOUT_COUNTRY]->(c:Country) RETURN c.name as country, count(n) as news_count ORDER BY news_count DESC"),
        ("Компании по секторам", "MATCH (comp:Company)-[:BELONGS_TO]->(s:Sector) RETURN s.name as sector, collect(comp.name) as companies ORDER BY size(companies) DESC")
    ]
    
    try:
        async with graph.driver.session() as session:
            for name, query in queries:
                print(f"\n📊 {name}:")
                result = await session.run(query)
                async for record in result:
                    print(f"   {dict(record)}")
                    
    except Exception as e:
        print(f"   ❌ Ошибка выполнения запросов: {e}")


async def main():
    """Главная функция"""
    print("🚀" * 30)
    print("ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ К NEO4J")
    print("🚀" * 30)
    
    # Список вариантов подключения
    connections = [
        {
            "uri": settings.NEO4J_URI,
            "user": settings.NEO4J_USER,
            "password": settings.NEO4J_PASSWORD,
            "description": "Локальная настройка (config.py)"
        },
        {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "password",
            "description": "Локальный Neo4j (Docker)"
        },
        {
            "uri": "bolt://localhost:7687",
            "user": "neo4j",
            "password": "neo4j",
            "description": "Локальный Neo4j (стандартный пароль)"
        }
    ]
    
    # Тестируем подключения
    working_connection = None
    for conn in connections:
        graph = await test_connection(conn["uri"], conn["user"], conn["password"], conn["description"])
        if graph:
            working_connection = graph
            break
    
    if working_connection:
        try:
            # Создаем демо данные
            await create_demo_data(working_connection)
            
            # Запрашиваем данные
            await query_demo_data(working_connection)
            
            # Запускаем полезные запросы
            await run_useful_queries(working_connection)
            
            print("\n✅ Тестирование завершено успешно!")
            print("\n💡 Для просмотра данных в Neo4j Browser:")
            print("   1. Откройте http://localhost:7474 (если локальный)")
            print("   2. Или используйте Neo4j Desktop")
            print("   3. Или Neo4j AuraDB (облачная версия)")
            
        finally:
            await working_connection.close()
    else:
        print("\n❌ Не удалось подключиться к Neo4j")
        print("\n💡 Варианты решения:")
        print("1. Установите Docker Desktop и запустите: .\start_neo4j.ps1")
        print("2. Установите Neo4j Desktop: https://neo4j.com/download/")
        print("3. Используйте Neo4j AuraDB (облачная версия)")
        print("4. Настройте подключение в .env файле")


if __name__ == "__main__":
    asyncio.run(main())
