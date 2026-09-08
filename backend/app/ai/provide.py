"""RAG 相依的單一實例提供者（env → 具象化，快取）。

FastAPI 用 ``Depends(get_vector_store)`` 等注入；Celery task 直接呼叫。
測試端以 ``app.dependency_overrides`` 取代這三支函式即可注入替身。
"""
from __future__ import annotations

import os
from functools import lru_cache

from .config import RagConfig
from .embedder import OpenAIEmbedder
from .vector_store import VectorStore, VectorStoreConfig, get_vector_store as _build_store


@lru_cache(maxsize=1)
def get_rag_config() -> RagConfig:
    return RagConfig.from_env()


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStore:
    return _build_store(
        VectorStoreConfig(
            backend=os.getenv("VECTOR_STORE", "qdrant"),
            vector_dim=int(os.getenv("EMBEDDING_DIM", "1536")),
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
            collection=os.getenv("QDRANT_COLLECTION", "testweaver_chunks"),
            postgres_dsn=os.getenv("POSTGRES_DSN") or None,
        )
    )


@lru_cache(maxsize=1)
def get_embedder() -> OpenAIEmbedder:
    return OpenAIEmbedder(
        model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        dim=int(os.getenv("EMBEDDING_DIM", "1536")),
        base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
        api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY"),
    )
