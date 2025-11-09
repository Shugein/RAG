"""
Скрипт для очистки данных в Neo4j
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from Parser.src.graph_models import GraphService
from Parser.src.core.config import settings

async def clear_neo4j():
    """Очистить все данные в Neo4j"""
    print("🗑️  Connecting to Neo4j...")
    graph_service = GraphService(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    
    try:
        async with graph_service.driver.session() as session:
            # Удаляем все узлы и связи
            print("🗑️  Deleting all nodes and relationships...")
            await session.run("MATCH (n) DETACH DELETE n")
            print("✅ All data deleted")
            
            # Пересоздаем констрейнты
            print("🔧 Recreating constraints...")
            await graph_service.create_constraints()
            print("✅ Constraints recreated")
            
    finally:
        await graph_service.close()
        print("✅ Done")

if __name__ == "__main__":
    asyncio.run(clear_neo4j())
