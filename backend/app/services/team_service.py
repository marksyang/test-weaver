"""多團隊（multi-team）服務層（v1.1 T1）。

- ``seed_default_teams``：確保「預設團隊」存在 + 為「尚無任何 membership」的用戶補上
  （依全域 role 映射：admin→owner、qa_lead/tester 原樣）。冪等，可在啟動/migration 呼叫。
- ``backfill_null_projects``：把 team_id 為空的既有專案歸到預設團隊（T1 legacy）。
- ``accessible_team_ids`` / ``visible_project_query`` / ``get_accessible_project``：資料隔離。
  ``user is None``（AUTH_ENABLED=false）→ 放過（permissive），不破壞既有離線開發/測試。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.project import Project
from ..models.team import DEFAULT_TEAM_NAME, TEAM_ROLES, Team, TeamMember
from ..models.user import User


def map_role(global_role: str) -> str:
    """全域 role → 團隊級 role。admin→owner，其餘（qa_lead/tester）原樣。"""
    return "owner" if global_role == "admin" else global_role


def get_default_team(db: Session) -> Team:
    """取得「預設團隊」（不存在則建立並 flush 以拿到 id）。"""
    team = db.query(Team).filter_by(name=DEFAULT_TEAM_NAME).first()
    if team is None:
        team = Team(name=DEFAULT_TEAM_NAME, description="系統自動建立的預設團隊")
        db.add(team)
        db.flush()
    return team


def ensure_membership(db: Session, user: User, team: Team, role: str) -> TeamMember:
    m = db.query(TeamMember).filter_by(team_id=team.id, user_id=user.id).first()
    if m is None:
        m = TeamMember(team_id=team.id, user_id=user.id, role=role)
        db.add(m)
    return m


def seed_default_teams(db: Session) -> Team:
    """確保預設團隊存在，並為「尚無任何 membership」的用戶補上（依全域 role 映射）。冪等。"""
    team = get_default_team(db)
    users_without_team = (
        db.query(User)
        .outerjoin(TeamMember, TeamMember.user_id == User.id)
        .filter(TeamMember.id.is_(None))
        .all()
    )
    for u in users_without_team:
        ensure_membership(db, u, team, map_role(u.role))
    db.commit()
    return team


def backfill_null_projects(db: Session) -> int:
    """把 team_id 為空的專案歸到預設團隊（T1：legacy 資料）。回傳更新筆數。"""
    team = get_default_team(db)
    updated = (
        db.query(Project)
        .filter(Project.team_id.is_(None))
        .update({Project.team_id: team.id}, synchronize_session=False)
    )
    db.commit()
    return int(updated or 0)


def accessible_team_ids(db: Session, user: Optional[User]) -> list[int]:
    """user 所在團隊 id 列表（user is None → []）。"""
    if user is None:
        return []
    rows = db.query(TeamMember.team_id).filter_by(user_id=user.id).all()
    return [r[0] for r in rows]


def user_team_roles(db: Session, user: User) -> list[dict]:
    """回傳 user 所在團隊 [{id, name, role}]。"""
    out: list[dict] = []
    for m in db.query(TeamMember).filter_by(user_id=user.id).all():
        team = db.get(Team, m.team_id)
        if team is not None:
            out.append({"id": team.id, "name": team.name, "role": m.role})
    return out


def visible_project_query(db: Session, user: Optional[User]):
    """可見專案查詢。

    - user is None（AUTH 未啟用）→ 全部（permissive）。
    - 否則 → 自己團隊的專案 + 未指派(NULL) 的專案。
      （T1：legacy NULL 視為可見；T2 會把專案明確指派團隊後收緊此規則。）
    """
    q = db.query(Project)
    if user is None:
        return q
    tids = accessible_team_ids(db, user)
    cond = [Project.team_id.is_(None)]
    if tids:
        cond.append(Project.team_id.in_(tids))
    return q.filter(or_(*cond))


def get_accessible_project(
    db: Session, user: Optional[User], project_id: int
) -> Optional[Project]:
    """取得可存取專案；不可見（跨團隊）回 None（由 API 轉 404）。"""
    p = db.get(Project, project_id)
    if p is None:
        return None
    if user is None or p.team_id is None:
        return p  # permissive / legacy 未指派 → 可見
    if p.team_id in accessible_team_ids(db, user):
        return p
    return None


# ================= 多團隊 T2：team CRUD + members + 團隊級 RBAC =================
class TeamError(Exception):
    """團隊業務錯誤（由 API 轉為對應 4xx）。"""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def is_platform_admin(user: Optional[User]) -> bool:
    return user is not None and user.role == "admin"


def get_membership(db: Session, team_id: int, user_id: int) -> Optional[TeamMember]:
    return db.query(TeamMember).filter_by(team_id=team_id, user_id=user_id).first()


def get_accessible_team(db: Session, user: Optional[User], team_id: int) -> Optional[Team]:
    """member 或 platform admin → team；否則 None（API→404）。"""
    team = db.get(Team, team_id)
    if team is None or user is None:
        return None
    if is_platform_admin(user):
        return team
    return team if get_membership(db, team_id, user.id) is not None else None


def can_manage_team(db: Session, user: Optional[User], team_id: int) -> bool:
    """team owner 或 platform admin。"""
    if is_platform_admin(user):
        return True
    m = get_membership(db, team_id, user.id)
    return bool(m and m.role == "owner")


def _count_owners(db: Session, team_id: int) -> int:
    return db.query(TeamMember).filter_by(team_id=team_id, role="owner").count()


def create_team(db: Session, name: str, description: Optional[str], owner_user: User) -> Team:
    name = (name or "").strip()
    if not name:
        raise TeamError(422, "team name required")
    if db.query(Team).filter_by(name=name).first() is not None:
        raise TeamError(409, "team name already exists")
    team = Team(name=name, description=description)
    db.add(team)
    db.flush()
    db.add(TeamMember(team_id=team.id, user_id=owner_user.id, role="owner"))
    db.commit()
    db.refresh(team)
    return team


def list_members(db: Session, team_id: int) -> list[dict]:
    out: list[dict] = []
    for m in db.query(TeamMember).filter_by(team_id=team_id).order_by(TeamMember.id).all():
        u = db.get(User, m.user_id)
        out.append({"user_id": m.user_id, "username": u.username if u else "?", "role": m.role})
    return out


def add_member(db: Session, team_id: int, user_id: int, role: str) -> TeamMember:
    if role not in TEAM_ROLES:
        raise TeamError(422, f"invalid team role: {role}")
    if db.get(User, user_id) is None:
        raise TeamError(404, "user not found")
    m = get_membership(db, team_id, user_id)
    if m is None:
        m = TeamMember(team_id=team_id, user_id=user_id, role=role)
        db.add(m)
    else:
        m.role = role  # 已是成員 → 更新角色
    db.commit()
    db.refresh(m)
    return m


def set_member_role(db: Session, team_id: int, user_id: int, role: str) -> TeamMember:
    if role not in TEAM_ROLES:
        raise TeamError(422, f"invalid team role: {role}")
    m = get_membership(db, team_id, user_id)
    if m is None:
        raise TeamError(404, "member not found")
    if m.role == "owner" and role != "owner" and _count_owners(db, team_id) == 1:
        raise TeamError(400, "cannot demote the last owner of a team")
    m.role = role
    db.commit()
    db.refresh(m)
    return m


def remove_member(db: Session, team_id: int, user_id: int) -> None:
    m = get_membership(db, team_id, user_id)
    if m is None:
        raise TeamError(404, "member not found")
    if m.role == "owner" and _count_owners(db, team_id) == 1:
        raise TeamError(400, "cannot remove the last owner of a team")
    db.delete(m)
    db.commit()


def delete_team(db: Session, team_id: int) -> None:
    """刪除團隊（v1.1 T3）。有專案的團隊不可刪（409）；先清 memberships。"""
    team = db.get(Team, team_id)
    if team is None:
        raise TeamError(404, "team not found")
    proj_count = db.query(Project).filter_by(team_id=team_id).count()
    if proj_count > 0:
        raise TeamError(409, f"cannot delete a team with {proj_count} project(s)")
    db.query(TeamMember).filter_by(team_id=team_id).delete()
    db.delete(team)
    db.commit()
