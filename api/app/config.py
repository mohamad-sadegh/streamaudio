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

    # Preferred: discrete Postgres settings (no URL parsing issues)
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # Optional legacy override — ignored when POSTGRES_USER/PASSWORD/DB are set
    database_url: str | None = None

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

    # Built at validation time for psycopg
    conninfo: str = ""

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_nonempty(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("JWT_SECRET is required and must not be empty")
        return v

    @model_validator(mode="after")
    def build_conninfo(self) -> Settings:
        # Always prefer discrete vars — passwords may contain @ : / # etc.
        if self.postgres_user and self.postgres_password is not None and self.postgres_db:
            # libpq keyword format — password is not URL-parsed
            # Escape backslashes and spaces in password if needed via quoting
            def q(value: str) -> str:
                # Wrap in single quotes and escape single quotes for libpq
                return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

            self.conninfo = " ".join(
                [
                    f"host={self.postgres_host}",
                    f"port={self.postgres_port}",
                    f"dbname={q(self.postgres_db)}",
                    f"user={q(self.postgres_user)}",
                    f"password={q(self.postgres_password)}",
                ]
            )
            return self

        if self.database_url and self.database_url.strip():
            url = self.database_url.strip()
            if url.startswith("postgres://"):
                url = "postgresql://" + url[len("postgres://") :]
            self.conninfo = url
            return self

        raise ValueError(
            "Set POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB "
            "(recommended), or DATABASE_URL"
        )

    @property
    def ip_allowlist(self) -> list[str]:
        return [
            s.strip()
            for s in self.admin_login_ip_allowlist.split(",")
            if s.strip()
        ]

    @property
    def db_target(self) -> str:
        if self.postgres_user and self.postgres_db:
            return (
                f"{self.postgres_host}:{self.postgres_port}/"
                f"{self.postgres_db} (user={self.postgres_user})"
            )
        return "(database_url override)"


@lru_cache
def get_settings() -> Settings:
    return Settings()
