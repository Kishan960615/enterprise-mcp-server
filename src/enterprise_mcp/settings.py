"""Typed application configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server settings with restrictive production validation."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    database_url: str = "sqlite+aiosqlite:///./enterprise_mcp.db"
    redis_url: str | None = None
    auth_mode: Literal["development", "oidc"] = "development"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    development_tenant: str = "demo"
    development_subject: str = "demo-user"
    log_level: str = "INFO"
    tool_timeout_seconds: float = Field(default=30, gt=0, le=300)
    max_result_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    max_sql_rows: int = Field(default=100, ge=1, le=500)
    file_roots: dict[str, Path] = Field(default_factory=dict)
    rest_operations: dict[str, dict[str, str]] = Field(default_factory=dict)
    knowledge_base_url: str | None = None
    github_token: str | None = None
    github_allowed_repositories: list[str] = Field(default_factory=list)
    cors_origins: list[str] = Field(default_factory=list)

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production":
            if self.auth_mode != "oidc":
                raise ValueError("production requires OIDC authentication")
            if not all((self.oidc_issuer, self.oidc_audience, self.oidc_jwks_url)):
                raise ValueError("production OIDC settings are incomplete")
            if "*" in self.cors_origins:
                raise ValueError("wildcard CORS is forbidden in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("production requires PostgreSQL")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""

    return Settings()
