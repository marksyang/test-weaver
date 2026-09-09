"""FR-5 / M8 認證 API：``POST /auth/login``、``GET /auth/me``。

``/auth`` 為公開路由（不套全域 token 護）；``/me`` 啟用時仍要求有效 token。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...services.auth_service import (
    RefreshTokenError,
    authenticate,
    issue_tokens,
    revoke_refresh,
    rotate_refresh,
)
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
    refresh_token: str
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
    access, refresh = issue_tokens(db, user)
    db.commit()
    return LoginOut(
        access_token=access, refresh_token=refresh, token_type="bearer", user=_user_out(user)
    )


class RefreshIn(BaseModel):
    refresh_token: str


@router.post("/refresh")
def refresh(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    """用 refresh token 換新的 access + refresh（旋轉，作廢舊 refresh）。"""
    request.state.audit_action = "auth.refresh"
    try:
        access, refresh = rotate_refresh(db, body.refresh_token)
    except RefreshTokenError as exc:
        raise HTTPException(401, f"invalid refresh token: {exc}")
    db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@router.post("/logout")
def logout(body: RefreshIn, request: Request, db: Session = Depends(get_db)):
    """登出：撤銷 refresh token（使之後無法再換 access）。冪等。"""
    request.state.audit_action = "auth.logout"
    revoke_refresh(db, body.refresh_token)
    db.commit()
    return {"ok": True}


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
