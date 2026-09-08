"""FR-3 / M4 服務層：案例執行（Fail → 自動開 Defect）+ 缺陷狀態機。

核心規則（FR-3）：任一 Test Case 執行結果為 Fail → 自動開立 1 個 Defect
（綁定 execution_id + test_case_id，title 取自案例名稱）。
"""
from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy.orm import Session

from ..models.defect import Defect, TestExecution
from ..models.test_plan import TestCase, TestFunction, TestPlan

EXECUTION_RESULTS = {"pass", "fail", "blocked"}
DEFECT_SEVERITIES = {"low", "medium", "high", "critical"}

DEFECT_STATUSES = ["open", "in_progress", "resolved", "closed"]
# §6.2：open → in_progress → resolved → closed（可 reopened 回 in_progress）
DEFECT_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress"},
    "in_progress": {"resolved", "open"},
    "resolved": {"closed", "in_progress"},  # 可 reopen
    "closed": {"in_progress"},              # 可 reopen
}


class DefectError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def assert_defect_transition(defect: Defect, new_status: str) -> None:
    if new_status not in DEFECT_STATUSES:
        raise DefectError(f"unknown defect status: {new_status}", 422)
    if new_status == defect.status:
        return
    if new_status not in DEFECT_TRANSITIONS.get(defect.status, set()):
        raise DefectError(f"invalid transition: {defect.status} -> {new_status}", 409)


def execute_case(
    session: Session,
    test_case_id: int,
    result: str,
    executed_by: Optional[str] = None,
    actual_result: Optional[str] = None,
) -> Tuple[TestExecution, Optional[Defect]]:
    """記錄一次案例執行；result == 'fail' 時自動開立 1 個 Defect。"""
    if result not in EXECUTION_RESULTS:
        raise DefectError(f"invalid result: {result} (expected pass/fail/blocked)", 422)

    c = session.get(TestCase, test_case_id)
    if c is None:
        raise DefectError("test case not found", 404)
    fn = session.get(TestFunction, c.test_function_id)
    plan = session.get(TestPlan, fn.test_plan_id) if fn else None
    if plan is None:
        raise DefectError("test plan not found for this case", 409)

    execution = TestExecution(
        test_case_id=c.id,
        test_plan_id=plan.id,
        executed_by=executed_by,
        result=result,
        actual_result=actual_result,
    )
    session.add(execution)
    session.flush()

    defect: Optional[Defect] = None
    if result == "fail":
        # FR-3：Fail → 自動開立 1 個 Defect
        desc = f"測試案例「{c.name}」執行結果為 Fail。"
        if actual_result:
            desc += f"\n實際結果：{actual_result}"
        defect = Defect(
            execution_id=execution.id,
            test_case_id=c.id,
            title=f"[FAIL] {c.name}",
            description=desc,
            severity="medium",
            status="open",
        )
        session.add(defect)
        session.flush()

    return execution, defect


def create_manual_defect(
    session: Session,
    title: str,
    description: Optional[str] = None,
    severity: str = "medium",
    priority: str = "medium",
    test_case_id: Optional[int] = None,
    execution_id: Optional[int] = None,
) -> Defect:
    """手動補建缺陷（M4）。test_case_id 可為 NULL（FR-3a 場景將觸發 Revision Request）。"""
    if severity not in DEFECT_SEVERITIES:
        raise DefectError(f"invalid severity: {severity}", 422)
    if test_case_id is not None and session.get(TestCase, test_case_id) is None:
        raise DefectError("test case not found", 404)
    d = Defect(
        title=title,
        description=description,
        severity=severity,
        priority=priority,
        test_case_id=test_case_id,
        execution_id=execution_id,
        status="open",
    )
    session.add(d)
    session.flush()
    return d


def list_defects(
    session: Session, status: Optional[str] = None, severity: Optional[str] = None
):
    q = session.query(Defect)
    if status:
        q = q.filter(Defect.status == status)
    if severity:
        q = q.filter(Defect.severity == severity)
    return q.order_by(Defect.id.desc()).all()
