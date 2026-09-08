"""VectorStore 抽象介面與共用型別。

RAG（FR-6）的向量存取引擎可切換（Qdrant / pgvector）。上層（RAG 檢索器、
索引服務）僅依賴此介面，不綁定具體引擎。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence


@dataclass
class VectorStoreConfig:
    """引擎設定（由設定檔 / 環境變數注入）。"""

    backend: str = "qdrant"  # qdrant | pgvector
    vector_dim: int = 1536

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    collection: str = "testweaver_chunks"

    # pgvector（需 PostgreSQL）
    postgres_dsn: Optional[str] = None  # e.g. postgresql+psycopg://user:pass@host/db


@dataclass
class ChunkDoc:
    """一個切塊（與關聯表 ``knowledge_chunk`` 對應）。"""

    vector_store_id: str
    source_type: str  # spec / plan / case / defect / report
    source_id: int
    content: str
    section_title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)  # e.g. {"project_id": 1}

    def payload(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "content": self.content,
            "section_title": self.section_title,
            **self.metadata,
        }


@dataclass
class SearchHit:
    """檢索回傳的片段。"""

    vector_store_id: str
    score: float
    source_type: str
    source_id: int
    content: str
    section_title: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """向量存取介面。"""

    def __init__(self, config: VectorStoreConfig) -> None:
        self.config = config

    @abstractmethod
    def setup(self) -> None:
        """初始化 container / collection / table（冪等）。"""

    @abstractmethod
    def upsert(self, vector: Sequence[float], doc: ChunkDoc) -> None:
        """寫入 / 更新單個向量。"""

    def upsert_many(self, items: list[tuple[Sequence[float], ChunkDoc]]) -> None:
        """批量寫入（預設逐個 upsert；實作可覆寫為 batch）。"""
        for vector, doc in items:
            self.upsert(vector, doc)

    @abstractmethod
    def search(
        self,
        vector: Sequence[float],
        top_k: int,
        *,
        filters: Optional[dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchHit]:
        """相似度檢索。

        filters: payload 欄位過濾；值為標量 = 精確匹配、list = any-of。
        score_threshold: 最低相似分（cosine，越高越相似）。
        """

    @abstractmethod
    def delete_by_source(self, source_type: str, source_id: int) -> None:
        """刪除某來源的所有向量（供 REINDEX_ON_CHANGE 增量重建）。"""
