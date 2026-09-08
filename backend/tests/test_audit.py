"""FR-5 稽核日誌：服務層（record / list）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.services.audit_service import list_audit, record_audit


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def test_record_and_list(db: Session):
    record_audit(
        db, action="auth.login", method="POST", path="/api/v1/auth/login", status_code=200, username="admin"
    )
    record_audit(
        db, action="POST /api/v1/projects", method="POST", path="/api/v1/projects", status_code=201
    )
    db.commit()
    rows = list_audit(db, limit=50)
    assert len(rows) == 2
    assert rows[0].action == "POST /api/v1/projects"  # id desc
    assert rows[1].username == "admin"


def test_list_respects_limit(db: Session):
    for i in range(5):
        record_audit(db, action=f"a{i}", method="GET", path="/x", status_code=200)
    db.commit()
    assert len(list_audit(db, limit=3)) == 3
