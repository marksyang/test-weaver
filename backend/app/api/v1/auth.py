"""FR-5 / M8 認證 API：``POST /auth/login``、``GET /auth/me``。

``/auth`` 為公開路由（不套全域 token 護）；``/me`` 啟用時仍要求有效 token。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...core.security import create_token
from ...services.auth_service import authenticate
from ..deps import get_current_user
from ...models.user import User

router = APIRouter(prefix="/auth", tags=["Auth/M8"])


class LoginIn(BaseModel):
    username: str
    password: str


class AuthUserOut(BaseModel):
    id: int
    username: str
    role: str


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserOut


def _user_out(u: User) -> AuthUserOut:
    return AuthUserOut(id=u.id, username=u.username, role=u.role)


@router.post("/login", response_model=LoginOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    request.state.audit_action = "auth.login"
    request.state.audit_username = body.username
    user = authenticate(db, body.username, body.password)
    if user is None:
        raise HTTPException(401, "invalid credentials")
    token = create_token({"sub": str(user.id), "username": user.username, "role": user.role})
    return LoginOut(access_token=token, token_type="bearer", user=_user_out(user))


@router.get("/me", response_model=AuthUserOut)
def me(current: Optional[User] = Depends(get_current_user)):
    # AUTH_ENABLED=false → current is None → 匿名 admin（前後端免登入即可用）
    if current is None:
        return AuthUserOut(id=0, username="anonymous", role="admin")
    return _user_out(current)


@router.get("/me/teams")
def my_teams(
    current: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """回傳當前使用者所在團隊 [{id, name, role}]（多團隊 v1.1 T1）。AUTH 未啟用 → []。"""
    if current is None:
        return []
    from ...services.team_service import user_team_roles

    return user_team_roles(db, current)
