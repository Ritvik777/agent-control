"""Server configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentProtectServerDatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="DB_",
    )

    host: str = "localhost"
    port: int = 5432
    user: str = "agent_protect"
    password: str = "agent_protect"
    database: str = "agent_protect"
    driver: str = "psycopg"

    @property
    def url(self) -> str:
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
    )

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # API settings
    api_version: str = "v1"
    api_prefix: str = "/api"


db_config = AgentProtectServerDatabaseConfig()
settings = Settings()

