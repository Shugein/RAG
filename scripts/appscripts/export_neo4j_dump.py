#!/usr/bin/env python3
# scripts/export_neo4j_dump.py
"""
Скрипт для выгрузки дампа базы данных Neo4j
Поддерживает несколько форматов экспорта:
1. Cypher скрипт (CREATE/MERGE statements)
2. JSON формат
3. CSV формат
4. GraphML формат
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


class Neo4jDumpExporter:
    """Класс для экспорта данных из Neo4j в различные форматы"""
    
    def __init__(self, graph_service: GraphService):
        self.graph = graph_service
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    async def export_cypher_dump(self, output_file: str) -> None:
        """Экспорт в формате Cypher скрипта"""
        print(f"📝 Экспорт в Cypher формат: {output_file}")
        
        cypher_statements = []
        
        async with self.graph.driver.session() as session:
            # 1. Создаем констрейнты и индексы
            cypher_statements.append("-- Constraints and Indexes")
            result = await session.run("SHOW CONSTRAINTS")
            async for record in result:
                constraint_info = dict(record)
                if constraint_info.get('type') == 'UNIQUENESS':
                    cypher_statements.append(f"CREATE CONSTRAINT {constraint_info['name']} IF NOT EXISTS FOR (n:{constraint_info['labelsOrTypes'][0]}) REQUIRE n.{constraint_info['properties'][0]} IS UNIQUE;")
                elif constraint_info.get('type') == 'NODE_PROPERTY_EXISTENCE':
                    cypher_statements.append(f"CREATE CONSTRAINT {constraint_info['name']} IF NOT EXISTS FOR (n:{constraint_info['labelsOrTypes'][0]}) REQUIRE n.{constraint_info['properties'][0]} IS NOT NULL;")
            
            result = await session.run("SHOW INDEXES")
            async for record in result:
                index_info = dict(record)
                if not index_info.get('name', '').startswith('constraint_'):
                    cypher_statements.append(f"CREATE INDEX {index_info['name']} IF NOT EXISTS FOR (n:{index_info['labelsOrTypes'][0]}) ON (n.{index_info['properties'][0]});")
            
            cypher_statements.append("")
            
            # 2. Экспортируем узлы
            cypher_statements.append("-- Nodes")
            node_types = await self._get_node_types(session)
            
            for node_type in node_types:
                cypher_statements.append(f"-- {node_type} nodes")
                query = f"MATCH (n:{node_type}) RETURN n"
                result = await session.run(query)
                
                async for record in result:
                    node = record['n']
                    properties = dict(node)
                    labels = list(node.labels)
                    
                    # Создаем MERGE statement
                    merge_parts = [f"MERGE (n:{':'.join(labels)}"]
                    
                    # Добавляем свойства для идентификации
                    id_props = []
                    for prop in ['id', 'code', 'name']:
                        if prop in properties:
                            id_props.append(f"n.{prop} = ${prop}")
                    
                    if id_props:
                        merge_parts.append(f" {{ {', '.join(id_props)} }}")
                    else:
                        merge_parts.append(" { id: $id }")
                    
                    merge_parts.append(")")
                    cypher_statements.append(" ".join(merge_parts))
                    
                    # Добавляем SET для всех свойств
                    set_parts = []
                    for key, value in properties.items():
                        if value is not None:
                            if isinstance(value, str):
                                value = value.replace("'", "\\'")
                                set_parts.append(f"n.{key} = '{value}'")
                            else:
                                set_parts.append(f"n.{key} = {value}")
                    
                    if set_parts:
                        cypher_statements.append(f"SET {', '.join(set_parts)};")
                    
                    cypher_statements.append("")
            
            # 3. Экспортируем связи
            cypher_statements.append("-- Relationships")
            relationship_types = await self._get_relationship_types(session)
            
            for rel_type in relationship_types:
                cypher_statements.append(f"-- {rel_type} relationships")
                query = f"MATCH (a)-[r:{rel_type}]->(b) RETURN a, r, b"
                result = await session.run(query)
                
                async for record in result:
                    start_node = record['a']
                    rel = record['r']
                    end_node = record['b']
                    
                    # Определяем идентификаторы узлов
                    start_id = self._get_node_identifier(start_node)
                    end_id = self._get_node_identifier(end_node)
                    
                    # Создаем MATCH для узлов
                    start_labels = ':'.join(list(start_node.labels))
                    end_labels = ':'.join(list(end_node.labels))
                    
                    cypher_statements.append(f"MATCH (a:{start_labels} {{ {start_id} }})")
                    cypher_statements.append(f"MATCH (b:{end_labels} {{ {end_id} }})")
                    
                    # Создаем связь
                    rel_props = dict(rel)
                    if rel_props:
                        prop_str = ', '.join([f"{k}: {repr(v)}" for k, v in rel_props.items()])
                        cypher_statements.append(f"MERGE (a)-[r:{rel_type} {{{prop_str}}}]->(b);")
                    else:
                        cypher_statements.append(f"MERGE (a)-[r:{rel_type}]->(b);")
                    
                    cypher_statements.append("")
        
        # Сохраняем в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(cypher_statements))
        
        print(f"✅ Cypher дамп сохранен: {output_file}")
    
    async def export_json_dump(self, output_file: str) -> None:
        """Экспорт в JSON формат"""
        print(f"📄 Экспорт в JSON формат: {output_file}")
        
        data = {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "neo4j_uri": settings.NEO4J_URI,
                "database": settings.NEO4J_DATABASE
            },
            "nodes": [],
            "relationships": []
        }
        
        async with self.graph.driver.session() as session:
            # Экспортируем узлы
            result = await session.run("MATCH (n) RETURN n")
            async for record in result:
                node = record['n']
                node_data = {
                    "id": node.element_id,
                    "labels": list(node.labels),
                    "properties": dict(node)
                }
                data["nodes"].append(node_data)
            
            # Экспортируем связи
            result = await session.run("MATCH (a)-[r]->(b) RETURN a, r, b")
            async for record in result:
                rel = record['r']
                rel_data = {
                    "id": rel.element_id,
                    "type": rel.type,
                    "start_node": record['a'].element_id,
                    "end_node": record['b'].element_id,
                    "properties": dict(rel)
                }
                data["relationships"].append(rel_data)
        
        # Сохраняем в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ JSON дамп сохранен: {output_file}")
    
    async def export_csv_dump(self, output_dir: str) -> None:
        """Экспорт в CSV формат (отдельные файлы для узлов и связей)"""
        print(f"📊 Экспорт в CSV формат: {output_dir}")
        
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        async with self.graph.driver.session() as session:
            # Экспортируем узлы
            nodes_file = Path(output_dir) / f"nodes_{self.timestamp}.csv"
            with open(nodes_file, 'w', newline='', encoding='utf-8') as f:
                writer = None
                
                result = await session.run("MATCH (n) RETURN n")
                async for record in result:
                    node = record['n']
                    node_data = {
                        "id": node.element_id,
                        "labels": '|'.join(list(node.labels)),
                        **dict(node)
                    }
                    
                    if writer is None:
                        writer = csv.DictWriter(f, fieldnames=node_data.keys())
                        writer.writeheader()
                    
                    writer.writerow(node_data)
            
            print(f"✅ Узлы экспортированы: {nodes_file}")
            
            # Экспортируем связи
            rels_file = Path(output_dir) / f"relationships_{self.timestamp}.csv"
            with open(rels_file, 'w', newline='', encoding='utf-8') as f:
                writer = None
                
                result = await session.run("MATCH (a)-[r]->(b) RETURN a, r, b")
                async for record in result:
                    rel = record['r']
                    rel_data = {
                        "id": rel.element_id,
                        "type": rel.type,
                        "start_node": record['a'].element_id,
                        "end_node": record['b'].element_id,
                        **dict(rel)
                    }
                    
                    if writer is None:
                        writer = csv.DictWriter(f, fieldnames=rel_data.keys())
                        writer.writeheader()
                    
                    writer.writerow(rel_data)
            
            print(f"✅ Связи экспортированы: {rels_file}")
    
    async def _get_node_types(self, session) -> List[str]:
        """Получить список типов узлов"""
        result = await session.run("CALL db.labels()")
        return [record['label'] for record in result]
    
    async def _get_relationship_types(self, session) -> List[str]:
        """Получить список типов связей"""
        result = await session.run("CALL db.relationshipTypes()")
        return [record['relationshipType'] for record in result]
    
    def _get_node_identifier(self, node) -> str:
        """Получить идентификатор узла для MERGE statement"""
        properties = dict(node)
        
        # Пробуем найти уникальный идентификатор
        for prop in ['id', 'code', 'name']:
            if prop in properties:
                value = properties[prop]
                if isinstance(value, str):
                    value = value.replace("'", "\\'")
                    return f"{prop}: '{value}'"
                else:
                    return f"{prop}: {value}"
        
        # Если не нашли, используем element_id
        return f"element_id: '{node.element_id}'"


async def main():
    """Главная функция"""
    print("🚀" * 30)
    print("ЭКСПОРТ ДАМПА NEO4J")
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
    
    # Создаем экспортер
    exporter = Neo4jDumpExporter(graph)
    
    # Создаем директорию для дампов
    dump_dir = Path("dumps")
    dump_dir.mkdir(exist_ok=True)
    
    try:
        # Экспортируем в разные форматы
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 1. Cypher дамп
        cypher_file = dump_dir / f"neo4j_dump_{timestamp}.cypher"
        await exporter.export_cypher_dump(str(cypher_file))
        
        # 2. JSON дамп
        json_file = dump_dir / f"neo4j_dump_{timestamp}.json"
        await exporter.export_json_dump(str(json_file))
        
        # 3. CSV дамп
        csv_dir = dump_dir / f"neo4j_dump_{timestamp}_csv"
        await exporter.export_csv_dump(str(csv_dir))
        
        print(f"\n✅ Все дампы созданы в директории: {dump_dir.absolute()}")
        print(f"📁 Cypher: {cypher_file}")
        print(f"📁 JSON: {json_file}")
        print(f"📁 CSV: {csv_dir}")
        
        print(f"\n💡 Для восстановления дампа:")
        print(f"   cypher-shell -u {settings.NEO4J_USER} -p {settings.NEO4J_PASSWORD} < {cypher_file}")
        
    except Exception as e:
        print(f"❌ Ошибка экспорта: {e}")
    
    finally:
        await graph.close()


if __name__ == "__main__":
    asyncio.run(main())
