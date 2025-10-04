#!/usr/bin/env python3
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import sys

async def test_database_connection():
    try:
        # Тестируем подключение к базе данных через SQLAlchemy
        engine = create_async_engine('postgresql+asyncpg://newsuser:newspass@localhost:5432/newsdb')
        
        async with engine.begin() as conn:
            result = await conn.execute("SELECT 1")
            value = result.scalar()
            print(f'✅ Database connection successful (SQLAlchemy): {value}')
        
        await engine.dispose()
        print('✅ Database connection closed successfully')
        return True
        
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        return False

if __name__ == "__main__":
    success = asyncio.run(test_database_connection())
    sys.exit(0 if success else 1)
