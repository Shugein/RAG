#!/usr/bin/env python3
import asyncio
import sys
from src.core.database import init_db
from src.core.config import settings

async def test_app():
    try:
        print("🧠 Testing application components...")
        
        # Test database connection
        print("📊 Testing database connection...")
        await init_db()
        print("✅ Database connection successful")
        
        # Test Redis connection
        print("🔴 Testing Redis connection...")
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        print("✅ Redis connection successful")
        
        # Test Neo4j connection
        print("🕸️ Testing Neo4j connection...")
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            value = result.single()["test"]
            print(f"✅ Neo4j connection successful: {value}")
        driver.close()
        
        print("🎉 All components working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_app())
    sys.exit(0 if success else 1)
