"""Alembic 環境設定。

- 自 backend/ 執行：``alembic -c alembic.ini upgrade head``
- 資料庫連線優先讀取環境變數 ``DATABASE_URL``（例：mysql+pymysql://user:pass@host/testweaver）。
- ``target_metadata = Base.metadata``，故 autogenerate 能對照模型。

說明：目前專案僅有 RAG 兩表的遷移（down_revision=None）；其餘表
（project / spec_file / test_case / defect 等）建好後，請以新的 revision
串接在本 head 之後。
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 使 `app` 套件可匯入（自 backend/ 目錄執行 alembic 時）
BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models.base import Base  # noqa: E402
import app.models  # noqa: F401,E402  匯入所有模型以填滿 Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 資料庫 URL：優先 DATABASE_URL 環境變數
db_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """offline 模式：僅產生 SQL，不連庫。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """online 模式：實際連線執行遷移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
