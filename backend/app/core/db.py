"""資料庫存取：lazy engine + FastAPI 相依 + Celery 用 session_scope。

- ``get_db``：FastAPI 每個 request 一個 session（測試可 override）。
- ``session_scope``：Celery task / 背景邏輯用的 context manager（自動 commit/rollback）。
- engine 延遲建立，import 本模組不會觸發 DB driver 解析（未裝 pymysql 也不會掛）。
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _default_url() -> str:
    # 預設用 SQLite 便於本機開發；實務以 DATABASE_URL 覆蓋（如 mysql+pymysql://...）
    return os.getenv("DATABASE_URL", "sqlite:///./testweaver_dev.db")


_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        url = _default_url()
        kwargs = {} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_engine(url, **kwargs)
    return _engine


def get_db() -> Iterator[Session]:
    """FastAPI 相依：每 request 一個 session。"""
    session = sessionmaker(bind=_get_engine(), autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """背景/工作器用的 session（commit on success, rollback on error）。"""
    session = sessionmaker(bind=_get_engine(), autoflush=False, expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
