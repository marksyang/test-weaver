"""FR-5 稽核日誌 API 測試（middleware 記錄 + /audit/logs 角色門檻）。

middleware 以獨立 session_scope 寫入 → monkeypatch ``app.core.db._get_engine`` 指向測試 DB。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.main import create_app
from app.models.audit import AuditLog
from app.models.base import Base
from app.services.auth_service import make_user


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'audit.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    with TestSession() as db:
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
    # middleware 的 session_scope → 測試 DB
    monkeypatch.setattr("app.core.db._get_engine", lambda: engine)

    yield {"client": TestClient(app), "TS": TestSession}
    app.dependency_overrides.clear()
    engine.dispose()


def _rows(env):
    with env["TS"]() as db:
        return db.query(AuditLog).order_by(AuditLog.id).all()


def _bearer(client: TestClient, username: str, password: str) -> dict:
    token = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_mutation_is_audited_when_enabled(env, monkeypatch):
    monkeypatch.setenv("AUDIT_ENABLED", "true")  # AUTH 保持關閉（免 token）
    env["client"].post("/api/v1/projects", json={"name": "P"})
    rows = _rows(env)
    assert any(r.path == "/api/v1/projects" and r.method == "POST" for r in rows)


def test_mutation_not_audited_when_disabled(env):
    env["client"].post("/api/v1/projects", json={"name": "P"})
    assert _rows(env) == []


def test_login_success_and_failure_audited(env, monkeypatch):
    monkeypatch.setenv("AUDIT_ENABLED", "true")
    c = env["client"]
    assert c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200
    assert c.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    logins = [r for r in _rows(env) if r.action == "auth.login"]
    assert len(logins) == 2
    assert {r.status_code for r in logins} == {200, 401}
    assert all(r.username == "admin" for r in logins)


def test_audit_logs_endpoint_requires_admin(env, monkeypatch):
    monkeypatch.setenv("AUDIT_ENABLED", "true")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    c = env["client"]
    # 無 token → 401
    assert c.get("/api/v1/audit/logs").status_code == 401
    # tester → 403
    assert c.get("/api/v1/audit/logs", headers=_bearer(c, "tester", "tester123")).status_code == 403
    # admin → 200，且包含 login 稽核項
    r = c.get("/api/v1/audit/logs", headers=_bearer(c, "admin", "admin123"))
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and any(x.get("action") == "auth.login" for x in body)
