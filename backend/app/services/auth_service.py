"""FR-5 / M8 服務層：認證 + 預設 admin 種子。"""
from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.orm import Session

from ..core.security import generate_salt, hash_password, verify_password
from ..core.db import session_scope
from ..models.user import User


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
