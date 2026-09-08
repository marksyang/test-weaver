"""FastAPI /rag/* 路由（對應計劃書 §7 M9）。

端點：
- ``POST /rag/index``           → 非同步建立/更新向量索引（Celery），回 task_id
- ``POST /rag/query``           → 同步檢索，回 Top-K 引用 + context（快速路徑，無 LLM）
- ``POST /rag/query/async``     → 非同步檢索 + LLM 答案（Celery），回 task_id
- ``GET  /rag/tasks/{task_id}`` → 查詢 Celery 任務狀態/結果
- ``GET  /rag/query-logs``      → 列出 RAG 查詢紀錄（分頁）

碰到 Celery 的動作皆抽成模組層 helper（``_enqueue_*`` / ``_task_status``），
以便測試 monkeypatch，無需真實 broker / qdrant。
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...ai.config import RagConfig
from ...ai.provide import get_embedder, get_rag_config, get_vector_store
from ...ai.rag import rag_query as do_rag_query
from ...ai.vector_store import VectorStore
from ...core.db import get_db
from ...models.rag import RagQueryLog

router = APIRouter(prefix="/rag", tags=["RAG"])


# ── schemas ─────────────────────────────────────────────────────────────
class IndexRequest(BaseModel):
    source_type: str = Field(..., pattern="^(spec|plan|case|defect|report)$")
    source_id: int
    text: str
    section_title: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    source_types: Optional[list[str]] = None
    filters: dict[str, Any] = Field(default_factory=dict)


class AsyncQueryRequest(QueryRequest):
    answer: bool = True
    user_id: Optional[int] = None


class QueryResponse(BaseModel):
    question: str
    hits: list[dict[str, Any]]
    context: list[str]
    answer: Optional[str] = None


class TaskAck(BaseModel):
    task_id: str
    status: str = "queued"


class TaskStatusOut(BaseModel):
    task_id: str
    state: str
    result: Any = None


class LogOut(BaseModel):
    id: int
    question: str
    top_k: int
    answer: Optional[str] = None
    created_at: datetime


# ── Celery 動作（抽成 helper 供 monkeypatch）─────────────────────────────
def _enqueue_index(req: IndexRequest) -> str:
    from ...workers.rag_tasks import index_source_task

    return index_source_task.delay(
        req.source_type, req.source_id, req.text, req.section_title, req.metadata
    ).id


def _enqueue_query(req: AsyncQueryRequest, filters: dict[str, Any]) -> str:
    from ...workers.rag_tasks import rag_query_task

    return rag_query_task.delay(req.question, req.top_k, filters, req.answer, req.user_id).id


def _task_status(task_id: str) -> dict[str, Any]:
    from celery.result import AsyncResult

    from ...workers.celery_app import celery_app

    res = AsyncResult(task_id, app=celery_app)
    out: dict[str, Any] = {"task_id": task_id, "state": res.state}
    if res.ready():
        out["result"] = res.result
    return out


def _build_filters(req: QueryRequest) -> dict[str, Any]:
    filters = dict(req.filters or {})
    if req.source_types:
        filters["source_type"] = req.source_types
    return filters


# ── endpoints ───────────────────────────────────────────────────────────
@router.post("/index", response_model=TaskAck)
def index_endpoint(req: IndexRequest) -> TaskAck:
    return TaskAck(task_id=_enqueue_index(req))


@router.post("/query", response_model=QueryResponse)
def query_endpoint(
    req: QueryRequest,
    store: VectorStore = Depends(get_vector_store),
    embedder=Depends(get_embedder),
    cfg: RagConfig = Depends(get_rag_config),
) -> QueryResponse:
    eff = replace(cfg, top_k=req.top_k) if req.top_k else cfg
    result = do_rag_query(store, embedder, req.question, eff, filters=_build_filters(req))
    return QueryResponse(
        question=req.question,
        hits=[h.__dict__ for h in result.hits],
        context=result.context,
        answer=result.answer,
    )


@router.post("/query/async", response_model=TaskAck)
def query_async_endpoint(req: AsyncQueryRequest) -> TaskAck:
    return TaskAck(task_id=_enqueue_query(req, _build_filters(req)))


@router.get("/tasks/{task_id}", response_model=TaskStatusOut)
def task_status_endpoint(task_id: str) -> dict[str, Any]:
    return _task_status(task_id)


@router.get("/query-logs", response_model=list[LogOut])
def query_logs(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> list[RagQueryLog]:
    q = (
        db.query(RagQueryLog)
        .order_by(RagQueryLog.created_at.desc(), RagQueryLog.id.desc())
    )
    return q.offset((page - 1) * page_size).limit(page_size).all()
