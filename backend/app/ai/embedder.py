"""OpenAI-compatible embedding client（實作 ``app.ai.rag.Embedder`` 介面）。

以 httpx 直連 ``{base_url}/embeddings``；支援 OpenAI / 任何相容 API。
"""
from __future__ import annotations

from typing import Optional, Sequence

import httpx


class OpenAIEmbedder:
    def __init__(
        self,
        model: str,
        dim: int,
        base_url: str = "https://api.openai.com/v1",
        api_key: Optional[str] = None,
    ) -> None:
        self.model = model
        self.dim = dim
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError("未設定 EMBEDDING_API_KEY / LLM_API_KEY，無法呼叫 embedding API")
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": list(texts)},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda d: d.get("index", 0))  # 依輸入順序回排
        return [d["embedding"] for d in data]
