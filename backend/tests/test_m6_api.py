"""M6 API 測試（TestClient + SQLite，離線）。

complete → 同步生成報表；非法狀態→409；未完成→報表 404；CSV 匯出；worker 任務可內聯執行。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.main import create_app
from app.models.base import Base


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'm6.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def _override_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db
    # session_scope（供內聯 generate_report_task）指向測試 DB
    monkeypatch.setattr("app.core.db._get_engine", lambda: engine)

    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def _seed(client, status: str = "in_progress"):
    from app.models.project import Project
    from app.models.test_plan import TestCase, TestFunction, TestPlan

    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    p = Project(name="P")
    db.add(p)
    db.flush()
    plan = TestPlan(project_id=p.id, name="P1", status=status)
    db.add(plan)
    db.flush()
    f1 = TestFunction(test_plan_id=plan.id, name="A", sort_order=1)
    db.add(f1)
    db.flush()
    c1 = TestCase(test_function_id=f1.id, name="c1", status="passed", sort_order=1)
    db.add(c1)
    c2 = TestCase(test_function_id=f1.id, name="c2", status="failed", sort_order=2)
    db.add(c2)
    db.flush()
    db.commit()
    ids = {"project_id": p.id, "plan_id": plan.id}
    next(gen, None)
    return ids


def test_complete_generates_report(client):
    s = _seed(client)
    r = client.post(f"/api/v1/test-plans/{s['plan_id']}/complete")
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "completed" and isinstance(b["report_id"], int)


def test_complete_draft_409(client):
    s = _seed(client, status="draft")  # draft 不可直接 completed
    assert client.post(f"/api/v1/test-plans/{s['plan_id']}/complete").status_code == 409


def test_report_not_ready_before_complete(client):
    s = _seed(client)
    assert client.get(f"/api/v1/reports/{s['plan_id']}").status_code == 404


def test_report_ready_after_complete(client):
    s = _seed(client)
    client.post(f"/api/v1/test-plans/{s['plan_id']}/complete")
    r = client.get(f"/api/v1/reports/{s['plan_id']}")
    assert r.status_code == 200
    b = r.json()
    assert b["metrics"]["total_cases"] == 2 and b["metrics"]["failed"] == 1
    assert len(b["recommendations"]) >= 1 and b["model_name"]


def test_export_csv(client):
    s = _seed(client)
    client.post(f"/api/v1/test-plans/{s['plan_id']}/complete")
    r = client.get(f"/api/v1/reports/{s['plan_id']}/export")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    assert "pass_rate" in r.text


def test_generate_report_task_inline(client):
    from app.workers.m6_tasks import generate_report_task

    s = _seed(client)
    res = generate_report_task(s["plan_id"])  # worker 路徑直接同步執行
    assert "report_id" in res
