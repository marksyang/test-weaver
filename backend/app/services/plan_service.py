"""FR-2 / M2 服務層：Test Plan 狀態機、排序、三層樹組裝。

純邏輯（可離線用 SQLite + Session 測試）。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.test_plan import TestCase, TestFunction, TestPlan

# 狀態機（§6.1）：draft → in_progress → completed → archived
PLAN_STATUS: list[str] = ["draft", "in_progress", "completed", "archived"]
PLAN_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"in_progress"},
    "in_progress": {"completed", "draft"},  # 進行中可回 draft 再修訂
    "completed": {"archived"},
    "archived": set(),
}

CASE_STATUS: list[str] = ["draft", "ready", "passed", "failed", "blocked"]


class PlanError(ValueError):
    """業務規則錯誤（狀態機/參數），由 API 轉為 4xx。"""


def can_transition(current: str, new: str) -> bool:
    return new in PLAN_TRANSITIONS.get(current, set())


def assert_plan_transition(plan: TestPlan, new_status: str) -> None:
    if new_status not in PLAN_STATUS:
        raise PlanError(f"unknown plan status: {new_status}")
    if new_status == plan.status:
        return  # 無變化
    if not can_transition(plan.status, new_status):
        raise PlanError(f"invalid transition: {plan.status} -> {new_status}")


def assert_case_status(status: str) -> None:
    if status not in CASE_STATUS:
        raise PlanError(f"unknown case status: {status}")


def next_sort_order_functions(session: Session, test_plan_id: int) -> int:
    row = session.query(func.max(TestFunction.sort_order)).filter_by(
        test_plan_id=test_plan_id
    ).scalar()
    return (row or 0) + 1


def next_sort_order_cases(session: Session, test_function_id: int) -> int:
    row = session.query(func.max(TestCase.sort_order)).filter_by(
        test_function_id=test_function_id
    ).scalar()
    return (row or 0) + 1


def build_tree(session: Session, plan: TestPlan) -> dict:
    """組裝三層樹（UI 用）：plan → functions(sort_order) → cases(sort_order)。"""
    functions = (
        session.query(TestFunction)
        .filter_by(test_plan_id=plan.id)
        .order_by(TestFunction.sort_order, TestFunction.id)
        .all()
    )
    funcs = []
    for f in functions:
        cases = (
            session.query(TestCase)
            .filter_by(test_function_id=f.id)
            .order_by(TestCase.sort_order, TestCase.id)
            .all()
        )
        funcs.append(
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "sort_order": f.sort_order,
                "cases": [
                    {
                        "id": c.id,
                        "test_function_id": c.test_function_id,
                        "name": c.name,
                        "precondition": c.precondition,
                        "steps": c.steps,
                        "expected_result": c.expected_result,
                        "priority": c.priority,
                        "status": c.status,
                        "sort_order": c.sort_order,
                    }
                    for c in cases
                ],
            }
        )
    return {
        "id": plan.id,
        "project_id": plan.project_id,
        "name": plan.name,
        "version": plan.version,
        "status": plan.status,
        "functions": funcs,
    }
