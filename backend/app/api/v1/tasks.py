"""通用 Celery 任務狀態查詢（供 M1 等模組輪詢；RAG 亦有專屬 /rag/tasks）。

_task_status 以模組層 helper 封裝，便於測試 monkeypatch（避免測試連 Redis）。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _task_status(task_id: str) -> dict:
    from celery.result import AsyncResult

    from ...workers.celery_app import celery_app

    res = AsyncResult(task_id, app=celery_app)
    out: dict = {"task_id": task_id, "state": res.state}
    if res.ready():
        out["result"] = res.result
    return out


@router.get("/{task_id}")
def task_status(task_id: str):
    return _task_status(task_id)
