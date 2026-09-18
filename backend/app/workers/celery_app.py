"""Celery app（broker/result 皆走 Redis，可用環境變數覆蓋）。

Worker 啟動：``celery -A app.workers.celery_app.celery_app worker --loglevel=info``
Beat 啟動：  ``celery -A app.workers.celery_app.celery_app beat --loglevel=info``
"""
from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "testweaver",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)


def _build_beat_schedule() -> dict:
    """依環境變數組建 beat 排程（離線可測）。

    ``REPORT_SCHEDULE_ENABLED=true`` 時，排定 ``m6.schedule_reports``（預設每日 07:00；
    可用 ``REPORT_SCHEDULE_HOUR`` / ``REPORT_SCHEDULE_MINUTE`` 覆寫）。未啟用 → ``{}``。
    """
    if os.getenv("REPORT_SCHEDULE_ENABLED", "false").strip().lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return {}
    return {
        "testweaver-report-schedule": {
            "task": "m6.schedule_reports",
            "schedule": crontab(
                hour=int(os.getenv("REPORT_SCHEDULE_HOUR", "7")),
                minute=int(os.getenv("REPORT_SCHEDULE_MINUTE", "0")),
            ),
        }
    }


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=os.getenv("TZ", "Asia/Taipei"),
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule=_build_beat_schedule(),
)
