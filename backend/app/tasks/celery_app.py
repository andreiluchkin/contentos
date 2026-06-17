from celery import Celery
from celery.schedules import crontab

from ..config import settings

app = Celery(
    "contentos",
    broker=settings.redis_url,
    backend=settings.redis_url.replace("/0", "/1"),
    include=[
        "app.tasks.publish",
        "app.tasks.accounts",
        "app.tasks.generation",
        "app.tasks.feedback",
        "app.tasks.repurpose",
        "app.tasks.metrics",
        "app.tasks.notifications",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        # Проверяем и публикуем запланированные посты каждую минуту
        "publish-scheduled-posts": {
            "task": "app.tasks.publish.check_and_publish",
            "schedule": 60.0,
        },
        # Обновляем истекающие токены каждый час
        "refresh-expiring-tokens": {
            "task": "app.tasks.accounts.refresh_expiring_tokens",
            "schedule": crontab(minute=0),
        },
        # Еженедельная обратная связь — понедельник 08:00 UTC
        "send-weekly-feedback": {
            "task": "app.tasks.feedback.send_weekly_feedback",
            "schedule": crontab(day_of_week=1, hour=8, minute=0),
        },
        # Проверка пустых дней — каждое утро 07:00 UTC
        "check-content-gaps": {
            "task": "app.tasks.feedback.check_content_gaps",
            "schedule": crontab(hour=7, minute=0),
        },
        # Сбор метрик опубликованных постов каждые 6 часов
        "collect-metrics": {
            "task": "app.tasks.metrics.collect_all_metrics",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # Ежедневный дайджест — 19:00 UTC
        "daily-digest": {
            "task": "app.tasks.notifications.send_daily_digest_task",
            "schedule": crontab(hour=19, minute=0),
        },
    },
)
