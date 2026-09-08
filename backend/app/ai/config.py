"""RAG 檢索設定（對應計劃書 §8.1）。

以資料類別集中管理 chunking / 相似度門檻等參數；可從環境變數建立（`from_env`）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class RagConfig:
    # ── chunking ────────────────────────────────
    chunk_by: str = "recursive"  # fixed | paragraph | recursive
    chunk_size: int = 512  # tokens（單塊目標長度）
    chunk_overlap: int = 64  # tokens（相鄰塊重疊）
    chunk_separators: list[str] = field(
        default_factory=lambda: ["\n\n", "\n", "。", ". "]
    )  # recursive 策略分隔優先序（由粗到細）

    # ── retrieval ───────────────────────────────
    top_k: int = 5
    similarity_threshold: float = 0.75  # cosine 最低門檻
    score_function: str = "cosine"
    relative_margin: float | None = None  # e.g. 0.9 → 保留 score >= top1 * margin
    max_context_tokens: int = 2048

    # ── behavior ────────────────────────────────
    reindex_on_change: bool = True  # 源文件更新時先刪舊向量再重寫

    @classmethod
    def from_env(cls) -> "RagConfig":
        return cls(
            chunk_by=os.getenv("RAG_CHUNK_BY", "recursive"),
            chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "512")),
            chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "64")),
            top_k=int(os.getenv("RAG_TOP_K", "5")),
            similarity_threshold=float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.75")),
            score_function=os.getenv("RAG_SCORE_FUNCTION", "cosine"),
            max_context_tokens=int(os.getenv("RAG_MAX_CONTEXT_TOKENS", "2048")),
            reindex_on_change=os.getenv("RAG_REINDEX_ON_CHANGE", "true").lower()
            != "false",
        )
