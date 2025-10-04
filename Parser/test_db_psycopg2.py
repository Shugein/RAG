#!/usr/bin/env python3
import psycopg2
import sys

def test_database_connection():
    try:
        # Тестируем подключение к базе данных через psycopg2
        conn = psycopg2.connect(
            host='localhost',
            port=5432,
            database='newsdb',
            user='newsuser',
            password='newspass',
            sslmode='disable'
        )
        print('✅ Database connection successful (psycopg2)')
        
        # Проверяем, что можем выполнить запрос
        cursor = conn.cursor()
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        print(f'✅ Database query successful: {result[0]}')
        
        cursor.close()
        conn.close()
        print('✅ Database connection closed successfully')
        return True
        
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1)
