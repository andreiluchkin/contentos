from datetime import date, datetime, timezone, timedelta
import calendar as cal_module

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_auth
from ..database import get_db
from ..models import Post, SocialAccount, ScheduleSlot
from ..models.enums import PipelineStatus

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/month", dependencies=[Depends(require_auth)])
async def calendar_month(
    year: int = Query(...),
    month: int = Query(...),
    platform: str | None = None,
    pillar_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает агрегированные данные по дням месяца.
    Каждый день: total, platforms, has_error, is_gap.
    """
    # Первый и последний день месяца
    first_day = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = datetime(year, month, cal_module.monthrange(year, month)[1], 23, 59, 59, tzinfo=timezone.utc)

    filters = [
        Post.scheduled_at >= first_day,
        Post.scheduled_at <= last_day,
        Post.status.in_([
            PipelineStatus.SCHEDULED,
            PipelineStatus.PUBLISHED,
            PipelineStatus.ERROR,
        ]),
    ]
    if platform:
        platforms = [p.strip() for p in platform.split(",")]
        filters.append(Post.platform.in_(platforms))
    if pillar_id:
        filters.append(Post.pillar_id == pillar_id)

    result = await db.execute(
        select(
            func.date_trunc("day", Post.scheduled_at).label("day"),
            Post.platform,
            Post.pillar_id,
            Post.status,
            func.count(Post.id).label("cnt"),
        )
        .where(and_(*filters))
        .group_by("day", Post.platform, Post.pillar_id, Post.status)
    )
    rows = result.all()

    # Агрегируем по дням
    days: dict[str, dict] = {}
    for row in rows:
        day_str = row.day.strftime("%Y-%m-%d")
        if day_str not in days:
            days[day_str] = {
                "total": 0,
                "platforms": set(),
                "pillars": {},
                "has_error": False,
            }
        d = days[day_str]
        d["total"] += row.cnt
        d["platforms"].add(row.platform)
        if row.status == PipelineStatus.ERROR:
            d["has_error"] = True
        if row.pillar_id:
            pid = str(row.pillar_id)
            d["pillars"][pid] = d["pillars"].get(pid, 0) + row.cnt

    # Определяем gaps (дни без постов) — только текущий и будущие дни
    today = date.today()
    all_days_in_month = cal_module.monthrange(year, month)[1]
    gaps = []
    for day_num in range(1, all_days_in_month + 1):
        d = date(year, month, day_num)
        day_str = d.strftime("%Y-%m-%d")
        if d >= today and day_str not in days:
            gaps.append(day_str)

    # Сериализуем
    serialized = {}
    for day_str, d in days.items():
        serialized[day_str] = {
            "total": d["total"],
            "platforms": list(d["platforms"]),
            "pillars": [
                {"id": pid, "count": cnt}
                for pid, cnt in d["pillars"].items()
            ],
            "has_error": d["has_error"],
            "is_gap": False,
        }
    for gap in gaps:
        serialized[gap] = {
            "total": 0,
            "platforms": [],
            "pillars": [],
            "has_error": False,
            "is_gap": True,
        }

    return {
        "year": year,
        "month": month,
        "days": serialized,
        "total_posts": sum(d["total"] for d in days.values()),
        "gap_count": len(gaps),
    }


@router.get("/day/{day}", dependencies=[Depends(require_auth)])
async def calendar_day(day: str, db: AsyncSession = Depends(get_db)):
    """Список постов на конкретный день."""
    try:
        target = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    day_end = target.replace(hour=23, minute=59, second=59)

    result = await db.execute(
        select(Post)
        .where(
            and_(
                Post.scheduled_at >= target,
                Post.scheduled_at <= day_end,
            )
        )
        .order_by(Post.scheduled_at)
    )
    posts = result.scalars().all()

    return {
        "date": day,
        "posts": [
            {
                "id": str(p.id),
                "platform": p.platform,
                "content_type": p.content_type,
                "body_preview": p.body[:120],
                "status": p.status,
                "scheduled_at": p.scheduled_at.isoformat() if p.scheduled_at else None,
                "content_score": p.content_score,
                "pillar_id": str(p.pillar_id) if p.pillar_id else None,
            }
            for p in posts
        ],
    }


@router.get("/week", dependencies=[Depends(require_auth)])
async def calendar_week(
    year: int = Query(...),
    week: int = Query(..., description="ISO week number 1-53"),
    db: AsyncSession = Depends(get_db),
):
    """Посты за ISO неделю."""
    # Находим первый день ISO недели
    first_day = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u").replace(tzinfo=timezone.utc)
    last_day = first_day + timedelta(days=6, hours=23, minutes=59, seconds=59)

    result = await db.execute(
        select(Post)
        .where(
            and_(
                Post.scheduled_at >= first_day,
                Post.scheduled_at <= last_day,
                Post.status.in_([PipelineStatus.SCHEDULED, PipelineStatus.PUBLISHED, PipelineStatus.ERROR]),
            )
        )
        .order_by(Post.scheduled_at)
    )
    posts = result.scalars().all()

    # Группируем по дням
    by_day: dict[str, list] = {}
    for p in posts:
        if p.scheduled_at:
            day_str = p.scheduled_at.strftime("%Y-%m-%d")
            by_day.setdefault(day_str, []).append({
                "id": str(p.id),
                "platform": p.platform,
                "status": p.status,
                "scheduled_at": p.scheduled_at.isoformat(),
                "body_preview": p.body[:80],
                "content_score": p.content_score,
            })

    return {
        "year": year,
        "week": week,
        "from": first_day.date().isoformat(),
        "to": last_day.date().isoformat(),
        "days": by_day,
    }


@router.get("/gaps", dependencies=[Depends(require_auth)])
async def calendar_gaps(db: AsyncSession = Depends(get_db)):
    """Дни без контента на текущей и следующей неделе."""
    today = date.today()
    next_two_weeks = today + timedelta(days=14)

    start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = datetime.combine(next_two_weeks, datetime.max.time()).replace(tzinfo=timezone.utc)

    result = await db.execute(
        select(func.date_trunc("day", Post.scheduled_at).label("day"))
        .where(
            and_(
                Post.scheduled_at >= start,
                Post.scheduled_at <= end,
                Post.status.in_([PipelineStatus.SCHEDULED, PipelineStatus.PUBLISHED]),
            )
        )
        .group_by("day")
    )
    scheduled_days = {row.day.date() for row in result.all()}

    gaps = []
    d = today
    while d <= next_two_weeks:
        if d not in scheduled_days:
            gaps.append(d.isoformat())
        d += timedelta(days=1)

    return {"gaps": gaps, "count": len(gaps)}


@router.get("/next-slot", dependencies=[Depends(require_auth)])
async def next_available_slot(
    account_id: str = Query(...),
    after: str | None = Query(None, description="ISO datetime, default=now"),
    db: AsyncSession = Depends(get_db),
):
    """Следующий свободный слот для аккаунта с учётом оптимального времени."""
    account = await db.get(SocialAccount, account_id)
    if not account:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Account not found")

    start = datetime.now(timezone.utc)
    if after:
        try:
            start = datetime.fromisoformat(after.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Optimal posting times {"mon": "09:00", "tue": "14:00", ...}
    optimal = account.optimal_posting_times or {}
    day_names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

    # Ищем слот в следующие 14 дней
    candidate = start + timedelta(minutes=30)
    for _ in range(14 * 24):
        day_key = day_names[candidate.weekday()]
        optimal_time = optimal.get(day_key, "09:00")
        hour, minute = (int(x) for x in optimal_time.split(":"))

        # Предлагаем оптимальное время дня
        slot = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if slot <= candidate:
            slot += timedelta(days=1)

        # Проверяем конфликт
        window_start = slot - timedelta(minutes=30)
        window_end = slot + timedelta(minutes=30)
        conflict = await db.execute(
            select(ScheduleSlot).where(
                and_(
                    ScheduleSlot.account_id == account_id,
                    ScheduleSlot.scheduled_at >= window_start,
                    ScheduleSlot.scheduled_at <= window_end,
                )
            )
        )
        if not conflict.scalar_one_or_none():
            return {
                "next_slot": slot.isoformat(),
                "reason": "optimal_time",
                "day": day_key,
            }

        candidate = slot + timedelta(hours=1)

    return {"next_slot": None, "reason": "no_slot_found"}
