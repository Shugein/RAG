#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации нового формата entity_recognition для построения графа
"""

import os
import json
from dotenv import load_dotenv
from entity_recognition import CachedFinanceNERExtractor, GraphExtractedData, NewsItem

def test_new_graph_format():
    """Тестирование нового формата данных для графа"""
    
    # Загружаем переменные окружения
    load_dotenv()
    API_KEY = os.environ.get('API_KEY_2')
    
    if not API_KEY:
        print("❌ Ошибка: API_KEY_2 не найден в переменных окружения")
        return
    
    print("🚀 ТЕСТИРОВАНИЕ НОВОГО ФОРМАТА ДЛЯ ГРАФА")
    print("="*60)
    
    # Инициализация экстрактора
    extractor = CachedFinanceNERExtractor(
        api_key=API_KEY,
        enable_caching=True
    )
    
    # Тестовые новости
    test_news = [
        {
            "news_id": "test_001",
            "text": "Акции Сбербанка выросли на 3.2% после публикации квартального отчета. Чистая прибыль банка составила 389 млрд рублей за квартал. Глава Сбербанка Герман Греф заявил о планах увеличить дивиденды до 50% от прибыли.",
            "title": "Сбербанк показал рост прибыли",
            "date": "2025-01-15",
            "source": "РБК"
        },
        {
            "news_id": "test_002",
            "text": "Центральный банк России повысил ключевую ставку до 16%. Аналитики ВТБ Капитал ожидают замедления инфляции в следующем квартале до 5.5%.",
            "title": "ЦБ повышает ставку",
            "date": "2025-01-15",
            "source": "Коммерсант"
        },
        {
            "news_id": "test_003", 
            "text": "Индекс Московской биржи закрылся на отметке 3245 пунктов, что на 1.5%. Рост связан с увеличением цен на нефть.",
            "title": "Мосбиржа в плюсе",
            "date": "2025-01-15",
            "source": "ТАСС"
        }
    ]
    
    print(f"📊 Обрабатываем {len(test_news)} тестовых новостей...")
    
    try:
        # Тестируем новый формат
        graph_data = extractor.extract_graph_entities_batch(test_news, verbose=False, parallel=True)
        
        print("\n✅ УСПЕШНО! Новый формат работает")
        print("="*60)
        
        # Выводим статистику
        print(f"Всего новостей: {graph_data.total_news}")
        print(f"Финансовые новости: {graph_data.summary['financial_news_count']} ({graph_data.summary['financial_news_percentage']:.1f}%)")
        print(f"Найдено компаний: {graph_data.summary['total_companies']}")
        print(f"Найдено людей: {graph_data.summary['total_people']}")
        print(f"Найдено рынков: {graph_data.summary['total_markets']}")
        
        # Показываем примеры данных
        print("\n📋 ПРИМЕРЫ ИЗВЛЕЧЕННЫХ ДАННЫХ:")
        print("-"*60)
        
        for i, news_item in enumerate(graph_data.news_items, 1):
            print(f"\n{i}. Новость {news_item.news_id}:")
            print(f"   Финансовая: {'Да' if news_item.is_financial else 'Нет'}")
            print(f"   Страна: {news_item.country or 'Не определена'}")
            
            if news_item.event_types:
                types_str = ', '.join([f"{et.type} ({et.confidence:.1f})" for et in news_item.event_types])
                print(f"   Типы событий: {types_str}")
            
            if news_item.companies:
                companies_str = ', '.join([f"{c.name}" for c in news_item.companies])
                print(f"   Компании: {companies_str}")
            
            if news_item.people:
                people_str = ', '.join([f"{p.name}" for p in news_item.people])
                print(f"   Персоны: {people_str}")
        
        # Сохраняем результат в JSON для демонстрации
        result_json = graph_data.model_dump_json(indent=2, ensure_ascii=False)
        
        print(f"\n💾 Размер JSON результата: {len(result_json)} символов")
        
        # Показываем часть JSON
        print("\n📄 ФРАГМЕНТ JSON:")
        print("-"*60)
        
        json_obj = json.loads(result_json)
        sample_item = json_obj['news_items'][0]
        
        # Упрощенная версия для показа
        simplified = {
            "news_id": sample_item["news_id"],
            "title": sample_item["title"],
            "is_financial": sample_item["is_financial"],
            "country": sample_item["country"],
            "event_types": sample_item["event_types"],
            "companies": sample_item["companies"],
            "people": sample_item["people"]
        }
        
        print(json.dumps(simplified, ensure_ascii=False, indent=2))
        
        print("\n🎯 КЛЮЧЕВЫЕ ОСОБЕННОСТИ НОВОГО ФОРМАТА:")
        print("-"*60)
        print("✓ Разделение данных по каждой новости")
        print("✓ Автоматическое определение финансовых новостей")
        print("✓ Классификация типов событий (earnings, dividend и т.д.)")
        print("✓ Определение основной страны новости")
        print("✓ Извлечение затронутых секторов")
        print("✓ Совместимость с moex_linker для расчетных полей")
        print("✓ Структурированный JSON для построения графа")
        
        print(f"\n⚡ Статистика API:")
        stats = extractor.get_stats_summary()
        print(f"   Запросов: {stats['total_requests']}")
        print(f"   Токенов: {stats['input_tokens']} (входящие), {stats['output_tokens']} (исходящие)")
        print(f"   Стоимость: ${stats['total_cost']:.4f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ОШИБКА при тестировании: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def compare_old_vs_new():
    """Сравнение старого и нового формата"""
    
    load_dotenv()
    API_KEY = os.environ.get('API_KEY_2')
    
    if not API_KEY:
        return
    
    extractor = CachedFinanceNERExtractor(api_key=API_KEY, enable_caching=True)
    
    test_text = "Сбербанк отчитался о прибыли 389 млрд рублей. Герман Греф увеличит дивиденды."
    
    print("\n🔄 СРАВНЕНИЕ ФОРМАТОВ")
    print("="*60)
    
    try:
        # Старый формат
        print("🔹 СТАРЫЙ ФОРМАТ:")
        old_result = extractor.extract_entities(test_text)
        old_json = old_result.model_dump_json(indent=2, ensure_ascii=False)
        print(f"   Размер: {len(old_json)} символов")
        print(f"   Компаний: {len(old_result.companies)}")
        print(f"   Персон: {len(old_result.people)}")
        print(f"   Рынков: {len(old_result.markets)}")
        
        # Новый формат
        print("\n🔸 НОВЫЙ ФОРМАТ (для графа):")
        new_result = extractor.extract_graph_entities(test_text, "compare_test", "Тест сравнения")
        new_json = new_result.model_dump_json(indent=2, ensure_ascii=False)
        print(f"   Размер: {len(new_json)} символов")
        print(f"   Финансовая: {new_result.is_financial}")
        print(f"   Страна: {new_result.country}")
        print(f"   Секторы: {new_result.sectors}")
        print(f"   Типы событий: {len(new_result.event_types)}")
        print(f"   Компаний: {len(new_result.companies)}")
        print(f"   Персон: {len(new_result.people)}")
        print(f"   Рынков: {len(new_result.markets)}")
        
        print(f"\n📈 РАЗНИЦА В РАЗМЕРЕ: {len(new_json) - len(old_json):+d} символов")
        
    except Exception as e:
        print(f"❌ Ошибка сравнения: {e}")

if __name__ == "__main__":
    success = test_new_graph_format()
    
    if success:
        compare_old_vs_new()
    
    print("\n🎉 Тестирование завершено!")
