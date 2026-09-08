"""Seed a realistic demo dataset (offline) for UI screenshots.

由 scripts/capture-shots.sh 呼叫；DATABASE_URL 指向一個 temp SQLite 檔（不污染 repo）。
走真實服務層（execute_case / create_manual_defect / revision），確保資料與 API 一致。
計畫留在 in_progress；報表在截圖時由 UI「完成計畫並生成報表」產生。

用法（通常不用手動跑，直接執行 scripts/capture-shots.sh）：
  PYTHONPATH=backend DATABASE_URL="sqlite:////tmp/demo.db" python3 scripts/seed_demo.py
"""
import os

# DB 由呼叫端（capture-shots.sh）透過 DATABASE_URL 提供；此處僅 fallback。
os.environ.setdefault("DATABASE_URL", "sqlite:///./shots_demo.db")
os.environ.setdefault("AUTH_ENABLED", "true")

from app.core.db import _get_engine, session_scope
from app.models.base import Base
from app.models.project import Project
from app.models.test_plan import TestPlan, TestFunction, TestCase
from app.services.defect_service import execute_case, create_manual_defect
from app.services.revision_service import (
    create_revision_request,
    ensure_revision_for_defect,
)
from app.models.user import User
from app.models.team import Team, TeamMember
from app.services.auth_service import ensure_default_admin, make_user

Base.metadata.create_all(_get_engine())

# 確保 admin 存在（不依賴 lifespan，供登入）——env 預設 admin/admin123
ensure_default_admin()

_fn = [0]
_case = [0]


def add_fn(s, plan_id, name, desc=""):
    _fn[0] += 1
    f = TestFunction(test_plan_id=plan_id, name=name, description=desc or None, sort_order=_fn[0])
    s.add(f)
    s.flush()
    return f


def add_case(s, fn_id, name, status, priority="medium", pre="", steps="", exp=""):
    _case[0] += 1
    c = TestCase(
        test_function_id=fn_id,
        name=name,
        status=status,
        priority=priority,
        precondition=pre or None,
        steps=steps or None,
        expected_result=exp or None,
        sort_order=_case[0],
    )
    s.add(c)
    s.flush()
    return c


ids = {}
with session_scope() as s:
    # 多團隊示範：一個 populated 團隊 + 成員（供 UI 截圖：header switcher + TeamsPage）
    admin_name = os.getenv("AUTH_ADMIN_USERNAME", "admin")
    admin = s.query(User).filter_by(username=admin_name).first()
    lead = make_user(s, "chen-lead", "pw", role="qa_lead")
    t1 = make_user(s, "wang-tester", "pw", role="tester")
    t2 = make_user(s, "li-tester", "pw", role="tester")
    s.flush()
    team = Team(name="電商品質組", description="結帳系統品保團隊")
    s.add(team)
    s.flush()
    for uid, role in [
        (admin.id, "owner"),
        (lead.id, "qa_lead"),
        (t1.id, "tester"),
        (t2.id, "tester"),
    ]:
        s.add(TeamMember(team_id=team.id, user_id=uid, role=role))

    proj = Project(name="電商結帳系統", description="示範專案（自動產生資料）", team_id=team.id)
    s.add(proj)
    s.flush()

    plan = TestPlan(project_id=proj.id, name="結帳核心回歸測試", version=1, status="in_progress")
    s.add(plan)
    s.flush()

    f1 = add_fn(s, plan.id, "使用者登入", "帳號密碼登入流程")
    c1 = add_case(s, f1.id, "正確帳號密碼可登入", "passed", "high",
                  steps="1. 輸入帳號\n2. 輸入正確密碼\n3. 按下登入", exp="成功進入首頁")
    c2 = add_case(s, f1.id, "錯誤密碼應被拒絕", "failed", "high",
                  steps="1. 輸入帳號\n2. 輸入錯誤密碼", exp="顯示驗證失敗訊息")
    c3 = add_case(s, f1.id, "空值必填驗證", "blocked", "medium",
                  pre="等待測試環境就緒", exp="顯示欄位必填提示")

    f2 = add_fn(s, plan.id, "帳號註冊", "新用戶註冊流程")
    c4 = add_case(s, f2.id, "可用 email 註冊成功", "passed", "high", exp="收到驗證信")
    c5 = add_case(s, f2.id, "重複 email 應被拒絕", "failed", "medium", exp="提示 email 已存在")

    f3 = add_fn(s, plan.id, "角色權限控制", "依角色限制可見功能")
    c6 = add_case(s, f3.id, "admin 可見全部選單", "passed", "medium", exp="選單完整顯示")
    c7 = add_case(s, f3.id, "tester 應隱藏平台選單", "failed", "high", exp="平台選單被隱藏")

    f4 = add_fn(s, plan.id, "報表匯出", "CSV / PDF 匯出（尚未撰寫案例）")  # coverage gap

    for cid, res, who, actual in [
        (c1.id, "pass", "qa-alice", "符合預期"),
        (c2.id, "fail", "qa-alice", "未顯示驗證失敗，直接登入成功"),
        (c3.id, "blocked", "qa-alice", "測試環境未就緒"),
        (c4.id, "pass", "qa-bob", "符合預期"),
        (c5.id, "fail", "qa-bob", "重複 email 未提示，重複建立成功"),
        (c6.id, "pass", "qa-bob", "符合預期"),
        (c7.id, "fail", "qa-alice", "tester 仍可看到「共通類別平台」選單"),
    ]:
        execute_case(s, cid, res, who, actual)

    da = create_manual_defect(s, "登入頁在行動版寬度斷版", "行動版（<375px）表單溢出",
                              "high", "high", test_case_id=c4.id)
    da.status = "in_progress"
    da.assigned_to = "dev-ui"

    dl = create_manual_defect(s, "註冊成功提示文案錯誤", "文案與設計稿不一致",
                              "low", "low", test_case_id=c6.id)
    dl.status = "resolved"
    dl.assigned_to = "dev-ui"

    dc = create_manual_defect(s, "規格未定義逾時自動登出", "無對應測試案例（覆蓋缺口），建議補件",
                              "high", "high", test_case_id=None)
    ensure_revision_for_defect(s, dc, test_plan_id=plan.id)

    create_revision_request(s, test_plan_id=plan.id,
                            reason="覆蓋缺口：「報表匯出」功能尚無測試案例",
                            proposed_change="為報表匯出新增 CSV 與 PDF 匯出案例各 1",
                            requested_by="qa_lead")

    ids = {"project": proj.id, "plan": plan.id}

print("SEED_OK project=%s plan=%s" % (ids["project"], ids["plan"]))
