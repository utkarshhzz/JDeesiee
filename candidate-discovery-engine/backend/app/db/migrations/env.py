"""
Alembic migration environment configuration.

WHAT THIS FILE DOES:
    When you run `alembic revision --autogenerate`, Alembic:
    1. Imports all your ORM models (via target_metadata)
    2. Connects to your database
    3. Compares the models to the actual tables
    4. Generates a migration file with the differences

    When you run `alembic upgrade head`, Alembic:
    1. Connects to the database
    2. Checks which migrations have been applied (alembic_version table)
    3. Runs any pending migrations in order

WHY ASYNC?
    Our app uses asyncpg (the async PostgreSQL driver). Alembic needs to
    use the same driver to avoid installing a second sync driver just for
    migrations. So we configure Alembic to run in async mode.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# ──────────────────────────────────────────────────────────────────────
# CRITICAL: Import ALL models BEFORE running migrations.
# This import triggers the models package __init__.py, which imports
# every model class. Alembic discovers tables through Base.metadata,
# and models only register with Base when their classes are imported.
# ──────────────────────────────────────────────────────────────────────
from app.models import Base  # noqa: F401 — import needed for side effects

# Alembic Config object — provides access to alembic.ini values
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is the metadata that Alembic uses to detect model changes.
# Base.metadata contains the schema of ALL models that inherit from Base.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This generates SQL scripts without connecting to a database.
    Useful for: reviewing migration SQL before applying it, or
    generating scripts for a DBA to apply manually.

    Usage: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """
    Helper that runs migrations using an existing database connection.
    Separated out so both online sync and async paths can use it.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations in 'online' async mode.

    WHY ASYNC?
    Our DATABASE_URL uses asyncpg (postgresql+asyncpg://...).
    Regular Alembic uses synchronous connections by default.
    This function creates an async engine specifically for migrations.

    pool_class=NullPool: Don't use connection pooling for migrations.
    Migrations are one-off operations, not long-running servers.
    Using a pool here would waste resources.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the actual database.

    This wraps the async migration function since Alembic's entry point
    is synchronous but our database connection is async.
    """
    asyncio.run(run_async_migrations())


# ──────────────────────────────────────────────────────────────────────
# ENTRY POINT: Alembic calls one of these based on --sql flag
# ──────────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
