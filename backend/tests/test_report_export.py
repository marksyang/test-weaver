"""FR-4 延伸：報表 PDF 匯出 + Email（SMTP，stdlib、可 monkeypatch）。

離線（SQLite）；reportlab 已在 requirements；email 用 monkeypatch 不真實發送。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.report_service as rs
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base
from app.models.project import Project
from app.models.test_plan import TestCase, TestFunction, TestPlan
from app.services.report_service import build_report_email, generate_report, render_report_pdf_bytes


@pytest.fixture()
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'export.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    plan_id_box: dict = {}

    with TestSession() as s:
        proj = Project(name="p")
        s.add(proj)
        s.flush()
        plan = TestPlan(project_id=proj.id, name="結帳計畫", version=1, status="in_progress")
        s.add(plan)
        s.flush()
        f1 = TestFunction(test_plan_id=plan.id, name="功能A", sort_order=1)
        s.add(f1)
        s.flush()
        f2 = TestFunction(test_plan_id=plan.id, name="功能B（缺案例）", sort_order=2)
        s.add(f2)
        s.flush()
        c1 = TestCase(test_function_id=f1.id, name="case-pass", status="passed", priority="high", sort_order=1)
        c2 = TestCase(test_function_id=f1.id, name="case-fail", status="failed", priority="high", sort_order=2)
        s.add_all([c1, c2])
        s.flush()
        generate_report(s, plan.id)
        s.commit()
        plan_id_box["id"] = plan.id

    app = create_app()

    def _override_db():
        d = TestSession()
        try:
            yield d
        finally:
            d.close()

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app), plan_id_box["id"], TestSession
    app.dependency_overrides.clear()
    engine.dispose()


# ---------- PDF 匯出 ----------
def test_export_pdf_returns_pdf(env):
    client, plan_id, _ = env
    r = client.get(f"/api/v1/reports/{plan_id}/export?format=pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_export_csv_default(env):
    client, plan_id, _ = env
    r = client.get(f"/api/v1/reports/{plan_id}/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert b"pass_rate" in r.content


def test_export_bad_format_400(env):
    client, plan_id, _ = env
    assert client.get(f"/api/v1/reports/{plan_id}/export?format=doc").status_code == 400


def test_render_pdf_bytes_magic_and_size():
    b = render_report_pdf_bytes(
        "plan X",
        "摘要：通過率 80%",
        [{"title": "處理失敗案例", "detail": "1 個失敗"}],
        {"total_functions": 2, "total_cases": 5, "passed": 4, "failed": 1,
         "blocked": 0, "pending": 0, "pass_rate": 0.8, "coverage": 0.5,
         "defects": {"total": 2, "open_or_in_progress": 1, "high_severity": 1},
         "coverage_gaps": ["gap"], "failed_cases": ["case-fail"]},
    )
    assert b[:4] == b"%PDF" and len(b) > 1000


# ---------- Email ----------
def test_build_report_email(env):
    client, plan_id, Sess = env
    with Sess() as s:
        subject, html, pdf = build_report_email(s, plan_id, "a@b.com")
    assert "結帳計畫" in subject
    assert "通過率" in html and "AI 分析建議" in html
    assert pdf[:4] == b"%PDF"


def test_send_report_email_configured(env, monkeypatch):
    client, plan_id, _ = env
    calls: dict = {}

    def fake_send(**kw):
        calls.update(kw)

    monkeypatch.setattr(rs, "_smtp_send", fake_send)
    monkeypatch.setenv("SMTP_HOST", "localhost")
    r = client.post(f"/api/v1/reports/{plan_id}/send", json={"to": "a@b.com"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert calls["to_addr"] == "a@b.com"
    assert calls["subject"].startswith("【TestWeaver】")
    assert calls["pdf_bytes"][:4] == b"%PDF"


def test_send_report_email_not_configured(env, monkeypatch):
    client, plan_id, _ = env
    monkeypatch.delenv("SMTP_HOST", raising=False)
    r = client.post(f"/api/v1/reports/{plan_id}/send", json={"to": "a@b.com"})
    assert r.status_code == 503


def test_send_report_email_invalid_recipient(env):
    client, plan_id, _ = env
    assert client.post(f"/api/v1/reports/{plan_id}/send", json={"to": "not-an-email"}).status_code == 422
