"""FR-2 / M2 服務層測試（狀態機、排序、三層樹；SQLite 離線）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.project import Project
from app.models.test_plan import TestCase, TestFunction, TestPlan
from app.services.plan_service import (
    PlanError,
    assert_case_status,
    assert_plan_transition,
    build_tree,
    next_sort_order_cases,
    next_sort_order_functions,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def _seed(session: Session):
    p = Project(name="P")
    session.add(p)
    session.flush()
    plan = TestPlan(project_id=p.id, name="P1")
    session.add(plan)
    session.flush()
    return p, plan


def test_state_machine_forward(db):
    _, plan = _seed(db)
    for target in ["in_progress", "completed", "archived"]:
        assert_plan_transition(plan, target)
        plan.status = target
    # archived 為終態
    with pytest.raises(PlanError):
        assert_plan_transition(plan, "draft")


def test_state_machine_illegal_jump(db):
    _, plan = _seed(db)  # draft
    with pytest.raises(PlanError):
        assert_plan_transition(plan, "completed")  # 不可跨越
    with pytest.raises(PlanError):
        assert_plan_transition(plan, "bogus")


def test_in_progress_back_to_draft(db):
    _, plan = _seed(db)
    plan.status = "in_progress"
    assert_plan_transition(plan, "draft")  # 允許回修訂


def test_case_status_validation(db):
    assert_case_status("passed")
    with pytest.raises(PlanError):
        assert_case_status("nope")


def test_sort_order_functions(db):
    _, plan = _seed(db)
    assert next_sort_order_functions(db, plan.id) == 1
    f = TestFunction(test_plan_id=plan.id, name="A", sort_order=1)
    db.add(f)
    db.flush()
    assert next_sort_order_functions(db, plan.id) == 2


def test_sort_order_cases(db):
    _, plan = _seed(db)
    f = TestFunction(test_plan_id=plan.id, name="F", sort_order=1)
    db.add(f)
    db.flush()
    assert next_sort_order_cases(db, f.id) == 1
    c = TestCase(test_function_id=f.id, name="C", sort_order=1)
    db.add(c)
    db.flush()
    assert next_sort_order_cases(db, f.id) == 2


def test_build_tree_ordering_and_shape(db):
    _, plan = _seed(db)
    # 故意亂序新增，驗證以 sort_order 排序
    f2 = TestFunction(test_plan_id=plan.id, name="F2", sort_order=2)
    db.add(f2)
    db.flush()
    f1 = TestFunction(test_plan_id=plan.id, name="F1", sort_order=1)
    db.add(f1)
    db.flush()
    c_b = TestCase(test_function_id=f1.id, name="B", sort_order=2)
    db.add(c_b)
    db.flush()
    c_a = TestCase(test_function_id=f1.id, name="A", sort_order=1)
    db.add(c_a)
    db.flush()
    db.commit()

    t = build_tree(db, plan)
    assert [fn["name"] for fn in t["functions"]] == ["F1", "F2"]
    assert [c["name"] for c in t["functions"][0]["cases"]] == ["A", "B"]
    assert [c["name"] for c in t["functions"][1]["cases"]] == []  # F2 無案例
    assert t["version"] == 1 and t["status"] == "draft"
    # case node 帶出 steps/priority
    assert t["functions"][0]["cases"][0]["priority"] == "medium"
