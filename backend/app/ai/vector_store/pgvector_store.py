"""pgvector 實作（需 PostgreSQL）。

依賴：``pip install "psycopg[binary]" sqlalchemy``
此處以原生 SQL + ``vector`` 型別實作，避免對 pgvector python 套件的硬依賴。

注意：
- 向量本體與元資料存在 PostgreSQL 的 ``rag_vector`` 表（與 MySQL 業務庫分離）。
- ``filters`` 僅允許白名單欄位，避免 SQL 注入。
"""
from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy import create_engine, text

from .base import ChunkDoc, SearchHit, VectorStore


class PgvectorStore(VectorStore):
    #: 允許用於 WHERE 過濾的欄位（避免 SQL 注入）
    _ALLOWED_FILTERS = {"source_type", "source_id", "section_title"}

    def __init__(self, config) -> None:
        super().__init__(config)
        if not config.postgres_dsn:
            raise ValueError("pgvector backend 需要設定 postgres_dsn")
        self._engine = create_engine(config.postgres_dsn)

    def _vec_str(self, vector: Sequence[float]) -> str:
        return "[" + ",".join(repr(float(x)) for x in vector) + "]"

    def setup(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS rag_vector ("
                    f"  id TEXT PRIMARY KEY,"
                    f"  source_type VARCHAR(16) NOT NULL,"
                    f"  source_id INTEGER NOT NULL,"
                    f"  section_title TEXT,"
                    f"  content TEXT NOT NULL,"
                    f"  metadata JSONB,"
                    f"  embedding vector({self.config.vector_dim}) NOT NULL"
                    f")"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_rag_vector_source "
                    "ON rag_vector (source_type, source_id)"
                )
            )

    def upsert(self, vector: Sequence[float], doc: ChunkDoc) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO rag_vector
                        (id, source_type, source_id, section_title, content, metadata, embedding)
                    VALUES (:id, :st, :sid, :title, :content, :meta, :emb)
                    ON CONFLICT (id) DO UPDATE SET
                        section_title = EXCLUDED.section_title,
                        content       = EXCLUDED.content,
                        metadata      = EXCLUDED.metadata,
                        embedding     = EXCLUDED.embedding
                    """
                ),
                {
                    "id": doc.vector_store_id,
                    "st": doc.source_type,
                    "sid": int(doc.source_id),
                    "title": doc.section_title,
                    "content": doc.content,
                    "meta": json.dumps(doc.metadata or {}),
                    "emb": self._vec_str(vector),
                },
            )

    def _build_where(self, filters: Optional[dict[str, Any]]):
        conds = ["TRUE"]
        params: dict[str, Any] = {}
        for i, (key, val) in enumerate((filters or {}).items()):
            if key not in self._ALLOWED_FILTERS:
                raise ValueError(f"filter 欄位不受允許: {key}")
            if isinstance(val, (list, tuple)):
                conds.append(f"({key} = ANY(:list{i}))")
                params[f"list{i}"] = list(val)
            else:
                conds.append(f"{key} = :f{i}")
                params[f"f{i}"] = val
        return " AND ".join(conds), params

    def search(
        self,
        vector: Sequence[float],
        top_k: int,
        *,
        filters: Optional[dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchHit]:
        where, params = self._build_where(filters)
        # 注意：text() 不允許同一具名參數重複使用，故以 q_sel / q_thr / q_ord 區分
        vec = self._vec_str(vector)
        params["q_sel"] = vec
        params["q_ord"] = vec
        params["k"] = top_k
        if score_threshold is not None:
            params["q_thr"] = vec
            params["thr"] = score_threshold
            score_clause = " AND (1 - (embedding <=> :q_thr)) >= :thr"
        else:
            score_clause = ""

        sql = (
            "SELECT id, source_type, source_id, section_title, content, metadata,"
            "       1 - (embedding <=> :q_sel) AS score"
            f" FROM rag_vector WHERE {where}{score_clause}"
            " ORDER BY embedding <=> :q_ord LIMIT :k"
        )
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [self._row_to_hit(r) for r in rows]

    def _row_to_hit(self, r: Any) -> SearchHit:
        meta = r["metadata"] or {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        return SearchHit(
            vector_store_id=str(r["id"]),
            score=float(r["score"]),
            source_type=str(r["source_type"]),
            source_id=int(r["source_id"]),
            content=str(r["content"] or ""),
            section_title=r["section_title"],
            metadata=meta,
        )

    def delete_by_source(self, source_type: str, source_id: int) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM rag_vector WHERE source_type = :st AND source_id = :sid"),
                {"st": source_type, "sid": int(source_id)},
            )
