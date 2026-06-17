"""
Еженедельная обратная связь для внешних источников (Reddit-проект и др.).
Собирает статистику за 7 дней и отправляет POST на feedback_webhook_url.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy import select, and_, func

from .celery_app import app
from ..database import AsyncSessionLocal
from ..models import Post, ExternalSource, ContentPillar
from ..models.enums import PipelineStatus

logger = logging.getLogger(__name__)


def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="app.tasks.feedback.send_weekly_feedback")
def send_weekly_feedback():
    return run_async(_send_weekly_feedback())


async def _send_weekly_feedback():
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=7)

    # Статистика по пилларам за неделю
    async with AsyncSessionLocal() as session:
        # Опубликованные посты за период
        result = await session.execute(
            select(
                Post.pillar_id,
                func.count(Post.id).label("published_count"),
                func.avg(Post.content_score).label("avg_score"),
            )
            .where(
                and_(
                    Post.status == PipelineStatus.PUBLISHED,
                    Post.published_at >= period_start,
                    Post.published_at <= now,
                )
            )
            .group_by(Post.pillar_id)
        )
        pillar_stats = result.all()

        # Топ content_types по среднему Score
        type_result = await session.execute(
            select(
                Post.content_type,
                func.count(Post.id).label("count"),
                func.avg(Post.content_score).label("avg_score"),
            )
            .where(
                and_(
                    Post.status == PipelineStatus.PUBLISHED,
                    Post.published_at >= period_start,
                    Post.content_score.is_not(None),
                )
            )
            .group_by(Post.content_type)
            .order_by(func.avg(Post.content_score).desc())
            .limit(5)
        )
        top_types = type_result.all()

        # Получаем имена пилларов
        pillar_ids = [str(r.pillar_id) for r in pillar_stats if r.pillar_id]
        pillars_map: dict[str, str] = {}
        if pillar_ids:
            pillars_result = await session.execute(
                select(ContentPillar).where(ContentPillar.id.in_(pillar_ids))
            )
            pillars_map = {str(p.id): p.name for p in pillars_result.scalars().all()}

        # Получаем активные источники с webhook
        sources_result = await session.execute(
            select(ExternalSource).where(
                and_(
                    ExternalSource.is_active == True,
                    ExternalSource.feedback_webhook_url.is_not(None),
                )
            )
        )
        sources = sources_result.scalars().all()

    if not sources:
        logger.info("send_weekly_feedback: no active sources with webhook")
        return {"sent": 0}

    # Строим payload
    performing = []
    weak = []
    for row in pillar_stats:
        avg = float(row.avg_score or 0)
        count = int(row.published_count)
        pillar_name = pillars_map.get(str(row.pillar_id), "Unknown") if row.pillar_id else "No pillar"
        entry = {
            "pillar": pillar_name,
            "published": count,
            "avg_score": round(avg, 1),
        }
        if avg >= 80 and count >= 3:
            performing.append(entry)
        elif avg < 60 or count < 1:
            weak.append(entry)

    payload = {
        "event": "weekly_feedback",
        "period_start": period_start.isoformat(),
        "period_end": now.isoformat(),
        "performing_pillars": performing,
        "weak_pillars": weak,
        "top_content_types": [
            {
                "type": row.content_type,
                "count": int(row.count),
                "avg_score": round(float(row.avg_score or 0), 1),
            }
            for row in top_types
        ],
        "total_published": sum(int(r.published_count) for r in pillar_stats),
    }

    # Отправляем всем источникам
    sent = 0
    errors = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for source in sources:
            try:
                resp = await client.post(
                    source.feedback_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code < 300:
                    sent += 1
                    logger.info("feedback sent to %s: %s", source.name, resp.status_code)
                else:
                    errors.append({"source": source.name, "status": resp.status_code})
                    logger.warning("feedback to %s returned %s", source.name, resp.status_code)
            except Exception as e:
                errors.append({"source": source.name, "error": str(e)})
                logger.error("feedback to %s failed: %s", source.name, e)

    return {"sent": sent, "errors": errors, "payload": payload}


@app.task(name="app.tasks.feedback.check_content_gaps")
def check_content_gaps():
    return run_async(_check_content_gaps())


async def _check_content_gaps():
    from datetime import date
    today = datetime.now(timezone.utc)
    next_week = today + timedelta(days=7)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.date_trunc("day", Post.scheduled_at).label("day"))
            .where(
                and_(
                    Post.scheduled_at >= today,
                    Post.scheduled_at <= next_week,
                    Post.status.in_([PipelineStatus.SCHEDULED, PipelineStatus.PUBLISHED]),
                )
            )
            .group_by("day")
        )
        scheduled_days = {row.day.date() for row in result.all()}

    gaps = []
    d = today.date()
    while d <= next_week.date():
        if d not in scheduled_days:
            gaps.append(d.isoformat())
        d += timedelta(days=1)

    if gaps:
        logger.warning("Content gaps detected: %s", gaps)

    return {"gaps": gaps, "count": len(gaps)}
