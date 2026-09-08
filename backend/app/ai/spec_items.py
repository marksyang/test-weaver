"""FR-1：從規格書文字中抽取候選測試項目。

策略：
1. 若設定 LLM（LLM_API_KEY 或 EMBEDDING_API_KEY）→ 用 LLM 抽取（JSON 輸出）。
2. 無 LLM 或失敗 → 離線啟發式：依 Markdown 標題設定類別、條列/行產生項目。
   離線路徑決定性，可被測試。

LLM 為 OpenAI-compatible chat 介面（與 app.ai.llm 相同），此處獨立實作以回傳結構化項目。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class CandidateItem:
    name: str
    description: str = ""
    suggested_category: str = ""


def _llm_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY") or os.getenv("EMBEDDING_API_KEY"))


def extract_candidates_offline(spec_text: str) -> list[CandidateItem]:
    """決定性啟發式：Markdown 標題 → 類別，條列/行 → 候選項目。"""
    items: list[CandidateItem] = []
    current_cat = "通用"
    for raw in (spec_text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title:
                current_cat = title
            continue
        # 去除條列/編號前綴
        name = re.sub(r"^[-*\d\.\)\s]+", "", line).strip()
        if not name:
            continue
        items.append(
            CandidateItem(name=name[:120], description=line, suggested_category=current_cat)
        )
    return items


def _parse_candidates(text: str) -> list[CandidateItem]:
    """解析 LLM 回傳的 JSON（支援 {"items":[...]}、{"candidates":[...]} 或純陣列）。"""
    try:
        data = json.loads(text)
    except Exception:
        return []
    if isinstance(data, dict):
        arr = data.get("items") or data.get("candidates") or []
    elif isinstance(data, list):
        arr = data
    else:
        arr = []
    out: list[CandidateItem] = []
    for it in arr:
        if isinstance(it, dict) and str(it.get("name", "")).strip():
            out.append(
                CandidateItem(
                    name=str(it["name"]).strip()[:120],
                    description=str(it.get("description", "")),
                    suggested_category=str(it.get("suggested_category", "")),
                )
            )
    return out


def extract_candidates_llm(spec_text: str, categories: list[str]) -> list[CandidateItem]:
    if not _llm_configured():
        return extract_candidates_offline(spec_text)

    api_key = os.getenv("LLM_API_KEY") or os.getenv("EMBEDDING_API_KEY")
    base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    cat_list = ", ".join(categories) if categories else "（無）"
    prompt = (
        "你是測試分析師。請從下方產品規格書中，抽取「可測試的功能項目」（test items）。\n"
        f"現有平台類別（請盡量對應其中之一，避免不必要的新建）：{cat_list}\n"
        '輸出 JSON 物件：{"items":[{"name":"...","description":"...","suggested_category":"..."}]}\n'
        "只輸出 JSON，不要附加說明。\n\n規格書：\n" + (spec_text or "")[:20000]
    )
    resp = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return _parse_candidates(content)


def extract_candidates(
    spec_text: str, categories: Optional[list[str]] = None, use_llm: bool = True
) -> list[CandidateItem]:
    """主入口：LLM 優先，失敗或無配置時回退離線啟發式。"""
    if use_llm and _llm_configured():
        try:
            c = extract_candidates_llm(spec_text, categories or [])
            if c:
                return c
        except Exception:
            pass
    return extract_candidates_offline(spec_text)
