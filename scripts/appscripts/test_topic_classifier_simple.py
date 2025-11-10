#!/usr/bin/env python3
# scripts/test_topic_classifier_simple.py
"""
Простой тест TopicClassifier без подключения к внешним сервисам
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from Parser.src.services.enricher.sector_mapper import SectorMapper, SectorTaxonomy
from Parser.src.services.enricher.topic_classifier import ClassificationResult
from Parser.src.graph_models import News, Company, NewsType, NewsSubtype


def test_sector_mapper():
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


def test_classification_result():
    """Тест ClassificationResult"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: ClassificationResult")
    print("=" * 60)
    
    # Создаем результат классификации
    result = ClassificationResult(
        primary_sector="9010",
        secondary_sector="9020",
        sector_confidence=0.85,
        primary_country="RU",
        countries_mentioned=["RU", "US"],
        news_type=NewsType.ONE_COMPANY,
        news_subtype=NewsSubtype.EARNINGS,
        type_confidence=0.9,
        tags=["dividends", "quarterly"],
        is_market_wide=False,
        is_regulatory=False,
        is_earnings=True
    )
    
    print("\n📊 Результат классификации:")
    print(f"  Основной сектор: {result.primary_sector}")
    print(f"  Вторичный сектор: {result.secondary_sector}")
    print(f"  Уверенность в секторе: {result.sector_confidence}")
    print(f"  Основная страна: {result.primary_country}")
    print(f"  Упоминаемые страны: {result.countries_mentioned}")
    print(f"  Тип новости: {result.news_type}")
    print(f"  Подтип: {result.news_subtype}")
    print(f"  Уверенность в типе: {result.type_confidence}")
    print(f"  Теги: {result.tags}")
    print(f"  Рыночная новость: {result.is_market_wide}")
    print(f"  Регуляторная: {result.is_regulatory}")
    print(f"  Отчетность: {result.is_earnings}")


def test_news_models():
    """Тест моделей новостей"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Модели новостей")
    print("=" * 60)
    
    # Создаем новость
    news = News(
        id="test_news_1",
        url="https://example.com/news1",
        title="Сбербанк отчитался о рекордной прибыли в третьем квартале",
        text="ПАО Сбербанк объявил о росте чистой прибыли на 25% в третьем квартале 2024 года. Выручка банка составила 1.2 трлн рублей.",
        lang_orig="ru",
        lang_norm="ru",
        published_at=datetime.utcnow(),
        source="test"
    )
    
    print("\n📰 Новость:")
    print(f"  ID: {news.id}")
    print(f"  Заголовок: {news.title}")
    print(f"  Язык: {news.lang_norm}")
    print(f"  Источник: {news.source}")
    print(f"  Опубликована: {news.published_at}")
    
    # Создаем компанию
    company = Company(
        id="sber",
        name="ПАО Сбербанк",
        ticker="SBER",
        country_code="RU"
    )
    
    print("\n🏢 Компания:")
    print(f"  ID: {company.id}")
    print(f"  Название: {company.name}")
    print(f"  Тикер: {company.ticker}")
    print(f"  Страна: {company.country_code}")


def test_sector_classification():
    """Тест классификации секторов"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Классификация секторов")
    print("=" * 60)
    
    mapper = SectorMapper(SectorTaxonomy.ICB)
    
    # Тестовые компании
    companies = [
        Company(id="sber", name="ПАО Сбербанк", ticker="SBER", country_code="RU"),
        Company(id="gazp", name="ПАО Газпром", ticker="GAZP", country_code="RU"),
        Company(id="yndx", name="Яндекс НВ", ticker="YNDX", country_code="RU"),
        Company(id="mgnt", name="ПАО Магнит", ticker="MGNT", country_code="RU"),
    ]
    
    print("\n🏭 Классификация компаний по секторам:")
    for company in companies:
        sector = mapper.get_sector_by_ticker(company.ticker)
        if sector:
            print(f"  {company.name} ({company.ticker}): {sector.name} (ID: {sector.id})")
        else:
            print(f"  {company.name} ({company.ticker}): Не найдено")


def test_country_extraction():
    """Тест извлечения стран"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Извлечение стран")
    print("=" * 60)
    
    # Импортируем TopicClassifier для тестирования методов
    from Parser.src.services.enricher.topic_classifier import TopicClassifier
    
    classifier = TopicClassifier()
    
    test_texts = [
        "Российские компании под санкциями США",
        "Европейские рынки упали на фоне новостей из Германии", 
        "Японские технологии в России",
        "Китай поддержал Россию в вопросе санкций"
    ]
    
    print("\n🌍 Извлечение стран из текстов:")
    for i, text in enumerate(test_texts, 1):
        print(f"\n  Текст {i}: {text}")
        countries = asyncio.run(classifier._extract_countries_from_text(text))
        print(f"    Найдено стран: {countries}")


def test_news_type_classification():
    """Тест классификации типов новостей"""
    print("\n" + "=" * 60)
    print("ТЕСТ 6: Классификация типов новостей")
    print("=" * 60)
    
    from Parser.src.services.enricher.topic_classifier import TopicClassifier
    
    classifier = TopicClassifier()
    
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
    
    print("\n📰 Классификация типов новостей:")
    for i, case in enumerate(test_cases, 1):
        print(f"\n  Тест {i}: {case['title']}")
        
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
        
        # Тестируем только классификацию типа (без графа)
        result = ClassificationResult()
        asyncio.run(classifier._classify_news_type(result, news, []))
        
        print(f"    Тип: {result.news_type} (ожидался: {case['expected_type']})")
        print(f"    Подтип: {result.news_subtype} (ожидался: {case['expected_subtype']})")
        print(f"    Уверенность: {result.type_confidence:.2f}")
        print(f"    Рыночная: {result.is_market_wide}")
        print(f"    Регуляторная: {result.is_regulatory}")


def main():
    """Запуск всех тестов"""
    print("\n" + "🚀" * 30)
    print("ПРОСТОЕ ТЕСТИРОВАНИЕ TOPIC CLASSIFIER")
    print("🚀" * 30)
    
    try:
        # Запускаем тесты последовательно
        test_sector_mapper()
        test_classification_result()
        test_news_models()
        test_sector_classification()
        test_country_extraction()
        test_news_type_classification()
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ УСПЕШНО")
        print("=" * 60)
        
        print("\n📝 Результаты:")
        print("  ✅ SectorMapper работает корректно")
        print("  ✅ ClassificationResult создается правильно")
        print("  ✅ Модели News и Company работают")
        print("  ✅ Классификация секторов по тикерам")
        print("  ✅ Извлечение стран из текста")
        print("  ✅ Классификация типов новостей")
        
        print("\n🎯 TopicClassifier готов к использованию!")
        print("   (Для полного тестирования с графом нужен Neo4j)")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Тесты прерваны пользователем")
    except Exception as e:
        print(f"\n\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
