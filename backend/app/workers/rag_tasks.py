"""Celery tasks：把 RAG 的 index_source / rag_query 非同步化。

- ``index_source_task``：切塊 → embedding → 寫向量庫 → 持久化 knowledge_chunk。
- ``rag_query_task``：檢索（+ 可選 LLM 答案）→ 記錄 rag_query_log → 回傳結果。

Worker 使用與 API 相同的 provide 單一實例（env 驅動）。
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from ..ai.llm import llm_answer
from ..ai.provide import get_embedder, get_rag_config, get_vector_store
from ..ai.rag import index_source as do_index, persist_chunks, rag_query as do_query
from ..core.db import session_scope
from ..models.rag import RagQueryLog
from .celery_app import celery_app


@celery_app.task(name="rag.index_source", bind=True, max_retries=2)
def index_source_task(
    self,
    source_type: str,
    source_id: int,
    text: str,
    section_title: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
):
    store = get_vector_store()
    embedder = get_embedder()
    cfg = get_rag_config()

    store.setup()
    docs = do_index(
        store, embedder, source_type, source_id, text, cfg,
        section_title=section_title, metadata=metadata,
    )
    with session_scope() as db:
        persist_chunks(db, docs)

    return {"source_type": source_type, "source_id": int(source_id), "chunks": len(docs)}


@celery_app.task(name="rag.query")
def rag_query_task(
    question: str,
    top_k: Optional[int] = None,
    filters: Optional[dict[str, Any]] = None,
    answer: bool = True,
    user_id: Optional[int] = None,
):
    store = get_vector_store()
    embedder = get_embedder()
    cfg = get_rag_config()
    if top_k:
        cfg = replace(cfg, top_k=top_k)

    answerer = (lambda q, ctx: llm_answer(q, ctx)) if answer else None
    result = do_query(store, embedder, question, cfg, filters=filters or {}, answerer=answerer)

    with session_scope() as db:
        db.add(
            RagQueryLog(
                user_id=user_id,
                question=question,
                top_k=len(result.hits),
                matched_chunks_json=[
                    {
                        "vector_store_id": h.vector_store_id,
                        "source_type": h.source_type,
                        "source_id": h.source_id,
                        "score": round(h.score, 6),
                    }
                    for h in result.hits
                ],
                answer=result.answer,
            )
        )

    return {
        "question": question,
        "hits": [h.__dict__ for h in result.hits],
        "context": result.context,
        "answer": result.answer,
    }
