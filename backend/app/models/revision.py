"""FR-3a / M5：測試計畫修改要求（Test Plan Revision Request）。

當 Defect 無對應 Test Case（test_case_id 為 NULL，覆蓋缺口）時自動建立；
接受（accepted）→ 補建案例 + 測試計畫版本 +1（接 M2）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

_LONGTEXT = Text().with_variant(LONGTEXT(), "mysql")


class TestPlanRevisionRequest(Base):
    __tablename__ = "test_plan_revision_request"
    __test__ = False  # 非測試類別，避免 pytest 收集

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    defect_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("defect.id"), nullable=True, index=True
    )
    test_plan_id: Mapped[int] = mapped_column(
        ForeignKey("test_plan.id"), nullable=False, index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    proposed_change: Mapped[Optional[str]] = mapped_column(_LONGTEXT, nullable=True)
    # 狀態機（§6.3）：open → accepted → done，或 open → rejected
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open", server_default="open"
    )
    requested_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
