# test_html_parsers.py
"""
Тестовый скрипт для проверки HTML парсеров
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent))

from src.core.database import init_db, close_db, get_db_session
from src.core.models import Source
from src.services.html_parser.forbes_parser import ForbesParser
from src.services.html_parser.interfax_parser import InterfaxParser
from sqlalchemy import select


async def test_forbes_parser():
    """Тест парсера Forbes"""
    print("🔍 Testing Forbes parser...")
    
    try:
        await init_db()
        
        async with get_db_session() as session:
            # Создаем тестовый источник Forbes
            result = await session.execute(
                select(Source).where(Source.code == "forbes")
            )
            source = result.scalar_one_or_none()
            
            if not source:
                print("❌ Forbes source not found in database")
                print("   Please run: python scripts/load_sources.py")
                return False
            
            # Создаем парсер
            parser = ForbesParser(source, session)
            
            # Тестируем получение URL статей
            print("   Getting article URLs...")
            urls = await parser.get_article_urls(max_articles=5)
            
            if not urls:
                print("❌ No article URLs found")
                return False
            
            print(f"   ✅ Found {len(urls)} article URLs")
            
            # Тестируем парсинг первой статьи
            if urls:
                print("   Parsing first article...")
                article = await parser.parse_article(urls[0])
                
                if article:
                    print("   ✅ Article parsed successfully")
                    print(f"      Title: {article['title'][:60]}...")
                    print(f"      Content length: {len(article['content'])} characters")
                    return True
                else:
                    print("   ❌ Failed to parse article")
                    return False
            
    except Exception as e:
        print(f"❌ Error testing Forbes parser: {e}")
        return False
    finally:
        await close_db()


async def test_interfax_parser():
    """Тест парсера Interfax"""
    print("🔍 Testing Interfax parser...")
    
    try:
        await init_db()
        
        async with get_db_session() as session:
            # Создаем тестовый источник Interfax
            result = await session.execute(
                select(Source).where(Source.code == "interfax")
            )
            source = result.scalar_one_or_none()
            
            if not source:
                print("❌ Interfax source not found in database")
                print("   Please run: python scripts/load_sources.py")
                return False
            
            # Создаем парсер
            parser = InterfaxParser(source, session)
            
            # Тестируем получение URL статей
            print("   Getting article URLs...")
            urls = await parser.get_article_urls(max_articles=5)
            
            if not urls:
                print("❌ No article URLs found")
                return False
            
            print(f"   ✅ Found {len(urls)} article URLs")
            
            # Тестируем парсинг первой статьи
            if urls:
                print("   Parsing first article...")
                article = await parser.parse_article(urls[0])
                
                if article:
                    print("   ✅ Article parsed successfully")
                    print(f"      Title: {article['title'][:60]}...")
                    print(f"      Content length: {len(article['content'])} characters")
                    return True
                else:
                    print("   ❌ Failed to parse article")
                    return False
            
    except Exception as e:
        print(f"❌ Error testing Interfax parser: {e}")
        return False
    finally:
        await close_db()


async def test_parser_service():
    """Тест сервиса парсеров"""
    print("🔍 Testing HTML parser service...")
    
    try:
        from src.services.html_parser.html_parser_service import HTMLParserService
        
        await init_db()
        
        async with get_db_session() as session:
            # Создаем сервис
            service = HTMLParserService(session, use_local_ai=True)
            
            # Проверяем доступные парсеры
            parsers = service.get_available_parsers()
            print(f"   ✅ Available parsers: {parsers}")
            
            # Тестируем парсинг конкретного источника
            print("   Testing Forbes source parsing...")
            stats = await service.parse_specific_source("forbes", max_articles=3)
            
            if 'error' in stats:
                print(f"   ❌ Error: {stats['error']}")
                return False
            else:
                print(f"   ✅ Forbes parsing completed: {stats}")
                return True
            
    except Exception as e:
        print(f"❌ Error testing parser service: {e}")
        return False
    finally:
        await close_db()


async def main():
    """Основная функция тестирования"""
    print("🚀 Testing HTML Parsers Integration")
    print("=" * 50)
    
    results = []
    
    # Тест 1: Forbes parser
    results.append(await test_forbes_parser())
    print()
    
    # Тест 2: Interfax parser
    results.append(await test_interfax_parser())
    print()
    
    # Тест 3: Parser service
    results.append(await test_parser_service())
    print()
    
    # Результаты
    print("=" * 50)
    print("📊 Test Results:")
    
    passed = sum(results)
    total = len(results)
    
    print(f"   Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Integration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
