#!/usr/bin/env python3
# scripts/test_moex_auto_search.py
"""
Тестовый скрипт для проверки автоматического поиска компаний на MOEX
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from Parser.src.services.enricher.moex_auto_search import MOEXAutoSearch
from Parser.src.services.enricher.company_aliases import get_alias_manager
from Parser.src.services.enricher.ner_extractor import NERExtractor


async def test_direct_search():
    """Тест прямого поиска"""
    print("=" * 60)
    print("ТЕСТ 1: Прямой поиск через MOEX ISS API")
    print("=" * 60)
    
    searcher = MOEXAutoSearch()
    await searcher.initialize()
    
    try:
        queries = ["Сбербанк", "Газпром", "Яндекс", "Полюс", "Норникель"]
        
        for query in queries:
            print(f"\n🔍 Поиск: {query}")
            results = await searcher.search_by_query(query, limit=3)
            
            if results:
                for i, result in enumerate(results, 1):
                    print(f"  {i}. {result.secid} - {result.shortname}")
                    print(f"     ISIN: {result.isin}")
                    print(f"     Торгуется: {'Да' if result.is_traded else 'Нет'}")
            else:
                print("  ❌ Не найдено")
    
    finally:
        await searcher.close()


async def test_best_match():
    """Тест поиска лучшего совпадения"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Поиск лучшего совпадения")
    print("=" * 60)
    
    searcher = MOEXAutoSearch()
    await searcher.initialize()
    
    try:
        companies = [
            "ПАО Сбербанк России",
            "Группа ПИК",
            "Норильский никель",
            "X5 Retail Group",
            "Московская биржа"
        ]
        
        for company in companies:
            print(f"\n🎯 {company}")
            match = await searcher.find_best_match(company)
            
            if match:
                print(f"  ✓ Найдено: {match.secid} ({match.shortname})")
                print(f"    ISIN: {match.isin}")
                print(f"    Режим: {match.primary_boardid}")
            else:
                print("  ❌ Не найдено")
    
    finally:
        await searcher.close()


async def test_auto_learning():
    """Тест автоматического обучения"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Автоматическое обучение")
    print("=" * 60)
    
    searcher = MOEXAutoSearch()
    await searcher.initialize()
    
    try:
        # Симулируем NER сущности
        ner_entities = [
            "ПАО Лукойл",
            "Газпром нефть",
            "Детский мир",
            "ВТБ банк",
            "HeadHunter"
        ]
        
        print("\n📚 Обучение на новых сущностях...")
        
        for entity in ner_entities:
            print(f"\n  Обрабатываем: {entity}")
            learned = await searcher.auto_learn_from_ner(entity, save_alias=True)
            
            if learned:
                print(f"    ✓ Выучен: {learned.secid} (ISIN: {learned.isin})")
                print(f"    Алиас сохранен: '{entity.lower()}' → '{learned.secid}'")
            else:
                print(f"    ✗ Не удалось выучить")
    
    finally:
        await searcher.close()


async def test_learned_aliases():
    """Проверка выученных алиасов"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Проверка выученных алиасов")
    print("=" * 60)
    
    manager = get_alias_manager()
    
    print(f"\n📊 Статистика алиасов:")
    print(f"  Всего алиасов: {len(manager.get_all_aliases())}")
    print(f"  Известных (ручных): {len(manager.KNOWN_ALIASES)}")
    print(f"  Выученных (авто): {len(manager.learned_aliases)}")
    
    if manager.learned_aliases:
        print(f"\n📝 Выученные алиасы:")
        for alias, ticker in manager.learned_aliases.items():
            print(f"  '{alias}' → {ticker}")
    else:
        print("\n  (Пока нет выученных алиасов)")
    
    # Тест получения алиасов для тикера
    print(f"\n🏷️  Алиасы для SBER:")
    sber_aliases = manager.get_aliases_for_ticker("SBER")
    for alias in sber_aliases:
        print(f"  - {alias}")


async def test_ner_integration():
    """Тест интеграции с NER экстрактором"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Интеграция с NER")
    print("=" * 60)
    
    # Инициализация
    ner = NERExtractor(use_ml_ner=False)  # Используем только regex
    searcher = MOEXAutoSearch()
    await searcher.initialize()
    
    try:
        # Пример новости
        text = """
        ПАО "Полюс" увеличило добычу золота на 15% в третьем квартале 2024 года.
        Компания Норильский Никель объявила о новых инвестициях в экологию.
        Газпром заключил крупный контракт на поставку газа.
        Сбербанк представил новые финансовые продукты для малого бизнеса.
        """
        
        print(f"\n📰 Обрабатываем новость...")
        print(f"Текст:\n{text[:200]}...\n")
        
        # Извлекаем сущности
        entities = ner.extract_entities(text)
        org_entities = [e for e in entities if e.type == "ORG"]
        
        print(f"🔍 Найдено организаций NER: {len(org_entities)}")
        
        # Связываем с MOEX
        print(f"\n🔗 Связывание с MOEX:")
        for entity in org_entities:
            match = await searcher.find_best_match(entity.text)
            
            if match:
                print(f"\n  {entity.text}")
                print(f"    → {match.secid} ({match.shortname})")
                print(f"    ISIN: {match.isin}")
            else:
                print(f"\n  {entity.text}")
                print(f"    → Не найдено на MOEX")
    
    finally:
        await searcher.close()


async def main():
    """Запуск всех тестов"""
    print("\n" + "🚀" * 30)
    print("ТЕСТИРОВАНИЕ АВТОПОИСКА КОМПАНИЙ НА MOEX")
    print("🚀" * 30)
    
    try:
        # Запускаем тесты последовательно
        await test_direct_search()
        await test_best_match()
        await test_auto_learning()
        await test_learned_aliases()
        
        # NER тест опционален (может не быть установлен)
        try:
            await test_ner_integration()
        except Exception as e:
            print(f"\n⚠️  NER тест пропущен: {e}")
        
        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 60)
        
        # Финальные инструкции
        print("\n📁 Проверьте файл data/learned_aliases.json")
        print("   для просмотра автоматически выученных алиасов")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Тесты прерваны пользователем")
    except Exception as e:
        print(f"\n\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

