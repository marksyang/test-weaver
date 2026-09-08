"""Qdrant 實作。

依賴：``pip install qdrant-client``
注意：呼叫假設 qdrant-client >= 1.7；較舊版本可將 ``search`` 改用
``client.search(collection, query_vector=..., ...)``。
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PointStruct,
)

from .base import ChunkDoc, SearchHit, VectorStore

_RESERVED_PAYLOAD_KEYS = {"source_type", "source_id", "content", "section_title"}


def _to_filter(filters: Optional[dict[str, Any]]) -> Optional[Filter]:
    if not filters:
        return None
    conds = []
    for key, val in filters.items():
        if isinstance(val, (list, tuple)):
            conds.append(FieldCondition(key=key, match=MatchAny(any=list(val))))
        else:
            conds.append(FieldCondition(key=key, match=MatchValue(value=val)))
    return Filter(must=conds) if conds else None


class QdrantStore(VectorStore):
    def __init__(self, config) -> None:
        super().__init__(config)
        self._client = QdrantClient(
            url=config.qdrant_url, api_key=config.qdrant_api_key
        )

    def setup(self) -> None:
        if not self._client.collection_exists(self.config.collection):
            self._client.create_collection(
                collection_name=self.config.collection,
                vectors_config={
                    "size": self.config.vector_dim,
                    "distance": Distance.COSINE,
                },
            )

    def upsert(self, vector: Sequence[float], doc: ChunkDoc) -> None:
        self._client.upsert(
            collection_name=self.config.collection,
            points=[
                PointStruct(
                    id=doc.vector_store_id,  # 需為 UUID 或 int
                    vector=list(vector),
                    payload=doc.payload(),
                )
            ],
        )

    def search(
        self,
        vector: Sequence[float],
        top_k: int,
        *,
        filters: Optional[dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchHit]:
        raw = self._client.search(
            collection_name=self.config.collection,
            query_vector=list(vector),
            limit=top_k,
            query_filter=_to_filter(filters),
            score_threshold=score_threshold,
        )
        hits: list[SearchHit] = []
        for h in raw:
            p = h.payload or {}
            meta = {k: v for k, v in p.items() if k not in _RESERVED_PAYLOAD_KEYS}
            hits.append(
                SearchHit(
                    vector_store_id=str(h.id),
                    score=float(h.score),
                    source_type=str(p.get("source_type", "")),
                    source_id=int(p.get("source_id", 0)),
                    content=str(p.get("content", "")),
                    section_title=p.get("section_title"),
                    metadata=meta,
                )
            )
        return hits

    def delete_by_source(self, source_type: str, source_id: int) -> None:
        self._client.delete(
            collection_name=self.config.collection,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(key="source_type", match=MatchValue(value=source_type)),
                        FieldCondition(key="source_id", match=MatchValue(value=int(source_id))),
                    ]
                )
            ),
        )
