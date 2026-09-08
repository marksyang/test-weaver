"""RAG 檢索器單元測試（SQLite + in-memory 向量庫，離線可跑）。

執行：``python -m pytest backend/tests/test_rag.py -q``
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.config import RagConfig
from app.ai.rag import (
    estimate_tokens,
    index_source,
    persist_chunks,
    rag_query,
    split_text,
)
from app.models.base import Base
from app.models.rag import KnowledgeChunk

from tests.doubles import FakeEmbedder, InMemoryVectorStore


# ──────────────────────────── chunking ────────────────────────────
def test_split_text_fixed_window_bounded():
    cfg = RagConfig(chunk_by="fixed", chunk_size=10, chunk_overlap=2)
    text = " ".join(f"w{i}" for i in range(40))  # 40 tokens
    chunks = split_text(text, cfg)
    assert len(chunks) > 1
    for c in chunks:
        assert estimate_tokens(c) <= cfg.chunk_size


def test_split_text_overlap_carries_tail():
    cfg = RagConfig(chunk_by="fixed", chunk_size=5, chunk_overlap=2)
    text = " ".join(f"w{i}" for i in range(12))
    chunks = split_text(text, cfg)
    for i in range(len(chunks) - 1):
        tail = chunks[i].split()[-cfg.chunk_overlap:]
        head = chunks[i + 1].split()[: cfg.chunk_overlap]
        assert tail == head, f"overlap 未連續於 chunk {i}/{i + 1}"


def test_split_text_empty():
    assert split_text("", RagConfig(chunk_by="fixed")) == []
    assert split_text("   ", RagConfig(chunk_by="fixed")) == []


# ─────────────────────── index + SQLite persistence ───────────────────────
def test_index_and_query_with_sqlite():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)  # 建立 knowledge_chunk / rag_query_log

    cfg = RagConfig(
        chunk_by="fixed",
        chunk_size=8,
        chunk_overlap=2,
        top_k=3,
        similarity_threshold=0.0,
    )
    store = InMemoryVectorStore()
    embedder = FakeEmbedder(dim=32)

    spec = (
        "登入功能 使用者輸入帳號密碼後 系統驗證並回傳 token。"
        "登出功能 使用者可登出並作廢 token。"
        "報表功能 完成後產生通過率與缺陷分佈圖表。"
    )

    with Session(engine) as session:
        docs = index_source(store, embedder, "spec", 1001, spec, cfg, section_title="功能規格")
        persisted = persist_chunks(session, docs)
        session.commit()

        # 關係表落數（SQLite）
        assert len(docs) == len(persisted) >= 1
        rows = (
            session.query(KnowledgeChunk)
            .filter_by(source_type="spec", source_id=1001)
            .all()
        )
        assert len(rows) == len(docs)
        assert all(r.vector_store_id for r in rows)
        assert all(r.token_count > 0 for r in rows)

        # 檢索：問「報表 通過率」應命中報表相關片段
        result = rag_query(store, embedder, "報表 通過率", cfg)
        assert result.hits
        # bag-of-words cosine 下單一 top 不保證含整詞（窗口邊界可能切開「通過率」），
        # 故對 top-k 合併文本斷言
        top_texts = " ".join(h.content for h in result.hits)
        assert "通過率" in top_texts or "報表" in top_texts


def test_index_reindex_clears_old():
    store = InMemoryVectorStore()
    embedder = FakeEmbedder(16)
    cfg = RagConfig(chunk_by="fixed", chunk_size=50, reindex_on_change=True)
    index_source(store, embedder, "defect", 7, "first version alpha beta", cfg)
    n1 = len(store._items)
    index_source(store, embedder, "defect", 7, "second gamma delta", cfg)
    # reindex 後不該再有舊版詞，且都屬 source_id=7
    assert all("alpha" not in d.content for _, d in store._items)
    assert n1 >= 1
    assert all(d.source_id == 7 for _, d in store._items)


# ──────────────────────────── retrieval behavior ────────────────────────────
def test_query_source_filter():
    store = InMemoryVectorStore()
    embedder = FakeEmbedder(16)
    cfg = RagConfig(chunk_by="fixed", chunk_size=50, top_k=10, similarity_threshold=0.0)
    index_source(store, embedder, "spec", 1, "login token", cfg)
    index_source(store, embedder, "defect", 2, "login bug", cfg)
    res = rag_query(store, embedder, "login", cfg, filters={"source_type": ["defect"]})
    assert res.hits
    assert all(h.source_type == "defect" for h in res.hits)


def test_score_threshold_filters():
    store = InMemoryVectorStore()
    embedder = FakeEmbedder(16)
    cfg = RagConfig(chunk_by="fixed", chunk_size=50, top_k=5, similarity_threshold=0.99)
    index_source(store, embedder, "defect", 1, "alpha beta gamma delta", cfg)
    res = rag_query(store, embedder, "completely unrelated words here", cfg)
    assert res.hits == []  # 無共享詞 → cosine≈0 < 0.99


def test_answerer_callback():
    store = InMemoryVectorStore()
    embedder = FakeEmbedder(16)
    cfg = RagConfig(chunk_by="fixed", chunk_size=50, top_k=2, similarity_threshold=0.0)
    index_source(store, embedder, "spec", 1, "the quick brown fox", cfg)

    captured: dict = {}

    def answerer(q, context):
        captured["q"] = q
        captured["ctx"] = context
        return f"A:{len(context)}"

    res = rag_query(store, embedder, "quick fox", cfg, answerer=answerer)
    assert res.answer and res.answer.startswith("A:")
    assert captured["ctx"], "context 應非空"
