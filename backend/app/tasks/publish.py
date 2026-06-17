import asyncio
import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, and_

from .celery_app import app
from ..database import AsyncSessionLocal
from ..models import Post, SocialAccount
from ..models.enums import PipelineStatus
from ..adapters.registry import registry
from ..services.notifier import notify_published, notify_error

logger = logging.getLogger(__name__)


def run_async(coro):
    """Запускает async корутину в Celery worker (sync контекст)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="app.tasks.publish.check_and_publish")
def check_and_publish():
    """
    Запускается каждую минуту.
    Находит посты со статусом SCHEDULED и scheduled_at <= now.
    Запускает publish_post для каждого.
    """
    return run_async(_check_and_publish())


async def _check_and_publish():
    now = datetime.now(timezone.utc)
    dispatched = []

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Post).where(
                and_(
                    Post.status == PipelineStatus.SCHEDULED,
                    Post.scheduled_at <= now,
                    Post.publish_attempts < 3,
                )
            )
        )
        posts = result.scalars().all()

    for post in posts:
        publish_post.delay(str(post.id))
        dispatched.append(str(post.id))

    logger.info("check_and_publish: dispatched %d posts", len(dispatched))
    return {"dispatched": dispatched}


@app.task(
    name="app.tasks.publish.publish_post",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def publish_post(self, post_id: str):
    return run_async(_publish_post(self, post_id))


async def _publish_post(task, post_id: str):
    async with AsyncSessionLocal() as session:
        post = await session.get(Post, post_id)
        if not post:
            logger.error("publish_post: post %s not found", post_id)
            return

        account = await session.get(SocialAccount, post.account_id)
        if not account:
            logger.error("publish_post: account %s not found", post.account_id)
            return

        # Обновляем счётчик попыток
        post.publish_attempts += 1
        post.last_attempt_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        adapter = registry.get(post.platform)

        # Валидация контента перед публикацией
        validation = await adapter.validate_content(post)
        if not validation.valid:
            async with AsyncSessionLocal() as session:
                post = await session.get(Post, post_id)
                post.status = PipelineStatus.ERROR
                post.publish_error = "; ".join(validation.errors)
                await session.commit()
            logger.error("publish_post: validation failed for %s: %s", post_id, validation.errors)
            return

        result = await adapter.publish_post(post, account)

        async with AsyncSessionLocal() as session:
            post = await session.get(Post, post_id)
            if result.success:
                post.status = PipelineStatus.PUBLISHED
                post.published_at = datetime.now(timezone.utc)
                post.external_post_id = result.external_post_id
                post.publish_error = None
                logger.info("publish_post: published %s → %s", post_id, result.external_post_id)
                await session.commit()
                await notify_published(
                    post_id=post_id,
                    platform=post.platform,
                    handle=account.handle,
                    body_preview=post.body or "",
                    external_id=result.external_post_id,
                )
            else:
                if post.publish_attempts >= 3:
                    post.status = PipelineStatus.ERROR
                    post.publish_error = result.error
                    logger.error("publish_post: max retries reached for %s: %s", post_id, result.error)
                    await session.commit()
                    await notify_error(post_id, post.platform, account.handle, result.error or "unknown error")
                else:
                    post.publish_error = result.error
                    logger.warning("publish_post: attempt %d failed for %s: %s",
                                   post.publish_attempts, post_id, result.error)
                    await session.commit()

    except Exception as exc:
        logger.exception("publish_post: unexpected error for %s", post_id)
        async with AsyncSessionLocal() as session:
            post = await session.get(Post, post_id)
            if post and post.publish_attempts >= 3:
                post.status = PipelineStatus.ERROR
                post.publish_error = str(exc)
                await session.commit()
                await notify_error(post_id, post.platform, account.handle if account else "?", str(exc))
        raise task.retry(exc=exc)
