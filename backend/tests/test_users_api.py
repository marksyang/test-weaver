"""FR-5 帳號管理 API 測試（角色門檻 + 建立/更新）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.main import create_app
from app.models.base import Base
from app.services.auth_service import make_user


@pytest.fixture()
def env(tmp_path, monkeypatch):  # noqa: ARG001
    engine = create_engine(
        f"sqlite:///{tmp_path / 'users.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine, expire_on_commit=False)

    with TS() as db:
        make_user(db, "admin", "admin123", role="admin")
        make_user(db, "tester", "tester123", role="tester")
        db.commit()

    app = create_app()

    def _override_db():
        d = TS()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def _bearer(c: TestClient, username: str, password: str) -> dict:
    token = c.post("/api/v1/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_users_requires_admin_when_enabled(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    c = env
    assert c.get("/api/v1/users").status_code == 401  # 無 token
    assert c.get("/api/v1/users", headers=_bearer(c, "tester", "tester123")).status_code == 403
    assert c.get("/api/v1/users", headers=_bearer(c, "admin", "admin123")).status_code == 200


def test_users_noop_when_auth_disabled(env):
    # AUTH_ENABLED 預設 false → 免 token、免角色即可存取
    assert env.get("/api/v1/users").status_code == 200


def test_create_and_update_user(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    c = env
    h = _bearer(c, "admin", "admin123")

    r = c.post(
        "/api/v1/users",
        json={"username": "newuser", "password": "pass1234", "role": "qa_lead"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["role"] == "qa_lead"
    uid = r.json()["id"]

    # 重複帳號 → 409
    assert (
        c.post("/api/v1/users", json={"username": "newuser", "password": "pass1234", "role": "tester"}, headers=h).status_code
        == 409
    )
    # 改角色
    r2 = c.patch(f"/api/v1/users/{uid}", json={"role": "tester"}, headers=h)
    assert r2.status_code == 200 and r2.json()["role"] == "tester"
    # 非法角色 → 400
    assert c.patch(f"/api/v1/users/{uid}", json={"role": "superuser"}, headers=h).status_code == 400


def test_cannot_remove_last_admin_via_api(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    c = env
    h = _bearer(c, "admin", "admin123")
    admin_id = next(x["id"] for x in c.get("/api/v1/users", headers=h).json() if x["username"] == "admin")
    assert c.patch(f"/api/v1/users/{admin_id}", json={"role": "tester"}, headers=h).status_code == 400
