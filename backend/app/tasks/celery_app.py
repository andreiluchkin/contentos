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
    },
)
