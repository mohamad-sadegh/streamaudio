from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote_plus, urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    port: int = 3000
    database_url: str | None = None
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    jwt_secret: str
    domain: str = "localhost"
    cookie_secure: bool = True
    admin_bootstrap_user: str = "admin"
    admin_bootstrap_password: str = ""
    admin_login_ip_allowlist: str = ""
    mediamtx_api_url: str = "http://mediamtx:9997"
    listen_token_ttl_seconds: int = 3600
    session_ttl_seconds: int = 60 * 60 * 12
    cookie_name: str = "sa_session"
    csrf_cookie_name: str = "sa_csrf"

    conninfo: str = Field(default="", exclude=True)

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("JWT_SECRET is required and must not be empty")
        return v

    @model_validator(mode="after")
    def build_conninfo(self) -> Settings:
        if self.database_url and self.database_url.strip():
            url = self.database_url.strip()
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://") :]
            self.conninfo = url
        elif self.postgres_user and self.postgres_password and self.postgres_db:
            user = quote_plus(self.postgres_user)
            password = quote_plus(self.postgres_password)
            db = quote_plus(self.postgres_db)
            self.conninfo = (
                f"postgresql://{user}:{password}"
                f"@{self.postgres_host}:{self.postgres_port}/{db}"
            )
        else:
            raise ValueError(
                "Set DATABASE_URL or POSTGRES_USER + POSTGRES_PASSWORD + POSTGRES_DB"
            )
        return self

    @property
    def ip_allowlist(self) -> list[str]:
        return [
            s.strip()
            for s in self.admin_login_ip_allowlist.split(",")
            if s.strip()
        ]

    @property
    def db_target(self) -> str:
        try:
            parsed = urlparse(self.conninfo)
            return f"{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"
        except Exception:  # noqa: BLE001
            return "(unparsed)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
