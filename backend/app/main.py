"""FastAPI 入口（RAG + M1~M6 路由 + M8 認證）。

啟動：自 ``backend/`` 目錄執行
    uvicorn app.main:app --reload

認證（FR-5 / M8）：``AUTH_ENABLED=false``（預設）時全域護為 no-op；啟用後
``/auth/*`` 以外皆需 Bearer token，``/platform/*`` 另需 admin 角色。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI

from .api.deps import get_current_user, require_roles
from .api.audit_middleware import AuditMiddleware
from .api.v1.rag import router as rag_router
from .api.v1.projects import router as projects_router
from .api.v1.test_plans import router as test_plans_router
from .api.v1.self_tests import router as self_tests_router
from .api.v1.defects import router as defects_router
from .api.v1.revision_requests import router as revision_router
from .api.v1.reports import router as reports_router
from .api.v1.platform import router as platform_router
from .api.v1.tasks import router as tasks_router
from .api.v1.auth import router as auth_router
from .api.v1.audit import router as audit_router
from .api.v1.users import router as users_router


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # 啟動種子：啟用認證時確保預設 admin（失敗不擋啟動，如 DB 未遷移）
        from .api.deps import auth_enabled
        from .services.auth_service import ensure_default_admin

        if auth_enabled():
            try:
                ensure_default_admin()
            except Exception:  # noqa: BLE001
                pass
        # 確保預設團隊 + membership（多團隊 v1.1 T1；冪等，失敗不擋啟動）
        from .core.db import session_scope
        from .services.team_service import seed_default_teams

        try:
            with session_scope() as db:
                seed_default_teams(db)
        except Exception:  # noqa: BLE001
            pass
        yield

    app = FastAPI(title="TestWeaver API", version="1.0", lifespan=lifespan)

    # 稽核日誌（AUDIT_ENABLED=false 時 no-op）
    app.add_middleware(AuditMiddleware)

    # 公開：認證（login / me）
    app.include_router(auth_router, prefix="/api/v1")

    # 受保護（AUTH_ENABLED=false 時 no-op）
    auth_deps = [Depends(get_current_user)]
    app.include_router(rag_router, prefix="/api/v1", dependencies=auth_deps)
    app.include_router(projects_router, prefix="/api/v1", dependencies=auth_deps)
    app.include_router(test_plans_router, prefix="/api/v1", dependencies=auth_deps)
    app.include_router(self_tests_router, prefix="/api/v1", dependencies=auth_deps)
    app.include_router(defects_router, prefix="/api/v1", dependencies=auth_deps)
    app.include_router(revision_router, prefix="/api/v1", dependencies=auth_deps)
    app.include_router(reports_router, prefix="/api/v1", dependencies=auth_deps)
    app.include_router(tasks_router, prefix="/api/v1", dependencies=auth_deps)
    # 類別平台：額外要求 admin 角色
    app.include_router(
        platform_router,
        prefix="/api/v1",
        dependencies=auth_deps + [Depends(require_roles("admin"))],
    )
    # 稽核日誌：額外要求 admin 角色
    app.include_router(
        audit_router,
        prefix="/api/v1",
        dependencies=auth_deps + [Depends(require_roles("admin"))],
    )
    # 帳號管理：額外要求 admin 角色
    app.include_router(
        users_router,
        prefix="/api/v1",
        dependencies=auth_deps + [Depends(require_roles("admin"))],
    )

    return app


app = create_app()
