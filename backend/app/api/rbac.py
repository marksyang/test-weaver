"""端點級 RBAC：角色 → 可存取模組（mirror 前端 src/auth/roles.ts）。

權限以「模組」為單位，與前端選單矩陣一致；每個模組對應一個或多個 API router，
在 main.py 以 ``require_module("<module>")`` 套用到該模組的**全部端點**——每個端點
都有明確、集中、可測試的角色要求（不再有隱含的「任何已登入角色皆可」）。

- 核心四模組（rag / plan / self_test / defect）：admin、qa_lead、tester 皆可。
- report：admin、qa_lead（**tester 不可**，含「完成計畫並產生報表」）。
- platform / settings（users + audit）：admin。
- teams：另以 team membership 細化（見 teams.py / team_service）。

``AUTH_ENABLED=false`` 時 ``get_current_user`` 回 None → ``require_module`` 放過
（no-op），與既有離線/免登入行為一致。
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException

from .deps import get_current_user
from ..models.user import User

# 模組 → 允許角色（mirror frontend/src/auth/roles.ts 的 ROLE_MENU）
ROLE_MODULES: dict[str, tuple[str, ...]] = {
    "rag": ("admin", "qa_lead", "tester"),
    "plan": ("admin", "qa_lead", "tester"),
    "self_test": ("admin", "qa_lead", "tester"),
    "defect": ("admin", "qa_lead", "tester"),
    "report": ("admin", "qa_lead"),
    "platform": ("admin",),
    "settings": ("admin",),
}


def require_module(module: str):
    """回傳一個 FastAPI 相依：當前使用者角色須在 ``ROLE_MODULES[module]`` 內，否則 403。

    AUTH 未啟用（get_current_user 回 None）時放過，維持免登入 no-op。
    """
    allowed = ROLE_MODULES[module]

    def _dep(current: Optional[User] = Depends(get_current_user)) -> Optional[User]:
        if current is None:  # auth disabled → permissive
            return None
        if current.role not in allowed:
            raise HTTPException(403, f"role '{current.role}' cannot access module '{module}'")
        return current

    return _dep
