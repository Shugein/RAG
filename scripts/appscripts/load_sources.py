# scripts/load_sources.py
"""
Скрипт загрузки источников из конфигурации
"""

import asyncio
import sys
import yaml
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from Parser.src.core.database import init_db, close_db, get_db_session
from Parser.src.core.models import Source
from sqlalchemy import select

async def load_sources():
    """Загрузка источников из config/sources.yml"""
    
    # Инициализация БД
    await init_db()
    
    try:
        # Читаем конфигурацию
        config_path = Path("config/sources.yml")
        if not config_path.exists():
            print(f"Creating default sources config at {config_path}")
            # Создаем дефолтный конфиг
            default_config = {
                "sources": [
                    {
                        "code": "interfax",
                        "name": "Интерфакс",
                        "kind": "telegram",
                        "tg_chat_id": "@interfaxonline",
                        "enabled": True,
                        "trust_level": 9,
                        "config": {
                            "fetch_limit": 100,
                            "backfill_enabled": True
                        }
                    },
                    {
                        "code": "rbc_news",
                        "name": "РБК",
                        "kind": "telegram",
                        "tg_chat_id": "@rbc_news",
                        "enabled": True,
                        "trust_level": 8,
                        "config": {
                            "fetch_limit": 100,
                            "backfill_enabled": True
                        }
                    }
                ]
            }
            
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        async with get_db_session() as session:
            # Проверяем и добавляем источники
            for source_data in config.get('sources', []):
                # Проверяем, существует ли уже
                result = await session.execute(
                    select(Source).where(Source.code == source_data['code'])
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    print(f"Source {source_data['code']} already exists, updating...")
                    # Обновляем существующий
                    for key, value in source_data.items():
                        if key != 'code':
                            setattr(existing, key, value)
                else:
                    print(f"Adding new source: {source_data['code']}")
                    # Создаем новый
                    source = Source(
                        id=uuid4(),
                        code=source_data['code'],
                        name=source_data['name'],
                        kind=source_data['kind'],
                        tg_chat_id=source_data.get('tg_chat_id'),
                        base_url=source_data.get('base_url'),
                        enabled=source_data.get('enabled', True),
                        trust_level=source_data.get('trust_level', 5),
                        config=source_data.get('config', {})
                    )
                    session.add(source)
            
            await session.commit()
            print(f"✓ Loaded {len(config.get('sources', []))} sources")
            
            # Показываем загруженные источники
            result = await session.execute(select(Source))
            all_sources = result.scalars().all()
            print("\nActive sources:")
            for source in all_sources:
                status = "✓" if source.enabled else "✗"
                print(f"  {status} {source.code}: {source.name} ({source.kind})")
    
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(load_sources())