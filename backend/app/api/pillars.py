import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import ContentPillar, Post
from ..schemas import PillarCreate, PillarUpdate, PillarOut

router = APIRouter(prefix="/pillars", tags=["pillars"])


@router.get("", response_model=list[PillarOut], dependencies=[Depends(require_auth)])
async def list_pillars(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ContentPillar).order_by(ContentPillar.sort_order, ContentPillar.name)
    )
    return result.scalars().all()


@router.post("", response_model=PillarOut, status_code=201, dependencies=[Depends(require_auth)])
async def create_pillar(data: PillarCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(ContentPillar).where(ContentPillar.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Pillar with slug '{data.slug}' already exists")

    pillar = ContentPillar(**data.model_dump())
    db.add(pillar)
    await db.commit()
    await db.refresh(pillar)
    return pillar


@router.patch("/{pillar_id}", response_model=PillarOut, dependencies=[Depends(require_auth)])
async def update_pillar(
    pillar_id: uuid.UUID,
    data: PillarUpdate,
    db: AsyncSession = Depends(get_db),
):
    pillar = await db.get(ContentPillar, pillar_id)
    if not pillar:
        raise HTTPException(status_code=404, detail="Pillar not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(pillar, field, value)

    await db.commit()
    await db.refresh(pillar)
    return pillar


@router.delete("/{pillar_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_pillar(pillar_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    pillar = await db.get(ContentPillar, pillar_id)
    if not pillar:
        raise HTTPException(status_code=404, detail="Pillar not found")
    await db.delete(pillar)
    await db.commit()


@router.get("/{pillar_id}/stats", dependencies=[Depends(require_auth)])
async def pillar_stats(pillar_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    pillar = await db.get(ContentPillar, pillar_id)
    if not pillar:
        raise HTTPException(status_code=404, detail="Pillar not found")

    result = await db.execute(
        select(Post.status, func.count(Post.id))
        .where(Post.pillar_id == pillar_id)
        .group_by(Post.status)
    )
    by_status = {row[0]: row[1] for row in result.all()}

    return {
        "pillar_id": str(pillar_id),
        "total_posts": sum(by_status.values()),
        "by_status": by_status,
    }
