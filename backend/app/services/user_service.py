"""FR-5 帳號管理服務（admin）：建立 / 更新使用者。

安全保護：角色白名單、唯一帳號、密碼長度、**最後一個啟用 admin 不可被移除**。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..core.security import generate_salt, hash_password
from ..models.user import User

VALID_ROLES = ("admin", "qa_lead", "tester")
_MIN_PASSWORD = 4


class UserError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id).all()


def _active_admin_count(db: Session, exclude_id: Optional[int] = None) -> int:
    q = db.query(User).filter(User.role == "admin", User.is_active.is_(True))
    if exclude_id is not None:
        q = q.filter(User.id != exclude_id)
    return q.count()


def create_user(db: Session, *, username: str, password: str, role: str) -> User:
    username = (username or "").strip()
    if not username:
        raise UserError("username required", 400)
    if role not in VALID_ROLES:
        raise UserError(f"invalid role (must be one of {', '.join(VALID_ROLES)})", 400)
    if len(password or "") < _MIN_PASSWORD:
        raise UserError(f"password too short (min {_MIN_PASSWORD})", 400)
    if db.query(User).filter_by(username=username).first() is not None:
        raise UserError("username already exists", 409)

    salt = generate_salt()
    user = User(
        username=username,
        password_salt=salt,
        hashed_password=hash_password(password, salt),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def update_user(
    db: Session,
    user_id: int,
    *,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    password: Optional[str] = None,
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise UserError("user not found", 404)

    if role is not None and role not in VALID_ROLES:
        raise UserError(f"invalid role (must be one of {', '.join(VALID_ROLES)})", 400)

    new_role = role if role is not None else user.role
    new_active = is_active if is_active is not None else user.is_active

    # 保護：不可移除「最後一個啟用 admin」
    if user.role == "admin" and user.is_active and (new_role != "admin" or not new_active):
        if _active_admin_count(db, exclude_id=user.id) == 0:
            raise UserError("cannot remove the last active admin", 400)

    user.role = new_role
    user.is_active = new_active

    if password is not None:
        if len(password) < _MIN_PASSWORD:
            raise UserError(f"password too short (min {_MIN_PASSWORD})", 400)
        user.password_salt = generate_salt()
        user.hashed_password = hash_password(password, user.password_salt)

    db.flush()
    return user
