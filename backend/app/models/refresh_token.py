"""FR-5 延伸：refresh token（可撤銷 / 旋轉）。

access token 短效、無狀態；refresh token 長效但存 DB（以 ``jti`` 為主鍵索引），
支援「登出即撤銷」與「每次 refresh 旋轉」（作廢舊 token、發新 token）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # JWT 的 jti claim（唯一）；作為 DB 中的撤銷/查詢鍵
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # 撤銷時間；NULL = 仍有效（登出或旋轉時設值）
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
