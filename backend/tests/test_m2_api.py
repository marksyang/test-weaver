"""M2 API 測試（TestClient + SQLite，離線可跑）。"""
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
        f"sqlite:///{tmp_path / 'm2.db'}", connect_args={"check_same_thread": False}
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


def _mk_project(client) -> int:
    r = client.post("/api/v1/projects", json={"name": "P"})
    assert r.status_code == 200
    return r.json()["id"]


def test_full_three_tier_and_tree(client):
    pid = _mk_project(client)
    plan = client.post(f"/api/v1/projects/{pid}/test-plans", json={"name": "RP"}).json()
    assert plan["version"] == 1 and plan["status"] == "draft" and plan["project_id"] == pid

    f = client.post(
        f"/api/v1/test-plans/{plan['id']}/functions", json={"name": "F1"}
    ).json()
    c = client.post(
        f"/api/v1/functions/{f['id']}/cases",
        json={"name": "C1", "steps": "1. x", "priority": "high"},
    ).json()
    assert c["status"] == "draft" and c["sort_order"] == 1 and c["priority"] == "high"

    tree = client.get(f"/api/v1/test-plans/{plan['id']}/tree").json()
    assert tree["name"] == "RP"
    assert tree["functions"][0]["cases"][0]["name"] == "C1"


def test_plan_state_machine_api(client):
    pid = _mk_project(client)
    plan = client.post(f"/api/v1/projects/{pid}/test-plans", json={"name": "P"}).json()

    # draft 不可直接跳 completed
    r = client.patch(f"/api/v1/test-plans/{plan['id']}", json={"status": "completed"})
    assert r.status_code == 409

    # draft -> in_progress OK
    r = client.patch(f"/api/v1/test-plans/{plan['id']}", json={"status": "in_progress"})
    assert r.status_code == 200 and r.json()["status"] == "in_progress"

    # in_progress -> completed OK
    r = client.patch(f"/api/v1/test-plans/{plan['id']}", json={"status": "completed"})
    assert r.json()["status"] == "completed"

    # completed -> archived OK；archived 為終態
    r = client.patch(f"/api/v1/test-plans/{plan['id']}", json={"status": "archived"})
    assert r.json()["status"] == "archived"
    r = client.patch(f"/api/v1/test-plans/{plan['id']}", json={"status": "draft"})
    assert r.status_code == 409


def test_version_bump(client):
    pid = _mk_project(client)
    plan = client.post(f"/api/v1/projects/{pid}/test-plans", json={"name": "P"}).json()
    r = client.post(f"/api/v1/test-plans/{plan['id']}/revisions")
    assert r.json()["version"] == 2 and r.json()["status"] == "draft"
    r = client.post(f"/api/v1/test-plans/{plan['id']}/revisions")
    assert r.json()["version"] == 3


def test_case_status_patch(client):
    pid = _mk_project(client)
    plan = client.post(f"/api/v1/projects/{pid}/test-plans", json={"name": "P"}).json()
    f = client.post(f"/api/v1/test-plans/{plan['id']}/functions", json={"name": "F"}).json()
    c = client.post(f"/api/v1/functions/{f['id']}/cases", json={"name": "C"}).json()

    r = client.patch(f"/api/v1/test-cases/{c['id']}/status", json={"status": "passed"})
    assert r.json()["status"] == "passed"
    r = client.patch(f"/api/v1/test-cases/{c['id']}/status", json={"status": "nope"})
    assert r.status_code == 422


def test_sort_order_auto_increment(client):
    pid = _mk_project(client)
    plan = client.post(f"/api/v1/projects/{pid}/test-plans", json={"name": "P"}).json()
    f1 = client.post(f"/api/v1/test-plans/{plan['id']}/functions", json={"name": "F1"}).json()
    f2 = client.post(f"/api/v1/test-plans/{plan['id']}/functions", json={"name": "F2"}).json()
    assert (f1["sort_order"], f2["sort_order"]) == (1, 2)

    c1 = client.post(f"/api/v1/functions/{f1['id']}/cases", json={"name": "C1"}).json()
    c2 = client.post(f"/api/v1/functions/{f1['id']}/cases", json={"name": "C2"}).json()
    assert (c1["sort_order"], c2["sort_order"]) == (1, 2)

    # tree 依 sort_order 排序
    tree = client.get(f"/api/v1/test-plans/{plan['id']}/tree").json()
    assert [fn["name"] for fn in tree["functions"]] == ["F1", "F2"]


def test_plan_refers_test_items(client):
    pid = _mk_project(client)
    from app.models.platform import TestItemCategory
    from app.models.test_item import TestItem

    gen = client.app.dependency_overrides[get_db]()
    db = next(gen)
    cat = TestItemCategory(name="C", code="cat-x1")
    db.add(cat)
    db.flush()
    item = TestItem(project_id=pid, category_id=cat.id, name="I1")
    db.add(item)
    db.flush()
    item_id = item.id
    db.commit()
    next(gen, None)

    # 合法 item → 200
    r = client.post(
        f"/api/v1/projects/{pid}/test-plans",
        json={"name": "P", "test_item_ids": [item_id]},
    )
    assert r.status_code == 200
    # 不存在的 item → 400（且 plan 不被建立）
    r = client.post(
        f"/api/v1/projects/{pid}/test-plans",
        json={"name": "P2", "test_item_ids": [9999]},
    )
    assert r.status_code == 400


def test_list_plans(client):
    pid = _mk_project(client)
    client.post(f"/api/v1/projects/{pid}/test-plans", json={"name": "A"})
    client.post(f"/api/v1/projects/{pid}/test-plans", json={"name": "B"})
    r = client.get(f"/api/v1/projects/{pid}/test-plans")
    assert len(r.json()) == 2


def test_404s(client):
    assert client.get("/api/v1/test-plans/9999").status_code == 404
    assert client.patch("/api/v1/test-plans/9999", json={"name": "x"}).status_code == 404
    assert (
        client.post("/api/v1/test-plans/9999/functions", json={"name": "F"}).status_code
        == 404
    )
    assert (
        client.post("/api/v1/functions/9999/cases", json={"name": "C"}).status_code == 404
    )
