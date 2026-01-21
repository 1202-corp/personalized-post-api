"""
Alembic environment configuration for SQLAlchemy database migrations.

This module configures Alembic to:
- Use sync psycopg2 driver for migrations (Alembic requires sync connections)
- Auto-generate migrations based on SQLAlchemy models
- Handle both online and offline migration modes

Note: The application uses asyncpg for async operations, but Alembic
migrations run with sync psycopg2 driver.
"""

from logging.config import fileConfig
import sys

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import models for autogenerate - all models must be imported
from app.models import Base
from app.config import get_settings

# Alembic Config object
config = context.config

# Setup logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate - includes all imported models
target_metadata = Base.metadata

# Get database URL from settings and convert async to sync driver
# Application uses asyncpg, but Alembic requires sync psycopg2
settings = get_settings()
if "+asyncpg" in settings.database_url:
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
elif "+psycopg2" not in settings.database_url and "postgresql" in settings.database_url:
    # Fallback: assume asyncpg if not specified
    sync_url = settings.database_url.replace("postgresql://", "postgresql+psycopg2://")
else:
    sync_url = settings.database_url

if not sync_url.startswith("postgresql"):
    sys.exit(f"Error: Invalid database URL for Alembic. Expected PostgreSQL, got: {sync_url[:20]}...")

config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
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
