"""OpenAI-compatible chat client（RAG 的 answerer）。

``llm_answer(question, context)``：把檢索片段拼入 prompt，回傳 LLM 答案。
未配置 API key 時回傳明確的 fallback 字串（不拋錯），方便離線/開發。
"""
from __future__ import annotations

import os
from typing import Sequence

import httpx


def llm_answer(question: str, context: Sequence[str]) -> str:
    api_key = os.getenv("LLM_API_KEY") or os.getenv("EMBEDDING_API_KEY")
    if not api_key:
        return f"（LLM 未配置）已檢索 {len(list(context))} 段相關內容。問題：{question}"

    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    ctx = "\n\n".join(f"[{i + 1}] {c}" for i, c in enumerate(context))
    prompt = (
        "以下為從測試管理平台檢索到的上下文。請據此回答問題，必要時指出依據來源編號。\n\n"
        f"上下文：\n{ctx}\n\n問題：{question}"
    )

    resp = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
