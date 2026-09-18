"""報表排程：beat 組態 + 服務邏輯 + Celery 任務 + 手動觸發 endpoint（離線）。"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.api.v1.reports as reports_mod
import app.services.report_service as rs
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base
from app.models.project import Project
from app.models.report import AiReport
from app.models.test_plan import TestPlan
from app.services.report_service import EmailNotConfigured, run_report_schedule
from app.workers import m6_tasks
from app.workers.celery_app import _build_beat_schedule


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def _plan(db, status):
    p = Project(name="P")
    db.add(p)
    db.flush()
    plan = TestPlan(project_id=p.id, name=f"plan-{status}", status=status)
    db.add(plan)
    db.flush()
    return plan


class _FakeReport:
    id = 999


# ── beat 組態 ──

def test_beat_schedule_disabled_by_default(monkeypatch):
    monkeypatch.delenv("REPORT_SCHEDULE_ENABLED", raising=False)
    assert _build_beat_schedule() == {}


def test_beat_schedule_enabled(monkeypatch):
    monkeypatch.setenv("REPORT_SCHEDULE_ENABLED", "true")
    sched = _build_beat_schedule()
    assert "testweaver-report-schedule" in sched
    assert sched["testweaver-report-schedule"]["task"] == "m6.schedule_reports"


# ── 服務邏輯 ──

def test_schedule_only_completed_without_report(db, monkeypatch):
    done = _plan(db, "completed")
    _plan(db, "draft")  # 未完成 → 不處理
    with_report = _plan(db, "completed")
    db.add(AiReport(project_id=with_report.project_id, test_plan_id=with_report.id))
    db.commit()

    calls = []

    def _gen(d, pid):
        calls.append(pid)
        return _FakeReport()

    monkeypatch.setattr(rs, "generate_report", _gen)
    summary = run_report_schedule(db)
    assert calls == [done.id]  # 只補生成「completed 且無報表」的那個
    assert summary["generated"] == [done.id]


def test_schedule_sends_email(db, monkeypatch):
    done = _plan(db, "completed")
    calls = []

    def _send(d, pid, to):
        calls.append((pid, to))

    monkeypatch.setattr(rs, "generate_report", lambda d, pid: _FakeReport())
    monkeypatch.setattr(rs, "send_report_email", _send)
    summary = run_report_schedule(db, email_to=["a@b.com"])
    assert calls == [(done.id, "a@b.com")]
    assert summary["emailed"] == 1


def test_schedule_skips_email_when_smtp_down(db, monkeypatch):
    done = _plan(db, "completed")

    def _boom(d, pid, to):
        raise EmailNotConfigured("no smtp")

    monkeypatch.setattr(rs, "generate_report", lambda d, pid: _FakeReport())
    monkeypatch.setattr(rs, "send_report_email", _boom)
    summary = run_report_schedule(db, email_to=["a@b.com"])
    assert summary["generated"] == [done.id]  # 報表仍生成
    assert summary["emailed"] == 0            # email 略過


# ── Celery 任務 ──

def test_email_recipients_parsing(monkeypatch):
    monkeypatch.delenv("REPORT_EMAIL_TO", raising=False)
    assert m6_tasks._email_recipients() is None
    monkeypatch.setenv("REPORT_EMAIL_TO", " a@b.com , c@d.com ")
    assert m6_tasks._email_recipients() == ["a@b.com", "c@d.com"]


def test_task_wiring(db, monkeypatch):
    seen = {}

    @contextmanager
    def _fake_session_scope():
        yield db

    def _run(d, email_to=None):
        seen["email_to"] = email_to
        return {"generated": []}

    monkeypatch.setenv("REPORT_EMAIL_TO", "a@b.com")
    monkeypatch.setattr(m6_tasks, "session_scope", _fake_session_scope)
    monkeypatch.setattr(m6_tasks, "run_report_schedule", _run)
    m6_tasks.schedule_reports_task()  # 直接呼叫（非 .delay），離線執行任務體
    assert seen["email_to"] == ["a@b.com"]


# ── API endpoint ──

@pytest.fixture()
def client(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sched.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    T = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def _db():
        s = T()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c


def test_schedule_run_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        reports_mod, "run_report_schedule",
        lambda db, email_to=None: {"generated": [7], "emailed": 0, "errors": []},
    )
    r = client.post("/api/v1/reports/schedule/run")
    assert r.status_code == 200
    assert r.json()["generated"] == [7]
