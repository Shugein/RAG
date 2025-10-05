#!/usr/bin/env python3
# scripts/import_neo4j_dump.py
"""
Скрипт для восстановления дампа базы данных Neo4j
Поддерживает восстановление из:
1. Cypher скрипта (.cypher)
2. JSON файла (.json)
3. CSV файлов (nodes_*.csv, relationships_*.csv)
"""

import asyncio
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from Parser.src.core.config import settings
from Parser.src.graph_models import GraphService


class Neo4jDumpImporter:
    """Класс для импорта данных в Neo4j из различных форматов"""
    
    def __init__(self, graph_service: GraphService):
        self.graph = graph_service
    
    async def import_cypher_dump(self, cypher_file: str) -> None:
        """Импорт из Cypher скрипта"""
        print(f"📝 Импорт из Cypher файла: {cypher_file}")
        
        if not Path(cypher_file).exists():
            raise FileNotFoundError(f"Файл не найден: {cypher_file}")
        
        with open(cypher_file, 'r', encoding='utf-8') as f:
            cypher_script = f.read()
        
        # Разбиваем скрипт на отдельные запросы
        statements = [stmt.strip() for stmt in cypher_script.split(';') if stmt.strip()]
        
        async with self.graph.driver.session() as session:
            for i, statement in enumerate(statements, 1):
                if statement.startswith('--'):
                    continue  # Пропускаем комментарии
                
                try:
                    print(f"  Выполнение запроса {i}/{len(statements)}...")
                    await session.run(statement)
                except Exception as e:
                    print(f"  ⚠️  Ошибка в запросе {i}: {e}")
                    print(f"  Запрос: {statement[:100]}...")
                    # Продолжаем выполнение остальных запросов
        
        print(f"✅ Cypher дамп импортирован: {cypher_file}")
    
    async def import_json_dump(self, json_file: str) -> None:
        """Импорт из JSON файла"""
        print(f"📄 Импорт из JSON файла: {json_file}")
        
        if not Path(json_file).exists():
            raise FileNotFoundError(f"Файл не найден: {json_file}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        async with self.graph.driver.session() as session:
            # Импортируем узлы
            print(f"  Импорт {len(data['nodes'])} узлов...")
            for node_data in data['nodes']:
                labels = ':'.join(node_data['labels'])
                properties = node_data['properties']
                
                # Создаем узел
                prop_str = ', '.join([f"{k}: ${k}" for k in properties.keys()])
                query = f"CREATE (n:{labels} {{{prop_str}}})"
                
                await session.run(query, properties)
            
            # Импортируем связи
            print(f"  Импорт {len(data['relationships'])} связей...")
            for rel_data in data['relationships']:
                rel_type = rel_data['type']
                start_id = rel_data['start_node']
                end_id = rel_data['end_node']
                properties = rel_data['properties']
                
                # Создаем связь
                prop_str = ', '.join([f"{k}: ${k}" for k in properties.keys()]) if properties else ""
                if prop_str:
                    query = f"""
                        MATCH (a), (b)
                        WHERE a.element_id = $start_id AND b.element_id = $end_id
                        CREATE (a)-[r:{rel_type} {{{prop_str}}}]->(b)
                    """
                    params = {"start_id": start_id, "end_id": end_id, **properties}
                else:
                    query = f"""
                        MATCH (a), (b)
                        WHERE a.element_id = $start_id AND b.element_id = $end_id
                        CREATE (a)-[r:{rel_type}]->(b)
                    """
                    params = {"start_id": start_id, "end_id": end_id}
                
                await session.run(query, params)
        
        print(f"✅ JSON дамп импортирован: {json_file}")
    
    async def import_csv_dump(self, csv_dir: str) -> None:
        """Импорт из CSV файлов"""
        print(f"📊 Импорт из CSV директории: {csv_dir}")
        
        csv_path = Path(csv_dir)
        if not csv_path.exists():
            raise FileNotFoundError(f"Директория не найдена: {csv_dir}")
        
        # Находим файлы узлов и связей
        nodes_files = list(csv_path.glob("nodes_*.csv"))
        rels_files = list(csv_path.glob("relationships_*.csv"))
        
        if not nodes_files:
            raise FileNotFoundError("Не найдены файлы узлов (nodes_*.csv)")
        
        async with self.graph.driver.session() as session:
            # Импортируем узлы
            for nodes_file in nodes_files:
                print(f"  Импорт узлов из: {nodes_file.name}")
                
                with open(nodes_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    
                    for row in reader:
                        labels = row['labels'].split('|')
                        labels_str = ':'.join(labels)
                        
                        # Убираем служебные поля
                        properties = {k: v for k, v in row.items() if k not in ['id', 'labels']}
                        
                        # Конвертируем значения
                        for key, value in properties.items():
                            if value == '':
                                properties[key] = None
                            elif value.lower() in ['true', 'false']:
                                properties[key] = value.lower() == 'true'
                            elif value.isdigit():
                                properties[key] = int(value)
                            elif value.replace('.', '').isdigit():
                                properties[key] = float(value)
                        
                        # Создаем узел
                        prop_str = ', '.join([f"{k}: ${k}" for k in properties.keys()])
                        query = f"CREATE (n:{labels_str} {{{prop_str}}})"
                        
                        await session.run(query, properties)
            
            # Импортируем связи
            for rels_file in rels_files:
                print(f"  Импорт связей из: {rels_file.name}")
                
                with open(rels_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    
                    for row in reader:
                        rel_type = row['type']
                        start_id = row['start_node']
                        end_id = row['end_node']
                        
                        # Убираем служебные поля
                        properties = {k: v for k, v in row.items() if k not in ['id', 'type', 'start_node', 'end_node']}
                        
                        # Конвертируем значения
                        for key, value in properties.items():
                            if value == '':
                                properties[key] = None
                            elif value.lower() in ['true', 'false']:
                                properties[key] = value.lower() == 'true'
                            elif value.isdigit():
                                properties[key] = int(value)
                            elif value.replace('.', '').isdigit():
                                properties[key] = float(value)
                        
                        # Создаем связь
                        prop_str = ', '.join([f"{k}: ${k}" for k in properties.keys()]) if properties else ""
                        if prop_str:
                            query = f"""
                                MATCH (a), (b)
                                WHERE a.element_id = $start_id AND b.element_id = $end_id
                                CREATE (a)-[r:{rel_type} {{{prop_str}}}]->(b)
                            """
                            params = {"start_id": start_id, "end_id": end_id, **properties}
                        else:
                            query = f"""
                                MATCH (a), (b)
                                WHERE a.element_id = $start_id AND b.element_id = $end_id
                                CREATE (a)-[r:{rel_type}]->(b)
                            """
                            params = {"start_id": start_id, "end_id": end_id}
                        
                        await session.run(query, params)
        
        print(f"✅ CSV дамп импортирован: {csv_dir}")
    
    async def clear_database(self) -> None:
        """Очистка базы данных перед импортом"""
        print("🗑️  Очистка базы данных...")
        
        async with self.graph.driver.session() as session:
            # Удаляем все связи и узлы
            await session.run("MATCH (n) DETACH DELETE n")
        
        print("✅ База данных очищена")
    
    async def verify_import(self) -> None:
        """Проверка успешности импорта"""
        print("🔍 Проверка импорта...")
        
        async with self.graph.driver.session() as session:
            # Подсчитываем узлы по типам
            result = await session.run("MATCH (n) RETURN labels(n) as labels, count(n) as count")
            print("  Узлы по типам:")
            async for record in result:
                labels = record['labels']
                count = record['count']
                print(f"    {':'.join(labels)}: {count}")
            
            # Подсчитываем связи по типам
            result = await session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count")
            print("  Связи по типам:")
            async for record in result:
                rel_type = record['type']
                count = record['count']
                print(f"    {rel_type}: {count}")
        
        print("✅ Проверка завершена")


async def main():
    """Главная функция"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Импорт дампа Neo4j")
    parser.add_argument("file", help="Путь к файлу дампа или директории с CSV файлами")
    parser.add_argument("--clear", action="store_true", help="Очистить базу данных перед импортом")
    parser.add_argument("--verify", action="store_true", help="Проверить импорт после завершения")
    
    args = parser.parse_args()
    
    print("🚀" * 30)
    print("ИМПОРТ ДАМПА NEO4J")
    print("🚀" * 30)
    
    # Создаем подключение к Neo4j
    try:
        graph = GraphService(
            uri=settings.NEO4J_URI,
            user=settings.NEO4J_USER,
            password=settings.NEO4J_PASSWORD
        )
        
        # Тестируем подключение
        async with graph.driver.session() as session:
            result = await session.run("RETURN 'Connected' as status")
            record = await result.single()
            print(f"✅ Подключение к Neo4j: {record['status']}")
        
    except Exception as e:
        print(f"❌ Ошибка подключения к Neo4j: {e}")
        print("\n💡 Убедитесь, что Neo4j запущен:")
        print("   docker-compose up neo4j")
        return
    
    # Создаем импортер
    importer = Neo4jDumpImporter(graph)
    
    try:
        # Очищаем базу данных если нужно
        if args.clear:
            await importer.clear_database()
        
        # Определяем тип файла и импортируем
        file_path = Path(args.file)
        
        if file_path.suffix == '.cypher':
            await importer.import_cypher_dump(str(file_path))
        elif file_path.suffix == '.json':
            await importer.import_json_dump(str(file_path))
        elif file_path.is_dir():
            await importer.import_csv_dump(str(file_path))
        else:
            print(f"❌ Неподдерживаемый формат файла: {file_path.suffix}")
            print("💡 Поддерживаемые форматы: .cypher, .json, директория с CSV файлами")
            return
        
        # Проверяем импорт если нужно
        if args.verify:
            await importer.verify_import()
        
        print(f"\n✅ Импорт завершен успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка импорта: {e}")
    
    finally:
        await graph.close()


if __name__ == "__main__":
    asyncio.run(main())
