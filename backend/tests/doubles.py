"""測試替身（doubles）：in-memory 向量庫 + 決定性 embedding。

供 test_rag.py 與 test_rag_api.py 共用，避免重複。
"""
from __future__ import annotations

import math
import re
import zlib
from typing import Any, Optional, Sequence

from app.ai.vector_store import ChunkDoc, SearchHit, VectorStore

_TOKEN_RE = re.compile(r"[\u3000-\u9fff\uf900-\ufaff]|[A-Za-z0-9]+")


def _toks(t: str) -> list[str]:
    return _TOKEN_RE.findall(t or "")


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _match_filters(payload: dict, filters: Optional[dict[str, Any]]) -> bool:
    if not filters:
        return True
    for k, v in filters.items():
        pv = payload.get(k)
        if isinstance(v, (list, tuple)):
            if pv not in v:
                return False
        elif pv != v:
            return False
    return True


class FakeEmbedder:
    """決定性 bag-of-words embedding（crc 分桶 + L2 正規化）。"""

    def __init__(self, dim: int = 32) -> None:
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = [0.0] * self.dim
            for tok in _toks(t):
                vec[zlib.crc32(tok.encode("utf-8")) % self.dim] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            out.append([x / norm for x in vec])
        return out


class InMemoryVectorStore(VectorStore):
    """純 Python 向量庫（測試用）；不使用 engine config。"""

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._items: list[tuple[list[float], ChunkDoc]] = []

    def setup(self) -> None:  # pragma: no cover - 測試用
        pass

    def upsert(self, vector: Sequence[float], doc: ChunkDoc) -> None:
        self._items = [it for it in self._items if it[1].vector_store_id != doc.vector_store_id]
        self._items.append((list(vector), doc))

    def delete_by_source(self, source_type: str, source_id: int) -> None:
        self._items = [
            (v, d)
            for (v, d) in self._items
            if not (d.source_type == source_type and d.source_id == source_id)
        ]

    def search(
        self,
        vector: Sequence[float],
        top_k: int,
        *,
        filters: Optional[dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchHit]:
        v = list(vector)
        scored = []
        for vec, doc in self._items:
            if not _match_filters(doc.payload(), filters):
                continue
            s = _cosine(v, vec)
            if score_threshold is not None and s < score_threshold:
                continue
            scored.append((s, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[SearchHit] = []
        for s, doc in scored[:top_k]:
            p = doc.payload()
            meta = {k: v for k, v in p.items() if k not in
                    ("source_type", "source_id", "content", "section_title")}
            out.append(
                SearchHit(
                    vector_store_id=doc.vector_store_id,
                    score=s,
                    source_type=doc.source_type,
                    source_id=doc.source_id,
                    content=doc.content,
                    section_title=doc.section_title,
                    metadata=meta,
                )
            )
        return out
