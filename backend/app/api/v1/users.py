"""FR-5 帳號管理 API（admin）：list / create / update。

角色門檻（admin）與全域 token 護於 ``main.py`` include 時套用。
建立/更新皆為 POST/PATCH → AUDIT_ENABLED 時自動入稽核日誌。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...services.user_service import UserError, create_user, list_users, update_user

router = APIRouter(prefix="/users", tags=["Users"])


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    role: str


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


@router.get("", response_model=list[UserOut])
def get_users(db: Session = Depends(get_db)):
    return list_users(db)


@router.post("", response_model=UserOut, status_code=201)
def post_user(body: UserCreate, db: Session = Depends(get_db)):
    try:
        u = create_user(db, username=body.username, password=body.password, role=body.role)
    except UserError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(u)
    return u


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db)):
    try:
        u = update_user(
            db,
            user_id,
            role=body.role,
            is_active=body.is_active,
            password=body.password,
        )
    except UserError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(u)
    return u
