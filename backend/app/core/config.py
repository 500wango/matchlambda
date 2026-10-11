from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL
from typing import Optional


from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = ROOT_DIR.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(ROOT_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "mlq_admin"
    # Left blank only for local setups that rely on Postgres trust auth. A blank
    # value logs a loud startup warning instead of being a required field, so
    # existing developer .env files keep working.
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "matchlambda"

    JWT_SECRET: str  # Required — must be set in .env; empty default removed to prevent token forgery
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Anti-abuse: maximum free trials granted per client IP per 24h. When the
    # quota is exhausted new accounts still register but start on the FREE tier.
    TRIAL_MAX_PER_IP_PER_DAY: int = 3

    # Used only while the database has zero administrators.
    INITIAL_ADMIN_EMAIL: Optional[str] = None
    INITIAL_ADMIN_PASSWORD: Optional[str] = None

    @field_validator("JWT_SECRET")
    @classmethod
    def jwt_secret_must_be_present(cls, value: str) -> str:
        secret = "" if value is None else str(value).strip()
        if len(secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters.")
        return secret

    @model_validator(mode="after")
    def warn_on_blank_postgres_password(self):
        if not str(self.POSTGRES_PASSWORD or "").strip():
            import logging

            logging.getLogger("matchlambda").warning(
                "POSTGRES_PASSWORD is empty. Postgres will be reached without "
                "a password — acceptable only for local trust-auth development. "
                "Set a strong POSTGRES_PASSWORD before any shared deployment."
            )
        return self

    APP_ORIGIN: str = "http://localhost:3000"
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # When true, the API also accepts http://localhost:3000 and
    # http://127.0.0.1:3000 as credentialed CORS origins. Off by default so a
    # production deployment never trusts a browser running on the server host.
    ALLOW_LOCAL_ORIGINS: bool = False

    # Swagger/ReDoc stay off unless a deployment opts in.
    SHOW_DOCS: bool = False

    # Asyncpg pool. NullPool was exhausting Postgres under concurrent API traffic.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # 0 ignores X-Forwarded-For. Behind one trusted proxy, set 1.
    TRUSTED_PROXY_HOPS: int = 0
    # Comma-separated CIDRs of the proxies allowed to set X-Forwarded-For.
    # Required whenever TRUSTED_PROXY_HOPS > 0: requests whose socket peer is
    # not in this list have their XFF header ignored (anti-spoofing fallback).
    TRUSTED_PROXY_CIDRS: str = ""

    THE_ODDS_API_KEY: Optional[str] = None
    NOWPAYMENTS_API_KEY: Optional[str] = None
    NOWPAYMENTS_IPN_SECRET: Optional[str] = None
    NOWPAYMENTS_IPN_CALLBACK_URL: Optional[str] = None

    # Explicit opt-in for mocked provider calls (local/dev only). Never inferred
    # from the API key prefix — a leaked IPN secret must not be able to credit
    # invoices without the provider reconciliation lookup in real deployments.
    PAYMENTS_SANDBOX_MODE: bool = False

    # Hard cap on the raw webhook body read before signature verification.
    WEBHOOK_MAX_BODY_BYTES: int = 65536

    @property
    def async_database_url(self) -> str:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

    @property
    def sync_database_url(self) -> str:
        return URL.create(
            drivername="postgresql+psycopg2",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


settings = Settings()
