"""FR-4 / M6 服務層：完成→報表指標 + AI 分析建議。

compute_metrics：通過率 / 缺陷分佈 / 覆蓋率 / 失敗案例（純邏輯，離線可測）。
AI：LLM 優先（JSON），未配置或失敗 → 離線啟發式 fallback（決定性）。
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Optional, Tuple

import httpx
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
