import uuid
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import ExternalSource

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceCreate(BaseModel):
    name: str
    display_name: str
    feedback_webhook_url: str | None = None


class SourceOut(BaseModel):
    id: uuid.UUID
    name: str
    display_name: str
    feedback_webhook_url: str | None
    is_active: bool
    ideas_count: int

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SourceOut], dependencies=[Depends(require_auth)])
async def list_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ExternalSource).order_by(ExternalSource.created_at))
    return result.scalars().all()


@router.post("", status_code=201, dependencies=[Depends(require_auth)])
async def create_source(data: SourceCreate, db: AsyncSession = Depends(get_db)):
    """Создаёт источник и возвращает API-ключ. Ключ показывается только один раз."""
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    source = ExternalSource(
        name=data.name,
        display_name=data.display_name,
        api_key_hash=key_hash,
        feedback_webhook_url=data.feedback_webhook_url,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    return {
        "id": str(source.id),
        "name": source.name,
        "display_name": source.display_name,
        "api_key": raw_key,  # Показываем только здесь — сохраните сразу
        "warning": "Save this API key — it will not be shown again",
    }


@router.delete("/{source_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_source(source_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_active = False
    await db.commit()
