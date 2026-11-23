from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    port: int = 3000
    database_url: str
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

    @property
    def ip_allowlist(self) -> list[str]:
        return [s.strip() for s in self.admin_login_ip_allowlist.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
