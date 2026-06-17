"""
Celery задачи для сбора метрик опубликованных постов.

collect_post_metrics()    — собирает метрики для конкретного поста
collect_all_metrics()     — Celery beat: раз в 6 часов обходит все published посты
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from .celery_app import app

logger = logging.getLogger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="app.tasks.metrics.collect_all_metrics")
def collect_all_metrics():
    """Запускает сбор метрик для всех опубликованных постов."""
    return run_async(_collect_all_metrics())


async def _collect_all_metrics():
    from ..database import AsyncSessionLocal
    from ..models import Post
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Post.id).where(
                Post.status == "published",
                Post.external_post_id.isnot(None),
            ).limit(200)
        )
        post_ids = [str(row[0]) for row in result.fetchall()]

    logger.info("Collecting metrics for %d published posts", len(post_ids))
    for pid in post_ids:
        collect_post_metrics.delay(pid)

    return {"queued": len(post_ids)}


@app.task(bind=True, max_retries=2, default_retry_delay=60, name="app.tasks.metrics.collect_post_metrics")
def collect_post_metrics(self, post_id: str):
    return run_async(_collect_post_metrics(self, post_id))


async def _collect_post_metrics(task, post_id: str):
    from ..database import AsyncSessionLocal
    from ..models import Post, SocialAccount
    from ..adapters.registry import registry

    async with AsyncSessionLocal() as db:
        post = await db.get(Post, uuid.UUID(post_id))
        if not post or not post.external_post_id:
            return

        account = await db.get(SocialAccount, post.account_id)
        if not account:
            return

        try:
            adapter = registry.get(post.platform)
        except ValueError:
            logger.warning("No adapter for platform %s", post.platform)
            return

        try:
            metrics = await adapter.get_metrics(post.external_post_id, account)
        except Exception as e:
            logger.error("Failed to collect metrics for post %s: %s", post_id, e)
            raise task.retry(exc=e)

        # Сохраняем в platform_meta.metrics
        meta = dict(post.platform_meta or {})
        meta["metrics"] = {
            "views": metrics.views,
            "likes": metrics.likes,
            "comments": metrics.comments,
            "shares": metrics.shares,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
        post.platform_meta = meta
        await db.commit()

        logger.info(
            "Metrics for post %s: views=%d likes=%d comments=%d shares=%d",
            post_id, metrics.views, metrics.likes, metrics.comments, metrics.shares,
        )
