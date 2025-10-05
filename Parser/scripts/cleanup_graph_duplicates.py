#!/usr/bin/env python3
"""
Скрипт для очистки дубликатов в графовой базе данных
Удаляет дублирующиеся узлы и объединяет связи
"""

import asyncio
import logging
import sys
from typing import Dict, List, Any
from pathlib import Path

# Добавляем путь кParser.src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from Parser.src.core.config import settings
from Parser.src.graph_models import GraphService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GraphDuplicateCleaner:
    """Очистка дубликатов в графовой базе данных"""
    
    def __init__(self):
        self.graph = None
    
    async def initialize(self):
        """Инициализация подключения к графу"""
        self.graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        logger.info("Connected to Neo4j")
    
    async def close(self):
        """Закрытие соединения"""
        if self.graph:
            await self.graph.close()
    
    async def cleanup_duplicate_companies(self) -> int:
        """Очистка дубликатов компаний"""
        
        async with self.graph.driver.session() as session:
            # Находим дубликаты компаний по тикеру
            query = """
            MATCH (c:Company)
            WHERE c.ticker IS NOT NULL AND c.ticker <> ""
            WITH c.ticker as ticker, collect(c) as companies
            WHERE size(companies) > 1
            RETURN ticker, companies
            ORDER BY size(companies) DESC
            """
            
            result = await session.run(query)
            duplicates = [record async for record in result]
            
            cleaned_count = 0
            
            for record in duplicates:
                ticker = record["ticker"]
                companies = record["companies"]
                
                # Берем первую компанию как основную
                main_company = companies[0]
                duplicate_companies = companies[1:]
                
                logger.info(f"Cleaning up {len(duplicate_companies)} duplicates for ticker {ticker}")
                
                for dup_company in duplicate_companies:
                    # Перемещаем все связи от дубликата к основной компании
                    await self._merge_company_relationships(session, dup_company, main_company)
                    
                    # Удаляем дубликат
                    delete_query = """
                    MATCH (c:Company {id: $company_id})
                    DETACH DELETE c
                    """
                    await session.run(delete_query, company_id=dup_company["id"])
                    
                    cleaned_count += 1
            
            return cleaned_count
    
    async def cleanup_duplicate_sectors(self) -> int:
        """Очистка дубликатов секторов"""
        
        async with self.graph.driver.session() as session:
            # Находим дубликаты секторов по названию
            query = """
            MATCH (s:Sector)
            WITH s.name as name, collect(s) as sectors
            WHERE size(sectors) > 1
            RETURN name, sectors
            ORDER BY size(sectors) DESC
            """
            
            result = await session.run(query)
            duplicates = [record async for record in result]
            
            cleaned_count = 0
            
            for record in duplicates:
                name = record["name"]
                sectors = record["sectors"]
                
                # Берем первый сектор как основной
                main_sector = sectors[0]
                duplicate_sectors = sectors[1:]
                
                logger.info(f"Cleaning up {len(duplicate_sectors)} duplicate sectors for '{name}'")
                
                for dup_sector in duplicate_sectors:
                    # Перемещаем все связи от дубликата к основному сектору
                    await self._merge_sector_relationships(session, dup_sector, main_sector)
                    
                    # Удаляем дубликат
                    delete_query = """
                    MATCH (s:Sector {id: $sector_id})
                    DETACH DELETE s
                    """
                    await session.run(delete_query, sector_id=dup_sector["id"])
                    
                    cleaned_count += 1
            
            return cleaned_count
    
    async def cleanup_duplicate_topics(self) -> int:
        """Очистка дубликатов тем"""
        
        async with self.graph.driver.session() as session:
            # Находим дубликаты тем по названию
            query = """
            MATCH (t:Topic)
            WITH t.name as name, collect(t) as topics
            WHERE size(topics) > 1
            RETURN name, topics
            ORDER BY size(topics) DESC
            """
            
            result = await session.run(query)
            duplicates = [record async for record in result]
            
            cleaned_count = 0
            
            for record in duplicates:
                name = record["name"]
                topics = record["topics"]
                
                # Берем первую тему как основную
                main_topic = topics[0]
                duplicate_topics = topics[1:]
                
                logger.info(f"Cleaning up {len(duplicate_topics)} duplicate topics for '{name}'")
                
                for dup_topic in duplicate_topics:
                    # Перемещаем все связи от дубликата к основной теме
                    await self._merge_topic_relationships(session, dup_topic, main_topic)
                    
                    # Удаляем дубликат
                    delete_query = """
                    MATCH (t:Topic {id: $topic_id})
                    DETACH DELETE t
                    """
                    await session.run(delete_query, topic_id=dup_topic["id"])
                    
                    cleaned_count += 1
            
            return cleaned_count
    
    async def _merge_company_relationships(self, session, from_company: Dict, to_company: Dict):
        """Перемещение связей от одной компании к другой"""
        
        # Перемещаем связи ABOUT
        query = """
        MATCH (n:News)-[r:ABOUT]->(c:Company {id: $from_id})
        MERGE (n)-[:ABOUT]->(target:Company {id: $to_id})
        DELETE r
        """
        await session.run(query, from_id=from_company["id"], to_id=to_company["id"])
        
        # Перемещаем связи AFFECTS
        query = """
        MATCH (n:News)-[r:AFFECTS]->(c:Company {id: $from_id})
        MERGE (n)-[:AFFECTS {weight: r.weight, window: r.window, dt: r.dt, method: r.method}]->(target:Company {id: $to_id})
        DELETE r
        """
        await session.run(query, from_id=from_company["id"], to_id=to_company["id"])
        
        # Перемещаем связи IN_SECTOR
        query = """
        MATCH (c:Company {id: $from_id})-[r:IN_SECTOR]->(s:Sector)
        MERGE (target:Company {id: $to_id})-[:IN_SECTOR]->(s)
        DELETE r
        """
        await session.run(query, from_id=from_company["id"], to_id=to_company["id"])
        
        # Перемещаем связи HAS_COMPANY
        query = """
        MATCH (m:Market)-[r:HAS_COMPANY]->(c:Company {id: $from_id})
        MERGE (m)-[:HAS_COMPANY]->(target:Company {id: $to_id})
        DELETE r
        """
        await session.run(query, from_id=from_company["id"], to_id=to_company["id"])
        
        # Перемещаем связи COVARIATES_WITH
        query = """
        MATCH (c1:Company {id: $from_id})-[r:COVARIATES_WITH]-(c2:Company)
        MERGE (target:Company {id: $to_id})-[:COVARIATES_WITH {rho: r.rho, window: r.window, updated_at: r.updated_at}]-(c2)
        DELETE r
        """
        await session.run(query, from_id=from_company["id"], to_id=to_company["id"])
    
    async def _merge_sector_relationships(self, session, from_sector: Dict, to_sector: Dict):
        """Перемещение связей от одного сектора к другому"""
        
        # Перемещаем связи IN_SECTOR
        query = """
        MATCH (c:Company)-[r:IN_SECTOR]->(s:Sector {id: $from_id})
        MERGE (c)-[:IN_SECTOR]->(target:Sector {id: $to_id})
        DELETE r
        """
        await session.run(query, from_id=from_sector["id"], to_id=to_sector["id"])
    
    async def _merge_topic_relationships(self, session, from_topic: Dict, to_topic: Dict):
        """Перемещение связей от одной темы к другой"""
        
        # Перемещаем связи HAS_TOPIC
        query = """
        MATCH (n:News)-[r:HAS_TOPIC]->(t:Topic {id: $from_id})
        MERGE (n)-[:HAS_TOPIC]->(target:Topic {id: $to_id})
        DELETE r
        """
        await session.run(query, from_id=from_topic["id"], to_id=to_topic["id"])
    
    async def run_cleanup(self, dry_run: bool = False) -> Dict[str, int]:
        """Запуск очистки дубликатов"""
        
        logger.info(f"Starting duplicate cleanup (dry_run={dry_run})...")
        
        results = {
            "companies_cleaned": 0,
            "sectors_cleaned": 0,
            "topics_cleaned": 0
        }
        
        if not dry_run:
            results["companies_cleaned"] = await self.cleanup_duplicate_companies()
            results["sectors_cleaned"] = await self.cleanup_duplicate_sectors()
            results["topics_cleaned"] = await self.cleanup_duplicate_topics()
        else:
            logger.info("Dry run mode - no changes will be made")
            # В режиме dry run просто считаем дубликаты
            results["companies_cleaned"] = await self._count_duplicate_companies()
            results["sectors_cleaned"] = await self._count_duplicate_sectors()
            results["topics_cleaned"] = await self._count_duplicate_topics()
        
        return results
    
    async def _count_duplicate_companies(self) -> int:
        """Подсчет дубликатов компаний"""
        async with self.graph.driver.session() as session:
            query = """
            MATCH (c:Company)
            WHERE c.ticker IS NOT NULL AND c.ticker <> ""
            WITH c.ticker as ticker, collect(c) as companies
            WHERE size(companies) > 1
            RETURN sum(size(companies) - 1) as total_duplicates
            """
            result = await session.run(query)
            record = await result.single()
            return record["total_duplicates"] if record else 0
    
    async def _count_duplicate_sectors(self) -> int:
        """Подсчет дубликатов секторов"""
        async with self.graph.driver.session() as session:
            query = """
            MATCH (s:Sector)
            WITH s.name as name, collect(s) as sectors
            WHERE size(sectors) > 1
            RETURN sum(size(sectors) - 1) as total_duplicates
            """
            result = await session.run(query)
            record = await result.single()
            return record["total_duplicates"] if record else 0
    
    async def _count_duplicate_topics(self) -> int:
        """Подсчет дубликатов тем"""
        async with self.graph.driver.session() as session:
            query = """
            MATCH (t:Topic)
            WITH t.name as name, collect(t) as topics
            WHERE size(topics) > 1
            RETURN sum(size(topics) - 1) as total_duplicates
            """
            result = await session.run(query)
            record = await result.single()
            return record["total_duplicates"] if record else 0
    
    def print_report(self, results: Dict[str, int], dry_run: bool = False):
        """Вывод отчета о очистке"""
        
        print("\n" + "="*60)
        print("GRAPH DUPLICATE CLEANUP REPORT")
        print("="*60)
        
        mode = "DRY RUN" if dry_run else "ACTUAL CLEANUP"
        print(f"\nMode: {mode}")
        
        total_cleaned = sum(results.values())
        
        print(f"\n📊 CLEANUP RESULTS:")
        print(f"  Companies cleaned: {results['companies_cleaned']}")
        print(f"  Sectors cleaned: {results['sectors_cleaned']}")
        print(f"  Topics cleaned: {results['topics_cleaned']}")
        print(f"  Total cleaned: {total_cleaned}")
        
        if dry_run:
            print(f"\n💡 This was a dry run. Use --execute to perform actual cleanup.")
        else:
            print(f"\n✅ Cleanup completed successfully!")
        
        print("\n" + "="*60)


async def main():
    """Основная функция"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up duplicates in Neo4j graph")
    parser.add_argument("--execute", action="store_true", 
                       help="Execute actual cleanup (default is dry run)")
    parser.add_argument("--companies", action="store_true",
                       help="Clean up only companies")
    parser.add_argument("--sectors", action="store_true",
                       help="Clean up only sectors")
    parser.add_argument("--topics", action="store_true",
                       help="Clean up only topics")
    
    args = parser.parse_args()
    
    cleaner = GraphDuplicateCleaner()
    
    try:
        await cleaner.initialize()
        
        dry_run = not args.execute
        
        if args.companies:
            # Очистка только компаний
            results = {"companies_cleaned": 0, "sectors_cleaned": 0, "topics_cleaned": 0}
            if dry_run:
                results["companies_cleaned"] = await cleaner._count_duplicate_companies()
            else:
                results["companies_cleaned"] = await cleaner.cleanup_duplicate_companies()
        elif args.sectors:
            # Очистка только секторов
            results = {"companies_cleaned": 0, "sectors_cleaned": 0, "topics_cleaned": 0}
            if dry_run:
                results["sectors_cleaned"] = await cleaner._count_duplicate_sectors()
            else:
                results["sectors_cleaned"] = await cleaner.cleanup_duplicate_sectors()
        elif args.topics:
            # Очистка только тем
            results = {"companies_cleaned": 0, "sectors_cleaned": 0, "topics_cleaned": 0}
            if dry_run:
                results["topics_cleaned"] = await cleaner._count_duplicate_topics()
            else:
                results["topics_cleaned"] = await cleaner.cleanup_duplicate_topics()
        else:
            # Полная очистка
            results = await cleaner.run_cleanup(dry_run=dry_run)
        
        cleaner.print_report(results, dry_run=dry_run)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return 1
        
    finally:
        await cleaner.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
