"""Server configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentControlServerDatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="DB_",
        extra="ignore",  # Ignore extra fields in .env
    )

    # Allow direct URL override for SQLite in local dev
    url: str | None = None

    # PostgreSQL settings (only used if url is not set)
    host: str = "localhost"
    port: int = 5432
    user: str = "agent_control"
    password: str = "agent_control"
    database: str = "agent_control"
    driver: str = "psycopg"

    def get_url(self) -> str:
        """Get database URL, preferring explicit url if set."""
        if self.url:
            return self.url
        return (
            f"postgresql+{self.driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        )


class Settings(BaseSettings):
    """Server configuration settings."""
    # TODO: Clean this up since we may want to connect to pg, etc., so
    # database_url may have to go

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env (like DB_* fields)
    )

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # API settings
    api_version: str = "v1"
    api_prefix: str = "/api"

    # CORS settings
    cors_origins: list[str] | str = "*"

    def get_cors_origins(self) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(self.cors_origins, str):
            if self.cors_origins == "*":
                return ["*"]
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return self.cors_origins


db_config = AgentControlServerDatabaseConfig()
settings = Settings()

