"""FR-3a / M5 服務層：測試計畫修改要求。

核心規則（FR-3a）：Defect 無對應 Test Case（test_case_id 為 NULL）→ 自動建立 Revision Request。
接受（accepted）→ 補建案例 + 測試計畫版本 +1（接 M2）。
狀態機（§6.3）：open → accepted → done，或 open → rejected。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..models.defect import Defect, TestExecution
from ..models.revision import TestPlanRevisionRequest
from ..models.test_plan import TestCase, TestFunction, TestPlan
from .plan_service import next_sort_order_cases, next_sort_order_functions

REVISION_STATUSES = ["open", "accepted", "rejected", "done"]
REVISION_TRANSITIONS: dict[str, set[str]] = {
    "open": {"accepted", "rejected"},
    "accepted": {"done"},
    "rejected": set(),
    "done": set(),
}


class RevisionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def assert_revision_transition(rr: TestPlanRevisionRequest, new_status: str) -> None:
    # 不允許「同狀態」視為成功：accept/reject/complete 皆具副作用，只能前向跳轉。
    if new_status not in REVISION_STATUSES:
        raise RevisionError(f"unknown revision status: {new_status}", 422)
    if new_status not in REVISION_TRANSITIONS.get(rr.status, set()):
        raise RevisionError(
            f"invalid transition: {rr.status} -> {new_status}", 409
        )


def create_revision_request(
    session: Session,
    defect_id: Optional[int] = None,
    test_plan_id: Optional[int] = None,
    reason: Optional[str] = None,
    proposed_change: Optional[str] = None,
    requested_by: Optional[str] = None,
) -> TestPlanRevisionRequest:
    if test_plan_id is None or session.get(TestPlan, test_plan_id) is None:
        raise RevisionError("test plan not found", 404)
    rr = TestPlanRevisionRequest(
        defect_id=defect_id,
        test_plan_id=test_plan_id,
        reason=reason,
        proposed_change=proposed_change,
        status="open",
        requested_by=requested_by,
    )
    session.add(rr)
    session.flush()
    return rr


def ensure_revision_for_defect(
    session: Session, defect: Defect, test_plan_id: Optional[int] = None
) -> Optional[TestPlanRevisionRequest]:
    """FR-3a：缺陷無對應案例 → 自動建立 Revision Request（冪等）。

    有案例者非覆蓋缺口，跳過。計畫由 test_plan_id 或執行紀錄推導；無法確定則跳過。
    """
    if defect.test_case_id is not None:
        return None

    plan_id = test_plan_id
    if plan_id is None and defect.execution_id is not None:
        ex = session.get(TestExecution, defect.execution_id)
        if ex is not None:
            plan_id = ex.test_plan_id
    if plan_id is None:
        return None

    existing = (
        session.query(TestPlanRevisionRequest).filter_by(defect_id=defect.id).first()
    )
    if existing is not None:
        return existing

    return create_revision_request(
        session,
        defect_id=defect.id,
        test_plan_id=plan_id,
        reason=f"缺陷 #{defect.id} 無對應測試案例，需補建/修訂",
    )


def accept_revision(session: Session, rr_id: int) -> TestPlanRevisionRequest:
    """接受：open → accepted，並補建案例 + 測試計畫版本 +1（接 M2）。"""
    rr = session.get(TestPlanRevisionRequest, rr_id)
    if rr is None:
        raise RevisionError("revision request not found", 404)
    assert_revision_transition(rr, "accepted")

    plan = session.get(TestPlan, rr.test_plan_id)
    if plan is None:
        raise RevisionError("test plan not found", 404)

    # 接 M2 版本：+1
    plan.version += 1

    # 補建案例（FR-3a：接受 → 補建案例納入計畫）
    fn = TestFunction(
        test_plan_id=plan.id,
        name=f"修訂補充（rev #{rr.id}）",
        description=(rr.reason or "").strip() or None,
        sort_order=next_sort_order_functions(session, plan.id),
    )
    session.add(fn)
    session.flush()

    change_text = (rr.proposed_change or rr.reason or "補建案例").strip()
    first_line = (change_text.splitlines()[0] if change_text else "").strip()
    case = TestCase(
        test_function_id=fn.id,
        name=(first_line or "補建案例")[:255],
        steps=change_text or None,
        sort_order=next_sort_order_cases(session, fn.id),
    )
    session.add(case)
    session.flush()

    rr.status = "accepted"
    return rr


def reject_revision(session: Session, rr_id: int, reason: str) -> TestPlanRevisionRequest:
    """拒絕：open → rejected（需理由）。"""
    if not (reason or "").strip():
        raise RevisionError("rejection reason is required", 400)
    rr = session.get(TestPlanRevisionRequest, rr_id)
    if rr is None:
        raise RevisionError("revision request not found", 404)
    assert_revision_transition(rr, "rejected")
    note = f"[rejected: {reason.strip()}]"
    rr.reason = f"{rr.reason}\n{note}".strip() if rr.reason else note
    rr.status = "rejected"
    return rr


def complete_revision(session: Session, rr_id: int) -> TestPlanRevisionRequest:
    """完成：accepted → done。"""
    rr = session.get(TestPlanRevisionRequest, rr_id)
    if rr is None:
        raise RevisionError("revision request not found", 404)
    assert_revision_transition(rr, "done")
    rr.status = "done"
    return rr


def list_revisions(
    session: Session, status: Optional[str] = None, test_plan_id: Optional[int] = None
):
    q = session.query(TestPlanRevisionRequest)
    if status:
        q = q.filter_by(status=status)
    if test_plan_id is not None:
        q = q.filter_by(test_plan_id=test_plan_id)
    return q.order_by(TestPlanRevisionRequest.id.desc()).all()
