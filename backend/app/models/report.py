"""FR-4 / M6：AI 報表分析結果（ai_report）。

測試計畫完成時觸發：匯總指標 + LLM 產出分析建議，存於此表。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

_LONGTEXT = Text().with_variant(LONGTEXT(), "mysql")


class AiReport(Base):
    __tablename__ = "ai_report"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), nullable=False, index=True
    )
    test_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("test_plan.id"), nullable=True, index=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON 陣列字串（[{"title":..., "detail":...}, ...]）
    recommendations: Mapped[Optional[str]] = mapped_column(_LONGTEXT, nullable=True)
    metrics_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
