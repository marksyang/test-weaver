"""Celery app（broker/result 皆走 Redis，可用環境變數覆蓋）。

Worker 啟動：``celery -A app.workers.celery_app.celery_app worker --loglevel=info``
"""
from __future__ import annotations

import os

from celery import Celery

celery_app = Celery(
    "testweaver",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=os.getenv("TZ", "Asia/Taipei"),
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
