"""RAG（檢索增強生成）相關資料模型。

- ``KnowledgeChunk``：文件切塊的關聯索引；向量本體存於外部向量資料庫
  （Qdrant / pgvector），此表僅記錄 chunk 與向量的對應及元資料。
- ``RagQueryLog``：RAG 查詢紀錄，含引用片段，供溯源與稽核。

設計說明
--------
- ``source_type`` 使用 ``String(16)`` + CHECK 約束（不採 MySQL native ENUM），
  以簡化後續 Alembic 遷移與擴增；應用層以 :class:`SourceType` 枚舉驗證。
- ``source_id`` 為多態參考（依 ``source_type`` 指向 spec_file / test_plan /
  test_case / defect / ai_report），故不設硬性外鍵。
- ``RagQueryLog.user_id`` 為對 user 的軟引用；user 表建立後可再補 FK 約束。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

# MySQL 用 LONGTEXT，其他方言（如 SQLite 測試）回落 TEXT
_LONGTEXT = Text().with_variant(LONGTEXT(), "mysql")


class SourceType(str, Enum):
    """chunk 的來源類型（多態）。"""

    spec = "spec"  # spec_file
    plan = "plan"  # test_plan
    case = "case"  # test_case
    defect = "defect"  # defect
    report = "report"  # ai_report

    @classmethod
    def values(cls) -> list[str]:
        return [m.value for m in cls]


class KnowledgeChunk(Base):
    """文件切塊索引（關聯表）；向量本體存於外部向量資料庫。"""

    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        Index("ix_knowledge_chunk_source", "source_type", "source_id"),
        CheckConstraint(
            f"source_type IN ({', '.join(repr(v) for v in SourceType.values())})",
            name="ck_knowledge_chunk_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(_LONGTEXT, nullable=False)
    token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    vector_store_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<KnowledgeChunk id={self.id} {self.source_type}:{self.source_id}>"


class RagQueryLog(Base):
    """RAG 查詢紀錄與引用（可溯源）。"""

    __tablename__ = "rag_query_log"
    __table_args__ = (
        Index("ix_rag_query_log_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 對 user 的軟引用；待 user 表建立後可補 FK 約束（避免此獨立遷移依賴未建的表）
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    top_k: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    matched_chunks_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    answer: Mapped[Optional[str]] = mapped_column(_LONGTEXT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:  # pragma: no cover
        preview = self.question[:20] if self.question else ""
        return f"<RagQueryLog id={self.id} q={preview!r}>"
