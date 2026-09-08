"""多團隊（v1.1 T1）API 測試：資料隔離（跨團隊 404）、/me/teams、NULL 可見規則。

啟用 AUTH_ENABLED=true；兩個團隊各有一用戶與專案。離線可跑（SQLite）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import get_db
from app.core.security import create_token
from app.main import create_app
from app.models.base import Base
from app.models.project import Project
from app.models.team import Team, TeamMember
from app.services.auth_service import make_user


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'team_api.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine, expire_on_commit=False)

    app = create_app()

    def _db():
        db = S()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    client = TestClient(app)

    # seed：兩個團隊 + 各一用戶 + 各一專案
    db = S()
    t_a, t_b = Team(name="Team A"), Team(name="Team B")
    db.add_all([t_a, t_b])
    db.commit()
    alice = make_user(db, "alice", "pw", role="tester")
    bob = make_user(db, "bob", "pw", role="tester")
    db.flush()  # 拿到 alice.id / bob.id
    db.add_all(
        [
            TeamMember(team_id=t_a.id, user_id=alice.id, role="tester"),
            TeamMember(team_id=t_b.id, user_id=bob.id, role="tester"),
            Project(name="A-proj", team_id=t_a.id),
            Project(name="B-proj", team_id=t_b.id),
        ]
    )
    db.commit()
    data = {
        "client": client,
        "t_a": t_a.id,
        "t_b": t_b.id,
        "pid_a": db.query(Project).filter_by(name="A-proj").first().id,
        "pid_b": db.query(Project).filter_by(name="B-proj").first().id,
        "auth_a": {"Authorization": f"Bearer {create_token({'sub': str(alice.id), 'username': 'alice', 'role': 'tester'})}"},
        "auth_b": {"Authorization": f"Bearer {create_token({'sub': str(bob.id), 'username': 'bob', 'role': 'tester'})}"},
    }
    db.close()

    yield data
    app.dependency_overrides.clear()
    engine.dispose()


def test_list_scoped_and_cross_team_404(env):
    c = env["client"]
    # alice 只看得到自己團隊的專案
    r = c.get("/api/v1/projects", headers=env["auth_a"])
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert env["pid_a"] in ids
    assert env["pid_b"] not in ids

    # alice 讀 bob（其他團隊）的專案 → 404
    r2 = c.get(f"/api/v1/projects/{env['pid_b']}", headers=env["auth_a"])
    assert r2.status_code == 404

    # alice 讀自己的 → 200
    r3 = c.get(f"/api/v1/projects/{env['pid_a']}", headers=env["auth_a"])
    assert r3.status_code == 200


def test_me_teams(env):
    c = env["client"]
    r = c.get("/api/v1/auth/me/teams", headers=env["auth_a"])
    assert r.status_code == 200
    teams = r.json()
    assert any(t["id"] == env["t_a"] and t["role"] == "tester" for t in teams)


def test_create_in_other_team_forbidden(env):
    c = env["client"]
    # bob（Team B）想在 Team A 建專案 → 403
    r = c.post(
        "/api/v1/projects",
        json={"name": "x", "team_id": env["t_a"]},
        headers=env["auth_b"],
    )
    assert r.status_code == 403


def test_null_team_project_visible_to_all(env):
    c = env["client"]
    # alice 建一個未指派團隊的專案（team_id=None）→ T1 規則：對所有人可見
    r = c.post("/api/v1/projects", json={"name": "orphan"}, headers=env["auth_a"])
    assert r.status_code == 200
    pid = r.json()["id"]
    r2 = c.get(f"/api/v1/projects/{pid}", headers=env["auth_b"])
    assert r2.status_code == 200
