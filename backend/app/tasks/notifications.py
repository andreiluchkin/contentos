import asyncio
import logging
from datetime import datetime, date, timezone

from sqlalchemy import select, func, and_

from .celery_app import app
from ..database import AsyncSessionLocal
from ..models import Post
from ..models.enums import PipelineStatus
from ..services.notifier import send_daily_digest

logger = logging.getLogger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="app.tasks.notifications.send_daily_digest_task")
def send_daily_digest_task():
    return run_async(_send_daily_digest())


async def _send_daily_digest():
    today = date.today()
    async with AsyncSessionLocal() as session:
        total = await session.scalar(select(func.count(Post.id)))

        published_today = await session.scalar(
            select(func.count(Post.id)).where(
                and_(
                    Post.status == PipelineStatus.PUBLISHED,
                    func.date(Post.published_at) == today,
                )
            )
        )

        pending_review = await session.scalar(
            select(func.count(Post.id)).where(Post.status == PipelineStatus.REVIEW)
        )

        score_row = await session.execute(
            select(func.round(func.avg(Post.content_score), 1)).where(
                Post.content_score.isnot(None)
            )
        )
        score_avg = score_row.scalar()

        # top platform by published count
        top_row = await session.execute(
            select(Post.platform, func.count(Post.id).label("cnt"))
            .where(Post.status == PipelineStatus.PUBLISHED)
            .group_by(Post.platform)
            .order_by(func.count(Post.id).desc())
            .limit(1)
        )
        top = top_row.first()
        top_platform = top[0] if top else None

    stats = {
        "total": total or 0,
        "published_today": published_today or 0,
        "pending_review": pending_review or 0,
        "score_avg": float(score_avg) if score_avg else None,
        "top_platform": top_platform,
    }
    await send_daily_digest(stats)
    logger.info("Daily digest sent: %s", stats)
    return stats
