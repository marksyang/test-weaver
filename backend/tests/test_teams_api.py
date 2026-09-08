"""多團隊（v1.1 T2）API 測試：team CRUD + members + 團隊級 RBAC + 最後一個 owner 保護。

啟用 AUTH_ENABLED=true。Team T：boss=owner、bob=tester；root=admin（platform admin，非 T 成員）；
eve（無團隊）；newu（待加入）。離線可跑（SQLite）。
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
from app.models.team import Team, TeamMember
from app.services.auth_service import make_user


def _tok(uid: int, username: str, role: str) -> dict:
    return {"Authorization": f"Bearer {create_token({'sub': str(uid), 'username': username, 'role': role})}"}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    engine = create_engine(
        f"sqlite:///{tmp_path / 'teams.db'}", connect_args={"check_same_thread": False}
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

    db = S()
    t = Team(name="Team T")
    db.add(t)
    db.flush()
    boss = make_user(db, "boss", "pw", role="tester")
    bob = make_user(db, "bob", "pw", role="tester")
    root = make_user(db, "root", "pw", role="admin")
    eve = make_user(db, "eve", "pw", role="tester")
    newu = make_user(db, "newu", "pw", role="tester")
    db.flush()
    db.add_all(
        [
            TeamMember(team_id=t.id, user_id=boss.id, role="owner"),
            TeamMember(team_id=t.id, user_id=bob.id, role="tester"),
        ]
    )
    db.commit()
    data = {
        "client": client,
        "tid": t.id,
        "uid_boss": boss.id,
        "uid_newu": newu.id,
        "boss": _tok(boss.id, "boss", "tester"),
        "bob": _tok(bob.id, "bob", "tester"),
        "root": _tok(root.id, "root", "admin"),
        "eve": _tok(eve.id, "eve", "tester"),
    }
    db.close()
    yield data
    app.dependency_overrides.clear()
    engine.dispose()


def test_create_team_makes_creator_owner(env):
    r = env["client"].post("/api/v1/teams", json={"name": "Brand New"}, headers=env["bob"])
    assert r.status_code == 201
    assert r.json()["my_role"] == "owner"
    # 重複名稱 → 409
    r2 = env["client"].post("/api/v1/teams", json={"name": "Brand New"}, headers=env["boss"])
    assert r2.status_code == 409


def test_list_teams_scoped(env):
    rb = env["client"].get("/api/v1/teams", headers=env["boss"])
    assert rb.status_code == 200
    assert any(t["id"] == env["tid"] for t in rb.json())
    # eve 非 Team T 成員 → 看不到 T
    re_ = env["client"].get("/api/v1/teams", headers=env["eve"])
    assert re_.status_code == 200
    assert not any(t["id"] == env["tid"] for t in re_.json())


def test_owner_manage_members_crud(env):
    c = env["client"]
    r = c.post(
        f"/api/v1/teams/{env['tid']}/members",
        json={"user_id": env["uid_newu"], "role": "tester"},
        headers=env["boss"],
    )
    assert r.status_code == 201 and r.json()["role"] == "tester"
    r2 = c.patch(
        f"/api/v1/teams/{env['tid']}/members/{env['uid_newu']}",
        json={"role": "qa_lead"},
        headers=env["boss"],
    )
    assert r2.status_code == 200 and r2.json()["role"] == "qa_lead"
    r3 = c.delete(f"/api/v1/teams/{env['tid']}/members/{env['uid_newu']}", headers=env["boss"])
    assert r3.status_code == 204


def test_tester_cannot_manage(env):
    r = env["client"].post(
        f"/api/v1/teams/{env['tid']}/members",
        json={"user_id": env["uid_newu"], "role": "tester"},
        headers=env["bob"],
    )
    assert r.status_code == 403
    r2 = env["client"].delete(
        f"/api/v1/teams/{env['tid']}/members/{env['uid_newu']}", headers=env["bob"]
    )
    assert r2.status_code == 403


def test_last_owner_protected(env):
    c = env["client"]
    # boss 是 Team T 唯一 owner → 移除/降級自己 → 400
    r = c.delete(f"/api/v1/teams/{env['tid']}/members/{env['uid_boss']}", headers=env["boss"])
    assert r.status_code == 400
    r2 = c.patch(
        f"/api/v1/teams/{env['tid']}/members/{env['uid_boss']}",
        json={"role": "tester"},
        headers=env["boss"],
    )
    assert r2.status_code == 400


def test_platform_admin_override(env):
    # root（admin，非 T 成員）仍可加入成員
    r = env["client"].post(
        f"/api/v1/teams/{env['tid']}/members",
        json={"user_id": env["uid_newu"], "role": "tester"},
        headers=env["root"],
    )
    assert r.status_code == 201
    # 但移除最後一個 owner 仍被擋 → 400
    r2 = env["client"].delete(
        f"/api/v1/teams/{env['tid']}/members/{env['uid_boss']}", headers=env["root"]
    )
    assert r2.status_code == 400


def test_non_member_404(env):
    r = env["client"].get(f"/api/v1/teams/{env['tid']}", headers=env["eve"])
    assert r.status_code == 404
    r2 = env["client"].get(f"/api/v1/teams/{env['tid']}/members", headers=env["eve"])
    assert r2.status_code == 404


def test_auth_required(env):
    # AUTH_ENABLED=true 但無 token → 401
    r = env["client"].post("/api/v1/teams", json={"name": "X"})
    assert r.status_code == 401
