"""create M4 tables (test_execution / defect)

Revision ID: 0005_m4
Revises: 0004_m3
Create Date: 2026-07-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_m4"
down_revision: Union[str, None] = "0004_m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_execution",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=False),
        sa.Column("test_plan_id", sa.Integer(), nullable=False),
        sa.Column("executed_by", sa.String(length=128), nullable=True),
        sa.Column("result", sa.String(length=8), nullable=False),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_case.id"]),
        sa.ForeignKeyConstraint(["test_plan_id"], ["test_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_execution_test_case_id", "test_execution", ["test_case_id"])
    op.create_index("ix_test_execution_test_plan_id", "test_execution", ["test_plan_id"])

    op.create_table(
        "defect",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=True),
        sa.Column("test_case_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "severity", sa.String(length=16), server_default="medium", nullable=False
        ),
        sa.Column(
            "priority", sa.String(length=16), server_default="medium", nullable=False
        ),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("assigned_to", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["test_execution.id"]),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_defect_test_case_id", "defect", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_defect_test_case_id", table_name="defect")
    op.drop_table("defect")
    op.drop_index("ix_test_execution_test_plan_id", table_name="test_execution")
    op.drop_index("ix_test_execution_test_case_id", table_name="test_execution")
    op.drop_table("test_execution")
