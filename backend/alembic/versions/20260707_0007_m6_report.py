"""create M6 table (ai_report)

Revision ID: 0007_m6
Revises: 0006_m5
Create Date: 2026-07-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0007_m6"
down_revision: Union[str, None] = "0006_m5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_report",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("test_plan_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "recommendations",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column("metrics_json", sa.JSON(), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("generated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["test_plan_id"], ["test_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_report_project_id", "ai_report", ["project_id"])
    op.create_index("ix_ai_report_test_plan_id", "ai_report", ["test_plan_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_report_test_plan_id", table_name="ai_report")
    op.drop_index("ix_ai_report_project_id", table_name="ai_report")
    op.drop_table("ai_report")
