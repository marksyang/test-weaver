"""FR-5 / M8 API 測試（TestClient + SQLite，離線）。

覆蓋：免登入模式（AUTH_ENABLED 預設 false）匿名放行；啟用後 login / me / token 護 / 角色門檻。
"""
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
def env(tmp_path, monkeypatch):  # noqa: ARG001 - monkeypatch 供個別測試切 AUTH_ENABLED
    engine = create_engine(
        f"sqlite:///{tmp_path / 'auth.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    with TestSession() as db:  # 種子：admin + tester
        make_user(db, "admin", "admin123", role="admin")
        make_user(db, "tester", "tester123", role="tester")
        db.commit()

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


def _login(client: TestClient, username: str, password: str):
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


def _bearer(client: TestClient, username: str, password: str) -> dict:
    token = _login(client, username, password).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── 免登入模式（預設）──
def test_me_anonymous_when_disabled(env):
    r = env.get("/api/v1/auth/me")
    assert r.status_code == 200 and r.json()["role"] == "admin"


def test_protected_works_without_token_when_disabled(env):
    assert env.get("/api/v1/projects").status_code == 200
    # 平台角色門檻在免登入模式也放過
    assert env.get("/api/v1/platform/categories").status_code == 200


# ── 啟用模式 ──
def test_login_success_returns_token_and_user(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    r = _login(env, "admin", "admin123")
    assert r.status_code == 200
    b = r.json()
    assert b["token_type"] == "bearer" and b["user"]["role"] == "admin"
    assert b["access_token"].count(".") == 2


def test_login_wrong_password_401(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    assert _login(env, "admin", "wrong").status_code == 401


def test_me_with_token(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    headers = _bearer(env, "tester", "tester123")
    r = env.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200 and r.json()["username"] == "tester"


def test_me_without_token_401(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    assert env.get("/api/v1/auth/me").status_code == 401


def test_me_with_garbage_token_401(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    assert (
        env.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code
        == 401
    )


def test_protected_endpoint_requires_token(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    assert env.get("/api/v1/projects").status_code == 401  # 無 token
    assert (
        env.get("/api/v1/projects", headers=_bearer(env, "tester", "tester123")).status_code
        == 200
    )


def test_platform_admin_only(env, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    # tester → 平台 403
    assert (
        env.get("/api/v1/platform/categories", headers=_bearer(env, "tester", "tester123")).status_code
        == 403
    )
    # admin → 平台 200
    assert (
        env.get("/api/v1/platform/categories", headers=_bearer(env, "admin", "admin123")).status_code
        == 200
    )
