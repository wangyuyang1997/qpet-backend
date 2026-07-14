import sys
from pathlib import Path

# 把 backend 目录加入 path，让 `app` 可导入
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from logging.config import fileConfig
from sqlalchemy import pool
from alembic import context
from app.config import settings
from app.models.base import Base

# 导入所有模型，确保 metadata 完整
import app.models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url_sync,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    connectable = create_engine(settings.database_url_sync, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
