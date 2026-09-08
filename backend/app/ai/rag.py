"""RAG 檢索器（對應計劃書 §5.5 / §8）。

职责：
- ``split_text``：依 ``RagConfig`` 切塊（fixed / paragraph / recursive + 重疊窗口）。
- ``index_source``：切塊 → embedding → 寫入 ``VectorStore``；回傳 :class:`ChunkDoc`
  列表，供上層持久化到 ``knowledge_chunk``（SQLite/MySQL）。
- ``persist_chunks``：把 chunk 紀錄寫入關係表（與向量庫分離的關聯索引）。
- ``rag_query``：檢索 Top-K（門檻/相對邊距/上下文 token 上限）；``answerer`` 可選，
  由呼叫端注入 LLM，使本模組可離線測試。

上層僅依賴 :class:`~app.ai.vector_store.VectorStore` 與 :class:`Embedder` 介面，
不綁定具體向量引擎或 LLM。
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, Sequence

from sqlalchemy.orm import Session

from .config import RagConfig
from .vector_store import ChunkDoc, SearchHit, VectorStore
from ..models.rag import KnowledgeChunk

_CJK = re.compile(r"[\u3000-\u9fff\uf900-\ufaff]")


# ────────────────────────────────────────────────────────────────
# token / 切塊
# ────────────────────────────────────────────────────────────────
def _token_spans(text: str) -> list[tuple[int, int]]:
    """回傳每個 token 在原文中的 (start, end) 跨度。

    CJK 字元各為一個 token；連續的半形字元（英數）為一個 token；空白跳過。
    """
    spans: list[tuple[int, int]] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if _CJK.match(c):
            spans.append((i, i + 1))
            i += 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and not _CJK.match(text[j]):
                j += 1
            spans.append((i, j))
            i = j
    return spans


def estimate_tokens(text: str) -> int:
    """token 數的輕量估計（CJK 每字 1、半形串每詞 1）。"""
    return len(_token_spans(text))


def _window(text: str, size: int, overlap: int) -> list[str]:
    """在單段內以固定 token 窗口切分（帶 overlap），保留原文字元。"""
    spans = _token_spans(text)
    if not spans:
        return []
    step = max(1, size - overlap)
    out: list[str] = []
    for start in range(0, len(spans), step):
        window = spans[start : start + size]
        out.append(text[window[0][0] : window[-1][1]])
        if start + size >= len(spans):
            break
    return [c for c in out if c.strip()]


def _recursive_split(text: str, separators: Sequence[str]) -> list[str]:
    """依分隔符號由粗到細遞迴切分，回傳葉段。"""
    if not text.strip():
        return []
    if not separators:
        return [text.strip()]
    sep, rest = separators[0], separators[1:]
    if sep in text:
        out: list[str] = []
        for part in text.split(sep):
            out.extend(_recursive_split(part, rest))
        return [s for s in out if s.strip()]
    return _recursive_split(text, rest)


def split_text(text: str, config: RagConfig) -> list[str]:
    """依 config 切塊。"""
    text = (text or "").strip()
    if not text:
        return []
    if config.chunk_by == "fixed":
        segments = [text]
    elif config.chunk_by == "paragraph":
        segments = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    else:  # recursive
        segments = _recursive_split(text, list(config.chunk_separators))

    chunks: list[str] = []
    for seg in segments:
        chunks.extend(_window(seg, config.chunk_size, config.chunk_overlap))
    return [c for c in chunks if c.strip()]


# ────────────────────────────────────────────────────────────────
# 介面與型別
# ────────────────────────────────────────────────────────────────
class Embedder(Protocol):
    """embedding 介面：批次文字 → 向量。"""

    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        ...


@dataclass
class RetrievalResult:
    question: str
    hits: list[SearchHit] = field(default_factory=list)
    context: list[str] = field(default_factory=list)  # 依 max_context_tokens 修剪後
    answer: Optional[str] = None


# ────────────────────────────────────────────────────────────────
# 索引 / 持久化 / 檢索
# ────────────────────────────────────────────────────────────────
def index_source(
    store: VectorStore,
    embedder: Embedder,
    source_type: str,
    source_id: int,
    text: str,
    config: RagConfig,
    *,
    section_title: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> list[ChunkDoc]:
    """切塊 → embedding → 寫向量庫；回傳 ChunkDoc（供持久化 knowledge_chunk）。"""
    parts = split_text(text, config)
    if not parts:
        return []
    vectors = embedder.embed(parts)
    docs: list[ChunkDoc] = []
    pairs: list[tuple[Sequence[float], ChunkDoc]] = []
    for part, vec in zip(parts, vectors):
        doc = ChunkDoc(
            vector_store_id=str(uuid.uuid4()),
            source_type=source_type,
            source_id=int(source_id),
            content=part,
            section_title=section_title,
            metadata=dict(metadata or {}),
        )
        docs.append(doc)
        pairs.append((vec, doc))

    if config.reindex_on_change:
        store.delete_by_source(source_type, source_id)
    store.upsert_many(pairs)
    return docs


def persist_chunks(
    session: Session, docs: Sequence[ChunkDoc]
) -> list[KnowledgeChunk]:
    """把 chunk 關聯紀錄寫入 ``knowledge_chunk``（與向量庫分離）。"""
    rows = [
        KnowledgeChunk(
            source_type=doc.source_type,
            source_id=int(doc.source_id),
            section_title=doc.section_title,
            content=doc.content,
            token_count=estimate_tokens(doc.content),
            vector_store_id=doc.vector_store_id,
        )
        for doc in docs
    ]
    session.add_all(rows)
    return rows


def rag_query(
    store: VectorStore,
    embedder: Embedder,
    question: str,
    config: RagConfig,
    *,
    filters: Optional[dict[str, Any]] = None,
    answerer: Optional[Callable[[str, list[str]], str]] = None,
) -> RetrievalResult:
    """檢索 Top-K 並（可選）以注入的 answerer 生成答案。

    - ``filters``：payload 過濾（值為 list = any-of）。
    - ``answerer(question, context)``：由呼叫端提供 LLM；未提供則只回傳檢索結果。
    """
    qv = embedder.embed([question])[0]
    hits = store.search(
        qv,
        top_k=config.top_k,
        filters=filters,
        score_threshold=config.similarity_threshold,
    )

    if config.relative_margin is not None and hits:
        top = hits[0].score
        kept = [h for h in hits if h.score >= top * config.relative_margin]
        hits = kept or [hits[0]]

    context: list[str] = []
    used = 0
    for h in hits:
        t = estimate_tokens(h.content)
        if context and used + t > config.max_context_tokens:
            break
        context.append(h.content)
        used += t

    answer = answerer(question, context) if (answerer and context) else None
    return RetrievalResult(question=question, hits=hits, context=context, answer=answer)
