"""FR-4 / M6 服務層：完成→報表指標 + AI 分析建議。

compute_metrics：通過率 / 缺陷分佈 / 覆蓋率 / 失敗案例（純邏輯，離線可測）。
AI：LLM 優先（JSON），未配置或失敗 → 離線啟發式 fallback（決定性）。
"""
from __future__ import annotations

import io
import json
import os
from collections import Counter
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Tuple

import httpx
import smtplib
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.defect import Defect, TestExecution
from ..models.report import AiReport
from ..models.test_plan import TestCase, TestFunction, TestPlan


class ReportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def compute_metrics(session: Session, plan_id: int) -> dict:
    functions = session.query(TestFunction).filter_by(test_plan_id=plan_id).all()
    function_ids = [f.id for f in functions]
    cases = (
        session.query(TestCase).filter(TestCase.test_function_id.in_(function_ids)).all()
        if function_ids
        else []
    )

    status_counts = Counter(c.status for c in cases)
    total = len(cases)
    passed = status_counts.get("passed", 0)
    failed = status_counts.get("failed", 0)
    blocked = status_counts.get("blocked", 0)
    pending = total - passed - failed - blocked
    pass_rate = (passed / total) if total else 0.0
    fail_rate = (failed / total) if total else 0.0

    cases_per_fn = Counter(c.test_function_id for c in cases)
    coverage_gaps = [f.name for f in functions if cases_per_fn.get(f.id, 0) == 0]
    coverage = ((len(functions) - len(coverage_gaps)) / len(functions)) if functions else 0.0

    case_ids = [c.id for c in cases]
    exec_ids = [r[0] for r in session.query(TestExecution.id).filter_by(test_plan_id=plan_id).all()]
    cond = []
    if case_ids:
        cond.append(Defect.test_case_id.in_(case_ids))
    if exec_ids:
        cond.append(Defect.execution_id.in_(exec_ids))
    defects = session.query(Defect).filter(or_(*cond)).all() if cond else []

    sev_counts = Counter(d.severity for d in defects)
    st_counts = Counter(d.status for d in defects)
    open_or_in_progress = st_counts.get("open", 0) + st_counts.get("in_progress", 0)
    high_sev = sev_counts.get("critical", 0) + sev_counts.get("high", 0)
    failed_cases = [c.name for c in cases if c.status == "failed"]

    return {
        "plan_id": plan_id,
        "total_functions": len(functions),
        "total_cases": total,
        "passed": passed,
        "failed": failed,
        "blocked": blocked,
        "pending": pending,
        "pass_rate": round(pass_rate, 4),
        "fail_rate": round(fail_rate, 4),
        "coverage": round(coverage, 4),
        "coverage_gaps": coverage_gaps,
        "defects": {
            "total": len(defects),
            "by_severity": dict(sev_counts),
            "by_status": dict(st_counts),
            "open_or_in_progress": open_or_in_progress,
            "high_severity": high_sev,
        },
        "failed_cases": failed_cases,
    }


def analyze_offline(m: dict) -> Tuple[str, list, str]:
    """決定性離線分析（無 LLM key 也能產出報表建議）。"""
    total = m["total_cases"]
    d = m["defects"]
    gaps = m["coverage_gaps"]
    summary = (
        f"測試計畫共 {m['total_functions']} 個功能、{total} 個案例：通過 {m['passed']}"
        f"（{m['pass_rate']:.0%}）、失敗 {m['failed']}、阻塞 {m['blocked']}、未執行 {m['pending']}；"
        f"缺陷 {d['total']} 個（未結 {d['open_or_in_progress']}，高嚴重度 {d['high_severity']}）；"
        f"覆蓋率 {m['coverage']:.0%}。"
    )
    recs: list[dict] = []
    if m["failed"]:
        recs.append(
            {
                "title": "處理失敗案例",
                "detail": f"{m['failed']} 個案例失敗（{', '.join(m['failed_cases']) or '-'}），"
                "建議修復或補強步驟後重測。",
            }
        )
    if gaps:
        recs.append(
            {
                "title": "補件覆蓋缺口",
                "detail": f"以下功能缺測試案例，建議補件（可一鍵轉 Revision Request）：{', '.join(gaps)}。",
            }
        )
    if d["high_severity"]:
        recs.append(
            {
                "title": "高嚴重度缺陷",
                "detail": f"{d['high_severity']} 個 high/critical 缺陷，建議優先分析根因。",
            }
        )
    if d["open_or_in_progress"]:
        recs.append(
            {
                "title": "缺陷未收斂",
                "detail": f"尚有 {d['open_or_in_progress']} 個缺陷未結案，建議排期追蹤。",
            }
        )
    if not recs:
        recs.append({"title": "測試收斂", "detail": "無失敗、無覆蓋缺口且缺陷已收斂，建議進入發布評估。"})
    return summary, recs, "heuristic-offline"


def analyze_with_llm(m: dict) -> Optional[Tuple[str, list, str]]:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("EMBEDDING_API_KEY")
    if not api_key:
        return None
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    prompt = (
        "你是 QA 分析師。以下為測試計畫指標（JSON）。請產出分析：\n"
        "1. summary：整體通過率與風險簡述（2-3 句）。\n"
        "2. recommendations：建議陣列，每項 {\"title\":..., \"detail\":...}，"
        "重點涵蓋失敗案例、覆蓋缺口（可補件）、高嚴重度缺陷、未收斂風險。\n"
        "只輸出 JSON：{\"summary\":\"...\",\"recommendations\":[{\"title\":\"...\",\"detail\":\"...\"}]}\n\n"
        f"指標：\n{json.dumps(m, ensure_ascii=False)}"
    )
    try:
        resp = httpx.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = json.loads(resp.json()["choices"][0]["message"]["content"])
        summary = str(data.get("summary", "")).strip()
        recs_raw = data.get("recommendations", [])
        recs_raw = recs_raw if isinstance(recs_raw, list) else []
        clean = [
            {"title": str(r.get("title", "建議")), "detail": str(r.get("detail", ""))}
            for r in recs_raw
            if isinstance(r, dict)
        ]
        if not summary and not clean:
            return None
        if not clean:
            clean = [{"title": "見摘要", "detail": summary}]
        return (summary or "（見建議）"), clean, model
    except Exception:
        return None


def generate_report(session: Session, plan_id: int) -> AiReport:
    plan = session.get(TestPlan, plan_id)
    if plan is None:
        raise ReportError("test plan not found", 404)

    metrics = compute_metrics(session, plan_id)
    ai = analyze_with_llm(metrics)
    if ai is None:
        summary, recs, model_name = analyze_offline(metrics)
    else:
        summary, recs, model_name = ai

    report = AiReport(
        project_id=plan.project_id,
        test_plan_id=plan_id,
        summary=summary,
        recommendations=json.dumps(recs, ensure_ascii=False),
        metrics_json=metrics,
        model_name=model_name,
    )
    session.add(report)
    session.flush()
    return report


# ---------- 匯出：PDF + Email（FR-4 延伸）----------
class EmailNotConfigured(Exception):
    """SMTP 未設定（SMTP_HOST 為空）。"""


def _report_pdf_font() -> str:
    """回傳可用 CJK 字型名。優先用 `PDF_FONT` env 指向的 TTF（可改善繁體覆蓋），
    否則回落到 reportlab 內建 CID 字型 STSong-Light（免外掛字型檔）。"""
    from reportlab.pdfbase import pdfmetrics

    custom = os.getenv("PDF_FONT", "").strip()
    if custom and os.path.exists(custom):
        try:
            from reportlab.pdfbase.ttfonts import TTFont
            pdfmetrics.registerFont(TTFont("tw_custom", custom))
            return "tw_custom"
        except Exception:  # noqa: BLE001
            pass
    try:
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    except Exception:  # noqa: BLE001
        pass  # 已註冊或不支援 → STSong-Light 通常仍可用
    return "STSong-Light"


def render_report_pdf_bytes(plan_name: str, summary: str, recs: list, m: dict) -> bytes:
    """以 reportlab 產生報表 PDF（指標 + 摘要 + AI 建議），含 CJK。"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font = _report_pdf_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
    )
    base = getSampleStyleSheet()
    h1 = ParagraphStyle("tw_h1", parent=base["Title"], fontName=font, fontSize=18, leading=22)
    body = ParagraphStyle("tw_body", parent=base["Normal"], fontName=font, fontSize=10, leading=14)
    bullet = ParagraphStyle("tw_bullet", parent=body, leftIndent=8, leading=14)

    d = m.get("defects", {}) or {}

    def pct(x):
        return f"{(x or 0) * 100:.1f}%"

    rows = [
        ["功能數", str(m.get("total_functions", 0))],
        ["案例數（通過/失敗/阻塞/未執行）",
         f"{m.get('total_cases', 0)}（{m.get('passed', 0)}/{m.get('failed', 0)}/{m.get('blocked', 0)}/{m.get('pending', 0)}）"],
        ["通過率 / 覆蓋率", f"{pct(m.get('pass_rate'))} / {pct(m.get('coverage'))}"],
        ["缺陷（未結 / 高嚴重度）",
         f"{d.get('total', 0)}（{d.get('open_or_in_progress', 0)} / {d.get('high_severity', 0)}）"],
        ["覆蓋缺口", ", ".join(m.get("coverage_gaps", []) or []) or "無"],
        ["失敗案例", ", ".join(m.get("failed_cases", []) or []) or "無"],
    ]
    data = [[Paragraph(str(a), body), Paragraph(str(b), body)] for a, b in rows]
    tbl = Table(data, colWidths=[62 * mm, 108 * mm])
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    elements = [
        Paragraph("測試報表", h1),
        Spacer(1, 6),
        Paragraph(f"計畫：{plan_name}", body),
        Spacer(1, 4),
        Paragraph(f"摘要：{summary or '（無）'}", body),
        Spacer(1, 10),
        Paragraph("指標", h1),
        Spacer(1, 4),
        tbl,
        Spacer(1, 10),
        Paragraph("AI 分析建議", h1),
        Spacer(1, 4),
    ]
    if recs:
        for r in recs:
            elements.append(Paragraph(f"• {r.get('title', '建議')}：{r.get('detail', '')}", bullet))
    else:
        elements.append(Paragraph("（無）", body))

    doc.build(elements)
    return buf.getvalue()


def parse_recs(report: AiReport) -> list:
    """把 report.recommendations（JSON 陣列字串）解析為 list[dict]。"""
    try:
        recs = json.loads(report.recommendations) if report.recommendations else []
    except Exception:  # noqa: BLE001
        recs = []
    return [r for r in recs if isinstance(r, dict)] if isinstance(recs, list) else []


def latest_report(db: Session, plan_id: int) -> Optional[AiReport]:
    return (
        db.query(AiReport).filter_by(test_plan_id=plan_id).order_by(AiReport.id.desc()).first()
    )


def _report_html(plan_name: str, summary: str, recs: list, m: dict) -> str:
    d = m.get("defects", {}) or {}

    def pct(x):
        return f"{(x or 0) * 100:.1f}%"

    rec_html = "".join(
        f"<li><b>{r.get('title', '建議')}</b>：{r.get('detail', '')}</li>" for r in recs
    ) or "<li>（無）</li>"
    return f"""
    <div style="font-family:sans-serif;font-size:14px;line-height:1.6;">
      <h2 style="margin-bottom:0;">測試報表</h2>
      <p><b>計畫：</b>{plan_name}</p>
      <p><b>摘要：</b>{summary or '（無）'}</p>
      <table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;border-color:#ddd;">
        <tr><td>功能數</td><td>{m.get('total_functions', 0)}</td></tr>
        <tr><td>案例數（通過/失敗/阻塞/未執行）</td>
            <td>{m.get('total_cases', 0)}（{m.get('passed', 0)}/{m.get('failed', 0)}/{m.get('blocked', 0)}/{m.get('pending', 0)}）</td></tr>
        <tr><td>通過率 / 覆蓋率</td><td>{pct(m.get('pass_rate'))} / {pct(m.get('coverage'))}</td></tr>
        <tr><td>缺陷（未結 / 高嚴重度）</td>
            <td>{d.get('total', 0)}（{d.get('open_or_in_progress', 0)} / {d.get('high_severity', 0)}）</td></tr>
        <tr><td>覆蓋缺口</td><td>{', '.join(m.get('coverage_gaps', []) or []) or '無'}</td></tr>
        <tr><td>失敗案例</td><td>{', '.join(m.get('failed_cases', []) or []) or '無'}</td></tr>
      </table>
      <h3>AI 分析建議</h3>
      <ul>{rec_html}</ul>
    </div>
    """


def build_report_email(db: Session, plan_id: int, to_addr: str) -> Tuple[str, str, bytes]:
    """組一則報表 email：回傳 (subject, html_body, pdf_bytes)。不實際發送。"""
    report = latest_report(db, plan_id)
    if report is None:
        raise ReportError("report not ready", 404)
    plan = db.get(TestPlan, plan_id)
    plan_name = plan.name if plan else f"plan #{plan_id}"
    m = report.metrics_json or {}
    recs = parse_recs(report)
    summary = report.summary or ""
    subject = f"【TestWeaver】測試報表：{plan_name}（通過率 {(m.get('pass_rate') or 0) * 100:.0f}%）"
    html = _report_html(plan_name, summary, recs, m)
    pdf = render_report_pdf_bytes(plan_name, summary, recs, m)
    return subject, html, pdf


def _smtp_send(*, subject: str, html_body: str, pdf_bytes: bytes, to_addr: str) -> None:
    """實際 SMTP 發送（測試可 monkeypatch）。"""
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("EMAIL_FROM") or user or "testweaver@localhost"

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    if pdf_bytes:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", 'attachment; filename="testweaver-report.pdf"')
        msg.attach(part)

    with smtplib.SMTP(host, port, timeout=30) as s:
        if os.getenv("SMTP_STARTTLS", "true").strip().lower() in ("1", "true", "yes", "on"):
            try:
                s.starttls()
            except Exception:  # noqa: BLE001
                pass
        if user:
            s.login(user, password)
        s.send_message(msg)


def send_report_email(db: Session, plan_id: int, to_addr: str) -> None:
    """組報表 email 並發送。SMTP 未設定 → EmailNotConfigured；無報表 → ReportError(404)。"""
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        raise EmailNotConfigured("SMTP 未設定（請設 SMTP_HOST）")
    subject, html, pdf = build_report_email(db, plan_id, to_addr)
    _smtp_send(subject=subject, html_body=html, pdf_bytes=pdf, to_addr=to_addr)
