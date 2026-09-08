"""M4 API 測試（TestClient + SQLite，離線）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.main import create_app
from app.models.base import Base


@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'm4.db'}", connect_args={"check_same_thread": False}
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
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def _seed(client):
    from app.models.project import Project
    from app.models.test_plan import TestCase, TestFunction, TestPlan

    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
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
    ids = {"project_id": p.id, "plan_id": plan.id, "fn_id": f.id, "case_id": c.id}
    next(gen, None)
    return ids


def test_execute_fail_creates_defect(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/test-executions",
        json={"test_case_id": s["case_id"], "result": "fail", "actual_result": "boom"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["execution"]["result"] == "fail"
    assert body["execution"]["case_name"] == "C"
    assert body["defect"] is not None
    assert body["defect"]["test_case_id"] == s["case_id"]
    assert body["defect"]["status"] == "open"


def test_execute_pass_no_defect(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/test-executions",
        json={"test_case_id": s["case_id"], "result": "pass"},
    )
    assert r.status_code == 200
    assert r.json()["defect"] is None


def test_execute_case_not_found(client):
    _seed(client)
    r = client.post(
        "/api/v1/test-executions", json={"test_case_id": 9999, "result": "pass"}
    )
    assert r.status_code == 404


def test_list_case_executions(client):
    s = _seed(client)
    client.post("/api/v1/test-executions", json={"test_case_id": s["case_id"], "result": "pass"})
    client.post("/api/v1/test-executions", json={"test_case_id": s["case_id"], "result": "fail"})
    r = client.get(f"/api/v1/test-cases/{s['case_id']}/executions")
    assert r.status_code == 200 and len(r.json()) == 2


def test_defects_list_and_filter(client):
    s = _seed(client)
    client.post("/api/v1/test-executions", json={"test_case_id": s["case_id"], "result": "fail"})
    client.post("/api/v1/defects", json={"title": "manual", "severity": "high"})

    r = client.get("/api/v1/defects")
    assert r.status_code == 200 and len(r.json()) == 2

    r = client.get("/api/v1/defects", params={"severity": "high"})
    assert len(r.json()) == 1 and r.json()[0]["title"] == "manual"


def test_manual_defect_without_case(client):
    _seed(client)
    r = client.post("/api/v1/defects", json={"title": "no case"})
    assert r.status_code == 200
    assert r.json()["test_case_id"] is None


def test_defect_state_transition(client):
    s = _seed(client)
    body = client.post(
        "/api/v1/test-executions", json={"test_case_id": s["case_id"], "result": "fail"}
    ).json()
    did = body["defect"]["id"]

    r = client.patch(f"/api/v1/defects/{did}", json={"status": "in_progress"})
    assert r.status_code == 200 and r.json()["status"] == "in_progress"

    # open 已轉 in_progress；in_progress 不可直接跳 closed
    r = client.patch(f"/api/v1/defects/{did}", json={"status": "closed"})
    assert r.status_code == 409

    # in_progress -> resolved OK；指派
    r = client.patch(
        f"/api/v1/defects/{did}", json={"status": "resolved", "assigned_to": "Bob"}
    )
    assert r.json()["status"] == "resolved" and r.json()["assigned_to"] == "Bob"


def test_defect_404(client):
    _seed(client)
    assert client.get("/api/v1/defects/9999").status_code == 404
    assert client.patch("/api/v1/defects/9999", json={"status": "in_progress"}).status_code == 404
