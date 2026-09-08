"""FR-5 帳號管理：服務層（建立 / 更新 / 最後一個 admin 保護）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.base import Base
from app.services.user_service import UserError, create_user, list_users, update_user


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    yield session
    session.close()
    engine.dispose()


def test_create_and_list(db: Session):
    u = create_user(db, username="alice", password="pass1234", role="tester")
    db.commit()
    users = list_users(db)
    assert len(users) == 1 and users[0].username == "alice" and users[0].role == "tester"
    assert u.password_salt and u.hashed_password != "pass1234"  # 不存明文


def test_create_duplicate_409(db: Session):
    create_user(db, username="alice", password="pass1234", role="tester")
    db.flush()
    with pytest.raises(UserError) as e:
        create_user(db, username="alice", password="pass1234", role="tester")
    assert e.value.status_code == 409


def test_create_bad_role(db: Session):
    with pytest.raises(UserError) as e:
        create_user(db, username="x", password="pass1234", role="superuser")
    assert e.value.status_code == 400


def test_create_short_password(db: Session):
    with pytest.raises(UserError) as e:
        create_user(db, username="x", password="123", role="tester")
    assert e.value.status_code == 400


def test_update_role_and_active(db: Session):
    u = create_user(db, username="bob", password="pass1234", role="tester")
    db.commit()
    u2 = update_user(db, u.id, role="qa_lead", is_active=False)
    db.commit()
    assert u2.role == "qa_lead" and u2.is_active is False


def test_update_password_rehashes(db: Session):
    u = create_user(db, username="carol", password="oldpass1", role="tester")
    db.commit()
    old = (u.password_salt, u.hashed_password)
    update_user(db, u.id, password="newpass2")
    db.commit()
    assert (u.password_salt, u.hashed_password) != old
    assert verify_password("newpass2", u.password_salt, u.hashed_password)
    assert not verify_password("oldpass1", u.password_salt, u.hashed_password)


def test_cannot_remove_last_admin(db: Session):
    admin = create_user(db, username="root", password="admin1234", role="admin")
    db.commit()
    with pytest.raises(UserError) as e:
        update_user(db, admin.id, role="tester")
    assert e.value.status_code == 400
    with pytest.raises(UserError):
        update_user(db, admin.id, is_active=False)


def test_can_demote_admin_when_another_admin_exists(db: Session):
    a1 = create_user(db, username="a1", password="admin1234", role="admin")
    create_user(db, username="a2", password="admin1234", role="admin")
    db.commit()
    u = update_user(db, a1.id, role="qa_lead")
    db.commit()
    assert u.role == "qa_lead"


def test_update_missing_404(db: Session):
    with pytest.raises(UserError) as e:
        update_user(db, 9999, role="tester")
    assert e.value.status_code == 404
