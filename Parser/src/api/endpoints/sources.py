# src/api/endpoints/sources.py
"""
Sources endpoints
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.database import get_db
from src.core.models import Source
from src.api.schemas import SourceResponse

router = APIRouter()


@router.get("", response_model=List[SourceResponse])
async def list_sources(
    enabled_only: bool = True,
    db: AsyncSession = Depends(get_db)
) -> List[SourceResponse]:
    """Получить список источников"""
    
    stmt = select(Source)
    
    if enabled_only:
        stmt = stmt.where(Source.enabled == True)
    
    stmt = stmt.order_by(Source.name)
    
    result = await db.execute(stmt)
    sources = result.scalars().all()
    
    return [
        SourceResponse(
            code=s.code,
            name=s.name,
            kind=s.kind,
            enabled=s.enabled,
            trust_level=s.trust_level,
            url=s.base_url
        ) for s in sources
    ]


@router.get("/{source_code}", response_model=SourceResponse)
async def get_source(
    source_code: str,
    db: AsyncSession = Depends(get_db)
) -> SourceResponse:
    """Получить информацию об источнике"""
    
    stmt = select(Source).where(Source.code == source_code)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    return SourceResponse(
        code=source.code,
        name=source.name,
        kind=source.kind,
        enabled=source.enabled,
        trust_level=source.trust_level,
        url=source.base_url
    )

