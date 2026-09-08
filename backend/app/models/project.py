"""專案與規格書模型（FR-1 / M1）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

_LONGTEXT = Text().with_variant(LONGTEXT(), "mysql")


class Project(Base):
    __tablename__ = "project"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 多團隊（v1.1 T1）：所屬團隊；NULL = legacy 未指派（T1 對所有人可見，T2 會指派團隊後收緊）
    team_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("team.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SpecFile(Base):
    __tablename__ = "spec_file"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="txt")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    raw_text: Mapped[Optional[str]] = mapped_column(_LONGTEXT, nullable=True)
    parsed_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
