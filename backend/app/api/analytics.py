"""
Analytics API.

GET /analytics/overview   — общая статистика (посты, score, платформы)
GET /analytics/posts      — топ постов по метрикам
GET /analytics/pillars    — разбивка по контент-столбам
GET /analytics/timeline   — посты по дням за период
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import Post, ContentPillar

router = APIRouter(prefix="/analytics", tags=["analytics"])


class OverviewOut(BaseModel):
    total_posts: int
    published_posts: int
    avg_content_score: float | None
    posts_this_week: int
    posts_last_week: int
    top_platform: str | None
    platform_counts: dict[str, int]
    status_counts: dict[str, int]


class PostMetricOut(BaseModel):
    id: str
    platform: str
    content_type: str
    body_preview: str
    content_score: float | None
    views: int
    likes: int
    comments: int
    shares: int
    published_at: str | None
    pillar_id: str | None


class PillarStatOut(BaseModel):
    pillar_id: str
    pillar_name: str
    pillar_color: str
    total_posts: int
    published_posts: int
    avg_score: float | None


class DayStatOut(BaseModel):
    date: str
    count: int
    published: int
    avg_score: float | None


@router.get("/overview", response_model=OverviewOut, dependencies=[Depends(require_auth)])
async def get_overview(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    prev_week_start = now - timedelta(days=14)

    # Всего постов
    total_result = await db.execute(select(func.count(Post.id)))
    total_posts = total_result.scalar() or 0

    # Опубликованных
    pub_result = await db.execute(
        select(func.count(Post.id)).where(Post.status == "published")
    )
    published_posts = pub_result.scalar() or 0

    # Средний score
    score_result = await db.execute(
        select(func.avg(Post.content_score)).where(Post.content_score.isnot(None))
    )
    avg_score = score_result.scalar()
    if avg_score is not None:
        avg_score = round(float(avg_score), 1)

    # Посты за эту неделю
    this_week_result = await db.execute(
        select(func.count(Post.id)).where(Post.created_at >= week_start)
    )
    posts_this_week = this_week_result.scalar() or 0

    # Посты за прошлую неделю
    last_week_result = await db.execute(
        select(func.count(Post.id)).where(
            and_(Post.created_at >= prev_week_start, Post.created_at < week_start)
        )
    )
    posts_last_week = last_week_result.scalar() or 0

    # Разбивка по платформам
    platform_result = await db.execute(
        select(Post.platform, func.count(Post.id))
        .group_by(Post.platform)
        .order_by(func.count(Post.id).desc())
    )
    platform_rows = platform_result.fetchall()
    platform_counts = {row[0]: row[1] for row in platform_rows}
    top_platform = platform_rows[0][0] if platform_rows else None

    # Разбивка по статусам
    status_result = await db.execute(
        select(Post.status, func.count(Post.id)).group_by(Post.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.fetchall()}

    return OverviewOut(
        total_posts=total_posts,
        published_posts=published_posts,
        avg_content_score=avg_score,
        posts_this_week=posts_this_week,
        posts_last_week=posts_last_week,
        top_platform=top_platform,
        platform_counts=platform_counts,
        status_counts=status_counts,
    )


@router.get("/posts", response_model=list[PostMetricOut], dependencies=[Depends(require_auth)])
async def get_top_posts(
    sort_by: str = Query("score", regex="^(score|views|likes|recent)$"),
    platform: str | None = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    q = select(Post).where(Post.status == "published")
    if platform:
        q = q.where(Post.platform == platform)

    if sort_by == "score":
        q = q.order_by(Post.content_score.desc().nulls_last())
    elif sort_by == "recent":
        q = q.order_by(Post.scheduled_at.desc().nulls_last())
    else:
        # views / likes сортируем после загрузки (из JSONB)
        q = q.order_by(Post.content_score.desc().nulls_last())

    q = q.limit(limit * 2)  # берём больше для post-sort
    result = await db.execute(q)
    posts = result.scalars().all()

    out = []
    for post in posts:
        meta = post.platform_meta or {}
        metrics = meta.get("metrics", {})
        out.append(PostMetricOut(
            id=str(post.id),
            platform=post.platform,
            content_type=post.content_type,
            body_preview=(post.body or "")[:120],
            content_score=post.content_score,
            views=metrics.get("views", 0),
            likes=metrics.get("likes", 0),
            comments=metrics.get("comments", 0),
            shares=metrics.get("shares", 0),
            published_at=post.scheduled_at.isoformat() if post.scheduled_at else None,
            pillar_id=str(post.pillar_id) if post.pillar_id else None,
        ))

    # Post-sort для views/likes
    if sort_by == "views":
        out.sort(key=lambda x: x.views, reverse=True)
    elif sort_by == "likes":
        out.sort(key=lambda x: x.likes, reverse=True)

    return out[:limit]


@router.get("/pillars", response_model=list[PillarStatOut], dependencies=[Depends(require_auth)])
async def get_pillar_stats(db: AsyncSession = Depends(get_db)):
    pillars_result = await db.execute(
        select(ContentPillar).where(ContentPillar.is_active == True)
    )
    pillars = pillars_result.scalars().all()

    out = []
    for pillar in pillars:
        posts_result = await db.execute(
            select(func.count(Post.id)).where(Post.pillar_id == pillar.id)
        )
        total = posts_result.scalar() or 0

        pub_result = await db.execute(
            select(func.count(Post.id)).where(
                and_(Post.pillar_id == pillar.id, Post.status == "published")
            )
        )
        published = pub_result.scalar() or 0

        score_result = await db.execute(
            select(func.avg(Post.content_score)).where(
                and_(Post.pillar_id == pillar.id, Post.content_score.isnot(None))
            )
        )
        avg_score = score_result.scalar()

        out.append(PillarStatOut(
            pillar_id=str(pillar.id),
            pillar_name=pillar.name,
            pillar_color=pillar.color or "#7a40ed",
            total_posts=total,
            published_posts=published,
            avg_score=round(float(avg_score), 1) if avg_score else None,
        ))

    return sorted(out, key=lambda x: x.total_posts, reverse=True)


@router.get("/timeline", response_model=list[DayStatOut], dependencies=[Depends(require_auth)])
async def get_timeline(
    days: int = Query(30, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Количество постов по дням за последние N дней."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(Post).where(Post.created_at >= since).order_by(Post.created_at)
    )
    posts = result.scalars().all()

    # Группируем по дате
    day_map: dict[str, dict] = {}
    for post in posts:
        day = post.created_at.strftime("%Y-%m-%d")
        if day not in day_map:
            day_map[day] = {"count": 0, "published": 0, "scores": []}
        day_map[day]["count"] += 1
        if post.status == "published":
            day_map[day]["published"] += 1
        if post.content_score is not None:
            day_map[day]["scores"].append(post.content_score)

    # Заполняем пропущенные дни
    out = []
    now = datetime.now(timezone.utc)
    for i in range(days):
        d = (now - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        stats = day_map.get(d, {"count": 0, "published": 0, "scores": []})
        scores = stats["scores"]
        out.append(DayStatOut(
            date=d,
            count=stats["count"],
            published=stats["published"],
            avg_score=round(sum(scores) / len(scores), 1) if scores else None,
        ))

    return out
