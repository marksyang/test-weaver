"""FR-3 / M4 服務層測試（SQLite 離線）。

核心：案例判 Fail → 自動開立且僅 1 個 Defect。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.project import Project
from app.models.test_plan import TestCase, TestFunction, TestPlan
from app.services.defect_service import (
    DefectError,
    assert_defect_transition,
    create_manual_defect,
    execute_case,
    list_defects,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def seeded(db: Session):
    p = Project(name="P")
    db.add(p)
    db.flush()
    plan = TestPlan(project_id=p.id, name="P1")
    db.add(plan)
    db.flush()
    f = TestFunction(test_plan_id=plan.id, name="F", sort_order=1)
    db.add(f)
    db.flush()
    c = TestCase(test_function_id=f.id, name="C", sort_order=1)
    db.add(c)
    db.flush()
    db.commit()
    return {"project": p, "plan": plan, "fn": f, "case": c}


def test_execute_pass_no_defect(db, seeded):
    ex, d = execute_case(db, seeded["case"].id, "pass", executed_by="me")
    db.commit()
    assert d is None and ex.result == "pass"


def test_execute_fail_creates_exactly_one_defect(db, seeded):
    ex, d = execute_case(db, seeded["case"].id, "fail", actual_result="boom")
    db.commit()
    assert d is not None
    assert d.test_case_id == seeded["case"].id
    assert d.execution_id == ex.id
    assert d.status == "open" and d.title.startswith("[FAIL]")
    assert len(list_defects(db)) == 1


def test_execute_blocked_no_defect(db, seeded):
    ex, d = execute_case(db, seeded["case"].id, "blocked")
    db.commit()
    assert d is None


def test_two_fails_two_defects(db, seeded):
    execute_case(db, seeded["case"].id, "fail")
    db.commit()
    execute_case(db, seeded["case"].id, "fail")
    db.commit()
    assert len(list_defects(db)) == 2


def test_execute_invalid_result(db, seeded):
    with pytest.raises(DefectError) as e:
        execute_case(db, seeded["case"].id, "nope")
    assert e.value.status_code == 422


def test_execute_case_not_found(db, seeded):
    with pytest.raises(DefectError) as e:
        execute_case(db, 9999, "pass")
    assert e.value.status_code == 404


def test_defect_state_machine(db, seeded):
    _, d = execute_case(db, seeded["case"].id, "fail")
    db.commit()
    # open → in_progress → resolved → closed
    assert_defect_transition(d, "in_progress")
    d.status = "in_progress"
    assert_defect_transition(d, "resolved")
    d.status = "resolved"
    assert_defect_transition(d, "closed")
    d.status = "closed"
    # closed 不能直接回 open（只能 reopen 到 in_progress）
    with pytest.raises(DefectError) as e:
        assert_defect_transition(d, "open")
    assert e.value.status_code == 409
    assert_defect_transition(d, "in_progress")  # reopen OK


def test_manual_defect_without_case(db, seeded):
    d = create_manual_defect(db, "手動缺陷")
    db.commit()
    assert d.test_case_id is None and d.status == "open"


def test_manual_defect_bad_severity(db, seeded):
    with pytest.raises(DefectError) as e:
        create_manual_defect(db, "x", severity="nope")
    assert e.value.status_code == 422


def test_list_defects_filter(db, seeded):
    execute_case(db, seeded["case"].id, "fail")
    db.commit()
    create_manual_defect(db, "hi", severity="high")
    db.commit()

    assert len(list_defects(db)) == 2
    assert len(list_defects(db, severity="high")) == 1
    assert len(list_defects(db, status="open")) == 2
