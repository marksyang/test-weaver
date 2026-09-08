"""SQLAlchemy 模型匯出。

匯入所有模型模組，讓 Base.metadata 收錄全部資料表（供 create_all / Alembic autogenerate）。
"""
from .base import Base
from .rag import KnowledgeChunk, RagQueryLog, SourceType
from .project import Project, SpecFile
from .platform import TestItemCategory
from .test_item import TestItem, TestItemPlatformSync
from .test_plan import TestPlan, TestFunction, TestCase, TestPlanItem
from .self_test import SelfTest
from .defect import TestExecution, Defect
from .revision import TestPlanRevisionRequest
from .report import AiReport
from .user import User
from .team import Team, TeamMember
from .audit import AuditLog

__all__ = [
    "Base",
    # RAG
    "KnowledgeChunk",
    "RagQueryLog",
    "SourceType",
    # M1 / 專案
    "Project",
    "SpecFile",
    # 共通類別平台
    "TestItemCategory",
    # 測試項目
    "TestItem",
    "TestItemPlatformSync",
    # M2 三層測試結構
    "TestPlan",
    "TestFunction",
    "TestCase",
    "TestPlanItem",
    # M3 自測
    "SelfTest",
    # M4 缺陷 / 執行
    "TestExecution",
    "Defect",
    # M5 修改要求
    "TestPlanRevisionRequest",
    # M6 報表 / AI
    "AiReport",
    # M8 使用者 / 角色
    "User",
    # 多團隊（v1.1 T1）
    "Team",
    "TeamMember",
    # FR-5 稽核日誌
    "AuditLog",
]
