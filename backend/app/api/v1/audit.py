"""FR-5 稽核日誌 API：``GET /audit-logs``（admin）。

角色門檻（admin）與全域 token 護於 ``main.py`` include 時套用。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.audit import AuditLog
from ...services.audit_service import list_audit

router = APIRouter(prefix="/audit", tags=["Audit"])


class AuditOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    method: str
    path: str
    status_code: int
    ip: Optional[str] = None
    detail: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/logs", response_model=list[AuditOut])
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list_audit(db, limit=limit)
