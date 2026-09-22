

from logging.config import fileConfig
from alembic import context
from sqlmodel import SQLModel

# Import application runtime settings
from app.core.config import settings

# MUST import all database domain models so SQLModel metadata detects them
from app.domains.audit.models import AuditLog
from app.domains.auth.models import User, Member
from app.domains.campaigns.models import Campaign, Pledge
from app.domains.donations.models import Donation, Receipt, IdempotencyKey
# from app.domains.webhooks.models import ProcessedEvent

# Setup Alembic configuration object
config = context.config

# Interpret logging configuration file
if config.config_file_name:
    fileConfig(config.config_file_name)

# Set DB URL dynamically from app settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Assign SQLModel metadata target for schema auto-diffing
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates raw SQL scripts)."""
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
    """Run migrations in 'online' mode (applies migration directly to DB)."""
    from sqlalchemy import engine_from_config, pool

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()