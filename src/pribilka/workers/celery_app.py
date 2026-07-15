from celery import Celery
from celery.schedules import crontab

from pribilka.config import get_settings

settings = get_settings()

celery_app = Celery("pribilka", broker=settings.celery_broker_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Warsaw",
    enable_utc=True,
    beat_schedule={
        "collect-deposits": {
            "task": "pribilka.workers.tasks.run_collector",
            "schedule": crontab(minute=0, hour="*/4"),
            "args": ["deposit"],
        },
        "collect-bonds": {
            "task": "pribilka.workers.tasks.run_collector",
            "schedule": crontab(minute=0),
            "args": ["bond"],
        },
        "collect-fx": {
            "task": "pribilka.workers.tasks.run_collector",
            "schedule": crontab(minute="*/15"),
            "args": ["fx"],
        },
        "collect-gold": {
            "task": "pribilka.workers.tasks.run_collector",
            "schedule": crontab(minute="*/15"),
            "args": ["gold"],
        },
        "collect-rental": {
            "task": "pribilka.workers.tasks.run_collector",
            "schedule": crontab(minute=30, hour="*/3"),
            "args": ["rental"],
        },
        "weekly-digest": {
            "task": "pribilka.workers.tasks.generate_weekly_digest_task",
            "schedule": crontab(minute=0, hour=8, day_of_week="monday"),
            "args": ["PL"],
        },
        "daily-market-brief": {
            "task": "pribilka.workers.tasks.send_daily_market_brief_task",
            "schedule": crontab(minute=0, hour=9),
            "args": ["PL"],
        },
    },
)

celery_app.autodiscover_tasks(["pribilka.workers"])
