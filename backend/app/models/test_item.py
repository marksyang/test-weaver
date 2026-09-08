"""測試項目與平台同步模型（FR-1 / FR-1a / M7）。

test_item 必須對應 platform 的 category_id（FR-1a 強制規則）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TestItem(Base):
    __tablename__ = "test_item"
    __test__ = False  # 非測試類別，避免 pytest 收集

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("test_item_category.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_newly_created: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    source_spec_file_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("spec_file.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class TestItemPlatformSync(Base):
    __tablename__ = "test_item_platform_sync"
    __test__ = False  # 非測試類別，避免 pytest 收集

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_item_id: Mapped[int] = mapped_column(
        ForeignKey("test_item.id"), nullable=False, index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("test_item_category.id"), nullable=False
    )
    matched_by: Mapped[str] = mapped_column(
        String(16), nullable=False, default="exact", server_default="exact"
    )
    similarity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
