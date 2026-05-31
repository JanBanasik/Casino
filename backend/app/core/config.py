from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Inteligentne Kasyno API"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://casino:casino@localhost:15432/casino"
    redis_url: str = "redis://localhost:16379/0"

    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    table_state_ttl_seconds: int = 3600

    ws_ticket_ttl_seconds: int = 120
    ws_auth_timeout_seconds: int = 10

    # Comma-separated list of allowed CORS origins (frontend URLs).
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
