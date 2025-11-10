#!/usr/bin/env python3
"""
Автоматическое обновление импортов после рефакторинга

Заменяет старые импорты на новые согласно MIGRATION_GUIDE.md
"""

import os
import re
from pathlib import Path
from typing import List, Tuple

# Таблица замен импортов
IMPORT_REPLACEMENTS = [
    # Core modules
    (r'from Parser\.src\.core\.models import', 'from core.database.models import'),
    (r'from Parser\.src\.core\.config import', 'from core.database.config import'),
    (r'from Parser\.src\.core\.database import', 'from core.database.database import'),
    (r'from Parser\.src\.graph_models import', 'from core.graph.service import'),
    (r'from Parser\.src\.services\.event_bus import', 'from core.messaging.event_bus import'),
    (r'from entity_recognition import', 'from core.nlp.entity_recognition import'),

    # Aggregator services
    (r'from Parser\.src\.services\.telegram_parser\.', 'from services.aggregator.telegram.'),
    (r'from Parser\.src\.services\.html_parser\.', 'from services.aggregator.html.'),
    (r'from Parser\.src\.services\.enricher\.', 'from services.aggregator.enrichment.'),
    (r'from Parser\.src\.services\.outbox\.', 'from services.aggregator.outbox.'),
    (r'from Parser\.src\.services\.ml\.news_clustering import', 'from services.aggregator.clustering.news_clustering import'),
    (r'from Parser\.src\.services\.storage\.', 'from services.aggregator.storage.'),

    # CEG services - events
    (r'from Parser\.src\.services\.events\.event_extractor import', 'from services.ceg.events.event_extractor import'),
    (r'from Parser\.src\.services\.events\.event_prediction import', 'from services.ceg.predictions.event_prediction import'),

    # CEG services - causal
    (r'from Parser\.src\.services\.events\.cmnln_engine import', 'from services.ceg.causal.cmnln_engine import'),
    (r'from Parser\.src\.services\.events\.causal_chains_engine import', 'from services.ceg.causal.causal_chains_engine import'),
    (r'from Parser\.src\.services\.events\.enhanced_evidence_engine import', 'from services.ceg.causal.enhanced_evidence_engine import'),

    # CEG services - importance
    (r'from Parser\.src\.services\.events\.importance_calculator import', 'from services.ceg.importance.calculator import'),
    (r'from Parser\.src\.services\.impact_calculator import', 'from services.ceg.importance.impact import'),
    (r'from Parser\.src\.services\.covariance_service import', 'from services.ceg.importance.covariance import'),

    # CEG services - watchers
    (r'from Parser\.src\.services\.events\.watchers import', 'from services.ceg.watchers.watchers import'),

    # CEG services - market
    (r'from Parser\.src\.services\.moex\.', 'from services.ceg.market.moex.'),
    (r'from Parser\.src\.services\.market_data_service import', 'from services.ceg.market.market_data_service import'),

    # CEG services - other events
    (r'from Parser\.src\.services\.events\.', 'from services.ceg.events.'),

    # RAG services
    (r'from src\.system\.vdb import', 'from services.rag.indexing.indexer import'),
    (r'from src\.download\.downloader_functions import', 'from services.rag.indexing.chunker import'),
    (r'from src\.system\.search import', 'from services.rag.search.search import'),
    (r'from src\.system\.engine import', 'from services.rag.search.engine import'),
    (r'from src\.system\.LLM_final\.', 'from services.rag.generation.LLM_final.'),
    (r'from src\.system\.', 'from services.rag.'),

    # API
    (r'from Parser\.src\.api\.', 'from api.'),

    # Utils
    (r'from Parser\.src\.utils\.', 'from core.utils.'),
]


def update_file(file_path: Path) -> Tuple[bool, int]:
    """
    Обновить импорты в одном файле

    Returns:
        (changed, num_replacements)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"⚠️  Ошибка чтения {file_path}: {e}")
        return False, 0

    original_content = content
    replacements_count = 0

    # Применить все замены
    for old_pattern, new_import in IMPORT_REPLACEMENTS:
        if re.search(old_pattern, content):
            content = re.sub(old_pattern, new_import, content)
            replacements_count += content.count(new_import) - original_content.count(new_import)

    # Если изменения есть - сохранить
    if content != original_content:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, replacements_count
        except Exception as e:
            print(f"⚠️  Ошибка записи {file_path}: {e}")
            return False, 0

    return False, 0


def find_python_files(directories: List[str]) -> List[Path]:
    """Найти все .py файлы в указанных директориях"""
    files = []
    for directory in directories:
        if not os.path.exists(directory):
            continue
        for root, dirs, filenames in os.walk(directory):
            # Пропустить venv, __pycache__, .git
            dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', 'node_modules']]

            for filename in filenames:
                if filename.endswith('.py'):
                    files.append(Path(root) / filename)

    return files


def main():
    print("Начинаем обновление импортов...")
    print()

    # Директории для обновления
    target_dirs = ['services', 'workers', 'api', 'core']

    # Найти все Python файлы
    files = find_python_files(target_dirs)
    print(f"Найдено {len(files)} Python файлов")
    print()

    # Обновить каждый файл
    updated_files = 0
    total_replacements = 0

    for file_path in files:
        changed, count = update_file(file_path)
        if changed:
            updated_files += 1
            total_replacements += count
            print(f"[OK] {file_path} ({count} замен)")

    print()
    print(f"Готово!")
    print(f"   Обновлено файлов: {updated_files}/{len(files)}")
    print(f"   Всего замен: {total_replacements}")
    print()

    # Проверка оставшихся старых импортов
    print("Проверка оставшихся старых импортов...")
    remaining = []

    for file_path in files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'from Parser.src' in content or 'from src.' in content:
                # Подсчитать количество
                count = content.count('from Parser.src') + content.count('from src.')
                remaining.append((file_path, count))

    if remaining:
        print(f"[WARNING] Найдено {len(remaining)} файлов с оставшимися старыми импортами:")
        for file_path, count in remaining[:10]:  # Показать первые 10
            print(f"   - {file_path} ({count} импортов)")
        if len(remaining) > 10:
            print(f"   ... и еще {len(remaining) - 10} файлов")
    else:
        print("[OK] Все старые импорты обновлены!")

    print()
    print("Следующие шаги:")
    print("   1. Проверьте что все работает: python -c 'from core.database.models import News'")
    print("   2. Запустите тесты: pytest tests/")
    print("   3. См. MIGRATION_GUIDE.md для деталей")


if __name__ == '__main__':
    main()
