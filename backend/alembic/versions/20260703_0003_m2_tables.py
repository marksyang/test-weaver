"""create M2 three-tier tables (test_plan/test_function/test_case/test_plan_item)

Revision ID: 0003_m2
Revises: 0002_m1
Create Date: 2026-07-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0003_m2"
down_revision: Union[str, None] = "0002_m1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_plan",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_plan_project_id", "test_plan", ["project_id"])

    op.create_table(
        "test_function",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_plan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["test_plan_id"], ["test_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_function_test_plan_id", "test_function", ["test_plan_id"])

    op.create_table(
        "test_case",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_function_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("precondition", sa.Text(), nullable=True),
        sa.Column(
            "steps", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=True
        ),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column(
            "priority", sa.String(length=16), server_default="medium", nullable=False
        ),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["test_function_id"], ["test_function.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_case_test_function_id", "test_case", ["test_function_id"])

    op.create_table(
        "test_plan_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_plan_id", sa.Integer(), nullable=False),
        sa.Column("test_item_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["test_plan_id"], ["test_plan.id"]),
        sa.ForeignKeyConstraint(["test_item_id"], ["test_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("test_plan_id", "test_item_id"),
    )
    op.create_index("ix_test_plan_item_test_plan_id", "test_plan_item", ["test_plan_id"])
    op.create_index("ix_test_plan_item_test_item_id", "test_plan_item", ["test_item_id"])


def downgrade() -> None:
    op.drop_index("ix_test_plan_item_test_item_id", table_name="test_plan_item")
    op.drop_index("ix_test_plan_item_test_plan_id", table_name="test_plan_item")
    op.drop_table("test_plan_item")
    op.drop_index("ix_test_case_test_function_id", table_name="test_case")
    op.drop_table("test_case")
    op.drop_index("ix_test_function_test_plan_id", table_name="test_function")
    op.drop_table("test_function")
    op.drop_index("ix_test_plan_project_id", table_name="test_plan")
    op.drop_table("test_plan")
