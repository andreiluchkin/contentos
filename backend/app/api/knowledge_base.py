import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import KnowledgeBaseItem, Post
from ..models.enums import KBItemType

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


class KBItemCreate(BaseModel):
    item_type: str
    title: str
    body: str
    tags: list[str] = []
    pillar_id: uuid.UUID | None = None


class KBItemUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    pillar_id: uuid.UUID | None = None
    is_active: bool | None = None


class KBItemOut(BaseModel):
    id: uuid.UUID
    item_type: str
    title: str
    body: str
    tags: list[str]
    pillar_id: uuid.UUID | None
    source_post_id: uuid.UUID | None
    is_active: bool

    model_config = {"from_attributes": True}


class KBSearchRequest(BaseModel):
    query: str
    limit: int = 3


@router.get("", response_model=list[KBItemOut], dependencies=[Depends(require_auth)])
async def list_kb(
    item_type: str | None = None,
    pillar_id: uuid.UUID | None = None,
    search: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    filters = [KnowledgeBaseItem.is_active == True]
    if item_type:
        filters.append(KnowledgeBaseItem.item_type == item_type)
    if pillar_id:
        filters.append(KnowledgeBaseItem.pillar_id == pillar_id)
    if search:
        filters.append(
            KnowledgeBaseItem.title.ilike(f"%{search}%")
            | KnowledgeBaseItem.body.ilike(f"%{search}%")
        )

    result = await db.execute(
        select(KnowledgeBaseItem)
        .where(and_(*filters))
        .order_by(KnowledgeBaseItem.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("", response_model=KBItemOut, status_code=201, dependencies=[Depends(require_auth)])
async def create_kb_item(data: KBItemCreate, db: AsyncSession = Depends(get_db)):
    item = KnowledgeBaseItem(**data.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/{item_id}", response_model=KBItemOut, dependencies=[Depends(require_auth)])
async def get_kb_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(KnowledgeBaseItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="KB item not found")
    return item


@router.put("/{item_id}", response_model=KBItemOut, dependencies=[Depends(require_auth)])
async def update_kb_item(item_id: uuid.UUID, data: KBItemUpdate, db: AsyncSession = Depends(get_db)):
    item = await db.get(KnowledgeBaseItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="KB item not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_kb_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(KnowledgeBaseItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="KB item not found")
    item.is_active = False
    await db.commit()


@router.post("/search", response_model=list[KBItemOut], dependencies=[Depends(require_auth)])
async def search_kb(data: KBSearchRequest, db: AsyncSession = Depends(get_db)):
    """Простой полнотекстовый поиск. Векторный поиск — в следующей итерации."""
    words = data.query.lower().split()[:5]
    result = await db.execute(
        select(KnowledgeBaseItem)
        .where(KnowledgeBaseItem.is_active == True)
        .limit(data.limit * 5)
    )
    items = result.scalars().all()

    scored = []
    for item in items:
        text_lower = (item.title + " " + item.body).lower()
        score = sum(1 for w in words if w in text_lower)
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:data.limit]]


@router.post("/import-post/{post_id}", response_model=KBItemOut, status_code=201, dependencies=[Depends(require_auth)])
async def import_post_to_kb(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Импортирует опубликованный пост в Knowledge Base."""
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    existing = await db.execute(
        select(KnowledgeBaseItem).where(KnowledgeBaseItem.source_post_id == post_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Post already imported to KB")

    title = post.body[:100].strip().split("\n")[0]
    item = KnowledgeBaseItem(
        item_type=KBItemType.POST,
        title=title,
        body=post.body,
        tags=[post.platform, post.content_type],
        pillar_id=post.pillar_id,
        source_post_id=post_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
