"""create knowledge_chunk and rag_query_log (RAG) tables

Revision ID: 0001_rag
Revises:
Create Date: 2026-07-01 00:00:00

注意：完整專案中，本遷移的 ``down_revision`` 應串接至既有 schema head（例如
建立 project / spec_file / test_case / defect 等表的那版）；此處為可獨立執行的
樣本，故暫設為 None。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "0001_rag"
down_revision = None  # full project: chain to the schema head revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunk",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=True),
        sa.Column(
            "content",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=False,
        ),
        sa.Column("token_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("vector_store_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "source_type IN ('spec', 'plan', 'case', 'defect', 'report')",
            name="ck_knowledge_chunk_source_type",
        ),
        sa.Index("ix_knowledge_chunk_source", "source_type", "source_id"),
    )

    op.create_table(
        "rag_query_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # FK to user（user 表建立後補 constraint）
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("top_k", sa.Integer(), server_default="5", nullable=False),
        sa.Column("matched_chunks_json", sa.JSON(), nullable=True),
        sa.Column(
            "answer",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_rag_query_log_user_created", "user_id", "created_at"),
    )


def downgrade() -> None:
    op.drop_index("ix_rag_query_log_user_created", table_name="rag_query_log")
    op.drop_table("rag_query_log")
    op.drop_index("ix_knowledge_chunk_source", table_name="knowledge_chunk")
    op.drop_table("knowledge_chunk")
