"""VectorStore 引擎：抽象介面 + Qdrant / pgvector 實作 + factory。

範例::

    from app.ai.vector_store import VectorStoreConfig, get_vector_store
    store = get_vector_store(VectorStoreConfig(backend="qdrant"))
    store.setup()
"""
from .base import (
    ChunkDoc,
    SearchHit,
    VectorStore,
    VectorStoreConfig,
)

__all__ = [
    "ChunkDoc",
    "SearchHit",
    "VectorStore",
    "VectorStoreConfig",
    "QdrantStore",
    "PgvectorStore",
    "get_vector_store",
]


def get_vector_store(config: VectorStoreConfig) -> VectorStore:
    """依 config 回傳對應引擎實例（lazy import，未安裝的引擎不會在匯入時報錯）。"""
    backend = config.backend.lower()
    if backend == "qdrant":
        from .qdrant_store import QdrantStore

        return QdrantStore(config)
    if backend == "pgvector":
        from .pgvector_store import PgvectorStore

        return PgvectorStore(config)
    raise ValueError(f"未知的向量引擎: {config.backend!r}")
