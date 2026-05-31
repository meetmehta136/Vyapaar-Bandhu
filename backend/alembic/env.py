"""Alembic env — configured to use app's database URL and models."""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool, create_engine

from alembic import context

import os, sys
from dotenv import load_dotenv

# Ensure backend/ is on sys.path so app imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all models so Base.metadata is complete
from app.models.base import Base  # noqa: E402

target_metadata = Base.metadata

# Database URL from environment (matches app/core/database.py logic)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5433/vyapaar_bandhu",
)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connect_args = {}
    if "render.com" in DATABASE_URL or "dpg-" in DATABASE_URL:
        connect_args["sslmode"] = "require"

    connectable = create_engine(DATABASE_URL, connect_args=connect_args, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
