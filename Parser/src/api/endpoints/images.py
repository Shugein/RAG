#Parser.src/api/endpoints/images.py

from uuid import UUID
from fastapi import APIRouter, Depends, Path, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from Parser.src.core.database import get_db
from Parser.src.core.models import Image

router = APIRouter()


@router.get("/{image_id}/bytes")
async def get_image_bytes(
    image_id: UUID = Path(..., description="Image ID"),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Get image binary data"""
    
    # Get image
    result = await db.execute(
        select(Image).where(Image.id == image_id)
    )
    image = result.scalar_one_or_none()
    
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    return Response(
        content=image.bytes,
        media_type=image.mime_type,
        headers={
            "Cache-Control": "public, max-age=31536000",  # 1 year
            "ETag": image.sha256
        }
    )
