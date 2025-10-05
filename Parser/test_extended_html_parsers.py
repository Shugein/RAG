#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест расширенных HTML парсеров
"""

import asyncio
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.append(str(Path(__file__).parent))

from Parser.src.core.database import get_async_session
from Parser.src.core.models import Source, SourceKind
from Parser.src.services.html_parser.html_parser_service import HTMLParserService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_extended_parsers():
    """Тестируем новые HTML парсеры"""
    print("🧪 Тестирование расширенных HTML парсеров")
    print("=" * 60)
    
    async with get_async_session() as session:
        # Инициализируем сервис
        parser_service = HTMLParserService(session, use_local_ai=False)
        
        # Получаем HTML источники
        result = await session.execute(
            f"""
            SELECT * FROM sources 
            WHERE kind = '{SourceKind.HTML}' 
            AND enabled = true
            AND code IN ('e_disclosure', 'e_disclosure_messages', 'moex')
            ORDER BY code
            """
        )
        sources = result.fetchall()
        
        if not sources:
            print("❌ HTML источники не найдены в базе данных")
            print("💡 Запустите scripts/load_sources.py для загрузки конфигурации")
            return
        
        print(f"📡 Найдено {len(sources)} HTML источников:")
        for source in sources:
            print(f"   - {source.name} ({source.code})")
        
        print("\n🔍 Тестирование парсеров:")
        print("-" * 40)
        
        for source in sources:
            source_code = source.code
            source_name = source.name
            
            print(f"\n🌐 Тестируем {source_name} ({source_code})")
            
            try:
                # Получаем парсер
                parser = parser_service.get_parser(source_code)
                if not parser:
                    print(f"   ❌ Парсер не найден для {source_code}")
                    continue
                
                print(f"   ✅ Парсер найден: {type(parser).__name__}")
                
                # Тестируем получение URL статей
                print(f"   📰 Получаем URL статей...")
                article_urls = await parser.get_article_urls(max_articles=5)
                
                if article_urls:
                    print(f"   ✅ Найдено {len(article_urls)} URL статей")
                    
                    # Тестируем парсинг первой статьи
                    test_url = article_urls[0]
                    print(f"   📖 Парсим статью: {test_url[:60]}...")
                    
                    article_data = await parser.parse_article(test_url)
                    
                    if article_data:
                        print(f"   ✅ Статья успешно спарсена:")
                        print(f"      📝 Заголовок: {article_data['title'][:80]}...")
                        print(f"      📄 Контент: {len(article_data['content'])} символов")
                        print(f"      📅 Дата: {article_data.get('date', 'N/A')}")
                        print(f"      🏷️ Парсер: {article_data.get('parser', 'N/A')}")
                        
                        if article_data.get('metadata'):
                            metadata = article_data['metadata']
                            print(f"      📊 Метаданные:")
                            for key, value in metadata.items():
                                if isinstance(value, str) and len(value) > 50:
                                    value = value[:50] + "..."
                                print(f"         - {key}: {value}")
                    else:
                        print(f"   ❌ Не удалось спарсить статью")
                else:
                    print(f"   ❌ URL статей не найдены")
                
            except Exception as e:
                print(f"   ❌ Ошибка тестирования {source_code}: {e}")
                logger.exception(f"Error testing {source_code}")
                continue
        
        # Тестируем общий сервис
        print(f"\n🔧 Тестирование HTML Parser Service:")
        print("-" * 40)
        
        try:
            # Тестируем run_source
            test_source = sources[0]  # Берем первый источник для теста
            print(f"🚀 Запускаем парсинг для {test_source.name}...")
            
            success = await parser_service.run_source(test_source.code)
            
            if success:
                print(f"✅ Парсинг {test_source.name} завершен успешно")
            else:
                print(f"❌ Парсинг {test_source.name} завершен с ошибками")
            
            # Показываем статистику
            stats = parser_service.get_stats()
            print(f"\n📊 Статистика сервиса:")
            for key, value in stats.items():
                print(f"   - {key}: {value}")
                
        except Exception as e:
            print(f"❌ Ошибка тестирования сервиса: {e}")
            logger.exception("Error testing parser service")
        
        print(f"\n🎯 Тестирование завершено!")
        print("=" * 60)


async def test_parser_registry():
    """Тестируем регистр парсеров"""
    print("\n🔍 Тестирование регистра парсеров:")
    print("-" * 40)
    
    async with get_async_session() as session:
        parser_service = HTMLParserService(session, use_local_ai=False)
        
        expected_parsers = [
            'forbes', 'interfax', 'edisclosure', 'moex', 'edisclosure_messages'
        ]
        
        for parser_code in expected_parsers:
            parser_class = parser_service.parser_registry.get(parser_code)
            if parser_class:
                print(f"   ✅ {parser_code}: {parser_class.__name__}")
            else:
                print(f"   ❌ {parser_code}: НЕ НАЙДЕН")


async def main():
    """Главная функция"""
    try:
        await test_parser_registry()
        await test_extended_parsers()
        
    except Exception as e:
        logger.error(f"Fatal error in test: {e}", exc_info=True)
        print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
