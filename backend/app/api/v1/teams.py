"""多團隊（multi-team）API（v1.1 T2）：team CRUD + members 管理 + 團隊級 RBAC。

授權規則：
- 管理者 = 該 team 的 owner 或 platform admin（user.role='admin'）。
- 最後一個 owner 保護：移除/降級唯一 owner → 400。
- 非成員存取他隊 → 404（避免洩露存在）；無權管理 → 403。
- 需「真實」使用者（get_required_user）：AUTH 未啟用 → 401。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...api.deps import get_current_user, get_required_user
from ...core.db import get_db
from ...models.team import Team
from ...models.user import User
from ...services.team_service import (
    TeamError,
    add_member,
    can_manage_team,
    create_team,
    get_accessible_team,
    get_membership,
    list_members,
    remove_member,
    set_member_role,
)

router = APIRouter(prefix="/teams", tags=["Teams"])


class TeamOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    my_role: Optional[str] = None  # 當前使用者在此 team 的團隊級角色（非成員→null）


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class MemberOut(BaseModel):
    user_id: int
    username: str
    role: str


class MemberIn(BaseModel):
    user_id: int
    role: str


class RoleIn(BaseModel):
    role: str


def _team_out(db: Session, team: Team, user: Optional[User]) -> TeamOut:
    m = get_membership(db, team.id, user.id) if user else None
    return TeamOut(
        id=team.id,
        name=team.name,
        description=team.description,
        my_role=(m.role if m else None),
    )


def _http(e: TeamError) -> HTTPException:
    return HTTPException(e.status_code, e.detail)


# ---------- team ----------
@router.get("", response_model=list[TeamOut])
def list_teams(
    current: Optional[User] = Depends(get_current_user), db: Session = Depends(get_db)
):
    if current is None:
        return []
    teams = db.query(Team).order_by(Team.id).all()
    if current.role != "admin":
        teams = [t for t in teams if get_membership(db, t.id, current.id) is not None]
    return [_team_out(db, t, current) for t in teams]


@router.post("", response_model=TeamOut, status_code=201)
def create_team_ep(
    body: TeamCreate,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    try:
        team = create_team(db, body.name, body.description, current)
    except TeamError as e:
        raise _http(e)
    return _team_out(db, team, current)


@router.get("/{team_id}", response_model=TeamOut)
def get_team_ep(
    team_id: int, current: User = Depends(get_required_user), db: Session = Depends(get_db)
):
    team = get_accessible_team(db, current, team_id)
    if team is None:
        raise HTTPException(404, "team not found")
    return _team_out(db, team, current)


@router.patch("/{team_id}", response_model=TeamOut)
def update_team_ep(
    team_id: int,
    body: TeamUpdate,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    team = get_accessible_team(db, current, team_id)
    if team is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can update the team")
    if body.name is not None and body.name.strip():
        team.name = body.name.strip()
    if body.description is not None:
        team.description = body.description
    db.commit()
    db.refresh(team)
    return _team_out(db, team, current)


# ---------- members ----------
@router.get("/{team_id}/members", response_model=list[MemberOut])
def members_list(
    team_id: int, current: User = Depends(get_required_user), db: Session = Depends(get_db)
):
    if get_accessible_team(db, current, team_id) is None:
        raise HTTPException(404, "team not found")
    return list_members(db, team_id)


@router.post("/{team_id}/members", response_model=MemberOut, status_code=201)
def members_add(
    team_id: int,
    body: MemberIn,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    if get_accessible_team(db, current, team_id) is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can manage members")
    try:
        m = add_member(db, team_id, body.user_id, body.role)
    except TeamError as e:
        raise _http(e)
    u = db.get(User, m.user_id)
    return MemberOut(user_id=m.user_id, username=u.username if u else "?", role=m.role)


@router.patch("/{team_id}/members/{user_id}", response_model=MemberOut)
def members_set_role(
    team_id: int,
    user_id: int,
    body: RoleIn,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    if get_accessible_team(db, current, team_id) is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can manage members")
    try:
        m = set_member_role(db, team_id, user_id, body.role)
    except TeamError as e:
        raise _http(e)
    u = db.get(User, user_id)
    return MemberOut(user_id=user_id, username=u.username if u else "?", role=m.role)


@router.delete("/{team_id}/members/{user_id}", status_code=204)
def members_remove(
    team_id: int,
    user_id: int,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    if get_accessible_team(db, current, team_id) is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can manage members")
    try:
        remove_member(db, team_id, user_id)
    except TeamError as e:
        raise _http(e)
    return Response(status_code=204)
