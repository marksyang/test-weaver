"""M5 API 測試（TestClient + SQLite，離線）。

端到端：手動建「無案例」Defect → 自動 RR；accept → 計畫版本 +1 + 補建案例。
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
        f"sqlite:///{tmp_path / 'm5.db'}", connect_args={"check_same_thread": False}
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
    ids = {
        "project_id": p.id, "plan_id": plan.id,
        "fn_id": f.id, "case_id": c.id,
        "version": plan.version,
    }
    next(gen, None)
    return ids


def test_no_case_defect_auto_creates_revision(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/defects",
        json={"title": "覆蓋缺口", "test_plan_id": s["plan_id"]},
    )
    assert r.status_code == 200
    defect_id = r.json()["id"]

    rr = client.get("/api/v1/revision-requests").json()
    assert len(rr) == 1
    assert rr[0]["defect_id"] == defect_id
    assert rr[0]["test_plan_id"] == s["plan_id"]
    assert rr[0]["status"] == "open"


def test_has_case_defect_no_revision(client):
    s = _seed(client)
    client.post(
        "/api/v1/defects",
        json={"title": "有案例", "test_case_id": s["case_id"], "test_plan_id": s["plan_id"]},
    )
    assert client.get("/api/v1/revision-requests").json() == []


def test_accept_bumps_version_and_adds_case(client):
    s = _seed(client)
    client.post("/api/v1/defects", json={"title": "gap", "test_plan_id": s["plan_id"]})
    rr_id = client.get("/api/v1/revision-requests").json()[0]["id"]

    r = client.post(f"/api/v1/revision-requests/{rr_id}/accept")
    assert r.status_code == 200 and r.json()["status"] == "accepted"

    # 接 M2 版本：+1
    plan = client.get(f"/api/v1/test-plans/{s['plan_id']}").json()
    assert plan["version"] == s["version"] + 1

    # 補建案例：tree 出現「修訂補充」function 且含案例
    tree = client.get(f"/api/v1/test-plans/{s['plan_id']}/tree").json()
    supp = [fn for fn in tree["functions"] if "修訂補充" in fn["name"]]
    assert supp and len(supp[0]["cases"]) >= 1


def test_double_accept_409(client):
    s = _seed(client)
    client.post("/api/v1/defects", json={"title": "gap", "test_plan_id": s["plan_id"]})
    rr_id = client.get("/api/v1/revision-requests").json()[0]["id"]
    assert client.post(f"/api/v1/revision-requests/{rr_id}/accept").status_code == 200
    assert client.post(f"/api/v1/revision-requests/{rr_id}/accept").status_code == 409


def test_reject_requires_reason(client):
    s = _seed(client)
    client.post("/api/v1/defects", json={"title": "gap", "test_plan_id": s["plan_id"]})
    rr_id = client.get("/api/v1/revision-requests").json()[0]["id"]

    # 缺理由 → 422（Pydantic min_length=1）
    assert client.post(f"/api/v1/revision-requests/{rr_id}/reject", json={}).status_code == 422
    # 有理由 → rejected
    r = client.post(f"/api/v1/revision-requests/{rr_id}/reject", json={"reason": "不需補建"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"


def test_complete_only_from_accepted(client):
    s = _seed(client)
    client.post("/api/v1/defects", json={"title": "gap", "test_plan_id": s["plan_id"]})
    rr_id = client.get("/api/v1/revision-requests").json()[0]["id"]
    # open 不可直接 done
    assert client.post(f"/api/v1/revision-requests/{rr_id}/complete").status_code == 409
    # accept → complete OK
    client.post(f"/api/v1/revision-requests/{rr_id}/accept")
    r = client.post(f"/api/v1/revision-requests/{rr_id}/complete")
    assert r.status_code == 200 and r.json()["status"] == "done"


def test_manual_create_revision(client):
    s = _seed(client)
    r = client.post(
        "/api/v1/revision-requests",
        json={
            "test_plan_id": s["plan_id"],
            "reason": "報表建議補件",
            "proposed_change": "新增案例",
        },
    )
    assert r.status_code == 200
    b = r.json()
    assert b["status"] == "open" and b["test_plan_id"] == s["plan_id"]
    # plan 不存在 → 404
    r2 = client.post("/api/v1/revision-requests", json={"test_plan_id": 9999})
    assert r2.status_code == 404


def test_get_revision_and_404(client):
    s = _seed(client)
    client.post("/api/v1/defects", json={"title": "gap", "test_plan_id": s["plan_id"]})
    rr_id = client.get("/api/v1/revision-requests").json()[0]["id"]
    assert client.get(f"/api/v1/revision-requests/{rr_id}").status_code == 200
    assert client.get("/api/v1/revision-requests/9999").status_code == 404
    assert client.post("/api/v1/revision-requests/9999/accept").status_code == 404
