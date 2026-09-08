"""create M3 self_test table

Revision ID: 0004_m3
Revises: 0003_m2
Create Date: 2026-07-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_m3"
down_revision: Union[str, None] = "0003_m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "self_test",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("tester", sa.String(length=128), nullable=True),
        sa.Column("test_function_id", sa.Integer(), nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(length=8), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["test_function_id"], ["test_function.id"]),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_case.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_self_test_project_id", "self_test", ["project_id"])
    op.create_index("ix_self_test_test_function_id", "self_test", ["test_function_id"])
    op.create_index("ix_self_test_test_case_id", "self_test", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_self_test_test_case_id", table_name="self_test")
    op.drop_index("ix_self_test_test_function_id", table_name="self_test")
    op.drop_index("ix_self_test_project_id", table_name="self_test")
    op.drop_table("self_test")
