from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    port: int = 3000

    postgres_user: str
    postgres_password: str
    postgres_db: str
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

    @field_validator("jwt_secret", "postgres_user", "postgres_db")
    @classmethod
    def required_nonempty(cls, v: str) -> str:
        if v is None or not str(v).strip():
            raise ValueError("value is required and must not be empty")
        return v

    @field_validator("postgres_password")
    @classmethod
    def password_present(cls, v: str) -> str:
        if v is None:
            raise ValueError("POSTGRES_PASSWORD is required")
        return v

    @model_validator(mode="after")
    def warn_host(self) -> Settings:
        host = (self.postgres_host or "").strip()
        if host in {"localhost", "127.0.0.1", "stream"}:
            raise ValueError(
                f"POSTGRES_HOST={host!r} is invalid inside Docker. "
                "Use POSTGRES_HOST=postgres (the compose service name)."
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
        return (
            f"{self.postgres_host}:{self.postgres_port}/"
            f"{self.postgres_db} (user={self.postgres_user})"
        )

    def psycopg_kwargs(self) -> dict:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": self.postgres_password,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
