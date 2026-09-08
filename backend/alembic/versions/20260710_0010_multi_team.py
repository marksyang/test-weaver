"""create multi-team tables (team, team_member) + project.team_id backfill

Revision ID: 0010_multi_team
Revises: 0009_audit
Create Date: 2026-07-10

多團隊（v1.1 T1）：新增 team / team_member；project 加 team_id 並 backfill 到
「預設團隊」。Backfill 邏輯與 ``app/services/team_service.py`` 保持同步
（migration 用 raw SQL 以在 alembic 單一交易內安全執行）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_multi_team"
down_revision: Union[str, None] = "0009_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "team",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_name", "team", ["name"], unique=True)

    op.create_table(
        "team_member",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "role", sa.String(length=16), server_default="tester", nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["team_id"], ["team.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_member"),
    )
    op.create_index("ix_team_member_team_id", "team_member", ["team_id"])
    op.create_index("ix_team_member_user_id", "team_member", ["user_id"])

    op.add_column("project", sa.Column("team_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_project_team_id", "project", "team", ["team_id"], ["id"])

    # ---- backfill（與 team_service.seed_default_teams / backfill_null_projects 同步）----
    c = op.get_bind()
    # 1) 預設團隊
    c.execute(
        sa.text(
            "INSERT INTO team (name, description) "
            "SELECT '預設團隊', '系統自動建立的預設團隊' "
            "WHERE NOT EXISTS (SELECT 1 FROM team WHERE name='預設團隊')"
        )
    )
    # 2) 既有用戶 → membership（role 映射：admin→owner，qa_lead/tester 原樣）
    c.execute(
        sa.text(
            "INSERT INTO team_member (team_id, user_id, role) "
            "SELECT t.id, u.id, CASE WHEN u.role='admin' THEN 'owner' ELSE u.role END "
            "FROM user u INNER JOIN team t ON t.name='預設團隊' "
            "WHERE NOT EXISTS (SELECT 1 FROM team_member tm "
            " WHERE tm.user_id=u.id AND tm.team_id=t.id)"
        )
    )
    # 3) 既有專案 team_id 為空 → 預設團隊
    c.execute(
        sa.text(
            "UPDATE project SET team_id = "
            "(SELECT t.id FROM team t WHERE t.name='預設團隊') "
            "WHERE team_id IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_constraint("fk_project_team_id", "project", type_="foreignkey")
    op.drop_column("project", "team_id")
    op.drop_index("ix_team_member_user_id", table_name="team_member")
    op.drop_index("ix_team_member_team_id", table_name="team_member")
    op.drop_table("team_member")
    op.drop_index("ix_team_name", table_name="team")
    op.drop_table("team")
