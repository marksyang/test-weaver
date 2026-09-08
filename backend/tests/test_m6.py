"""FR-4 / M6 服務層測試（SQLite 離線）。"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.defect import Defect
from app.models.project import Project
from app.models.test_plan import TestCase, TestFunction, TestPlan
from app.services.report_service import (
    analyze_offline,
    compute_metrics,
    generate_report,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def _seed(db: Session):
    p = Project(name="P")
    db.add(p)
    db.flush()
    plan = TestPlan(project_id=p.id, name="P1")
    db.add(plan)
    db.flush()
    f1 = TestFunction(test_plan_id=plan.id, name="A", sort_order=1)
    db.add(f1)
    db.flush()
    f2 = TestFunction(test_plan_id=plan.id, name="B", sort_order=2)
    db.add(f2)
    db.flush()
    c1 = TestCase(test_function_id=f1.id, name="c1", status="passed", sort_order=1)
    db.add(c1)
    c2 = TestCase(test_function_id=f1.id, name="c2", status="failed", sort_order=2)
    db.add(c2)
    c3 = TestCase(test_function_id=f1.id, name="c3", status="blocked", sort_order=3)
    db.add(c3)
    db.flush()
    d = Defect(title="x", test_case_id=c2.id, severity="critical")
    db.add(d)
    db.flush()
    db.commit()
    return p, plan


def test_compute_metrics(db):
    _, plan = _seed(db)
    m = compute_metrics(db, plan.id)
    assert m["total_cases"] == 3
    assert (m["passed"], m["failed"], m["blocked"], m["pending"]) == (1, 1, 1, 0)
    assert m["pass_rate"] == round(1 / 3, 4)
    assert m["coverage_gaps"] == ["B"]  # f2 無案例
    assert m["defects"]["total"] == 1 and m["defects"]["high_severity"] == 1
    assert m["failed_cases"] == ["c2"]


def test_analyze_offline_has_recs(db):
    _, plan = _seed(db)
    m = compute_metrics(db, plan.id)
    summary, recs, model = analyze_offline(m)
    assert model == "heuristic-offline"
    assert summary and len(recs) >= 1
    titles = {r["title"] for r in recs}
    assert "處理失敗案例" in titles and "補件覆蓋缺口" in titles


def test_generate_report_stores(db):
    _, plan = _seed(db)
    rep = generate_report(db, plan.id)
    db.commit()
    assert rep.test_plan_id == plan.id and rep.model_name
    recs = json.loads(rep.recommendations)
    assert isinstance(recs, list) and recs
    assert rep.metrics_json["total_cases"] == 3


def test_empty_plan_metrics(db):
    p = Project(name="P")
    db.add(p)
    db.flush()
    plan = TestPlan(project_id=p.id, name="empty")
    db.add(plan)
    db.flush()
    db.commit()
    m = compute_metrics(db, plan.id)
    assert m["total_cases"] == 0 and m["pass_rate"] == 0.0 and m["coverage_gaps"] == []
