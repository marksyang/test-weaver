"""M6 Celery 任務：完成計畫後生成報表 + AI 分析（FR-4）；報表排程補生成。"""
from __future__ import annotations

import os

from ..core.db import session_scope
from ..services.report_service import (
    ReportError,
    generate_report,
    run_report_schedule,
)
from .celery_app import celery_app


@celery_app.task(name="m6.generate_report")
def generate_report_task(plan_id: int) -> dict:
    with session_scope() as db:
        try:
            report = generate_report(db, plan_id)
        except ReportError as e:
            return {"plan_id": plan_id, "error": str(e)}
    return {"plan_id": plan_id, "report_id": report.id}


def _email_recipients() -> list[str] | None:
    """依 ``REPORT_EMAIL_TO``（逗號分隔）解析收件人；未設 → None。"""
    raw = os.getenv("REPORT_EMAIL_TO", "")
    recs = [x.strip() for x in raw.split(",") if x.strip()]
    return recs or None


@celery_app.task(name="m6.schedule_reports")
def schedule_reports_task() -> dict:
    """排程：為「已完成且無報表」的計畫補生成報表；依 REPORT_EMAIL_TO 選配 email。"""
    with session_scope() as db:
        return run_report_schedule(db, email_to=_email_recipients())
