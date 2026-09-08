"""FR-5 / M8 安全/服務層測試（離線）：密碼雜湊 + JWT + authenticate。"""
from __future__ import annotations

import base64
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import security as sec
from app.models.base import Base
from app.services.auth_service import authenticate, make_user


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def test_password_roundtrip():
    salt = sec.generate_salt()
    h = sec.hash_password("p@ss", salt)
    assert sec.verify_password("p@ss", salt, h)
    assert not sec.verify_password("wrong", salt, h)
    # 不同 salt → 不同 hash（salt 具隨機性）
    assert sec.hash_password("p@ss", sec.generate_salt()) != h


def test_jwt_roundtrip():
    tok = sec.create_token({"sub": "3", "role": "qa_lead"})
    p = sec.decode_token(tok)
    assert p["sub"] == "3" and p["role"] == "qa_lead" and "exp" in p


def test_jwt_tampered_signature():
    tok = sec.create_token({"sub": "1", "role": "tester"})
    parts = tok.split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
    payload["role"] = "admin"  # 竄改內容
    parts[1] = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    with pytest.raises(sec.JWTError):
        sec.decode_token(".".join(parts))


def test_jwt_expired():
    tok = sec.create_token({"sub": "1"}, expires_minutes=-1)
    with pytest.raises(sec.JWTError):
        sec.decode_token(tok)


def test_authenticate(db: Session):
    make_user(db, "alice", "pw123", role="tester")
    db.commit()
    assert authenticate(db, "alice", "pw123") is not None
    assert authenticate(db, "alice", "bad") is None
    assert authenticate(db, "ghost", "x") is None


def test_inactive_user_rejected(db: Session):
    make_user(db, "bob", "pw", role="tester", is_active=False)
    db.commit()
    assert authenticate(db, "bob", "pw") is None
