#!/usr/bin/env python3
import asyncio
import asyncpg
import sys

async def test_database_connection():
    try:
        # Тестируем подключение к базе данных через host.docker.internal
        conn = await asyncpg.connect('postgresql://newsuser:newspass@host.docker.internal:5432/newsdb', ssl='disable')
        print('✅ Database connection successful (host.docker.internal)')
        
        # Проверяем, что можем выполнить запрос
        result = await conn.fetchval('SELECT 1')
        print(f'✅ Database query successful: {result}')
        
        await conn.close()
        print('✅ Database connection closed successfully')
        return True
        
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_database_connection())
    sys.exit(0 if success else 1)
