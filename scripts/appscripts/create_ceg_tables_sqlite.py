"""
Создание CEG таблиц в SQLite базе данных
"""

import sys
import os
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sqlite3

def create_ceg_tables():
    """Создать CEG таблицы в SQLite"""

    # Проверяем оба возможных расположения
    root_path = Path(__file__).parent.parent.parent / 'newsdb.sqlite'
    parser_path = Path(__file__).parent.parent / 'newsdb.sqlite'

    if root_path.exists():
        db_path = root_path
    elif parser_path.exists():
        db_path = parser_path
    else:
        # Создаём в корне проекта
        db_path = root_path

    print(f"Подключение к БД: {db_path}")

    if not db_path.exists():
        print(f"⚠️  База данных не найдена: {db_path}")
        print("   Создаем новую БД...")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Events table
        print("Создание таблицы events...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            news_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            ts TIMESTAMP NOT NULL,
            attrs TEXT,  -- JSON as TEXT in SQLite
            is_anchor INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.8,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
        );
        """)

        # Event Importance table
        print("Создание таблицы event_importance...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_importance (
            id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            importance_score REAL NOT NULL,
            novelty REAL NOT NULL,
            burst REAL NOT NULL,
            credibility REAL NOT NULL,
            breadth REAL NOT NULL,
            price_impact REAL NOT NULL,
            components_details TEXT,  -- JSON as TEXT
            calculation_timestamp TIMESTAMP NOT NULL,
            weights_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
        );
        """)

        # Triggered Watches table
        print("Создание таблицы triggered_watches...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS triggered_watches (
            id TEXT PRIMARY KEY,
            rule_id TEXT NOT NULL,
            rule_name TEXT NOT NULL,
            watch_level TEXT NOT NULL,
            event_id TEXT NOT NULL,
            trigger_time TIMESTAMP NOT NULL,
            auto_expire_at TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'triggered',
            notifications_sent INTEGER DEFAULT 0,
            context TEXT,  -- JSON as TEXT
            alerts TEXT,   -- JSON as TEXT
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notified_at TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
        );
        """)

        # Event Predictions table
        print("Создание таблицы event_predictions...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_predictions (
            id TEXT PRIMARY KEY,
            watch_id TEXT NOT NULL,
            base_event_id TEXT NOT NULL,
            predicted_event_type TEXT NOT NULL,
            prediction_probability REAL NOT NULL,
            prediction_window_days INTEGER NOT NULL,
            target_date_estimate TIMESTAMP NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            fulfilled_at TIMESTAMP,
            actual_event_id TEXT,
            prediction_context TEXT,  -- JSON as TEXT
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (watch_id) REFERENCES triggered_watches(id) ON DELETE CASCADE,
            FOREIGN KEY (base_event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (actual_event_id) REFERENCES events(id) ON DELETE SET NULL
        );
        """)

        # Create indexes
        print("Создание индексов...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_news ON events(news_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_is_anchor ON events(is_anchor);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_importance_event_id ON event_importance(event_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_importance_score ON event_importance(importance_score);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_triggered_watches_rule_id ON triggered_watches(rule_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_triggered_watches_level ON triggered_watches(watch_level);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_triggered_watches_event_id ON triggered_watches(event_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_triggered_watches_status ON triggered_watches(status);")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_predictions_watch_id ON event_predictions(watch_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_predictions_base_event_id ON event_predictions(base_event_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_predictions_status ON event_predictions(status);")

        conn.commit()

        # Проверка созданных таблиц
        print("\nПроверка созданных таблиц:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%event%';")
        tables = cursor.fetchall()

        for table in tables:
            print(f"  ✓ {table[0]}")

        print(f"\n✅ CEG таблицы успешно созданы в {db_path}")

        # Показать статистику
        print("\nСтатистика таблиц:")
        for table in ['events', 'event_importance', 'triggered_watches', 'event_predictions']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count} записей")
            except sqlite3.OperationalError:
                print(f"  - {table}: не найдена")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    # Настройка кодировки для Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    print("="*60)
    print("Создание CEG таблиц в SQLite")
    print("="*60)
    print()

    create_ceg_tables()
