from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db as get_session
from ..models import Post, SocialAccount
from ..models.enums import PipelineStatus
from ..auth import require_auth
from ..tasks.publish import publish_post

router = APIRouter(prefix="/posts", tags=["publishing"])


@router.post("/{post_id}/publish-now")
async def publish_now(
    post_id: str,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post.status == PipelineStatus.PUBLISHED:
        raise HTTPException(400, "Post already published")
    if post.status not in (PipelineStatus.READY, PipelineStatus.REVIEW, PipelineStatus.ERROR):
        raise HTTPException(400, f"Cannot publish post in status '{post.status.value}'")

    account = await session.get(SocialAccount, post.account_id)
    if not account:
        raise HTTPException(400, "Account not found")

    # Move to SCHEDULED so the existing publish_post task handles it
    post.status = PipelineStatus.SCHEDULED
    post.publish_attempts = 0
    post.publish_error = None
    await session.commit()

    publish_post.delay(str(post.id))
    return {"status": "queued", "post_id": post_id}


@router.post("/{post_id}/approve")
async def approve_post(
    post_id: str,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    if post.status != PipelineStatus.REVIEW:
        raise HTTPException(400, f"Post must be in 'review' status, got '{post.status.value}'")

    post.status = PipelineStatus.READY
    await session.commit()
    await session.refresh(post)
    return {"status": "approved", "post_id": post_id, "new_status": post.status.value}


@router.post("/{post_id}/reject")
async def reject_post(
    post_id: str,
    body: dict = {},
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    post = await session.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")

    reason = body.get("reason", "") if body else ""
    post.status = PipelineStatus.DRAFT
    if reason:
        meta = post.platform_meta or {}
        meta["reject_reason"] = reason
        post.platform_meta = meta
    await session.commit()
    return {"status": "rejected", "post_id": post_id}


@router.get("/review-queue")
async def review_queue(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_auth),
):
    result = await session.execute(
        select(Post).where(Post.status == PipelineStatus.REVIEW).order_by(Post.created_at.desc())
    )
    posts = result.scalars().all()

    rows = []
    for post in posts:
        account = await session.get(SocialAccount, post.account_id)
        rows.append({
            "id": str(post.id),
            "platform": post.platform,
            "content_type": post.content_type,
            "body": post.body,
            "body_preview": (post.body or "")[:200],
            "content_score": post.content_score,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "account_handle": account.handle if account else None,
            "account_display": account.display_name if account else None,
            "hashtags": post.hashtags or [],
            "pillar_id": str(post.pillar_id) if post.pillar_id else None,
        })
    return rows
