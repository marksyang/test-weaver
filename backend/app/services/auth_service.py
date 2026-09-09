"""FR-5 / M8 服務層：認證 + 預設 admin 種子。"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from ..core.security import (
    JWTError,
    create_token,
    decode_token,
    generate_salt,
    hash_password,
    verify_password,
)
from ..core.db import session_scope
from ..models.user import User
from ..models.refresh_token import RefreshToken


class RefreshTokenError(Exception):
    """refresh token 無效 / 已撤銷 / 過期。"""


ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))


def authenticate(db: Session, username: str, password: str) -> Optional[User]:
    """回傳匹配的啟用使用者，否則 None（含帳號不存在 / 密碼錯）。"""
    user = db.query(User).filter_by(username=username).first()
    if user is None:
        return None
    if not verify_password(password, user.password_salt, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def make_user(
    db: Session, username: str, password: str, role: str = "tester", is_active: bool = True
) -> User:
    salt = generate_salt()
    user = User(
        username=username,
        password_salt=salt,
        hashed_password=hash_password(password, salt),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    return user


def ensure_default_admin() -> None:
    """首次啟動確保存在一個 admin（供開發登入）。可用 env 覆蓋帳號/密碼。"""
    username = os.getenv("AUTH_ADMIN_USERNAME", "admin")
    password = os.getenv("AUTH_ADMIN_PASSWORD", "admin123")
    with session_scope() as db:
        existing = db.query(User).filter_by(username=username).first()
        if existing is None:
            make_user(db, username, password, role="admin")


# ---------- refresh token（access 短效無狀態；refresh 長效可撤銷/旋轉）----------
def _access_payload(user: User) -> dict:
    return {"sub": str(user.id), "username": user.username, "role": user.role}


def issue_tokens(db: Session, user: User) -> Tuple[str, str]:
    """發一組 access + refresh；refresh 的 jti 記入 DB（供撤銷/旋轉）。

    呼叫端負責 commit（API 端點 db.commit()；測試自行 commit）。
    """
    access = create_token(
        _access_payload(user), expires_minutes=ACCESS_TOKEN_MINUTES, token_type="access"
    )
    refresh = create_token(
        {"sub": str(user.id)}, expires_minutes=REFRESH_TOKEN_DAYS * 1440, token_type="refresh"
    )
    jti = decode_token(refresh)["jti"]
    db.add(
        RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_DAYS),
        )
    )
    return access, refresh


def _find_valid_refresh(db: Session, refresh_token: str) -> RefreshToken:
    try:
        payload = decode_token(refresh_token)
    except JWTError as exc:
        raise RefreshTokenError(str(exc)) from exc
    if payload.get("type") != "refresh":
        raise RefreshTokenError("not a refresh token")
    jti = payload.get("jti")
    row = db.query(RefreshToken).filter_by(jti=jti).first() if jti else None
    if row is None or row.revoked_at is not None:
        raise RefreshTokenError("refresh token unknown or revoked")
    if row.expires_at < datetime.utcnow():
        raise RefreshTokenError("refresh token expired")
    return row


def rotate_refresh(db: Session, refresh_token: str) -> Tuple[str, str]:
    """驗證並旋轉：作廢舊 refresh，發新 access + refresh。呼叫端負責 commit。"""
    row = _find_valid_refresh(db, refresh_token)
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise RefreshTokenError("user not found or inactive")
    row.revoked_at = datetime.utcnow()  # 旋轉：作廢舊 token
    return issue_tokens(db, user)


def revoke_refresh(db: Session, refresh_token: str) -> bool:
    """登出撤銷（冪等）。回 True 表示確實撤銷了一張有效 token。"""
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        return False
    if payload.get("type") != "refresh":
        return False
    jti = payload.get("jti")
    row = db.query(RefreshToken).filter_by(jti=jti).first() if jti else None
    if row is None or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.utcnow()
    return True
