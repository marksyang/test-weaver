"""FR-3a / M5 服務層測試（SQLite 離線）。

核心：Defect 無案例 → 自動建 Revision Request；接受 → 版本 +1 + 補建案例。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.defect import Defect
from app.models.project import Project
from app.models.test_plan import TestCase, TestFunction, TestPlan
from app.services.revision_service import (
    RevisionError,
    accept_revision,
    complete_revision,
    create_revision_request,
    ensure_revision_for_defect,
    list_revisions,
    reject_revision,
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


def test_no_case_defect_creates_revision(db, seeded):
    d = Defect(title="gap")
    db.add(d)
    db.flush()
    rr = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()
    assert rr is not None
    assert rr.status == "open" and rr.defect_id == d.id
    assert rr.test_plan_id == seeded["plan"].id


def test_has_case_no_revision(db, seeded):
    d = Defect(title="ok", test_case_id=seeded["case"].id)
    db.add(d)
    db.flush()
    rr = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()
    assert rr is None


def test_no_plan_resolvable_returns_none(db, seeded):
    d = Defect(title="gap")
    db.add(d)
    db.flush()
    rr = ensure_revision_for_defect(db, d, test_plan_id=None)
    db.commit()
    assert rr is None


def test_ensure_idempotent(db, seeded):
    d = Defect(title="gap")
    db.add(d)
    db.flush()
    r1 = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()
    r2 = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    assert r2.id == r1.id


def test_accept_bumps_version_and_creates_case(db, seeded):
    d = Defect(title="gap")
    db.add(d)
    db.flush()
    rr = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()

    v0 = seeded["plan"].version
    accept_revision(db, rr.id)
    db.commit()

    assert rr.status == "accepted"
    assert seeded["plan"].version == v0 + 1
    supp = [
        fn
        for fn in db.query(TestFunction).filter_by(test_plan_id=seeded["plan"].id).all()
        if "修訂補充" in fn.name
    ]
    assert supp
    assert db.query(TestCase).filter_by(test_function_id=supp[0].id).count() >= 1


def test_double_accept_blocked(db, seeded):
    d = Defect(title="gap")
    db.add(d)
    db.flush()
    rr = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()
    accept_revision(db, rr.id)
    db.commit()
    with pytest.raises(RevisionError) as e:
        accept_revision(db, rr.id)
    assert e.value.status_code == 409


def test_reject_requires_reason_and_open(db, seeded):
    d = Defect(title="gap")
    db.add(d)
    db.flush()
    rr = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()
    with pytest.raises(RevisionError) as e:
        reject_revision(db, rr.id, "   ")
    assert e.value.status_code == 400
    reject_revision(db, rr.id, "不需補建")
    db.commit()
    assert rr.status == "rejected"


def test_complete_only_from_accepted(db, seeded):
    d = Defect(title="gap")
    db.add(d)
    db.flush()
    rr = ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()
    with pytest.raises(RevisionError) as e:
        complete_revision(db, rr.id)  # open 不可直接 done
    assert e.value.status_code == 409
    accept_revision(db, rr.id)
    db.commit()
    complete_revision(db, rr.id)
    db.commit()
    assert rr.status == "done"


def test_create_revision_plan_not_found(db, seeded):
    with pytest.raises(RevisionError) as e:
        create_revision_request(db, test_plan_id=9999)
    assert e.value.status_code == 404


def test_list_filters(db, seeded):
    for _ in range(2):
        d = Defect(title="gap")
        db.add(d)
        db.flush()
        ensure_revision_for_defect(db, d, test_plan_id=seeded["plan"].id)
    db.commit()
    assert len(list_revisions(db)) == 2
    assert len(list_revisions(db, status="open")) == 2

    first = list_revisions(db)[0]
    reject_revision(db, first.id, "no")
    db.commit()
    assert len(list_revisions(db, status="open")) == 1
    assert len(list_revisions(db, status="rejected")) == 1
