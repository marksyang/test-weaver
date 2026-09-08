"""FR-2a / M3 服務層測試（SQLite 離線）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.project import Project
from app.models.test_plan import TestCase, TestFunction, TestPlan
from app.services.self_test_service import (
    SelfTestError,
    list_self_tests,
    record_self_test,
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


def test_record_success(db, seeded):
    st = record_self_test(
        db, seeded["project"].id, seeded["fn"].id, seeded["case"].id, "pass", tester="me"
    )
    db.commit()
    assert st.result == "pass" and st.tester == "me"


def test_missing_ids_rejected(db, seeded):
    with pytest.raises(SelfTestError) as e1:
        record_self_test(db, seeded["project"].id, None, seeded["case"].id, "pass")
    assert e1.value.status_code == 422
    with pytest.raises(SelfTestError) as e2:
        record_self_test(db, seeded["project"].id, seeded["fn"].id, None, "pass")
    assert e2.value.status_code == 422


def test_function_not_found(db, seeded):
    with pytest.raises(SelfTestError) as e:
        record_self_test(db, seeded["project"].id, 9999, seeded["case"].id, "pass")
    assert e.value.status_code == 404


def test_case_not_found(db, seeded):
    with pytest.raises(SelfTestError) as e:
        record_self_test(db, seeded["project"].id, seeded["fn"].id, 9999, "pass")
    assert e.value.status_code == 404


def test_case_must_belong_to_function(db, seeded):
    f2 = TestFunction(test_plan_id=seeded["plan"].id, name="F2", sort_order=2)
    db.add(f2)
    db.flush()
    with pytest.raises(SelfTestError) as e:
        record_self_test(db, seeded["project"].id, f2.id, seeded["case"].id, "pass")
    assert e.value.status_code == 400


def test_bad_result(db, seeded):
    with pytest.raises(SelfTestError) as e:
        record_self_test(db, seeded["project"].id, seeded["fn"].id, seeded["case"].id, "nope")
    assert e.value.status_code == 422


def test_project_mismatch(db, seeded):
    other = Project(name="Other")
    db.add(other)
    db.flush()
    with pytest.raises(SelfTestError) as e:
        record_self_test(db, other.id, seeded["fn"].id, seeded["case"].id, "pass")
    assert e.value.status_code == 400


def test_list_and_filter(db, seeded):
    record_self_test(db, seeded["project"].id, seeded["fn"].id, seeded["case"].id, "pass")
    record_self_test(db, seeded["project"].id, seeded["fn"].id, seeded["case"].id, "fail")
    db.commit()

    assert len(list_self_tests(db, seeded["project"].id)) == 2
    assert len(list_self_tests(db, seeded["project"].id, result="pass")) == 1
    assert len(list_self_tests(db, seeded["project"].id, test_case_id=seeded["case"].id)) == 2
    assert len(list_self_tests(db, seeded["project"].id, test_case_id=12345)) == 0
