"""M1 API 測試（TestClient + SQLite，離線可跑）。

monkeypatch app.api.v1.projects._enqueue_generate（無需 Celery/broker）；
monkeypatch app.core.db._get_engine 讓 session_scope（內聯 task）也使用測試 DB。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.v1.projects as projects_api
import app.api.v1.tasks as tasks_api
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base

SPEC = "# 登入\n- 驗證帳號密碼\n- 失敗提示\n# 報表\n- 產生通過率圖表\n"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    engine = create_engine(
        f"sqlite:///{tmp_path / 'm1_api.db'}", connect_args={"check_same_thread": False}
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
    # 讓 session_scope（內聯執行 task）也指向測試 DB
    monkeypatch.setattr("app.core.db._get_engine", lambda: engine)

    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def _create_project(client) -> int:
    r = client.post("/api/v1/projects", json={"name": "Demo"})
    assert r.status_code == 200
    return r.json()["id"]


def test_create_and_list_projects(client):
    pid = _create_project(client)
    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())


def test_upload_spec_and_list(client):
    pid = _create_project(client)
    files = {"file": ("spec.md", SPEC, "text/markdown")}
    r = client.post(f"/api/v1/projects/{pid}/spec-files", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done" and body["char_count"] > 0 and body["format"] == "md"

    r = client.get(f"/api/v1/projects/{pid}/spec-files")
    assert r.status_code == 200
    assert any(s["id"] == body["id"] for s in r.json())


def test_upload_spec_404_project(client):
    files = {"file": ("spec.txt", "x", "text/plain")}
    r = client.post("/api/v1/projects/9999/spec-files", files=files)
    assert r.status_code == 404


def test_generate_items_enqueues(client, monkeypatch):
    pid = _create_project(client)
    files = {"file": ("spec.md", SPEC, "text/markdown")}
    sfid = client.post(f"/api/v1/projects/{pid}/spec-files", files=files).json()["id"]

    monkeypatch.setattr(projects_api, "_enqueue_generate", lambda sid: "fake-m1-task")
    r = client.post(f"/api/v1/projects/{pid}/spec-files/{sfid}/generate-items")
    assert r.status_code == 200
    assert r.json() == {"task_id": "fake-m1-task", "status": "queued"}


def test_generate_items_not_ready_409(client):
    # 直接插入一個未解析完成的 spec file
    pid = _create_project(client)
    from app.models.project import SpecFile

    # 透過 API session 插入 pending spec（用 get_db override 的同一 DB）
    app = client.app
    override = app.dependency_overrides[get_db]
    gen = override()
    db = next(gen)
    sf = SpecFile(project_id=pid, file_name="p.txt", format="txt", status="pending")
    db.add(sf)
    db.commit()
    sfid = sf.id
    next(gen, None)

    r = client.post(f"/api/v1/projects/{pid}/spec-files/{sfid}/generate-items")
    assert r.status_code == 409


def test_generate_items_end_to_end_inline(client):
    """直接同步執行 task（不經 broker），驗證項目確實生成並可列出。"""
    from app.workers.m1_tasks import generate_items_task

    pid = _create_project(client)
    files = {"file": ("spec.md", SPEC, "text/markdown")}
    sfid = client.post(f"/api/v1/projects/{pid}/spec-files", files=files).json()["id"]

    res = generate_items_task(sfid)  # inline run
    assert res["generated"] == 3  # 2 登入 + 1 報表

    r = client.get(f"/api/v1/projects/{pid}/test-items")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 3
    # SPEC：登入(2 項目) + 報表(1 項目)。第一筆「登入」為新建，第二筆重用同一類別。
    assert [i["category"]["name"] for i in items] == ["登入", "登入", "報表"]
    assert [i["matched_by"] for i in items] == ["new", "exact", "new"]
    assert items[0]["is_newly_created"] is True
    assert items[1]["is_newly_created"] is False  # 重用既有平台類別
    assert items[2]["is_newly_created"] is True


def test_platform_create_list_get(client):
    r = client.post("/api/v1/platform/categories", json={"name": "登入"})
    assert r.status_code == 200
    cid = r.json()["id"]

    r = client.get("/api/v1/platform/categories")
    assert any(c["id"] == cid for c in r.json())

    r = client.get(f"/api/v1/platform/categories/{cid}")
    assert r.json()["name"] == "登入"

    # 重複 code → 回既存
    r2 = client.post("/api/v1/platform/categories", json={"name": "登入"})
    assert r2.json()["id"] == cid


def test_platform_get_404(client):
    assert client.get("/api/v1/platform/categories/9999").status_code == 404


def test_generic_task_status_unknown(client, monkeypatch):
    # 避免實打 Redis：monkeypatch helper（與 rag 端點一致的模式）
    monkeypatch.setattr(tasks_api, "_task_status", lambda tid: {"task_id": tid, "state": "PENDING"})
    r = client.get("/api/v1/tasks/nonexistent-task-id")
    assert r.status_code == 200
    assert r.json() == {"task_id": "nonexistent-task-id", "state": "PENDING"}
