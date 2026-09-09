"""M6 API：完成計畫觸發報表 + 取回指標/AI 建議 + 匯出（FR-4）。

對應計劃書 §7 M6。complete 以模組層 helper（_enqueue_report）封裝 enqueue，供測試 monkeypatch。
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.report import AiReport
from ...models.test_plan import TestPlan
from ...services.plan_service import PlanError, assert_plan_transition
from ...services.report_service import (
    EmailNotConfigured,
    ReportError,
    generate_report,
    parse_recs,
    render_report_pdf_bytes,
    send_report_email,
)

router = APIRouter(tags=["Reports/M6"])


class Recommendation(BaseModel):
    title: str
    detail: str = ""


class ReportOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: int
    summary: Optional[str] = None
    recommendations: list[Recommendation] = []
    metrics: Optional[dict] = None
    model_name: Optional[str] = None
    generated_at: Optional[datetime] = None


class CompleteOut(BaseModel):
    plan_id: int
    name: str
    version: int
    status: str
    report_id: int


def _latest_report(db: Session, plan_id: int) -> Optional[AiReport]:
    return (
        db.query(AiReport)
        .filter_by(test_plan_id=plan_id)
        .order_by(AiReport.id.desc())
        .first()
    )


@router.post("/test-plans/{plan_id}/complete", response_model=CompleteOut)
def complete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(TestPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "test plan not found")
    try:
        assert_plan_transition(plan, "completed")
    except PlanError as e:
        raise HTTPException(409, str(e))
    plan.status = "completed"

    # 同步生成報表 + AI 分析（離線可用；需異用可改 dispatch generate_report_task）
    try:
        report = generate_report(db, plan.id)
    except ReportError as e:
        raise HTTPException(e.status_code, str(e))

    db.commit()
    return {
        "plan_id": plan.id,
        "name": plan.name,
        "version": plan.version,
        "status": plan.status,
        "report_id": report.id,
    }


@router.get("/reports/{plan_id}", response_model=ReportOut)
def get_report(plan_id: int, db: Session = Depends(get_db)):
    if db.get(TestPlan, plan_id) is None:
        raise HTTPException(404, "test plan not found")
    report = _latest_report(db, plan_id)
    if report is None:
        raise HTTPException(404, "report not ready")
    try:
        recs = json.loads(report.recommendations) if report.recommendations else []
    except Exception:
        recs = []
    if not isinstance(recs, list):
        recs = []
    return {
        "id": report.id,
        "summary": report.summary,
        "recommendations": [
            {"title": str(r.get("title", "建議")), "detail": str(r.get("detail", ""))}
            for r in recs
            if isinstance(r, dict)
        ],
        "metrics": report.metrics_json,
        "model_name": report.model_name,
        "generated_at": report.generated_at,
    }


@router.get("/reports/{plan_id}/export")
def export_report(plan_id: int, format: str = Query("csv"), db: Session = Depends(get_db)):
    report = _latest_report(db, plan_id)
    if report is None:
        raise HTTPException(404, "report not ready")
    m = report.metrics_json or {}

    fmt = (format or "csv").strip().lower()
    if fmt == "pdf":
        plan = db.get(TestPlan, plan_id)
        plan_name = plan.name if plan else f"plan #{plan_id}"
        recs = parse_recs(report)
        try:
            pdf = render_report_pdf_bytes(plan_name, report.summary or "", recs, m)
        except ImportError as e:
            raise HTTPException(501, f"PDF 匯出不可用（缺 reportlab）: {e}")
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="report_{plan_id}.pdf"'},
        )
    if fmt != "csv":
        raise HTTPException(400, f"unsupported export format: {format}（csv | pdf）")

    d = m.get("defects", {})

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["metric", "value"])
    for k in [
        "total_functions",
        "total_cases",
        "passed",
        "failed",
        "blocked",
        "pending",
        "pass_rate",
        "fail_rate",
        "coverage",
    ]:
        w.writerow([k, m.get(k)])
    w.writerow(["coverage_gaps", "; ".join(m.get("coverage_gaps", []) or [])])
    w.writerow([])
    w.writerow(["defect_severity", "count"])
    for sev, cnt in (d.get("by_severity") or {}).items():
        w.writerow([sev, cnt])
    w.writerow([])
    w.writerow(["defect_status", "count"])
    for st, cnt in (d.get("by_status") or {}).items():
        w.writerow([st, cnt])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="report_{plan_id}.csv"'
        },
    )


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SendIn(BaseModel):
    to: str


@router.post("/reports/{plan_id}/send")
def send_report(plan_id: int, body: SendIn, request: Request, db: Session = Depends(get_db)):
    """Email 報表（HTML + PDF 附件）給收件人。SMTP 未設定 → 503；無報表 → 404。"""
    request.state.audit_action = "report.send"
    to = (body.to or "").strip()
    if not _EMAIL_RE.match(to):
        raise HTTPException(422, "invalid recipient email")
    try:
        send_report_email(db, plan_id, to)
    except EmailNotConfigured as e:
        raise HTTPException(503, str(e))
    except ReportError as e:
        raise HTTPException(e.status_code, str(e))
    return {"ok": True, "to": to}
