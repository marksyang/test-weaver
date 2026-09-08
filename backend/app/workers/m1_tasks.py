"""M1 Celery 任務：AI 生成測試項目（FR-1 / FR-1a）。

在 worker 執行；用 session_scope 取得自己獨立 Session。
"""
from __future__ import annotations

from ..ai.spec_items import extract_candidates
from ..core.db import session_scope
from ..models.platform import TestItemCategory
from ..models.project import SpecFile
from ..services.spec_service import generate_and_store_items
from .celery_app import celery_app


@celery_app.task(name="m1.generate_items")
def generate_items_task(spec_file_id: int) -> dict:
    """讀取已解析的 spec_file → 抽取候選 → 匹配/新建平台類別 → 存 test_item。"""
    with session_scope() as db:
        sf = db.get(SpecFile, spec_file_id)
        if sf is None:
            return {"spec_file_id": spec_file_id, "error": "spec file not found"}

        # platform 現有類別（供 LLM 對應，減少不必要的建立）
        categories = [c.name for c in db.query(TestItemCategory).all()]

        candidates = extract_candidates(sf.raw_text or "", categories)
        items = generate_and_store_items(db, sf.project_id, sf.id, candidates)

    return {"spec_file_id": spec_file_id, "generated": len(items)}
