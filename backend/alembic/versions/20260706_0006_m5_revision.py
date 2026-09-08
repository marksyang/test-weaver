"""create M5 table (test_plan_revision_request)

Revision ID: 0006_m5
Revises: 0005_m4
Create Date: 2026-07-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0006_m5"
down_revision: Union[str, None] = "0005_m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_plan_revision_request",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("defect_id", sa.Integer(), nullable=True),
        sa.Column("test_plan_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "proposed_change",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["defect_id"], ["defect.id"]),
        sa.ForeignKeyConstraint(["test_plan_id"], ["test_plan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_test_plan_revision_request_defect_id",
        "test_plan_revision_request",
        ["defect_id"],
    )
    op.create_index(
        "ix_test_plan_revision_request_test_plan_id",
        "test_plan_revision_request",
        ["test_plan_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_test_plan_revision_request_test_plan_id", table_name="test_plan_revision_request"
    )
    op.drop_index(
        "ix_test_plan_revision_request_defect_id", table_name="test_plan_revision_request"
    )
    op.drop_table("test_plan_revision_request")
