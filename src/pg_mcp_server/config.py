"""Configuration management using pydantic-settings."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection configuration."""

    model_config = SettingsConfigDict(
        env_prefix="PG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    user: str = Field(..., description="Database user")
    password: SecretStr = Field(..., description="Database password")

    # Connection pool settings
    pool_size: int = Field(default=5, ge=1, le=20, description="Connection pool size")
    pool_timeout: float = Field(
        default=30.0, gt=0, description="Pool connection timeout in seconds"
    )

    # Query settings
    statement_timeout: int = Field(
        default=30000, ge=1000, description="Statement timeout in milliseconds"
    )
    default_schema: str = Field(default="public", description="Default schema for operations")

    @property
    def async_url(self) -> str:
        """Build async connection URL for asyncpg."""
        return (
            f"postgresql+asyncpg://{self.user}:"
            f"{self.password.get_secret_value()}@"
            f"{self.host}:{self.port}/{self.database}"
        )


class ServerSettings(BaseSettings):
    """MCP server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    transport: str = Field(default="stdio", pattern="^(stdio|http)$", description="Transport type")
    host: str = Field(default="0.0.0.0", description="HTTP server host")
    port: int = Field(default=8080, ge=1, le=65535, description="HTTP server port")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="json", pattern="^(json|text)$", description="Log output format"
    )


class Settings(BaseSettings):
    """Root settings combining all configuration."""

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
    )

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore[arg-type]
    server: ServerSettings = Field(default_factory=ServerSettings)


def get_settings() -> Settings:
    """Factory function to create settings instance."""
    return Settings()
