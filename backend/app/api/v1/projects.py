"""M1 API：專案 / 規格書上傳與解析 / AI 生成測試項目 / 測試項目列表。

對應計劃書 §7 M1。Celery enqueue 以模組層 helper 封裝（_enqueue_generate）以便測試 monkeypatch。
"""
from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...api.deps import get_current_user
from ...core.db import get_db
from ...models.project import Project, SpecFile
from ...models.platform import TestItemCategory
from ...models.test_item import TestItem, TestItemPlatformSync
from ...models.user import User
from ...services.spec_service import extract_text
from ...services.team_service import (
    accessible_team_ids,
    get_accessible_project,
    visible_project_query,
)

router = APIRouter(prefix="/projects", tags=["Projects/M1"])


# ---------- Schemas ----------
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    team_id: Optional[int] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    team_id: Optional[int] = None

    class Config:
        from_attributes = True


class SpecFileOut(BaseModel):
    id: int
    project_id: int
    file_name: str
    format: str
    status: str
    char_count: Optional[int] = None


# ---------- helpers ----------
def _upload_dir() -> str:
    d = os.getenv("UPLOAD_DIR", "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _spec_out(sf: SpecFile) -> SpecFileOut:
    return SpecFileOut(
        id=sf.id,
        project_id=sf.project_id,
        file_name=sf.file_name,
        format=sf.format,
        status=sf.status,
        char_count=len(sf.raw_text) if sf.raw_text else None,
    )


def _enqueue_generate(spec_file_id: int) -> str:
    from ...workers.m1_tasks import generate_items_task

    return generate_items_task.delay(spec_file_id).id


# ---------- 專案 ----------
@router.get("", response_model=list[ProjectOut])
def list_projects(
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return visible_project_query(db, current_user).order_by(Project.id.desc()).all()


@router.post("", response_model=ProjectOut)
def create_project(
    body: ProjectCreate,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team_id = body.team_id
    if team_id is not None and current_user is not None:
        if team_id not in accessible_team_ids(db, current_user):
            raise HTTPException(403, "cannot create a project in a team you are not a member of")
    p = Project(name=body.name, description=body.description, team_id=team_id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    current_user: Optional[User] = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    p = get_accessible_project(db, current_user, project_id)
    if p is None:
        raise HTTPException(404, "project not found")
    return p


# ---------- 規格書 ----------
@router.get("/{project_id}/spec-files", response_model=list[SpecFileOut])
def list_specs(project_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(SpecFile).filter_by(project_id=project_id).order_by(SpecFile.id.desc()).all()
    )
    return [_spec_out(r) for r in rows]


@router.post("/{project_id}/spec-files", response_model=SpecFileOut)
async def upload_spec(project_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if p is None:
        raise HTTPException(404, "project not found")

    data = await file.read()
    filename = file.filename or "spec.txt"
    ext = os.path.splitext(filename)[1].lstrip(".").lower() or "txt"

    # 存檔（二進位）
    safe = f"{uuid.uuid4().hex}_{os.path.basename(filename)}"
    path = os.path.join(_upload_dir(), safe)
    with open(path, "wb") as f:
        f.write(data)

    # 抽取文字
    try:
        text = extract_text(data, ext)
        status = "done"
    except Exception:
        text, status = None, "error"

    sf = SpecFile(
        project_id=project_id,
        file_name=filename,
        file_path=path,
        format=ext,
        status=status,
        raw_text=text,
    )
    db.add(sf)
    db.commit()
    db.refresh(sf)
    return _spec_out(sf)


# ---------- AI 生成測試項目 ----------
@router.post("/{project_id}/spec-files/{spec_file_id}/generate-items")
def generate_items(
    project_id: int, spec_file_id: int, db: Session = Depends(get_db)
):
    sf = db.get(SpecFile, spec_file_id)
    if sf is None or sf.project_id != project_id:
        raise HTTPException(404, "spec file not found")
    if sf.status != "done" or not sf.raw_text:
        raise HTTPException(409, "spec file not ready")
    return {"task_id": _enqueue_generate(spec_file_id), "status": "queued"}


# ---------- 測試項目 ----------
@router.get("/{project_id}/test-items")
def list_test_items(project_id: int, db: Session = Depends(get_db)):
    rows = db.query(TestItem).filter_by(project_id=project_id).order_by(TestItem.id).all()
    out = []
    for it in rows:
        cat = db.get(TestItemCategory, it.category_id)
        sync = (
            db.query(TestItemPlatformSync).filter_by(test_item_id=it.id).first()
        )
        out.append(
            {
                "id": it.id,
                "name": it.name,
                "description": it.description,
                "is_newly_created": it.is_newly_created,
                "source_spec_file_id": it.source_spec_file_id,
                "category": (
                    {"id": cat.id, "name": cat.name, "code": cat.code} if cat else None
                ),
                "matched_by": sync.matched_by if sync else None,
                "similarity": sync.similarity if sync else None,
            }
        )
    return out
