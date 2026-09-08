"""M3 API：自測錄入與列表（FR-2a，強制同時綁定 Function + Case）。

對應計劃書 §7 M3。缺 test_function_id / test_case_id → Pydantic 422（未綁定即拒收）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.project import Project
from ...models.self_test import SelfTest
from ...models.test_plan import TestCase, TestFunction
from ...services.self_test_service import (
    SelfTestError,
    list_self_tests,
    record_self_test,
)

router = APIRouter(tags=["SelfTests/M3"])


class SelfTestCreate(BaseModel):
    project_id: int
    test_function_id: int  # 必填（FR-2a）
    test_case_id: int      # 必填（FR-2a）
    result: str            # pass / fail
    tester: Optional[str] = None
    notes: Optional[str] = None


class SelfTestOut(BaseModel):
    id: int
    project_id: int
    tester: Optional[str] = None
    test_function_id: int
    function_name: Optional[str] = None
    test_case_id: int
    case_name: Optional[str] = None
    result: str
    notes: Optional[str] = None
    executed_at: Optional[datetime] = None


def _out(db: Session, st: SelfTest) -> dict:
    fn = db.get(TestFunction, st.test_function_id)
    c = db.get(TestCase, st.test_case_id)
    return {
        "id": st.id,
        "project_id": st.project_id,
        "tester": st.tester,
        "test_function_id": st.test_function_id,
        "function_name": fn.name if fn else None,
        "test_case_id": st.test_case_id,
        "case_name": c.name if c else None,
        "result": st.result,
        "notes": st.notes,
        "executed_at": st.executed_at,
    }


@router.post("/self-tests", response_model=SelfTestOut)
def create_self_test(body: SelfTestCreate, db: Session = Depends(get_db)):
    try:
        st = record_self_test(
            db,
            body.project_id,
            body.test_function_id,
            body.test_case_id,
            body.result,
            body.tester,
            body.notes,
        )
    except SelfTestError as e:
        raise HTTPException(e.status_code, str(e))
    db.commit()
    db.refresh(st)
    return _out(db, st)


@router.get("/projects/{project_id}/self-tests", response_model=list[SelfTestOut])
def list_self_tests_endpoint(
    project_id: int,
    result: Optional[str] = Query(None),
    test_function_id: Optional[int] = Query(None),
    test_case_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    rows = list_self_tests(db, project_id, result, test_function_id, test_case_id)
    return [_out(db, r) for r in rows]
