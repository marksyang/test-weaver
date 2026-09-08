"""M2 API：Test Plan → Function → Case 三層結構 + 版本（FR-2）。

對應計劃書 §7 M2。狀態機（§6.1）violations 回 409；案例狀態非法值回 422。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.project import Project
from ...models.test_item import TestItem
from ...models.test_plan import TestCase, TestFunction, TestPlan, TestPlanItem
from ...services.plan_service import (
    PlanError,
    assert_case_status,
    assert_plan_transition,
    build_tree,
    next_sort_order_cases,
    next_sort_order_functions,
)

router = APIRouter(tags=["TestPlans/M2"])


# ---------- Schemas ----------
class PlanCreate(BaseModel):
    name: str = Field(..., min_length=1)
    test_item_ids: list[int] = []


class PlanOut(BaseModel):
    id: int
    project_id: int
    name: str
    version: int
    status: str
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlanPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    status: Optional[str] = None


class FunctionCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    sort_order: Optional[int] = None


class FunctionOut(BaseModel):
    id: int
    test_plan_id: int
    name: str
    description: Optional[str] = None
    sort_order: int

    class Config:
        from_attributes = True


class FunctionPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    sort_order: Optional[int] = None


class CaseCreate(BaseModel):
    name: str = Field(..., min_length=1)
    precondition: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    priority: str = "medium"
    sort_order: Optional[int] = None


class CaseOut(BaseModel):
    id: int
    test_function_id: int
    name: str
    precondition: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    priority: str
    status: str
    sort_order: int

    class Config:
        from_attributes = True


class CasePatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    precondition: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    priority: Optional[str] = None
    sort_order: Optional[int] = None


class CaseStatus(BaseModel):
    status: str


class FunctionNode(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sort_order: int
    cases: list[CaseOut]


class PlanTree(BaseModel):
    id: int
    project_id: int
    name: str
    version: int
    status: str
    functions: list[FunctionNode]


# ---------- helpers ----------
def _get_plan_or_404(db: Session, plan_id: int) -> TestPlan:
    p = db.get(TestPlan, plan_id)
    if p is None:
        raise HTTPException(404, "test plan not found")
    return p


def _get_function_or_404(db: Session, function_id: int) -> TestFunction:
    f = db.get(TestFunction, function_id)
    if f is None:
        raise HTTPException(404, "test function not found")
    return f


def _get_case_or_404(db: Session, case_id: int) -> TestCase:
    c = db.get(TestCase, case_id)
    if c is None:
        raise HTTPException(404, "test case not found")
    return c


# ---------- Plan ----------
@router.post("/projects/{project_id}/test-plans", response_model=PlanOut)
def create_plan(project_id: int, body: PlanCreate, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")

    plan = TestPlan(project_id=project_id, name=body.name)
    db.add(plan)
    db.flush()

    if body.test_item_ids:
        for item_id in sorted(set(body.test_item_ids)):
            if db.get(TestItem, item_id) is None:
                raise HTTPException(400, f"test_item {item_id} not found")
            db.add(TestPlanItem(test_plan_id=plan.id, test_item_id=item_id))

    db.commit()
    db.refresh(plan)
    return plan


@router.get("/projects/{project_id}/test-plans", response_model=list[PlanOut])
def list_plans(project_id: int, db: Session = Depends(get_db)):
    if db.get(Project, project_id) is None:
        raise HTTPException(404, "project not found")
    return (
        db.query(TestPlan)
        .filter_by(project_id=project_id)
        .order_by(TestPlan.id.desc())
        .all()
    )


@router.get("/test-plans/{plan_id}", response_model=PlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    return _get_plan_or_404(db, plan_id)


@router.patch("/test-plans/{plan_id}", response_model=PlanOut)
def patch_plan(plan_id: int, body: PlanPatch, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    if body.name is not None:
        plan.name = body.name
    if body.status is not None:
        try:
            assert_plan_transition(plan, body.status)
        except PlanError as e:
            raise HTTPException(409, str(e))
        plan.status = body.status
    db.commit()
    db.refresh(plan)
    return plan


@router.post("/test-plans/{plan_id}/revisions", response_model=PlanOut)
def create_revision(plan_id: int, db: Session = Depends(get_db)):
    """bump 版本（+1）並回到 draft。M5 revision request 接受後亦會走此路徑。"""
    plan = _get_plan_or_404(db, plan_id)
    plan.version += 1
    plan.status = "draft"
    db.commit()
    db.refresh(plan)
    return plan


# ---------- Function ----------
@router.post("/test-plans/{plan_id}/functions", response_model=FunctionOut)
def create_function(plan_id: int, body: FunctionCreate, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    fn = TestFunction(
        test_plan_id=plan.id,
        name=body.name,
        description=body.description,
        sort_order=(
            body.sort_order
            if body.sort_order is not None
            else next_sort_order_functions(db, plan.id)
        ),
    )
    db.add(fn)
    db.commit()
    db.refresh(fn)
    return fn


@router.patch("/test-functions/{function_id}", response_model=FunctionOut)
def patch_function(function_id: int, body: FunctionPatch, db: Session = Depends(get_db)):
    fn = _get_function_or_404(db, function_id)
    if body.name is not None:
        fn.name = body.name
    if body.description is not None:
        fn.description = body.description
    if body.sort_order is not None:
        fn.sort_order = body.sort_order
    db.commit()
    db.refresh(fn)
    return fn


# ---------- Case ----------
@router.post("/functions/{function_id}/cases", response_model=CaseOut)
def create_case(function_id: int, body: CaseCreate, db: Session = Depends(get_db)):
    fn = _get_function_or_404(db, function_id)
    c = TestCase(
        test_function_id=fn.id,
        name=body.name,
        precondition=body.precondition,
        steps=body.steps,
        expected_result=body.expected_result,
        priority=body.priority,
        sort_order=(
            body.sort_order
            if body.sort_order is not None
            else next_sort_order_cases(db, fn.id)
        ),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.patch("/test-cases/{case_id}", response_model=CaseOut)
def patch_case(case_id: int, body: CasePatch, db: Session = Depends(get_db)):
    c = _get_case_or_404(db, case_id)
    if body.name is not None:
        c.name = body.name
    if body.precondition is not None:
        c.precondition = body.precondition
    if body.steps is not None:
        c.steps = body.steps
    if body.expected_result is not None:
        c.expected_result = body.expected_result
    if body.priority is not None:
        c.priority = body.priority
    if body.sort_order is not None:
        c.sort_order = body.sort_order
    db.commit()
    db.refresh(c)
    return c


@router.patch("/test-cases/{case_id}/status", response_model=CaseOut)
def patch_case_status(case_id: int, body: CaseStatus, db: Session = Depends(get_db)):
    c = _get_case_or_404(db, case_id)
    try:
        assert_case_status(body.status)
    except PlanError as e:
        raise HTTPException(422, str(e))
    c.status = body.status
    db.commit()
    db.refresh(c)
    return c


# ---------- Tree ----------
@router.get("/test-plans/{plan_id}/tree", response_model=PlanTree)
def get_tree(plan_id: int, db: Session = Depends(get_db)):
    plan = _get_plan_or_404(db, plan_id)
    return build_tree(db, plan)
