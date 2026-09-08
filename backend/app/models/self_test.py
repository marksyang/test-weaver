"""FR-2a / M3：自測紀錄（Self Test）。

雙向對應：同時綁定 test_function_id 與 test_case_id（皆必填，未綁定即拒收）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SelfTest(Base):
    __tablename__ = "self_test"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), nullable=False, index=True
    )
    tester: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # FR-2a：兩者皆必填
    test_function_id: Mapped[int] = mapped_column(
        ForeignKey("test_function.id"), nullable=False, index=True
    )
    test_case_id: Mapped[int] = mapped_column(
        ForeignKey("test_case.id"), nullable=False, index=True
    )
    # pass / fail
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
