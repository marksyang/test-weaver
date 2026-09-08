"""M5 API：測試計畫修改要求（FR-3a）。

對應計劃書 §7 M5 + 狀態機（§6.3）：open → accepted → done，或 open → rejected。
- accept：補建案例 + 測試計畫版本 +1（接 M2）。
- reject：需理由。
狀態機 violations → 409。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.revision import TestPlanRevisionRequest
from ...services.revision_service import (
    RevisionError,
    accept_revision,
    complete_revision,
    create_revision_request,
    list_revisions,
    reject_revision,
)

router = APIRouter(prefix="/revision-requests", tags=["Revisions/M5"])


class RevisionOut(BaseModel):
    id: int
    defect_id: Optional[int] = None
    test_plan_id: int
    reason: Optional[str] = None
    proposed_change: Optional[str] = None
    status: str
    requested_by: Optional[str] = None
    created_at: Optional[datetime] = None


class RejectBody(BaseModel):
    reason: str = Field(..., min_length=1)


class RevisionCreate(BaseModel):
    test_plan_id: int
    reason: Optional[str] = None
    proposed_change: Optional[str] = None
    requested_by: Optional[str] = None


def _out(rr: TestPlanRevisionRequest) -> dict:
    return {
        "id": rr.id,
        "defect_id": rr.defect_id,
        "test_plan_id": rr.test_plan_id,
        "reason": rr.reason,
        "proposed_change": rr.proposed_change,
        "status": rr.status,
        "requested_by": rr.requested_by,
        "created_at": rr.created_at,
    }


def _get_or_404(db: Session, rr_id: int) -> TestPlanRevisionRequest:
    rr = db.get(TestPlanRevisionRequest, rr_id)
    if rr is None:
        raise HTTPException(404, "revision request not found")
    return rr


@router.post("", response_model=RevisionOut)
def create_revision(body: RevisionCreate, db: Session = Depends(get_db)):
    """手動建立修改要求（供 M6 報表「一鍵轉 Revision Request」）。"""
    try:
        rr = create_revision_request(
            db,
            test_plan_id=body.test_plan_id,
            reason=body.reason,
            proposed_change=body.proposed_change,
            requested_by=body.requested_by,
        )
    except RevisionError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(rr)
    return _out(rr)


@router.get("", response_model=list[RevisionOut])
def list_revision_requests(
    status: Optional[str] = Query(None),
    test_plan_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    rows = list_revisions(db, status=status, test_plan_id=test_plan_id)
    return [_out(r) for r in rows]


@router.get("/{rr_id}", response_model=RevisionOut)
def get_revision_request(rr_id: int, db: Session = Depends(get_db)):
    return _out(_get_or_404(db, rr_id))


@router.post("/{rr_id}/accept", response_model=RevisionOut)
def accept(rr_id: int, db: Session = Depends(get_db)):
    try:
        rr = accept_revision(db, rr_id)
    except RevisionError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(rr)
    return _out(rr)


@router.post("/{rr_id}/reject", response_model=RevisionOut)
def reject(rr_id: int, body: RejectBody, db: Session = Depends(get_db)):
    try:
        rr = reject_revision(db, rr_id, body.reason)
    except RevisionError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(rr)
    return _out(rr)


@router.post("/{rr_id}/complete", response_model=RevisionOut)
def complete(rr_id: int, db: Session = Depends(get_db)):
    try:
        rr = complete_revision(db, rr_id)
    except RevisionError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(rr)
    return _out(rr)
