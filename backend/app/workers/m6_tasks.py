"""M6 Celery 任務：完成計畫後生成報表 + AI 分析（FR-4）。"""
from __future__ import annotations

from ..core.db import session_scope
from ..services.report_service import ReportError, generate_report
from .celery_app import celery_app


@celery_app.task(name="m6.generate_report")
def generate_report_task(plan_id: int) -> dict:
    with session_scope() as db:
        try:
            report = generate_report(db, plan_id)
        except ReportError as e:
            return {"plan_id": plan_id, "error": str(e)}
    return {"plan_id": plan_id, "report_id": report.id}
