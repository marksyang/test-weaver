"""FR-5 / M8 認證相依。

``get_current_user``：全域護 token。``AUTH_ENABLED=false``（預設）→ 回 None（no-op，
不破壞既有測試與離線開發）；啟用後無/錯 token → 401。
``require_roles(*roles)``：角色門檻；``AUTH_ENABLED=false`` 時放過（current is None）。
"""
from __future__ import annotations

import os
from typing import Callable, Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.security import JWTError, decode_token
from ..models.user import User


def auth_enabled() -> bool:
    return os.getenv("AUTH_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """回傳當前使用者；``AUTH_ENABLED=false`` 時回 None（放過）。"""
    if not auth_enabled():
        request.state.user = None
        return None
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise _unauthorized("missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise _unauthorized(f"invalid token: {exc}")
    sub = payload.get("sub")
    if sub is None:
        raise _unauthorized("invalid token payload")
    try:
        user = db.get(User, int(sub))
    except (TypeError, ValueError):
        raise _unauthorized("invalid token payload")
    if user is None or not user.is_active:
        raise _unauthorized("user not found or inactive")
    request.state.user = user
    return user


def require_roles(*roles: str) -> Callable[..., Optional[User]]:
    """建立一個只允許指定角色的相依。``AUTH_ENABLED=false`` 時不強制。"""

    def _dep(current: Optional[User] = Depends(get_current_user)) -> Optional[User]:
        if current is None:
            return None  # auth disabled → permissive
        if current.role not in roles:
            raise HTTPException(403, f"role '{current.role}' not allowed (need {', '.join(roles)})")
        return current

    return _dep
