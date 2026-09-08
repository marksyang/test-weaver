"""M3 API 測試（TestClient + SQLite，離線）。

重點：FR-2a「未同時綁定 Function + Case → 拒收」（缺欄位 → 422）。
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
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'm3.db'}", connect_args={"check_same_thread": False}
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
    """建立 project/plan/function/case（+ 第二組供 mismatch 測試），回傳 id dict。"""
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
    f2 = TestFunction(test_plan_id=plan.id, name="F2", sort_order=2)
    db.add(f2)
    db.flush()
    c2 = TestCase(test_function_id=f2.id, name="C2", sort_order=1)
    db.add(c2)
    db.flush()
    db.commit()
    ids = {
        "project_id": p.id, "plan_id": plan.id,
        "fn_id": f.id, "case_id": c.id,
        "fn2_id": f2.id, "case2_id": c2.id,
    }
    next(gen, None)
    return ids


def test_missing_case_id_rejected(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/self-tests",
        json={"project_id": s["project_id"], "test_function_id": s["fn_id"], "result": "pass"},
    )
    assert r.status_code == 422  # 未綁定 Case → 拒收


def test_missing_function_id_rejected(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/self-tests",
        json={"project_id": s["project_id"], "test_case_id": s["case_id"], "result": "pass"},
    )
    assert r.status_code == 422  # 未綁定 Function → 拒收


def test_create_success_with_names(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/self-tests",
        json={
            "project_id": s["project_id"],
            "test_function_id": s["fn_id"],
            "test_case_id": s["case_id"],
            "result": "pass",
            "tester": "Alice",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["function_name"] == "F" and body["case_name"] == "C"
    assert body["tester"] == "Alice" and body["result"] == "pass"


def test_case_function_mismatch_400(client):
    s = _seed(client)
    # case_id 屬於 fn，卻傳 fn2 → 400
    r = client.post(
        "/api/v1/self-tests",
        json={
            "project_id": s["project_id"],
            "test_function_id": s["fn2_id"],
            "test_case_id": s["case_id"],
            "result": "pass",
        },
    )
    assert r.status_code == 400


def test_bad_result_422(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/self-tests",
        json={
            "project_id": s["project_id"],
            "test_function_id": s["fn_id"],
            "test_case_id": s["case_id"],
            "result": "nope",
        },
    )
    assert r.status_code == 422


def test_list_and_filter(client):
    s = _seed(client)
    for res in ("pass", "fail"):
        client.post(
            "/api/v1/self-tests",
            json={
                "project_id": s["project_id"],
                "test_function_id": s["fn_id"],
                "test_case_id": s["case_id"],
                "result": res,
            },
        )
    r = client.get(f"/api/v1/projects/{s['project_id']}/self-tests")
    assert r.status_code == 200 and len(r.json()) == 2

    r = client.get(
        f"/api/v1/projects/{s['project_id']}/self-tests", params={"result": "pass"}
    )
    assert len(r.json()) == 1 and r.json()[0]["result"] == "pass"


def test_list_project_404(client):
    _seed(client)
    assert client.get("/api/v1/projects/9999/self-tests").status_code == 404
