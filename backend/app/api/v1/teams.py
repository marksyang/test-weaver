"""多團隊（multi-team）API（v1.1 T2/T3）：team CRUD + members 管理 + 團隊級 RBAC。

授權規則：
- 管理者 = 該 team 的 owner 或 platform admin（user.role='admin'）。
- 最後一個 owner 保護：移除/降級唯一 owner → 400。
- 非成員存取他隊 → 404（避免洩露存在）；無權管理 → 403。
- 刪除團隊：僅 platform admin（T3）；有專案 → 409。
- 需「真實」使用者（get_required_user）：AUTH 未啟用 → 401。
- 稽核（T3）：端點以 ``request.state.team_id`` + ``audit_action`` 標記；platform admin
  操作自己非成員的團隊 → ``audit_note='admin_override'``（稽核 detail）。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
    delete_team,
    get_accessible_team,
    get_membership,
    is_platform_admin,
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


def _mark(request: Request, db: Session, user: User, team_id: Optional[int], action: str) -> None:
    """標記稽核 context：team_id + action；platform admin 操作非成員團隊 → override。"""
    if team_id is not None:
        request.state.team_id = team_id
        if is_platform_admin(user) and get_membership(db, team_id, user.id) is None:
            request.state.audit_note = "admin_override"
    request.state.audit_action = action


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
    request: Request,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    try:
        team = create_team(db, body.name, body.description, current)
    except TeamError as e:
        raise _http(e)
    _mark(request, db, current, team.id, "team.create")
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
    request: Request,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    team = get_accessible_team(db, current, team_id)
    if team is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can update the team")
    _mark(request, db, current, team_id, "team.update")
    if body.name is not None and body.name.strip():
        team.name = body.name.strip()
    if body.description is not None:
        team.description = body.description
    db.commit()
    db.refresh(team)
    return _team_out(db, team, current)


@router.delete("/{team_id}", status_code=204)
def delete_team_ep(
    team_id: int,
    request: Request,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    if not is_platform_admin(current):
        raise HTTPException(403, "only a platform admin can delete a team")
    _mark(request, db, current, team_id, "team.delete")
    try:
        delete_team(db, team_id)
    except TeamError as e:
        raise _http(e)
    return Response(status_code=204)


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
    request: Request,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    if get_accessible_team(db, current, team_id) is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can manage members")
    _mark(request, db, current, team_id, "team.member.add")
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
    request: Request,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    if get_accessible_team(db, current, team_id) is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can manage members")
    _mark(request, db, current, team_id, "team.member.update_role")
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
    request: Request,
    current: User = Depends(get_required_user),
    db: Session = Depends(get_db),
):
    if get_accessible_team(db, current, team_id) is None:
        raise HTTPException(404, "team not found")
    if not can_manage_team(db, current, team_id):
        raise HTTPException(403, "only a team owner can manage members")
    _mark(request, db, current, team_id, "team.member.remove")
    try:
        remove_member(db, team_id, user_id)
    except TeamError as e:
        raise _http(e)
    return Response(status_code=204)
