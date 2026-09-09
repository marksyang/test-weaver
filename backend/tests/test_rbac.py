"""端點級 RBAC（roadmap P7）：角色 → 模組權限（mirror 前端 roles.ts）。

涵蓋：政策矩陣 + API 層強制
（report 排除 tester、plan 核心三角色皆可、platform / settings 只 admin）。
離線 SQLite；AUTH_ENABLED=true。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.rbac import ROLE_MODULES, require_module
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base
from app.services.auth_service import make_user


# ---------- 政策矩陣（mirror frontend/src/auth/roles.ts 的 ROLE_MENU）----------
def test_policy_core_modules_all_roles():
    for m in ("rag", "plan", "self_test", "defect"):
        assert ROLE_MODULES[m] == ("admin", "qa_lead", "tester")


def test_policy_report_excludes_tester():
    assert ROLE_MODULES["report"] == ("admin", "qa_lead")
    assert "tester" not in ROLE_MODULES["report"]


def test_policy_admin_only_modules():
    assert ROLE_MODULES["platform"] == ("admin",)
    assert ROLE_MODULES["settings"] == ("admin",)


def test_require_module_permissive_when_auth_disabled():
    # AUTH off → get_current_user 回 None → require_module 放過（回 None，不 403）
    dep = require_module("report")
    assert dep(None) is None


# ---------- API 層強制 ----------
@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rbac.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestSession() as db:
        make_user(db, "admin", "pw", role="admin")
        make_user(db, "lead", "pw", role="qa_lead")
        make_user(db, "tester", "pw", role="tester")
        db.commit()

    app = create_app()

    def _override_db():
        d = TestSession()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = _override_db
    monkeypatch.setenv("AUTH_ENABLED", "true")
    yield TestClient(app)
    app.dependency_overrides.clear()
    engine.dispose()


def _headers(client: TestClient, username: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": "pw"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_report_blocked_for_tester(env):
    # tester 無 /report → RBAC 403（在 handler 之前）
    assert env.get("/api/v1/reports/999", headers=_headers(env, "tester")).status_code == 403


def test_report_allowed_for_qa_lead_and_admin(env):
    # qa_lead / admin：RBAC 放行 → 進入 handler → plan 999 不存在 → 404（非 403）
    for u in ("lead", "admin"):
        assert env.get("/api/v1/reports/999", headers=_headers(env, u)).status_code == 404


def test_plan_open_to_all_roles(env):
    # plan 核心模組：三種角色皆放行（→ handler → 404，非 403）
    for u in ("admin", "lead", "tester"):
        assert env.get("/api/v1/test-plans/999", headers=_headers(env, u)).status_code == 404


def test_platform_admin_only(env):
    assert env.get("/api/v1/platform/categories", headers=_headers(env, "tester")).status_code == 403
    assert env.get("/api/v1/platform/categories", headers=_headers(env, "lead")).status_code == 403
    assert env.get("/api/v1/platform/categories", headers=_headers(env, "admin")).status_code == 200


def test_settings_users_admin_only(env):
    # /settings（帳號管理）：tester / qa_lead → 403；admin → 200（list）
    assert env.get("/api/v1/users", headers=_headers(env, "tester")).status_code == 403
    assert env.get("/api/v1/users", headers=_headers(env, "lead")).status_code == 403
    assert env.get("/api/v1/users", headers=_headers(env, "admin")).status_code == 200
