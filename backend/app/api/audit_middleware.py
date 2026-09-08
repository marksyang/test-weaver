"""FR-5 稽核 middleware：記錄狀態變更請求（POST/PATCH/DELETE）。

``AUDIT_ENABLED=false``（預設）時為 no-op，不影響既有測試與離線開發。
以獨立 ``session_scope`` 寫入（避免綁定 endpoint session），失敗不擋請求。
"""
from __future__ import annotations

import os
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..core.db import session_scope
from ..services.audit_service import record_audit

MUTATING = {"POST", "PATCH", "DELETE"}


def audit_enabled() -> bool:
    return os.getenv("AUDIT_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)

        if request.method in MUTATING and audit_enabled():
            try:
                user = getattr(request.state, "user", None)
                username = (
                    getattr(request.state, "audit_username", None)
                    or getattr(user, "username", None)
                )
                action = getattr(request.state, "audit_action", None) or (
                    f"{request.method} {request.url.path}"
                )
                with session_scope() as db:
                    record_audit(
                        db,
                        action=action,
                        method=request.method,
                        path=str(request.url.path),
                        status_code=response.status_code,
                        user_id=getattr(user, "id", None),
                        username=username,
                        ip=(request.client.host if request.client else None),
                    )
            except Exception:  # noqa: BLE001 - 稽核失敗不影響請求
                pass

        return response
