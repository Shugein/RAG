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


def get_sample_objects(client, collection_name="NewsChunks", limit=3):
    """Получение примеров объектов из коллекции"""
    try:
        collection = client.collections.get(collection_name)
        response = collection.query.fetch_objects(limit=limit)

        print(f"\n📋 Примеры объектов из коллекции '{collection_name}':")

        for i, obj in enumerate(response.objects, 1):
            print(f"\n   Объект {i}:")
            print(f"      ID: {obj.uuid}")

            # Показываем основные свойства
            props = obj.properties
            print(f"      Заголовок: {props.get('title', 'Не указан')[:100]}...")
            print(f"      Источник: {props.get('source', 'Не указан')}")
            print(f"      URL: {props.get('url', 'Не указан')}")

            # Показываем начало текста
            original_text = props.get('original_text', '')
            if original_text:
                preview = original_text[:200] + "..." if len(original_text) > 200 else original_text
                print(f"      Текст: {preview}")

            # Показываем timestamp если есть
            timestamp = props.get('timestamp')
            if timestamp:
                date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                print(f"      Дата: {date_str}")

        return True
    except Exception as e:
        print(f"❌ Ошибка при получении примеров объектов: {e}")
        return False


def check_server_status(client):
    """Проверка статуса сервера Weaviate"""
    try:
        print("\n🖥️  Статус сервера Weaviate:")

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


def main():
    """Основная функция проверки"""
    print("🔍 Проверка состояния коллекции Weaviate")
    print("=" * 50)

    # Подключение к серверу
    client = connect_to_weaviate()
    if not client:
        return

    try:
        # Проверка статуса сервера
        check_server_status(client)

        # Проверка существования коллекции
        collection_name = "NewsChunks"
        if not check_collection_exists(client, collection_name):
            return

        # Получение схемы коллекции
        get_collection_schema(client, collection_name)

        # Получение статистики
        get_collection_stats(client, collection_name)

        # Тестирование поиска
        test_search_functionality(client, collection_name)

        # Получение примеров объектов
        get_sample_objects(client, collection_name)

        print("\n✅ Проверка завершена успешно!")

    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    main()