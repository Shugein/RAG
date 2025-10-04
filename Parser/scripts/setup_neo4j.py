#!/usr/bin/env python3
# scripts/setup_neo4j.py
"""
Скрипт для настройки и тестирования Neo4j
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import settings
from src.graph_models import GraphService, News, Company, Sector, Country, NewsType, NewsSubtype


async def test_neo4j_connection():
    """Тест подключения к Neo4j"""
    print("🔌 Тестирование подключения к Neo4j...")
    
    try:
        # Создаем подключение
        graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Тестируем подключение
        async with graph.driver.session() as session:
            result = await session.run("RETURN 'Hello Neo4j!' as message")
            record = await result.single()
            print(f"✅ Подключение успешно: {record['message']}")
        
        return graph
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Neo4j: {e}")
        print("\n💡 Возможные решения:")
        print("1. Установите Neo4j Desktop: https://neo4j.com/download/")
        print("2. Или запустите через Docker:")
        print("   docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest")
        print("3. Или используйте Neo4j AuraDB (облачная версия)")
        return None


async def create_sample_data(graph: GraphService):
    """Создание тестовых данных"""
    print("\n📊 Создание тестовых данных...")
    
    try:
        async with graph.driver.session() as session:
            # 1. Создаем констрейнты
            await graph.create_constraints()
            print("✅ Констрейнты созданы")
            
            # 2. Создаем тестовую новость
            news = News(
                id="test_news_1",
                url="https://example.com/news1",
                title="Сбербанк отчитался о рекордной прибыли в третьем квартале",
                text="ПАО Сбербанк объявил о росте чистой прибыли на 25% в третьем квартале 2024 года. Выручка банка составила 1.2 трлн рублей.",
                lang_orig="ru",
                lang_norm="ru",
                published_at=datetime.utcnow(),
                source="test",
                news_type=NewsType.ONE_COMPANY,
                news_subtype=NewsSubtype.EARNINGS
            )
            
            await graph.upsert_news(news)
            print("✅ Новость создана")
            
            # 3. Создаем сектор
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
            print("✅ Сектор создан")
            
            # 4. Создаем страну
            await session.run("""
                MERGE (c:Country {
                    code: "RU",
                    name: "Россия"
                })
            """)
            print("✅ Страна создана")
            
            # 5. Создаем компанию
            await session.run("""
                MERGE (comp:Company {
                    id: "sber",
                    name: "ПАО Сбербанк",
                    ticker: "SBER",
                    country_code: "RU"
                })
            """)
            print("✅ Компания создана")
            
            # 6. Создаем связи
            await session.run("""
                MATCH (n:News {id: "test_news_1"})
                MATCH (s:Sector {id: "9010"})
                MATCH (c:Country {code: "RU"})
                MATCH (comp:Company {id: "sber"})
                MERGE (n)-[:ABOUT_SECTOR]->(s)
                MERGE (n)-[:ABOUT_COUNTRY]->(c)
                MERGE (n)-[:ABOUT]->(comp)
                MERGE (comp)-[:BELONGS_TO]->(s)
            """)
            print("✅ Связи созданы")
            
    except Exception as e:
        print(f"❌ Ошибка создания данных: {e}")


async def query_sample_data(graph: GraphService):
    """Запрос тестовых данных"""
    print("\n🔍 Запрос тестовых данных...")
    
    try:
        async with graph.driver.session() as session:
            # 1. Все новости
            print("\n📰 Все новости:")
            result = await session.run("MATCH (n:News) RETURN n.id, n.title, n.news_type, n.news_subtype")
            async for record in result:
                print(f"  ID: {record['n.id']}")
                print(f"  Заголовок: {record['n.title']}")
                print(f"  Тип: {record['n.news_type']}")
                print(f"  Подтип: {record['n.news_subtype']}")
                print()
            
            # 2. Все секторы
            print("🏭 Все секторы:")
            result = await session.run("MATCH (s:Sector) RETURN s.id, s.name, s.taxonomy, s.level")
            async for record in result:
                print(f"  ID: {record['s.id']}, Название: {record['s.name']}, Таксономия: {record['s.taxonomy']}, Уровень: {record['s.level']}")
            
            # 3. Все страны
            print("\n🌍 Все страны:")
            result = await session.run("MATCH (c:Country) RETURN c.code, c.name")
            async for record in result:
                print(f"  Код: {record['c.code']}, Название: {record['c.name']}")
            
            # 4. Все компании
            print("\n🏢 Все компании:")
            result = await session.run("MATCH (comp:Company) RETURN comp.id, comp.name, comp.ticker, comp.country_code")
            async for record in result:
                print(f"  ID: {record['comp.id']}, Название: {record['comp.name']}, Тикер: {record['comp.ticker']}, Страна: {record['comp.country_code']}")
            
            # 5. Связи новостей
            print("\n🔗 Связи новостей:")
            result = await session.run("""
                MATCH (n:News)-[r]->(target)
                RETURN n.id, type(r) as relationship, labels(target) as target_type, target.id as target_id, target.name as target_name
            """)
            async for record in result:
                print(f"  {record['n.id']} -[{record['relationship']}]-> {record['target_type']} ({record['target_id']}: {record['target_name']})")
            
            # 6. Связи компаний
            print("\n🏢 Связи компаний:")
            result = await session.run("""
                MATCH (comp:Company)-[r]->(target)
                RETURN comp.name, type(r) as relationship, labels(target) as target_type, target.name as target_name
            """)
            async for record in result:
                print(f"  {record['comp.name']} -[{record['relationship']}]-> {record['target_type']} ({record['target_name']})")
            
    except Exception as e:
        print(f"❌ Ошибка запроса данных: {e}")


async def run_cypher_queries(graph: GraphService):
    """Запуск полезных Cypher запросов"""
    print("\n🔍 Полезные Cypher запросы:")
    
    queries = {
        "Все узлы и связи": """
            MATCH (n)-[r]->(m)
            RETURN n, r, m
            LIMIT 10
        """,
        "Статистика узлов": """
            MATCH (n)
            RETURN labels(n) as node_type, count(n) as count
            ORDER BY count DESC
        """,
        "Статистика связей": """
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(r) as count
            ORDER BY count DESC
        """,
        "Новости по секторам": """
            MATCH (n:News)-[:ABOUT_SECTOR]->(s:Sector)
            RETURN s.name as sector, count(n) as news_count
            ORDER BY news_count DESC
        """,
        "Новости по странам": """
            MATCH (n:News)-[:ABOUT_COUNTRY]->(c:Country)
            RETURN c.name as country, count(n) as news_count
            ORDER BY news_count DESC
        """,
        "Компании по секторам": """
            MATCH (comp:Company)-[:BELONGS_TO]->(s:Sector)
            RETURN s.name as sector, collect(comp.name) as companies
            ORDER BY size(companies) DESC
        """
    }
    
    try:
        async with graph.driver.session() as session:
            for name, query in queries.items():
                print(f"\n📊 {name}:")
                result = await session.run(query)
                async for record in result:
                    print(f"  {dict(record)}")
                    
    except Exception as e:
        print(f"❌ Ошибка выполнения запросов: {e}")


async def main():
    """Главная функция"""
    print("🚀" * 30)
    print("НАСТРОЙКА И ТЕСТИРОВАНИЕ NEO4J")
    print("🚀" * 30)
    
    # Тестируем подключение
    graph = await test_neo4j_connection()
    
    if graph:
        try:
            # Создаем тестовые данные
            await create_sample_data(graph)
            
            # Запрашиваем данные
            await query_sample_data(graph)
            
            # Запускаем полезные запросы
            await run_cypher_queries(graph)
            
            print("\n✅ Тестирование завершено успешно!")
            print("\n💡 Для просмотра данных в Neo4j Browser:")
            print(f"   1. Откройте http://localhost:7474")
            print(f"   2. Войдите с логином: {settings.NEO4J_USER}")
            print(f"   3. Паролем: {settings.NEO4J_PASSWORD}")
            print("   4. Выполните запросы из скрипта")
            
        finally:
            await graph.close()
    else:
        print("\n❌ Не удалось подключиться к Neo4j")
        print("Пожалуйста, установите и запустите Neo4j перед тестированием")


if __name__ == "__main__":
    asyncio.run(main())
