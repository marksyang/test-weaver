"""M7 API：共通類別平台（test_item_category CRUD）。

對應計劃書 §7 M7。
"""
from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...core.db import get_db
from ...models.platform import TestItemCategory

router = APIRouter(prefix="/platform", tags=["Platform/M7"])


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1)
    code: Optional[str] = None
    description: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(TestItemCategory).order_by(TestItemCategory.id).all()


@router.post("/categories", response_model=CategoryOut)
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    code = (body.code or "").strip() or (
        "cat-" + hashlib.sha1(body.name.encode("utf-8")).hexdigest()[:12]
    )
    existing = db.query(TestItemCategory).filter_by(code=code).first()
    if existing is not None:
        return existing
    c = TestItemCategory(name=body.name, code=code, description=body.description)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/categories/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, db: Session = Depends(get_db)):
    c = db.get(TestItemCategory, category_id)
    if c is None:
        raise HTTPException(404, "category not found")
    return c
