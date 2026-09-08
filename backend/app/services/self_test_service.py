"""FR-2a / M3 服務層：自測錄入（強制同時綁定 Function + Case）。

核心規則：
- test_function_id 與 test_case_id 皆必填（缺任一即拒收，由 Pydantic 於 API 層以 422 攔截）。
- 兩者須存在；案例必須屬於該 Function（雙向對應一致）；Function 須落在指定專案下。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..models.self_test import SelfTest
from ..models.test_plan import TestCase, TestFunction, TestPlan

RESULTS = {"pass", "fail"}


class SelfTestError(Exception):
    """業務規則錯誤；status_code 供 API 層轉為 HTTP 狀態。"""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def record_self_test(
    session: Session,
    project_id: int,
    test_function_id: Optional[int],
    test_case_id: Optional[int],
    result: str,
    tester: Optional[str] = None,
    notes: Optional[str] = None,
) -> SelfTest:
    # FR-2a：未同時綁定 Function + Case → 拒收
    if test_function_id is None or test_case_id is None:
        raise SelfTestError("test_function_id and test_case_id are both required", 422)

    if result not in RESULTS:
        raise SelfTestError(f"invalid result: {result} (expected pass/fail)", 422)

    fn = session.get(TestFunction, test_function_id)
    if fn is None:
        raise SelfTestError("test function not found", 404)
    c = session.get(TestCase, test_case_id)
    if c is None:
        raise SelfTestError("test case not found", 404)

    # 雙向對應一致：案例須屬於該 Function
    if c.test_function_id != fn.id:
        raise SelfTestError(
            "test_case does not belong to the given test_function", 400
        )

    # Function 須在指定專案下（function → plan → project）
    plan = session.get(TestPlan, fn.test_plan_id)
    if plan is None or plan.project_id != project_id:
        raise SelfTestError("test function is not under the given project", 400)

    st = SelfTest(
        project_id=project_id,
        tester=tester,
        test_function_id=fn.id,
        test_case_id=c.id,
        result=result,
        notes=notes,
    )
    session.add(st)
    session.flush()
    return st


def list_self_tests(
    session: Session,
    project_id: int,
    result: Optional[str] = None,
    test_function_id: Optional[int] = None,
    test_case_id: Optional[int] = None,
):
    q = session.query(SelfTest).filter_by(project_id=project_id)
    if result:
        q = q.filter(SelfTest.result == result)
    if test_function_id is not None:
        q = q.filter_by(test_function_id=test_function_id)
    if test_case_id is not None:
        q = q.filter_by(test_case_id=test_case_id)
    return q.order_by(SelfTest.id.desc()).all()
