import os
import sys

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from agent_protect_server.config import db_config  # noqa: E402
from agent_protect_server.db import Base  # noqa: E402
import agent_protect_server.models  # noqa: E402,F401

config = context.config

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = db_config.url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = db_config.url
    connectable = create_engine(url, future=True, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
