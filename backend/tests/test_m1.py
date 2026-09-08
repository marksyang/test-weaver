"""FR-1 / M1 服務與單元測試（SQLite + Session，離線可跑）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.spec_items import (
    CandidateItem,
    _parse_candidates,
    extract_candidates_offline,
)
from app.models.base import Base
from app.models.platform import TestItemCategory
from app.models.project import Project
from app.models.test_item import TestItem, TestItemPlatformSync
from app.services.spec_service import (
    extract_text,
    generate_and_store_items,
    match_or_create_category,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


def test_extract_text_txt_and_default():
    assert extract_text("hello 世界".encode(), "txt") == "hello 世界"
    assert extract_text(b"abc", "") == "abc"
    assert extract_text("md # t".encode(), "md") == "md # t"


def test_offline_candidates_with_headings():
    spec = "# 登入\n- 驗證帳號密碼\n- 失敗提示\n# 報表\n- 產生通過率圖表\n"
    items = extract_candidates_offline(spec)
    assert len(items) == 3
    cats = {i.suggested_category for i in items}
    assert {"登入", "報表"} <= cats
    names = [i.name for i in items]
    assert "驗證帳號密碼" in names and "產生通過率圖表" in names


def test_offline_candidates_default_category():
    items = extract_candidates_offline("- a\n- b\n")
    assert all(i.suggested_category == "通用" for i in items)
    assert [i.name for i in items] == ["a", "b"]


def test_offline_candidates_empty():
    assert extract_candidates_offline("") == []


def test_parse_candidates_variants():
    p1 = _parse_candidates('{"items":[{"name":"A","description":"d","suggested_category":"c"}]}')
    assert p1[0].name == "A" and p1[0].suggested_category == "c"
    p2 = _parse_candidates('[{"name":"B"}]')
    assert p2[0].name == "B"
    assert _parse_candidates("not json") == []
    assert _parse_candidates('{"foo":1}') == []


def test_match_or_create_new_then_exact(db):
    cat1, is_new, matched_by, sim = match_or_create_category(db, "登入")
    db.commit()
    assert is_new is True and matched_by == "new" and sim is None

    cat2, is_new2, matched_by2, _ = match_or_create_category(db, "登入")
    db.commit()
    assert is_new2 is False and matched_by2 == "exact"
    assert cat2.id == cat1.id


def test_match_or_create_blank_fallback(db):
    cat, is_new, matched_by, _ = match_or_create_category(db, "   ")
    db.commit()
    assert cat.name == "通用" and is_new is True


def test_generate_and_store_items_end_to_end(db):
    p = Project(name="P")
    db.add(p)
    db.flush()

    cands = [
        CandidateItem(name="驗證登入", description="d1", suggested_category="登入"),
        CandidateItem(name="報表圖表", description="d2", suggested_category="報表"),
    ]
    items = generate_and_store_items(db, p.id, None, cands)
    db.commit()

    assert len(items) == 2
    cats = {c.name for c in db.query(TestItemCategory).all()}
    assert {"登入", "報表"} <= cats

    syncs = db.query(TestItemPlatformSync).all()
    assert len(syncs) == 2
    assert all(s.matched_by == "new" for s in syncs)

    # 每個 item 對應到正确的 platform category
    by_id = {c.id: c for c in db.query(TestItemCategory).all()}
    assert by_id[items[0].category_id].name == "登入"
    assert by_id[items[1].category_id].name == "報表"
    assert all(it.is_newly_created for it in items)


def test_generate_reuses_existing_category(db):
    p = Project(name="P")
    db.add(p)
    db.flush()
    # 先於 platform 建立既有類別
    db.add(TestItemCategory(name="登入", code="cat-login"))
    db.commit()

    items = generate_and_store_items(db, p.id, None, [CandidateItem(name="x", suggested_category="登入")])
    db.commit()
    assert items[0].is_newly_created is False
    sync = db.query(TestItemPlatformSync).filter_by(test_item_id=items[0].id).first()
    assert sync.matched_by == "exact" and sync.similarity == 1.0


def test_source_spec_file_recorded(db):
    from app.models.project import SpecFile

    p = Project(name="P")
    db.add(p)
    db.flush()
    sf = SpecFile(project_id=p.id, file_name="s.txt", format="txt", status="done", raw_text="x")
    db.add(sf)
    db.flush()

    items = generate_and_store_items(db, p.id, sf.id, [CandidateItem(name="y", suggested_category="c")])
    db.commit()
    assert items[0].source_spec_file_id == sf.id
