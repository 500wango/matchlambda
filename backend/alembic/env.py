import sys
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Migrations must run in CI before an application secret exists. The placeholder
# only satisfies Settings' JWT_SECRET validation inside this short-lived process;
# it never reaches the application. It is announced on stderr rather than applied
# silently, and hardened environments can set ALEMBIC_ALLOW_PLACEHOLDER_SECRET=0
# to fail fast instead.
def _jwt_secret_is_provided() -> bool:
    """True when JWT_SECRET comes from the environment or one of the .env files
    app.core.config reads. Mirrors that lookup order without importing Settings,
    which is what we are trying to satisfy in the first place."""
    if os.environ.get("JWT_SECRET"):
        return True
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for env_file in (
        os.path.join(os.path.dirname(backend_dir), ".env"),
        os.path.join(backend_dir, ".env"),
        ".env",
    ):
        try:
            with open(env_file, encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    key, separator, value = line.partition("=")
                    if separator and key.strip() == "JWT_SECRET" and value.strip():
                        return True
        except OSError:
            continue
    return False


if not _jwt_secret_is_provided():
    if os.environ.get("ALEMBIC_ALLOW_PLACEHOLDER_SECRET", "1") == "1":
        os.environ["JWT_SECRET"] = "alembic-offline-placeholder-secret-32ch"
        print(
            "[alembic] JWT_SECRET is not set anywhere; using a local placeholder "
            "for this migration process only. Set JWT_SECRET, or "
            "ALEMBIC_ALLOW_PLACEHOLDER_SECRET=0 to fail fast instead.",
            file=sys.stderr,
        )

from app.core.config import settings
from app.core.database import Base
import app.models  # Ensure all models are registered

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.sync_database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = settings.sync_database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=False,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
