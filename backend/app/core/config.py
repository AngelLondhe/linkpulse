"""Application settings, loaded from environment variables (and an optional .env file)."""

import ipaddress
import socket
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Typed configuration. Every value can be overridden with an env var of the same name."""

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "Linkpulse"
    log_level: str = "INFO"

    # Infrastructure
    database_url: str = Field(
        description="SQLAlchemy async URL, e.g. postgresql+asyncpg://user:pass@host:5432/db"
    )
    redis_url: str = "redis://localhost:6379/0"
    redis_socket_timeout_seconds: float = 0.5

    # Security
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    ip_hash_salt: SecretStr = Field(min_length=16)

    # HTTP
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    trusted_proxies: Annotated[list[str], NoDecode] = []

    # Rate limiting (Redis sliding window; rules in app/services/rate_limiter.py)
    rate_limit_enabled: bool = True

    # Caching / click pipeline
    link_cache_ttl_seconds: int = 3600
    stats_cache_ttl_seconds: int = 60
    click_queue_key: str = "clicks:queue"
    worker_batch_size: int = Field(default=100, ge=1, le=1000)
    # Names this worker's in-flight list; keep it stable across restarts (compose sets it).
    worker_id: str = Field(default_factory=socket.gethostname)
    worker_block_timeout_seconds: int = Field(default=1, ge=1)
    worker_max_backoff_seconds: float = 30.0

    # Google Safe Browsing (optional). Without a key, destination URLs are not checked.
    safe_browsing_api_key: SecretStr | None = None
    safe_browsing_timeout_seconds: float = 2.0

    # Geo lookup (MaxMind GeoLite2 City). Missing file => country/city "Unknown".
    geoip_db_path: str = "data/GeoLite2-City.mmdb"

    @field_validator("cors_origins", "trusted_proxies", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept comma-separated strings so lists are easy to set in hosting dashboards."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("trusted_proxies")
    @classmethod
    def _validate_proxies(cls, value: list[str]) -> list[str]:
        for entry in value:
            ipaddress.ip_network(entry, strict=False)  # raises ValueError on bad IP/CIDR
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_cors(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("Wildcard CORS is not allowed; list explicit origins")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached)."""
    return Settings()  # required fields come from the environment
