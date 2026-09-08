"""多團隊（v1.1 T1）服務層測試：seed_default_teams / backfill_null_projects / role 映射。

離線可跑（SQLite + create_all）。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.project import Project
from app.models.team import DEFAULT_TEAM_NAME, Team, TeamMember
from app.models.user import User
from app.services.auth_service import make_user
from app.services.team_service import (
    backfill_null_projects,
    map_role,
    seed_default_teams,
)


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'team.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine, expire_on_commit=False)
    s = S()
    yield s
    s.close()
    engine.dispose()


def _role_of(session, username: str) -> tuple[str | None, int]:
    u = session.query(User).filter_by(username=username).first()
    m = session.query(TeamMember).filter_by(user_id=u.id).first() if u else None
    return (m.role if m else None, session.query(Team).count())


def test_map_role():
    assert map_role("admin") == "owner"
    assert map_role("qa_lead") == "qa_lead"
    assert map_role("tester") == "tester"


def test_seed_creates_default_team_and_maps_roles(session):
    make_user(session, "boss", "x", role="admin")
    make_user(session, "lead", "x", role="qa_lead")
    make_user(session, "mem", "x", role="tester")
    session.commit()

    team = seed_default_teams(session)
    assert team.name == DEFAULT_TEAM_NAME

    assert _role_of(session, "boss") == ("owner", 1)
    assert _role_of(session, "lead") == ("qa_lead", 1)
    assert _role_of(session, "mem") == ("tester", 1)


def test_seed_is_idempotent(session):
    make_user(session, "boss", "x", role="admin")
    session.commit()

    seed_default_teams(session)
    seed_default_teams(session)  # 再跑不重複

    assert session.query(Team).count() == 1
    assert session.query(TeamMember).count() == 1


def test_seed_only_adds_users_without_membership(session):
    # 已存在其他團隊的用戶不應被塞進預設團隊
    other = Team(name="Other")
    session.add(other)
    session.commit()
    u = make_user(session, "member", "x", role="tester")
    session.flush()  # 拿到 u.id
    session.add(TeamMember(team_id=other.id, user_id=u.id, role="qa_lead"))
    session.commit()

    seed_default_teams(session)

    ms = session.query(TeamMember).filter_by(user_id=u.id).all()
    assert len(ms) == 1  # 只有 Original，未被再加進預設團隊
    assert ms[0].role == "qa_lead"


def test_backfill_null_projects(session):
    p = Project(name="legacy")  # team_id NULL
    session.add(p)
    session.commit()

    t = Team(name="T1")
    session.add(t)
    session.commit()

    p2 = Project(name="assigned", team_id=t.id)
    session.add(p2)
    session.commit()

    n = backfill_null_projects(session)
    assert n == 1

    default = session.query(Team).filter_by(name=DEFAULT_TEAM_NAME).first()
    re_legacy = session.query(Project).filter_by(name="legacy").first()
    re_assigned = session.query(Project).filter_by(name="assigned").first()
    assert re_legacy.team_id == default.id  # NULL → 預設團隊
    assert re_assigned.team_id == t.id  # 已指派的不變
