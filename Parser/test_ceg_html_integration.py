# test_ceg_html_integration.py
"""
Тестовый скрипт для проверки интеграции HTML парсеров в CEG систему
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.core.database import init_db, close_db, get_db_session
from src.core.models import Source, SourceKind
from src.services.html_parser.html_parser_service import HTMLParserService
from sqlalchemy import select


async def test_html_sources_configuration():
    """Тест конфигурации HTML источников"""
    print("🔍 Testing HTML sources configuration...")
    
    try:
        await init_db()
        
        async with get_db_session() as session:
            # Проверяем наличие HTML источников в БД
            result = await session.execute(
                select(Source).where(
                    Source.kind == SourceKind.HTML,
                    Source.enabled == True
                )
            )
            html_sources = result.scalars().all()
            
            if not html_sources:
                print("❌ No HTML sources found in database")
                print("   Please run: python scripts/load_sources.py")
                return False
            
            print(f"   ✅ Found {len(html_sources)} HTML sources:")
            for source in html_sources:
                print(f"      - {source.code}: {source.name}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing HTML sources: {e}")
        return False
    finally:
        await close_db()


async def test_html_parser_service():
    """Тест HTML parser service"""
    print("🔍 Testing HTML parser service...")
    
    try:
        await init_db()
        
        async with get_db_session() as session:
            # Создаем HTML parser service
            service = HTMLParserService(session, use_local_ai=True)
            
            # Проверяем доступные парсеры
            parsers = service.get_available_parsers()
            print(f"   ✅ Available parsers: {parsers}")
            
            # Проверяем, что есть парсеры для наших источников
            if 'forbes' in parsers and 'interfax' in parsers:
                print("   ✅ Forbes and Interfax parsers available")
            else:
                print("   ❌ Missing parsers for Forbes or Interfax")
                return False
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing HTML parser service: {e}")
        return False
    finally:
        await close_db()


async def test_ceg_integration():
    """Тест интеграции с CEG системой"""
    print("🔍 Testing CEG integration...")
    
    try:
        await init_db()
        
        async with get_db_session() as session:
            # Проверяем наличие всех типов источников
            telegram_result = await session.execute(
                select(Source).where(
                    Source.kind == SourceKind.TELEGRAM,
                    Source.enabled == True
                )
            )
            telegram_sources = telegram_result.scalars().all()
            
            html_result = await session.execute(
                select(Source).where(
                    Source.kind == SourceKind.HTML,
                    Source.enabled == True
                )
            )
            html_sources = html_result.scalars().all()
            
            total_sources = len(telegram_sources) + len(html_sources)
            
            if total_sources == 0:
                print("   ❌ No active sources found")
                return False
            
            print(f"   ✅ Found {len(telegram_sources)} Telegram sources")
            print(f"   ✅ Found {len(html_sources)} HTML sources")
            print(f"   ✅ Total sources: {total_sources}")
            
            # Проверяем конфигурацию источников
            for source in html_sources:
                config = source.config or {}
                if 'poll_interval' in config:
                    print(f"   ✅ {source.code}: poll_interval = {config['poll_interval']}s")
                else:
                    print(f"   ⚠️ {source.code}: no poll_interval configured")
            
            return True
            
    except Exception as e:
        print(f"❌ Error testing CEG integration: {e}")
        return False
    finally:
        await close_db()


async def test_html_parsing_simulation():
    """Тест симуляции HTML парсинга"""
    print("🔍 Testing HTML parsing simulation...")
    
    try:
        await init_db()
        
        async with get_db_session() as session:
            # Получаем HTML источники
            result = await session.execute(
                select(Source).where(
                    Source.kind == SourceKind.HTML,
                    Source.enabled == True
                ).limit(1)
            )
            source = result.scalar_one_or_none()
            
            if not source:
                print("   ❌ No HTML sources available for testing")
                return False
            
            print(f"   ✅ Testing with source: {source.name} ({source.code})")
            
            # Создаем HTML parser service
            service = HTMLParserService(session, use_local_ai=True)
            
            # Тестируем парсинг с ограниченным количеством статей
            print(f"   🔄 Parsing up to 3 articles from {source.code}...")
            
            stats = await service.parse_specific_source(source.code, max_articles=3)
            
            if 'error' in stats:
                print(f"   ❌ Parsing failed: {stats['error']}")
                return False
            else:
                print(f"   ✅ Parsing completed: {stats}")
                return True
            
    except Exception as e:
        print(f"❌ Error in HTML parsing simulation: {e}")
        return False
    finally:
        await close_db()


async def test_ceg_script_import():
    """Тест импорта CEG скрипта"""
    print("🔍 Testing CEG script import...")
    
    try:
        # Пробуем импортировать обновленный CEG скрипт
        import sys
        sys.path.insert(0, str(Path("scripts")))
        
        from start_telegram_parser_ceg import TelegramParserServiceCEG
        
        print("   ✅ CEG script imports successfully")
        
        # Проверяем, что класс имеет новые методы
        if hasattr(TelegramParserServiceCEG, '_monitor_html_source_batch'):
            print("   ✅ HTML monitoring method found")
        else:
            print("   ❌ HTML monitoring method not found")
            return False
        
        if hasattr(TelegramParserServiceCEG, '_collect_html_news_batch'):
            print("   ✅ HTML news collection method found")
        else:
            print("   ❌ HTML news collection method not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error importing CEG script: {e}")
        return False


async def main():
    """Основная функция тестирования"""
    print("🚀 Testing CEG HTML Integration")
    print("=" * 50)
    
    results = []
    
    # Тест 1: Конфигурация HTML источников
    results.append(await test_html_sources_configuration())
    print()
    
    # Тест 2: HTML parser service
    results.append(await test_html_parser_service())
    print()
    
    # Тест 3: CEG интеграция
    results.append(await test_ceg_integration())
    print()
    
    # Тест 4: Симуляция HTML парсинга
    results.append(await test_html_parsing_simulation())
    print()
    
    # Тест 5: Импорт CEG скрипта
    results.append(await test_ceg_script_import())
    print()
    
    # Результаты
    print("=" * 50)
    print("📊 Test Results:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"   Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! CEG HTML integration is working correctly.")
        print()
        print("✅ Ready to run:")
        print("   .\start_ceg_parser.ps1")
        print("   python scripts/start_telegram_parser_ceg.py")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
