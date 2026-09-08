"""FR-2：三層測試結構（Test Plan → Test Function → Test Case）+ 版本。

test_plan_item：計畫引用的 test_item（FR-2「建計畫可引用 test_items」）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

_LONGTEXT = Text().with_variant(LONGTEXT(), "mysql")


class TestPlan(Base):
    __tablename__ = "test_plan"
    __test__ = False  # 非測試類別，避免 pytest 收集

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    # 狀態機（§6.1）：draft → in_progress → completed → archived
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", server_default="draft"
    )
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class TestFunction(Base):
    __tablename__ = "test_function"
    __test__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_plan_id: Mapped[int] = mapped_column(
        ForeignKey("test_plan.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class TestCase(Base):
    __tablename__ = "test_case"
    __test__ = False

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_function_id: Mapped[int] = mapped_column(
        ForeignKey("test_function.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    precondition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps: Mapped[Optional[str]] = mapped_column(_LONGTEXT, nullable=True)
    expected_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    # draft/ready/passed/failed/blocked
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    # 支援案例拖曳排序（對照 test_function.sort_order 的擴充）
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class TestPlanItem(Base):
    """計畫引用的測試項目（plan ↔ item 多對多關聯）。"""

    __tablename__ = "test_plan_item"
    __test__ = False
    __table_args__ = (UniqueConstraint("test_plan_id", "test_item_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_plan_id: Mapped[int] = mapped_column(
        ForeignKey("test_plan.id"), nullable=False, index=True
    )
    test_item_id: Mapped[int] = mapped_column(
        ForeignKey("test_item.id"), nullable=False, index=True
    )
