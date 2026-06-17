import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import Post, SocialAccount, ScheduleSlot
from ..models.enums import PipelineStatus
from ..schemas import PostCreate, PostUpdate, PostOut, PostStatusUpdate, PostSchedule, BatchGenerateRequest
from ..models import Idea
from ..models.enums import ContentType

router = APIRouter(prefix="/posts", tags=["posts"])

# Допустимые переходы статусов
ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    PipelineStatus.DRAFT: [PipelineStatus.REVIEW, PipelineStatus.INBOX],
    PipelineStatus.REVIEW: [PipelineStatus.DRAFT, PipelineStatus.READY],
    PipelineStatus.READY: [PipelineStatus.REVIEW, PipelineStatus.SCHEDULED],
    PipelineStatus.SCHEDULED: [PipelineStatus.READY],
    PipelineStatus.PUBLISHED: [],  # финальный статус
    PipelineStatus.ERROR: [PipelineStatus.READY, PipelineStatus.DRAFT],
    PipelineStatus.IDEA_APPROVED: [PipelineStatus.DRAFT],
    PipelineStatus.INBOX: [PipelineStatus.IDEA_APPROVED],
}


@router.get("", response_model=list[PostOut], dependencies=[Depends(require_auth)])
async def list_posts(
    status: str | None = Query(None),
    platform: str | None = Query(None),
    pillar_id: uuid.UUID | None = None,
    content_type: str | None = None,
    account_id: uuid.UUID | None = None,
    search: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    order_by: str = Query("created_at_desc"),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if status:
        statuses = [s.strip() for s in status.split(",")]
        filters.append(Post.status.in_(statuses))
    if platform:
        platforms = [p.strip() for p in platform.split(",")]
        filters.append(Post.platform.in_(platforms))
    if pillar_id:
        filters.append(Post.pillar_id == pillar_id)
    if content_type:
        filters.append(Post.content_type == content_type)
    if account_id:
        filters.append(Post.account_id == account_id)
    if search:
        filters.append(Post.body.ilike(f"%{search}%"))

    order = Post.created_at.desc() if order_by == "created_at_desc" else Post.scheduled_at.asc()

    result = await db.execute(
        select(Post)
        .where(and_(*filters) if filters else True)
        .order_by(order)
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


@router.post("", response_model=PostOut, status_code=201, dependencies=[Depends(require_auth)])
async def create_post(data: PostCreate, db: AsyncSession = Depends(get_db)):
    account = await db.get(SocialAccount, data.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    post = Post(**data.model_dump())
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


@router.get("/{post_id}", response_model=PostOut, dependencies=[Depends(require_auth)])
async def get_post(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.patch("/{post_id}", response_model=PostOut, dependencies=[Depends(require_auth)])
async def update_post(post_id: uuid.UUID, data: PostUpdate, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == PipelineStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Cannot edit a published post")

    # Если тело меняется — сохраняем старую версию в историю
    if data.body and data.body != post.body:
        history = list(post.body_history or [])
        history.append({
            "body": post.body,
            "edited_at": datetime.now(timezone.utc).isoformat(),
            "score": post.content_score,
        })
        post.body_history = history

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(post, field, value)

    post.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(post)
    return post


@router.patch("/{post_id}/status", response_model=PostOut, dependencies=[Depends(require_auth)])
async def update_status(post_id: uuid.UUID, data: PostStatusUpdate, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    allowed = ALLOWED_TRANSITIONS.get(post.status, [])
    if data.status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Transition from '{post.status}' to '{data.status}' is not allowed",
        )

    post.status = data.status
    post.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(post)
    return post


@router.patch("/{post_id}/schedule", response_model=PostOut, dependencies=[Depends(require_auth)])
async def schedule_post(post_id: uuid.UUID, data: PostSchedule, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if data.scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="scheduled_at must be in the future")

    # Проверяем конфликт слотов (±30 минут для того же аккаунта)
    window_start = data.scheduled_at - timedelta(minutes=30)
    window_end = data.scheduled_at + timedelta(minutes=30)
    conflict = await db.execute(
        select(ScheduleSlot).where(
            and_(
                ScheduleSlot.account_id == post.account_id,
                ScheduleSlot.scheduled_at >= window_start,
                ScheduleSlot.scheduled_at <= window_end,
                ScheduleSlot.post_id != post_id,
            )
        )
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="Another post is scheduled within 30 minutes for this account",
        )

    # Удаляем старый слот если есть
    old_slot = await db.execute(
        select(ScheduleSlot).where(ScheduleSlot.post_id == post_id)
    )
    old = old_slot.scalar_one_or_none()
    if old:
        await db.delete(old)

    post.scheduled_at = data.scheduled_at
    post.status = PipelineStatus.SCHEDULED

    slot = ScheduleSlot(
        account_id=post.account_id,
        post_id=post_id,
        scheduled_at=data.scheduled_at,
    )
    db.add(slot)

    await db.commit()
    await db.refresh(post)
    return post


@router.delete("/{post_id}/schedule", response_model=PostOut, dependencies=[Depends(require_auth)])
async def unschedule_post(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    slot_result = await db.execute(select(ScheduleSlot).where(ScheduleSlot.post_id == post_id))
    slot = slot_result.scalar_one_or_none()
    if slot:
        await db.delete(slot)

    post.scheduled_at = None
    post.status = PipelineStatus.READY
    await db.commit()
    await db.refresh(post)
    return post


@router.delete("/{post_id}", status_code=204, dependencies=[Depends(require_auth)])
async def delete_post(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status == PipelineStatus.PUBLISHED:
        raise HTTPException(status_code=400, detail="Cannot delete a published post")
    await db.delete(post)
    await db.commit()


@router.post("/{post_id}/duplicate", response_model=PostOut, status_code=201, dependencies=[Depends(require_auth)])
async def duplicate_post(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    new_post = Post(
        account_id=post.account_id,
        pillar_id=post.pillar_id,
        platform=post.platform,
        content_type=post.content_type,
        body=post.body,
        hashtags=post.hashtags,
        platform_meta=post.platform_meta,
        status=PipelineStatus.DRAFT,
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post)
    return new_post


@router.get("/{post_id}/history", dependencies=[Depends(require_auth)])
async def get_post_history(post_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    post = await db.get(Post, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"post_id": str(post_id), "history": post.body_history}


class BatchGenerateFullRequest(BatchGenerateRequest):
    account_id: uuid.UUID
    content_type: str | None = None  # если None — берём из suggested_content_type идеи


@router.post("/batch-generate", status_code=202, dependencies=[Depends(require_auth)])
async def batch_generate(data: BatchGenerateFullRequest, db: AsyncSession = Depends(get_db)):
    """
    Batch Mode: создаёт Post для каждой одобренной идеи и запускает генерацию.
    Возвращает список созданных post_id и task_id для polling.
    """
    account = await db.get(SocialAccount, data.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    created_posts = []
    skipped = []

    for idea_id in data.idea_ids:
        idea = await db.get(Idea, idea_id)
        if not idea:
            skipped.append({"idea_id": str(idea_id), "reason": "not found"})
            continue
        if idea.status != PipelineStatus.IDEA_APPROVED:
            skipped.append({"idea_id": str(idea_id), "reason": f"status is {idea.status}"})
            continue

        content_type = (
            data.content_type
            or idea.suggested_content_type
            or "opinion"
        )

        post = Post(
            idea_id=idea_id,
            account_id=data.account_id,
            pillar_id=idea.pillar_id,
            platform=account.platform,
            content_type=content_type,
            body="",
            status=PipelineStatus.IDEA_APPROVED,
        )
        db.add(post)
        created_posts.append(post)

    await db.commit()
    for post in created_posts:
        await db.refresh(post)

    # Запускаем генерацию для каждого поста через Celery
    from ..tasks.generation import generate_post
    task_ids = []
    for post in created_posts:
        task = generate_post.delay(str(post.id))
        task_ids.append(task.id)

    return {
        "status": "queued",
        "created_count": len(created_posts),
        "skipped_count": len(skipped),
        "post_ids": [str(p.id) for p in created_posts],
        "task_ids": task_ids,
        "skipped": skipped,
        "estimated_seconds": len(created_posts) * 12,
    }
