#!/usr/bin/env python3
"""
Скрипт для проверки состояния коллекции Weaviate
Показывает подробную информацию о коллекции NewsChunks
"""

import weaviate
import json
from datetime import datetime
from collections import Counter


def connect_to_weaviate():
    """Подключение к локальному серверу Weaviate"""
    try:
        client = weaviate.connect_to_local()
        if not client.is_ready():
            print("❌ Weaviate сервер не готов")
            return None
        print("✅ Подключение к Weaviate успешно")
        return client
    except Exception as e:
        print(f"❌ Ошибка подключения к Weaviate: {e}")
        return None


def check_collection_exists(client, collection_name="NewsChunks"):
    """Проверка существования коллекции"""
    try:
        exists = client.collections.exists(collection_name)
        if exists:
            print(f"✅ Коллекция '{collection_name}' существует")
            return True
        else:
            print(f"❌ Коллекция '{collection_name}' не найдена")
            return False
    except Exception as e:
        print(f"❌ Ошибка при проверке коллекции: {e}")
        return False


def get_collection_schema(client, collection_name="NewsChunks"):
    """Получение схемы коллекции"""
    try:
        collection = client.collections.get(collection_name)
        config = collection.config.get()

        print(f"\n📋 Схема коллекции '{collection_name}':")
        print(f"   Название: {config.name}")
        print(f"   Описание: {config.description or 'Не указано'}")

        print("\n   🔧 Свойства:")
        for prop in config.properties:
            skip_vec = getattr(prop, 'skip_vectorization', None)
            vec_status = 'выключена' if skip_vec else 'включена' if skip_vec is not None else 'неизвестно'
            print(f"      • {prop.name}: {prop.data_type} (векторизация: {vec_status})")

        print("\n   🎯 Векторные конфигурации:")
        if config.vector_config:
            for vector_name, vector_config in config.vector_config.items():
                print(f"      • {vector_name}: {vector_config}")
        else:
            print("      Векторные конфигурации не найдены")

        return True
    except Exception as e:
        print(f"❌ Ошибка при получении схемы: {e}")
        return False


def get_collection_stats(client, collection_name="NewsChunks"):
    """Получение статистики коллекции"""
    try:
        collection = client.collections.get(collection_name)

        # Общее количество объектов
        total_count = collection.aggregate.over_all().total_count
        print(f"\n📊 Статистика коллекции '{collection_name}':")
        print(f"   Общее количество объектов: {total_count}")

        if total_count == 0:
            print("   ⚠️  Коллекция пустая")
            return True

        # Выборка данных для анализа
        sample_size = min(100, total_count)
        response = collection.query.fetch_objects(limit=sample_size)

        if not response.objects:
            print("   ⚠️  Не удалось получить объекты для анализа")
            return True

        # Анализ источников
        sources = [obj.properties.get('source', 'Unknown') for obj in response.objects]
        source_counts = Counter(sources)

        print(f"\n   📄 Источники данных (из {sample_size} объектов):")
        for source, count in source_counts.most_common():
            print(f"      • {source}: {count} объектов")

        # Анализ временных меток
        timestamps = [obj.properties.get('timestamp') for obj in response.objects if obj.properties.get('timestamp')]
        if timestamps:
            min_timestamp = min(timestamps)
            max_timestamp = max(timestamps)
            min_date = datetime.fromtimestamp(min_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            max_date = datetime.fromtimestamp(max_timestamp).strftime('%Y-%m-%d %H:%M:%S')

            print(f"\n   ⏰ Временной диапазон данных:")
            print(f"      • Самая старая запись: {min_date}")
            print(f"      • Самая новая запись: {max_date}")

        # Анализ размеров текста
        text_lengths = [len(obj.properties.get('original_text', '')) for obj in response.objects]
        if text_lengths:
            avg_length = sum(text_lengths) / len(text_lengths)
            min_length = min(text_lengths)
            max_length = max(text_lengths)

            print(f"\n   📝 Размеры текстов:")
            print(f"      • Средняя длина: {avg_length:.0f} символов")
            print(f"      • Минимальная длина: {min_length} символов")
            print(f"      • Максимальная длина: {max_length} символов")

        return True
    except Exception as e:
        print(f"❌ Ошибка при получении статистики: {e}")
        return False


def test_search_functionality(client, collection_name="NewsChunks"):
    """Тестирование функций поиска"""
    try:
        collection = client.collections.get(collection_name)

        print(f"\n🔍 Тестирование поиска в коллекции '{collection_name}':")

        # Тест семантического поиска
        try:
            semantic_response = collection.query.near_text(
                query="новости",
                limit=3
            )
            print(f"   ✅ Семантический поиск: найдено {len(semantic_response.objects)} объектов")
        except Exception as e:
            print(f"   ❌ Семантический поиск: {e}")

        # Тест поиска по ключевым словам (BM25)
        try:
            bm25_response = collection.query.bm25(
                query="новости",
                limit=3
            )
            print(f"   ✅ BM25 поиск: найдено {len(bm25_response.objects)} объектов")
        except Exception as e:
            print(f"   ❌ BM25 поиск: {e}")

        # Тест фильтрации
        try:
            from weaviate.classes.query import Filter
            filter_response = collection.query.fetch_objects(
                where=Filter.by_property("source").equal("buriy"),
                limit=3
            )
            print(f"   ✅ Фильтрация: найдено {len(filter_response.objects)} объектов")
        except Exception as e:
            print(f"   ❌ Фильтрация: {e}")

        return True
    except Exception as e:
        print(f"❌ Ошибка при тестировании поиска: {e}")
        return False


def get_sample_objects(client, collection_name="NewsChunks", limit=2):
    """Получение примеров объектов из коллекции со всеми метаданными"""
    try:
        collection = client.collections.get(collection_name)
        response = collection.query.fetch_objects(limit=limit)

        print(f"\n📋 Примеры объектов из коллекции '{collection_name}' (полные метаданные):")

        for i, obj in enumerate(response.objects, 1):
            print(f"\n{'='*80}")
            print(f"ОБЪЕКТ {i}/{limit}")
            print(f"{'='*80}")
            print(f"UUID: {obj.uuid}")

            props = obj.properties

            # ОСНОВНЫЕ ПОЛЯ
            print(f"\n📌 ОСНОВНАЯ ИНФОРМАЦИЯ:")
            print(f"   Заголовок: {props.get('title', 'Не указан')}")
            print(f"   Источник: {props.get('source', 'Не указан')}")
            print(f"   URL: {props.get('url', 'Не указан')}")

            timestamp = props.get('timestamp')
            if timestamp:
                date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                print(f"   Timestamp: {timestamp} ({date_str})")

            print(f"   Publication Date: {props.get('publication_date', 'Не указана')}")
            print(f"   Hotness: {props.get('hotness', 'N/A')}")

            # ТЕКСТОВЫЕ ПОЛЯ
            print(f"\n📝 ТЕКСТОВОЕ СОДЕРЖАНИЕ:")
            original_text = props.get('original_text', '')
            if original_text:
                preview = original_text[:150] + "..." if len(original_text) > 150 else original_text
                print(f"   Original Text: {preview}")
                print(f"   Длина: {len(original_text)} символов")

            text_for_bm25 = props.get('text_for_bm25', '')
            if text_for_bm25:
                preview_bm25 = text_for_bm25[:100] + "..." if len(text_for_bm25) > 100 else text_for_bm25
                print(f"   Text for BM25: {preview_bm25}")

            # МЕТАДАННЫЕ ЧАНКОВ
            print(f"\n🔗 МЕТАДАННЫЕ ЧАНКА:")
            print(f"   Parent Doc ID: {props.get('parent_doc_id', 'N/A')}")
            print(f"   Chunk Index: {props.get('chunk_index', 'N/A')}")
            parent_text = props.get('parent_doc_text', '')
            if parent_text:
                preview_parent = parent_text[:100] + "..." if len(parent_text) > 100 else parent_text
                print(f"   Parent Doc Text: {preview_parent}")

            # ИЗВЛЕЧЕННЫЕ СУЩНОСТИ
            print(f"\n🏢 ИЗВЛЕЧЕННЫЕ СУЩНОСТИ:")

            entities_json = props.get('entities_json', '')
            if entities_json:
                try:
                    entities = json.loads(entities_json)
                    print(f"   ✓ Entities JSON доступен")

                    # Компании
                    companies = props.get('companies', [])
                    if companies:
                        print(f"   Компании ({len(companies)}):")
                        for comp in companies:
                            print(f"      • {comp}")

                    company_tickers = props.get('company_tickers', [])
                    if company_tickers:
                        print(f"   Тикеры: {', '.join(company_tickers)}")

                    company_sectors = props.get('company_sectors', [])
                    if company_sectors:
                        print(f"   Секторы: {', '.join(company_sectors)}")

                    # Персоны
                    people = props.get('people', [])
                    if people:
                        print(f"   Персоны ({len(people)}):")
                        for person in people:
                            print(f"      • {person}")

                    people_positions = props.get('people_positions', [])
                    if people_positions:
                        print(f"   Должности: {', '.join(people_positions)}")

                    # Рынки
                    markets = props.get('markets', [])
                    if markets:
                        print(f"   Рынки ({len(markets)}):")
                        for market in markets:
                            print(f"      • {market}")

                    market_types = props.get('market_types', [])
                    if market_types:
                        print(f"   Типы рынков: {', '.join(market_types)}")

                    # Финансовые метрики
                    metric_types = props.get('financial_metric_types', [])
                    metric_values = props.get('financial_metric_values', [])
                    if metric_types or metric_values:
                        print(f"   Финансовые метрики ({len(metric_types)}):")
                        for mt, mv in zip(metric_types, metric_values):
                            print(f"      • {mt}: {mv}")

                    # Полный JSON для детального просмотра
                    print(f"\n   📄 Полный JSON сущностей:")
                    print(f"   {json.dumps(entities, ensure_ascii=False, indent=6)}")

                except json.JSONDecodeError:
                    print(f"   ⚠️  Entities JSON некорректен")
            else:
                print(f"   ⚠️  Сущности не извлечены")

            # ВЕКТОРНАЯ ИНФОРМАЦИЯ (если доступна)
            if hasattr(obj, 'vector') and obj.vector:
                print(f"\n🔢 ВЕКТОРНОЕ ПРЕДСТАВЛЕНИЕ:")
                print(f"   Vector dimension: {len(obj.vector)}")
                print(f"   First 5 values: {obj.vector[:5]}")

        return True
    except Exception as e:
        print(f"❌ Ошибка при получении примеров объектов: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_server_status(client):
    """Проверка статуса сервера Weaviate"""
    try:
        print("\n🖥️  СТАТУС СЕРВЕРА WEAVIATE:")

        # Получаем метаинформацию о сервере
        meta = client.get_meta()
        print(f"   Версия: {meta.get('version', 'Неизвестно')}")
        print(f"   Модули: {', '.join(meta.get('modules', {}).keys())}")

        # Проверяем готовность
        if client.is_ready():
            print("   ✅ Сервер готов к работе")
        else:
            print("   ❌ Сервер не готов")

        return True
    except Exception as e:
        print(f"❌ Ошибка при проверке статуса сервера: {e}")
        return False


def list_all_collections(client):
    """Получение списка всех коллекций в БД"""
    try:
        print("\n📚 СПИСОК ВСЕХ КОЛЛЕКЦИЙ В БД:")

        collections = client.collections.list_all()

        if not collections:
            print("   ⚠️  Коллекции не найдены")
            return True

        for coll_name, coll_config in collections.items():
            print(f"\n   📦 {coll_name}:")
            collection = client.collections.get(coll_name)
            total_count = collection.aggregate.over_all().total_count
            print(f"      • Объектов: {total_count}")
            print(f"      • Свойств: {len(coll_config.properties)}")

            # Список свойств
            prop_names = [prop.name for prop in coll_config.properties]
            print(f"      • Поля: {', '.join(prop_names[:5])}" + ("..." if len(prop_names) > 5 else ""))

        return True
    except Exception as e:
        print(f"❌ Ошибка при получении списка коллекций: {e}")
        return False


def main():
    """Основная функция проверки"""
    print("=" * 80)
    print("🔍 ПРОВЕРКА СОСТОЯНИЯ БАЗЫ ДАННЫХ WEAVIATE")
    print("=" * 80)

    # Подключение к серверу
    client = connect_to_weaviate()
    if not client:
        return

    try:
        # 1. Проверка статуса сервера
        check_server_status(client)

        # 2. Список всех коллекций в БД
        list_all_collections(client)

        # 3. Проверка существования коллекции NewsChunks
        collection_name = "NewsChunks"
        print(f"\n{'='*80}")
        print(f"📊 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О КОЛЛЕКЦИИ '{collection_name}'")
        print(f"{'='*80}")

        if not check_collection_exists(client, collection_name):
            print(f"\n⚠️  Коллекция '{collection_name}' не найдена. Создайте её запуском vdb.py")
            return

        # 4. Получение схемы коллекции
        get_collection_schema(client, collection_name)

        # 5. Получение статистики
        get_collection_stats(client, collection_name)

        # 6. Тестирование поиска
        test_search_functionality(client, collection_name)

        # 7. Получение примеров объектов со всеми метаданными
        get_sample_objects(client, collection_name, limit=2)

        print("\n" + "=" * 80)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА УСПЕШНО!")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Общая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()


if __name__ == "__main__":
    main()