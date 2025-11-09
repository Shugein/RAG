"""
Workers - фоновые задачи для обработки данных

Заменяют scripts/ из старой структуры:
- telegram_worker.py - парсинг Telegram (start_telegram_parser.py)
- enrichment_worker.py - обогащение новостей (start_enricher.py)
- ceg_worker.py - CEG processing
- rag_indexer_worker.py - индексация в Weaviate
"""
