"""create M1 tables (project/spec_file/platform/test_item/sync)

Revision ID: 0002_m1
Revises: 0001_rag
Create Date: 2026-07-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision: str = "0002_m1"
down_revision: Union[str, None] = "0001_rag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "spec_file",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), server_default="", nullable=False),
        sa.Column("format", sa.String(length=16), server_default="txt", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("raw_text", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=True),
        sa.Column("parsed_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spec_file_project_id", "spec_file", ["project_id"])

    op.create_table(
        "test_item_category",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["test_item_category.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "test_item",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_newly_created",
            sa.Boolean(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("source_spec_file_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["test_item_category.id"]),
        sa.ForeignKeyConstraint(["source_spec_file_id"], ["spec_file.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_item_project_id", "test_item", ["project_id"])

    op.create_table(
        "test_item_platform_sync",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("test_item_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("matched_by", sa.String(length=16), server_default="exact", nullable=False),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["test_item_id"], ["test_item.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["test_item_category.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_test_item_platform_sync_test_item_id",
        "test_item_platform_sync",
        ["test_item_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_test_item_platform_sync_test_item_id", table_name="test_item_platform_sync")
    op.drop_table("test_item_platform_sync")
    op.drop_index("ix_test_item_project_id", table_name="test_item")
    op.drop_table("test_item")
    op.drop_table("test_item_category")
    op.drop_index("ix_spec_file_project_id", table_name="spec_file")
    op.drop_table("spec_file")
    op.drop_table("project")
