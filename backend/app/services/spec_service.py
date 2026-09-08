"""FR-1 服務層：規格書文字抽取、平台類別匹配、測試項目生成與存檔。

純邏輯（可用 SQLite + Session 離線測試，不依賴 Celery / LLM / Qdrant）。
"""
from __future__ import annotations

import hashlib
import io
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..ai.spec_items import CandidateItem
from ..models.platform import TestItemCategory
from ..models.test_item import TestItem, TestItemPlatformSync


def extract_text(data: bytes, fmt: str) -> str:
    """從上傳位元組抽取純文字。docx/pdf 採 lazy import（未安裝則拋錯，呼叫端處理）。"""
    fmt = (fmt or "txt").lower()
    if fmt == "docx":
        from docx import Document  # lazy

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    if fmt == "pdf":
        from pypdf import PdfReader  # lazy

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    # txt / md / 預設
    return data.decode("utf-8", errors="replace")


def _make_code(name: str) -> str:
    """產生唯一 ascii code（決定性）。以 name 做 key，重複名稱可被 exact 匹配去重。"""
    digest = hashlib.sha1((name or "通用").encode("utf-8")).hexdigest()[:12]
    return f"cat-{digest}"


def match_or_create_category(
    session: Session, suggested_name: str
) -> tuple[TestItemCategory, bool, str, Optional[float]]:
    """FR-1a：把候選類別對應到 platform 既有類別；找不到則在 platform 新建並標記。

    回傳 (category, is_newly_created, matched_by, similarity)。
    匹配順序：code exact → name exact（大小寫不敏感）→ 新建。
    """
    name = (suggested_name or "").strip() or "通用"

    cat = (
        session.query(TestItemCategory)
        .filter(func.lower(TestItemCategory.code) == name.lower())
        .first()
    )
    if cat is not None:
        return cat, False, "exact", 1.0

    cat = (
        session.query(TestItemCategory)
        .filter(func.lower(TestItemCategory.name) == name.lower())
        .first()
    )
    if cat is not None:
        return cat, False, "exact", 1.0

    # platform 無對應 → 先於 platform 新建，再對應（FR-1a）
    cat = TestItemCategory(name=name, code=_make_code(name))
    session.add(cat)
    session.flush()  # 取得 cat.id（並觸發 code unique 檢查）
    return cat, True, "new", None


def generate_and_store_items(
    session: Session,
    project_id: int,
    spec_file_id: Optional[int],
    candidates: list[CandidateItem],
) -> list[TestItem]:
    """對每個候選：匹配/建立平台類別 → 建 test_item → 記 platform_sync。"""
    items: list[TestItem] = []
    for cand in candidates:
        cat, is_new, matched_by, similarity = match_or_create_category(
            session, cand.suggested_category
        )
        item = TestItem(
            project_id=project_id,
            category_id=cat.id,
            name=(cand.name or "未命名")[:255],
            description=cand.description or None,
            is_newly_created=is_new,
            source_spec_file_id=spec_file_id,
        )
        session.add(item)
        session.flush()  # 取得 item.id
        session.add(
            TestItemPlatformSync(
                test_item_id=item.id,
                category_id=cat.id,
                matched_by=matched_by,
                similarity=similarity,
            )
        )
        items.append(item)
    return items
