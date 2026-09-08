"""M4 API：案例執行（Fail → 自動開 Defect）+ 缺陷列表 / 手動補建 / 狀態流轉。

對應計劃書 §7 M4 + FR-3。Defect 狀態機（§6.2）violations → 409；非法枚舉值 → 422。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.defect import Defect, TestExecution
from ...models.test_plan import TestCase
from ...services.defect_service import (
    DefectError,
    assert_defect_transition,
    create_manual_defect,
    execute_case,
    list_defects,
)
from ...services.revision_service import RevisionError, ensure_revision_for_defect

router = APIRouter(tags=["Defects/M4"])


# ---------- Schemas ----------
class ExecuteCaseCreate(BaseModel):
    test_case_id: int
    result: str  # pass / fail / blocked
    executed_by: Optional[str] = None
    actual_result: Optional[str] = None


class ManualDefectCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    severity: str = "medium"
    priority: str = "medium"
    test_case_id: Optional[int] = None  # 可為 NULL（FR-3a）
    execution_id: Optional[int] = None
    test_plan_id: Optional[int] = None  # 無案例時用於自動建 Revision Request（FR-3a）


class DefectPatch(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None


class ExecutionOut(BaseModel):
    id: int
    test_case_id: int
    case_name: Optional[str] = None
    test_plan_id: int
    executed_by: Optional[str] = None
    result: str
    actual_result: Optional[str] = None
    executed_at: Optional[datetime] = None


class DefectOut(BaseModel):
    id: int
    execution_id: Optional[int] = None
    test_case_id: Optional[int] = None
    case_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    severity: str
    priority: str
    status: str
    assigned_to: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ExecuteOut(BaseModel):
    execution: ExecutionOut
    defect: Optional[DefectOut] = None


# ---------- helpers ----------
def _execution_out(db: Session, ex: TestExecution) -> dict:
    c = db.get(TestCase, ex.test_case_id)
    return {
        "id": ex.id,
        "test_case_id": ex.test_case_id,
        "case_name": c.name if c else None,
        "test_plan_id": ex.test_plan_id,
        "executed_by": ex.executed_by,
        "result": ex.result,
        "actual_result": ex.actual_result,
        "executed_at": ex.executed_at,
    }


def _defect_out(db: Session, d: Defect) -> dict:
    c = db.get(TestCase, d.test_case_id) if d.test_case_id else None
    return {
        "id": d.id,
        "execution_id": d.execution_id,
        "test_case_id": d.test_case_id,
        "case_name": c.name if c else None,
        "title": d.title,
        "description": d.description,
        "severity": d.severity,
        "priority": d.priority,
        "status": d.status,
        "assigned_to": d.assigned_to,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


# ---------- 案例執行 ----------
@router.post("/test-executions", response_model=ExecuteOut)
def run_execution(body: ExecuteCaseCreate, db: Session = Depends(get_db)):
    try:
        execution, defect = execute_case(
            db, body.test_case_id, body.result, body.executed_by, body.actual_result
        )
    except DefectError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(execution)
    return {
        "execution": _execution_out(db, execution),
        "defect": _defect_out(db, defect) if defect else None,
    }


@router.get("/test-cases/{case_id}/executions", response_model=list[ExecutionOut])
def list_case_executions(case_id: int, db: Session = Depends(get_db)):
    if db.get(TestCase, case_id) is None:
        raise HTTPException(404, "test case not found")
    rows = (
        db.query(TestExecution)
        .filter_by(test_case_id=case_id)
        .order_by(TestExecution.id.desc())
        .all()
    )
    return [_execution_out(db, r) for r in rows]


# ---------- 缺陷 ----------
@router.get("/defects", response_model=list[DefectOut])
def list_defects_endpoint(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    rows = list_defects(db, status=status, severity=severity)
    return [_defect_out(db, r) for r in rows]


@router.get("/defects/{defect_id}", response_model=DefectOut)
def get_defect(defect_id: int, db: Session = Depends(get_db)):
    d = db.get(Defect, defect_id)
    if d is None:
        raise HTTPException(404, "defect not found")
    return _defect_out(db, d)


@router.post("/defects", response_model=DefectOut)
def create_defect(body: ManualDefectCreate, db: Session = Depends(get_db)):
    try:
        d = create_manual_defect(
            db,
            body.title,
            body.description,
            body.severity,
            body.priority,
            body.test_case_id,
            body.execution_id,
        )
        # FR-3a：缺陷無對應案例 → 自動建立 Revision Request
        ensure_revision_for_defect(db, d, test_plan_id=body.test_plan_id)
    except DefectError as e:
        raise HTTPException(e.status_code, str(e))
    except RevisionError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(d)
    return _defect_out(db, d)


@router.patch("/defects/{defect_id}", response_model=DefectOut)
def patch_defect(defect_id: int, body: DefectPatch, db: Session = Depends(get_db)):
    d = db.get(Defect, defect_id)
    if d is None:
        raise HTTPException(404, "defect not found")
    if body.status is not None:
        try:
            assert_defect_transition(d, body.status)
        except DefectError as e:
            raise HTTPException(e.status_code, str(e))
        d.status = body.status
    if body.assigned_to is not None:
        d.assigned_to = body.assigned_to
    db.commit()
    db.refresh(d)
    return _defect_out(db, d)
