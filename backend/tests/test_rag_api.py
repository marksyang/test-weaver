"""FastAPI /rag/* 路由測試（TestClient + 替身，離線可跑）。

- 同步檢索 / filter：override ``get_vector_store``/``get_embedder``/``get_rag_config`` 為替身。
- 索引 / 非同步 / 任務狀態：monkeypatch 模組 helper（``_enqueue_*``/``_task_status``），
  不需真實 Celery / broker / qdrant。
- 查詢紀錄：file-based SQLite（TestClient 於獨立執行緒跑，避開 :memory: 跨執行緒問題）。
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.v1.rag as rag_api
from app.ai.config import RagConfig
from app.ai.provide import get_embedder, get_rag_config, get_vector_store
from app.ai.rag import index_source
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base
from app.models.rag import RagQueryLog

from tests.doubles import FakeEmbedder, InMemoryVectorStore


@pytest.fixture
def api_env():
    store = InMemoryVectorStore()
    embedder = FakeEmbedder(32)
    cfg = RagConfig(
        chunk_by="fixed", chunk_size=8, chunk_overlap=2, top_k=3, similarity_threshold=0.0
    )

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)

    app = create_app()
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_rag_config] = lambda: cfg

    def _override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app)

    yield {
        "client": client,
        "store": store,
        "embedder": embedder,
        "cfg": cfg,
        "session": TestSession,
    }

    engine.dispose()
    os.unlink(path)


def test_query_sync_returns_hits(api_env):
    spec = "登入功能 帳號密碼驗證 token。報表功能 產生通過率與缺陷分佈圖表。"
    index_source(api_env["store"], api_env["embedder"], "spec", 101, spec, api_env["cfg"])
    r = api_env["client"].post("/api/v1/rag/query", json={"question": "報表 通過率", "top_k": 3})
    assert r.status_code == 200
    data = r.json()
    assert data["question"] == "報表 通過率"
    assert isinstance(data["hits"], list) and data["hits"]
    joined = " ".join(h["content"] for h in data["hits"])
    assert "通過率" in joined or "報表" in joined


def test_query_with_source_type_filter(api_env):
    index_source(api_env["store"], api_env["embedder"], "spec", 1, "login token", api_env["cfg"])
    index_source(api_env["store"], api_env["embedder"], "defect", 2, "login bug", api_env["cfg"])
    r = api_env["client"].post(
        "/api/v1/rag/query",
        json={"question": "login", "top_k": 10, "source_types": ["defect"]},
    )
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert hits and all(h["source_type"] == "defect" for h in hits)


def test_index_endpoint_enqueues(api_env, monkeypatch):
    monkeypatch.setattr(rag_api, "_enqueue_index", lambda req: "fake-index-task")
    r = api_env["client"].post(
        "/api/v1/rag/index",
        json={"source_type": "spec", "source_id": 5, "text": "abc 內容"},
    )
    assert r.status_code == 200
    assert r.json() == {"task_id": "fake-index-task", "status": "queued"}


def test_query_async_enqueues(api_env, monkeypatch):
    monkeypatch.setattr(rag_api, "_enqueue_query", lambda req, filters: "fake-q-task")
    r = api_env["client"].post(
        "/api/v1/rag/query/async",
        json={"question": "hello", "answer": True},
    )
    assert r.status_code == 200
    assert r.json()["task_id"] == "fake-q-task"


def test_task_status(api_env, monkeypatch):
    monkeypatch.setattr(
        rag_api,
        "_task_status",
        lambda task_id: {"task_id": task_id, "state": "SUCCESS", "result": {"chunks": 2}},
    )
    r = api_env["client"].get("/api/v1/rag/tasks/some-id")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "SUCCESS"
    assert body["result"]["chunks"] == 2


def test_query_logs(api_env):
    db = api_env["session"]()
    db.add(
        RagQueryLog(
            user_id=1, question="hello", top_k=3, answer="ans",
            matched_chunks_json=[{"vector_store_id": "x"}],
        )
    )
    db.commit()
    db.close()

    r = api_env["client"].get("/api/v1/rag/query-logs")
    assert r.status_code == 200
    items = r.json()
    assert any(i["question"] == "hello" for i in items)


def test_index_rejects_bad_source_type(api_env):
    r = api_env["client"].post(
        "/api/v1/rag/index",
        json={"source_type": "bogus", "source_id": 5, "text": "x"},
    )
    assert r.status_code == 422  # source_type pattern 驗證失敗
