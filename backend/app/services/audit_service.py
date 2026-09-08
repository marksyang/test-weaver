"""FR-5 稽核日誌：寫入 + 查詢。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..models.audit import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    method: str,
    path: str,
    status_code: int,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip: Optional[str] = None,
    detail: Optional[str] = None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        username=username,
        action=action[:128],
        method=method[:8],
        path=path[:256],
        status_code=status_code,
        ip=(ip or None),
        detail=detail,
    )
    db.add(row)
    db.flush()
    return row


def list_audit(db: Session, limit: int = 50) -> list[AuditLog]:
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
