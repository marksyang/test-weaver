"""create audit_log.team_id (multi-team cross-team audit)

Revision ID: 0011_audit_team
Revises: 0010_multi_team
Create Date: 2026-07-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_audit_team"
down_revision: Union[str, None] = "0010_multi_team"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("team_id", sa.Integer(), nullable=True))
    op.create_index("ix_audit_log_team_id", "audit_log", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_team_id", table_name="audit_log")
    op.drop_column("audit_log", "team_id")
