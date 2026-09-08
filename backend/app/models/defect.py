"""FR-3 / M4：案例執行紀錄（test_execution）與缺陷（defect）。

- 任一 Test Case 執行結果為 Fail → 自動開立 1 個 Defect（綁 execution + test_case）。
- defect.test_case_id 可為 NULL（手動補建 / 無案例場景；FR-3a 將觸發 Revision Request）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TestExecution(Base):
    __tablename__ = "test_execution"
    __test__ = False  # 非測試類別，避免 pytest 收集

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_case.id"), nullable=False, index=True
    )
    test_plan_id: Mapped[int] = mapped_column(
        ForeignKey("test_plan.id"), nullable=False, index=True
    )
    executed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # pass / fail / blocked
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    actual_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class Defect(Base):
    __tablename__ = "defect"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_execution.id"), nullable=True
    )
    # 可為 NULL：無對應案例（手動補建 / FR-3a 場景）
    test_case_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_case.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # low / medium / high / critical
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    # 狀態機（§6.2）：open → in_progress → resolved → closed（可 reopened 回 in_progress）
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open", server_default="open"
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
