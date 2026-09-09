"""FR-5 延伸：JWT refresh token（access 短效 + refresh 可撤銷 / 旋轉）。

服務層（issue_tokens / rotate_refresh / revoke_refresh）+ API 層
（/login 回 access+refresh、/refresh 旋轉、/logout 撤銷、refresh 當 access 被拒）。
離線（SQLite）；JWT 用 stdlib，無外部依賴。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.core.security import decode_token
from app.main import create_app
from app.models.base import Base
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth_service import (
    RefreshTokenError,
    issue_tokens,
    make_user,
    revoke_refresh,
    rotate_refresh,
)

LOGIN = {"username": "admin", "password": "admin123"}


# ---------- 服務層 ----------
@pytest.fixture()
def db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'refresh.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestSession() as s:
        make_user(s, "admin", "admin123", role="admin")
        s.commit()
    yield TestSession
    engine.dispose()


def _admin(s):
    return s.query(User).filter_by(username="admin").first()


def test_issue_tokens_types_and_stored(db):
    s = db()
    try:
        access, refresh = issue_tokens(s, _admin(s))
        s.commit()
        assert decode_token(access)["type"] == "access"
        assert decode_token(refresh)["type"] == "refresh"
        rows = s.query(RefreshToken).all()
        assert len(rows) == 1 and rows[0].jti == decode_token(refresh)["jti"]
    finally:
        s.close()


def test_rotate_invalidates_old_and_issues_new(db):
    s = db()
    try:
        _, r1 = issue_tokens(s, _admin(s))
        s.commit()
        jti1 = decode_token(r1)["jti"]
        _a2, r2 = rotate_refresh(s, r1)
        s.commit()
        # 舊 token 被撤銷、新 token 不同且有效
        assert s.query(RefreshToken).filter_by(jti=jti1).first().revoked_at is not None
        assert r2 != r1 and decode_token(r2)["type"] == "refresh"
        # 新 token 可再旋轉一次
        a3, _r3 = rotate_refresh(s, r2)
        s.commit()
        assert decode_token(a3)["type"] == "access"
    finally:
        s.close()


def test_rotate_revoked_token_fails(db):
    s = db()
    try:
        _, r1 = issue_tokens(s, _admin(s))
        s.commit()
        revoke_refresh(s, r1)
        s.commit()
        with pytest.raises(RefreshTokenError):
            rotate_refresh(s, r1)
    finally:
        s.close()


def test_rotate_rejects_access_token(db):
    s = db()
    try:
        access, _ = issue_tokens(s, _admin(s))
        s.commit()
        with pytest.raises(RefreshTokenError):
            rotate_refresh(s, access)  # access 不是 refresh
    finally:
        s.close()


def test_revoke_is_idempotent(db):
    s = db()
    try:
        _, r1 = issue_tokens(s, _admin(s))
        s.commit()
        assert revoke_refresh(s, r1) is True
        s.commit()
        assert revoke_refresh(s, r1) is False  # 已撤銷 → False（冪等）
    finally:
        s.close()


# ---------- API 層 ----------
@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'refresh_api.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestSession() as db:
        make_user(db, "admin", "admin123", role="admin")
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


def _login(client: TestClient):
    r = client.post("/api/v1/auth/login", json=LOGIN)
    assert r.status_code == 200
    return r.json()


def test_login_returns_access_and_refresh(env):
    b = _login(env)
    assert b["access_token"] and b["refresh_token"]
    assert decode_token(b["access_token"])["type"] == "access"
    assert decode_token(b["refresh_token"])["type"] == "refresh"


def test_refresh_rotates_and_old_is_single_use(env):
    first = _login(env)
    assert env.get("/api/v1/auth/me",
                   headers={"Authorization": f"Bearer {first['access_token']}"}).status_code == 200
    rf = env.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rf.status_code == 200
    nb = rf.json()
    assert nb["refresh_token"] != first["refresh_token"] and nb["access_token"]
    # 舊 refresh 已被旋轉作廢 → 再使用 401
    assert (
        env.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )
    # 新 access 可用
    assert (
        env.get("/api/v1/auth/me",
                headers={"Authorization": f"Bearer {nb['access_token']}"}).status_code
        == 200
    )


def test_logout_revokes_refresh(env):
    first = _login(env)
    assert (
        env.post("/api/v1/auth/logout", json={"refresh_token": first["refresh_token"]}).status_code
        == 200
    )
    # 登出後 refresh 不能再換 access
    assert (
        env.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )


def test_refresh_token_rejected_as_access(env):
    first = _login(env)
    # 把 refresh token 當 access（Authorization header）用 → 401
    r = env.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {first['refresh_token']}"})
    assert r.status_code == 401


def test_refresh_with_garbage_401(env):
    assert env.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"}).status_code == 401
