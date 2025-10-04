#!/usr/bin/env python3
# scripts/test_topic_classifier.py
"""
Тестовый скрипт для проверки TopicClassifier
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.enricher.topic_classifier import TopicClassifier, ClassificationResult
from src.services.enricher.sector_mapper import SectorMapper, SectorTaxonomy
from src.graph_models import News, Company, NewsType, NewsSubtype


async def test_sector_mapper():
    """Тест SectorMapper"""
    print("=" * 60)
    print("ТЕСТ 1: SectorMapper")
    print("=" * 60)
    
    mapper = SectorMapper(SectorTaxonomy.ICB)
    
    # Тест по тикерам
    test_tickers = ["SBER", "GAZP", "YNDX", "MGNT", "GMKN", "MTSS"]
    
    print("\n🏷️  Классификация по тикерам:")
    for ticker in test_tickers:
        sector = mapper.get_sector_by_ticker(ticker)
        if sector:
            print(f"  {ticker}: {sector.name} (ID: {sector.id}, Level: {sector.level})")
        else:
            print(f"  {ticker}: Не найдено")
    
    # Тест по ключевым словам
    test_keywords = [
        ["банк", "кредит", "финансы"],
        ["нефть", "газ", "энергия"],
        ["технологии", "софт", "интернет"],
        ["ритейл", "торговля", "магазин"],
        ["металлы", "добыча", "шахта"]
    ]
    
    print("\n🔍 Классификация по ключевым словам:")
    for keywords in test_keywords:
        sector = mapper.get_sector_by_keywords(keywords)
        if sector:
            print(f"  {keywords}: {sector.name} (ID: {sector.id})")
        else:
            print(f"  {keywords}: Не найдено")
    
    # Тест иерархии
    print("\n🌳 Иерархия банковского сектора:")
    hierarchy = mapper.get_sector_hierarchy("9010")
    for parent in hierarchy["parents"]:
        print(f"  Родитель: {parent.name}")
    print(f"  Текущий: {hierarchy['current'][0].name}")
    for child in hierarchy["children"]:
        print(f"  Дочерний: {child.name}")


async def test_topic_classifier():
    """Тест TopicClassifier"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: TopicClassifier")
    print("=" * 60)
    
    classifier = TopicClassifier(taxonomy=SectorTaxonomy.ICB)
    await classifier.initialize()
    
    try:
        # Тестовые новости
        test_cases = [
            {
                "title": "Сбербанк отчитался о рекордной прибыли в третьем квартале",
                "text": "ПАО Сбербанк объявил о росте чистой прибыли на 25% в третьем квартале 2024 года. Выручка банка составила 1.2 трлн рублей.",
                "companies": [
                    Company(id="sber", name="ПАО Сбербанк", ticker="SBER", country_code="RU")
                ],
                "expected_sector": "9010",  # Banks
                "expected_type": NewsType.ONE_COMPANY,
                "expected_subtype": NewsSubtype.EARNINGS
            },
            {
                "title": "Газпром увеличил добычу газа на 15%",
                "text": "Российская компания Газпром сообщила об увеличении добычи природного газа на 15% по сравнению с прошлым годом.",
                "companies": [
                    Company(id="gazp", name="ПАО Газпром", ticker="GAZP", country_code="RU")
                ],
                "expected_sector": "1010",  # Oil & Gas
                "expected_type": NewsType.ONE_COMPANY,
                "expected_subtype": None
            },
            {
                "title": "Российский рынок показал рост на фоне новостей о санкциях",
                "text": "Московская биржа закрылась в плюсе на фоне новостей о новых санкциях США против российских компаний.",
                "companies": [],
                "expected_sector": None,
                "expected_type": NewsType.MARKET,
                "expected_subtype": NewsSubtype.SANCTIONS
            },
            {
                "title": "Яндекс представил новую технологию искусственного интеллекта",
                "text": "Российская IT-компания Яндекс анонсировала запуск новой платформы на базе машинного обучения.",
                "companies": [
                    Company(id="yndx", name="Яндекс НВ", ticker="YNDX", country_code="RU")
                ],
                "expected_sector": "9510",  # Software
                "expected_type": NewsType.ONE_COMPANY,
                "expected_subtype": None
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📰 Тест {i}: {case['title'][:50]}...")
            
            # Создаем новость
            news = News(
                id=f"test_news_{i}",
                url=f"https://example.com/news{i}",
                title=case["title"],
                text=case["text"],
                lang_orig="ru",
                lang_norm="ru",
                published_at=datetime.utcnow(),
                source="test"
            )
            
            # Классифицируем
            result = await classifier.classify_news(news, case["companies"])
            
            # Выводим результаты
            print(f"  🏭 Сектор: {result.primary_sector} (ожидался: {case['expected_sector']})")
            print(f"  🌍 Страна: {result.primary_country}")
            print(f"  📰 Тип: {result.news_type} (ожидался: {case['expected_type']})")
            print(f"  🏷️  Подтип: {result.news_subtype} (ожидался: {case['expected_subtype']})")
            print(f"  🏷️  Теги: {result.tags}")
            print(f"  📊 Рыночная: {result.is_market_wide}")
            print(f"  ⚖️  Регуляторная: {result.is_regulatory}")
            
            # Создаем связи в графе
            await classifier.create_graph_relationships(news, result, case["companies"])
            print(f"  ✅ Связи созданы в графе")
        
        # Статистика
        print(f"\n📊 Статистика классификатора:")
        stats = classifier.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    finally:
        await classifier.close()


async def test_country_classification():
    """Тест классификации по странам"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Классификация по странам")
    print("=" * 60)
    
    classifier = TopicClassifier()
    await classifier.initialize()
    
    try:
        test_cases = [
            {
                "title": "Российские компании под санкциями США",
                "text": "США ввели новые санкции против российских банков. Китай выразил поддержку России.",
                "expected_countries": ["RU", "US", "CN"]
            },
            {
                "title": "Европейские рынки упали на фоне новостей из Германии",
                "text": "Немецкие акции показали худший результат за месяц. Франция и Великобритания также в минусе.",
                "expected_countries": ["DE", "FR", "GB"]
            },
            {
                "title": "Японские технологии в России",
                "text": "Российская компания заключила партнерство с японской корпорацией.",
                "expected_countries": ["RU", "JP"]
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n🌍 Тест {i}: {case['title']}")
            
            news = News(
                id=f"country_test_{i}",
                url=f"https://example.com/country{i}",
                title=case["title"],
                text=case["text"],
                lang_orig="ru",
                lang_norm="ru",
                published_at=datetime.utcnow(),
                source="test"
            )
            
            result = await classifier.classify_news(news)
            
            print(f"  Найдено стран: {result.countries_mentioned}")
            print(f"  Основная: {result.primary_country}")
            print(f"  Ожидалось: {case['expected_countries']}")
            
            # Проверяем совпадения
            found_countries = set(result.countries_mentioned or [])
            expected_countries = set(case['expected_countries'])
            matches = found_countries.intersection(expected_countries)
            print(f"  Совпадений: {len(matches)}/{len(expected_countries)}")
    
    finally:
        await classifier.close()


async def test_news_type_classification():
    """Тест классификации типов новостей"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Классификация типов новостей")
    print("=" * 60)
    
    classifier = TopicClassifier()
    await classifier.initialize()
    
    try:
        test_cases = [
            {
                "title": "Сбербанк объявил о выплате дивидендов",
                "text": "ПАО Сбербанк принял решение о выплате дивидендов в размере 25 рублей на акцию.",
                "expected_type": NewsType.ONE_COMPANY,
                "expected_subtype": NewsSubtype.EARNINGS
            },
            {
                "title": "ЦБ РФ повысил ключевую ставку",
                "text": "Банк России повысил ключевую ставку на 1 процентный пункт до 16%.",
                "expected_type": NewsType.REGULATORY,
                "expected_subtype": None
            },
            {
                "title": "Московская биржа закрылась в плюсе",
                "text": "Индекс МосБиржи вырос на 2.5% на фоне позитивных новостей.",
                "expected_type": NewsType.MARKET,
                "expected_subtype": None
            },
            {
                "title": "Хакеры атаковали банковские системы",
                "text": "Кибератака на российские банки привела к временному отключению сервисов.",
                "expected_type": NewsType.REGULATORY,
                "expected_subtype": NewsSubtype.HACK
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📰 Тест {i}: {case['title']}")
            
            news = News(
                id=f"type_test_{i}",
                url=f"https://example.com/type{i}",
                title=case["title"],
                text=case["text"],
                lang_orig="ru",
                lang_norm="ru",
                published_at=datetime.utcnow(),
                source="test"
            )
            
            result = await classifier.classify_news(news)
            
            print(f"  Тип: {result.news_type} (ожидался: {case['expected_type']})")
            print(f"  Подтип: {result.news_subtype} (ожидался: {case['expected_subtype']})")
            print(f"  Уверенность: {result.type_confidence:.2f}")
            print(f"  Рыночная: {result.is_market_wide}")
            print(f"  Регуляторная: {result.is_regulatory}")
            print(f"  Теги: {result.tags}")
    
    finally:
        await classifier.close()


async def main():
    """Запуск всех тестов"""
    print("\n" + "🚀" * 30)
    print("ТЕСТИРОВАНИЕ TOPIC CLASSIFIER")
    print("🚀" * 30)
    
    try:
        # Запускаем тесты последовательно
        await test_sector_mapper()
        await test_topic_classifier()
        await test_country_classification()
        await test_news_type_classification()
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 60)
        
        print("\n📁 Проверьте Neo4j для просмотра созданных связей:")
        print("   - Секторы: MATCH (s:Sector) RETURN s")
        print("   - Страны: MATCH (c:Country) RETURN c")
        print("   - Связи новостей: MATCH (n:News)-[r]->(target) RETURN n, r, target")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Тесты прерваны пользователем")
    except Exception as e:
        print(f"\n\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
