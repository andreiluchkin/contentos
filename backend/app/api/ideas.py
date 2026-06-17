import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import Idea, ContentPillar, ExternalSource
from ..models.enums import PipelineStatus
from ..schemas import IdeaCreate, IdeaOut, IdeaReject, BatchApprove

router = APIRouter(tags=["ideas"])


# --- Входящий webhook от внешних источников (Reddit-проект и др.) ---

@router.post("/inbox/idea", status_code=201)
async def receive_idea(
    data: IdeaCreate,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Публичный endpoint — аутентификация по X-API-Key источника."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    # Проверяем ключ в БД
    import hashlib
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    result = await db.execute(
        select(ExternalSource).where(
            ExternalSource.api_key_hash == key_hash,
            ExternalSource.is_active == True,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Находим пиллар по slug если передан
    pillar_id = None
    if data.pillar:
        pillar_result = await db.execute(
            select(ContentPillar).where(ContentPillar.slug == data.pillar)
        )
        pillar = pillar_result.scalar_one_or_none()
        if pillar:
            pillar_id = pillar.id

    # Проверяем дубликаты по external_idea_id
    if data.external_idea_id:
        dup = await db.execute(
            select(Idea).where(
                Idea.external_source_id == source.id,
                Idea.external_idea_id == data.external_idea_id,
            )
        )
        if dup.scalar_one_or_none():
            return {"id": None, "status": "duplicate", "message": "Idea already exists"}

    idea = Idea(
        title=data.title,
        context=data.context,
        source_url=data.source_url,
        source_name=data.source_name,
        suggested_platform=data.suggested_platform,
        suggested_content_type=data.suggested_content_type,
        relevance_score=data.relevance_score,
        pillar_id=pillar_id,
        external_source_id=source.id,
        external_idea_id=data.external_idea_id,
        status=PipelineStatus.INBOX,
    )
    db.add(idea)

    # Обновляем счётчик источника
    source.ideas_count += 1
    source.last_idea_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(idea)

    return {"id": str(idea.id), "status": "inbox", "created_at": idea.created_at.isoformat()}


# --- CRUD идей ---

@router.get("/ideas", response_model=list[IdeaOut], dependencies=[Depends(require_auth)])
async def list_ideas(
    status: str | None = Query(None, description="Comma-separated statuses"),
    pillar_id: uuid.UUID | None = None,
    source_name: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if status:
        statuses = [s.strip() for s in status.split(",")]
        filters.append(Idea.status.in_(statuses))
    if pillar_id:
        filters.append(Idea.pillar_id == pillar_id)
    if source_name:
        filters.append(Idea.source_name == source_name)

    result = await db.execute(
        select(Idea)
        .where(and_(*filters) if filters else True)
        .order_by(Idea.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.get("/ideas/{idea_id}", response_model=IdeaOut, dependencies=[Depends(require_auth)])
async def get_idea(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    idea = await db.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.patch("/ideas/{idea_id}/approve", response_model=IdeaOut, dependencies=[Depends(require_auth)])
async def approve_idea(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    idea = await db.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    if idea.status != PipelineStatus.INBOX:
        raise HTTPException(status_code=400, detail=f"Cannot approve idea in status '{idea.status}'")

    idea.status = PipelineStatus.IDEA_APPROVED
    idea.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(idea)
    return idea


@router.patch("/ideas/{idea_id}/reject", response_model=IdeaOut, dependencies=[Depends(require_auth)])
async def reject_idea(idea_id: uuid.UUID, data: IdeaReject, db: AsyncSession = Depends(get_db)):
    idea = await db.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    idea.status = "rejected"
    idea.rejected_at = datetime.now(timezone.utc)
    idea.rejection_reason = data.reason
    await db.commit()
    await db.refresh(idea)
    return idea


@router.post("/ideas/batch-approve", dependencies=[Depends(require_auth)])
async def batch_approve(data: BatchApprove, db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    approved = []

    for idea_id in data.idea_ids:
        idea = await db.get(Idea, idea_id)
        if idea and idea.status == PipelineStatus.INBOX:
            idea.status = PipelineStatus.IDEA_APPROVED
            idea.approved_at = now
            approved.append(str(idea_id))

    await db.commit()
    return {"approved": approved, "count": len(approved)}


@router.delete("/ideas/{idea_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_idea(idea_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    idea = await db.get(Idea, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    await db.delete(idea)
    await db.commit()
