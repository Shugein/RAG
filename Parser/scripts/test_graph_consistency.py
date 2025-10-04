#!/usr/bin/env python3
"""
Скрипт для тестирования целостности графовой базы данных
Проверяет отсутствие дубликатов и правильность связей
"""

import asyncio
import logging
import sys
from typing import Dict, List, Any
from pathlib import Path

# Добавляем путь к src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.core.config import settings
from src.graph_models import GraphService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphConsistencyChecker:
    """Проверка целостности графовой базы данных"""
    
    def __init__(self):
        self.graph = None
    
    async def initialize(self):
        """Инициализация подключения к графу"""
        self.graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Создаем констрейнты
        await self.graph.create_constraints()
        logger.info("Graph constraints created/verified")
    
    async def close(self):
        """Закрытие соединения"""
        if self.graph:
            await self.graph.close()
    
    async def check_duplicates(self) -> Dict[str, List[Dict]]:
        """Проверка на дубликаты узлов"""
        
        async with self.graph.driver.session() as session:
            duplicates = {}
            
            # Проверяем дубликаты компаний
            query = """
            MATCH (c:Company)
            RETURN c.id as id, c.ticker as ticker, c.name as name, count(*) as count
            ORDER BY count DESC, c.ticker
            """
            result = await session.run(query)
            companies = [record async for record in result]
            
            company_duplicates = [c for c in companies if c["count"] > 1]
            if company_duplicates:
                duplicates["companies"] = company_duplicates
            
            # Проверяем дубликаты секторов
            query = """
            MATCH (s:Sector)
            RETURN s.id as id, s.name as name, count(*) as count
            ORDER BY count DESC, s.name
            """
            result = await session.run(query)
            sectors = [record async for record in result]
            
            sector_duplicates = [s for s in sectors if s["count"] > 1]
            if sector_duplicates:
                duplicates["sectors"] = sector_duplicates
            
            # Проверяем дубликаты тем
            query = """
            MATCH (t:Topic)
            RETURN t.id as id, t.name as name, count(*) as count
            ORDER BY count DESC, t.name
            """
            result = await session.run(query)
            topics = [record async for record in result]
            
            topic_duplicates = [t for t in topics if t["count"] > 1]
            if topic_duplicates:
                duplicates["topics"] = topic_duplicates
            
            return duplicates
    
    async def check_orphaned_nodes(self) -> Dict[str, int]:
        """Проверка на изолированные узлы"""
        
        async with self.graph.driver.session() as session:
            orphaned = {}
            
            # Изолированные компании (без связей с новостями)
            query = """
            MATCH (c:Company)
            WHERE NOT (c)<-[:ABOUT]-(:News) AND NOT (c)<-[:AFFECTS]-(:News)
            RETURN count(c) as count
            """
            result = await session.run(query)
            record = await result.single()
            orphaned["companies_without_news"] = record["count"] if record else 0
            
            # Изолированные секторы (без компаний)
            query = """
            MATCH (s:Sector)
            WHERE NOT (s)<-[:IN_SECTOR]-(:Company)
            RETURN count(s) as count
            """
            result = await session.run(query)
            record = await result.single()
            orphaned["sectors_without_companies"] = record["count"] if record else 0
            
            # Изолированные темы (без новостей)
            query = """
            MATCH (t:Topic)
            WHERE NOT (t)<-[:HAS_TOPIC]-(:News)
            RETURN count(t) as count
            """
            result = await session.run(query)
            record = await result.single()
            orphaned["topics_without_news"] = record["count"] if record else 0
            
            return orphaned
    
    async def check_data_quality(self) -> Dict[str, Any]:
        """Проверка качества данных"""
        
        async with self.graph.driver.session() as session:
            quality = {}
            
            # Статистика по узлам
            query = """
            MATCH (n)
            RETURN labels(n)[0] as label, count(n) as count
            ORDER BY count DESC
            """
            result = await session.run(query)
            node_stats = {record["label"]: record["count"] async for record in result}
            quality["node_counts"] = node_stats
            
            # Статистика по связям
            query = """
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(r) as count
            ORDER BY count DESC
            """
            result = await session.run(query)
            rel_stats = {record["relationship_type"]: record["count"] async for record in result}
            quality["relationship_counts"] = rel_stats
            
            # Компании с тикерами
            query = """
            MATCH (c:Company)
            WHERE c.ticker IS NOT NULL AND c.ticker <> ""
            RETURN count(c) as count
            """
            result = await session.run(query)
            record = await result.single()
            quality["companies_with_tickers"] = record["count"] if record else 0
            
            # Компании без тикеров
            query = """
            MATCH (c:Company)
            WHERE c.ticker IS NULL OR c.ticker = ""
            RETURN count(c) as count
            """
            result = await session.run(query)
            record = await result.single()
            quality["companies_without_tickers"] = record["count"] if record else 0
            
            return quality
    
    async def run_consistency_check(self) -> Dict[str, Any]:
        """Запуск полной проверки целостности"""
        
        logger.info("Starting graph consistency check...")
        
        results = {
            "duplicates": await self.check_duplicates(),
            "orphaned": await self.check_orphaned_nodes(),
            "quality": await self.check_data_quality()
        }
        
        # Анализ результатов
        issues = []
        
        # Проверяем дубликаты
        for node_type, duplicates in results["duplicates"].items():
            if duplicates:
                issues.append(f"Found {len(duplicates)} duplicate {node_type}")
                for dup in duplicates[:5]:  # Показываем первые 5
                    logger.warning(f"  Duplicate {node_type}: {dup['id']} (count: {dup['count']})")
        
        # Проверяем изолированные узлы
        if results["orphaned"]["companies_without_news"] > 0:
            issues.append(f"Found {results['orphaned']['companies_without_news']} companies without news links")
        
        if results["orphaned"]["sectors_without_companies"] > 0:
            issues.append(f"Found {results['orphaned']['sectors_without_companies']} sectors without companies")
        
        if results["orphaned"]["topics_without_news"] > 0:
            issues.append(f"Found {results['orphaned']['topics_without_news']} topics without news")
        
        results["issues"] = issues
        results["status"] = "PASS" if not issues else "FAIL"
        
        return results
    
    def print_report(self, results: Dict[str, Any]):
        """Вывод отчета о проверке"""
        
        print("\n" + "="*60)
        print("GRAPH CONSISTENCY CHECK REPORT")
        print("="*60)
        
        # Статус
        status = results["status"]
        status_emoji = "✅" if status == "PASS" else "❌"
        print(f"\nStatus: {status_emoji} {status}")
        
        # Качество данных
        print(f"\n📊 DATA QUALITY:")
        quality = results["quality"]
        
        print(f"  Node counts:")
        for label, count in quality["node_counts"].items():
            print(f"    {label}: {count}")
        
        print(f"  Relationship counts:")
        for rel_type, count in quality["relationship_counts"].items():
            print(f"    {rel_type}: {count}")
        
        print(f"  Companies with tickers: {quality['companies_with_tickers']}")
        print(f"  Companies without tickers: {quality['companies_without_tickers']}")
        
        # Проблемы
        if results["issues"]:
            print(f"\n⚠️  ISSUES FOUND ({len(results['issues'])}):")
            for issue in results["issues"]:
                print(f"    • {issue}")
        else:
            print(f"\n✅ No issues found!")
        
        # Изолированные узлы
        orphaned = results["orphaned"]
        print(f"\n🔍 ORPHANED NODES:")
        print(f"  Companies without news: {orphaned['companies_without_news']}")
        print(f"  Sectors without companies: {orphaned['sectors_without_companies']}")
        print(f"  Topics without news: {orphaned['topics_without_news']}")
        
        print("\n" + "="*60)


async def main():
    """Основная функция"""
    
    checker = GraphConsistencyChecker()
    
    try:
        await checker.initialize()
        results = await checker.run_consistency_check()
        checker.print_report(results)
        
        # Возвращаем код выхода
        return 0 if results["status"] == "PASS" else 1
        
    except Exception as e:
        logger.error(f"Error during consistency check: {e}")
        return 1
        
    finally:
        await checker.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
