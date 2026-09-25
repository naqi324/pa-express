from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables only."""

    model_config = SettingsConfigDict(env_prefix="PA_EXPRESS_", extra="ignore")

    hosted_mode: bool = False
    bedrock_enabled: bool = True
    codex_enabled: bool = True
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:5175", "http://localhost:5175"]
    )
    trusted_hosts: list[str] = Field(
        default_factory=lambda: ["127.0.0.1", "localhost", "testserver"]
    )
    session_cookie_name: str = "pa_express_session"
    session_idle_minutes: int = Field(default=60, ge=5, le=1440)
    session_cookie_secure: bool = False
    session_cookie_same_site: Literal["lax", "strict", "none"] = "lax"
    bedrock_model_id: str = "us.anthropic.claude-sonnet-5"
    bedrock_region: str = "us-west-2"
    bedrock_auth_method: Literal["profile", "access_keys"] = "profile"
    bedrock_effort: Literal["low", "medium", "high", "max"] = "high"
    bedrock_max_tokens: int = Field(default=8192, ge=1024, le=64000)
    # Empty means the standard boto3 credential chain (no named profile).
    aws_profile: str = ""
    # Runtime-only AWS access keys (never a committed default); used when
    # bedrock_auth_method == "access_keys". Populated per session, not from disk.
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    codex_command: str = "codex"
    codex_model_id: str = "gpt-5.5"
    codex_effort: Literal["low", "medium", "high", "xhigh"] = "xhigh"
    engine_timeout_seconds: float = Field(default=120.0, ge=1.0, le=600.0)
    mock_processing_seconds: float = Field(default=2.2, ge=0.0, le=10.0)

    @field_validator("allowed_origins", "trusted_hosts", mode="before")
    @classmethod
    def parse_csv_or_list(cls, value: object) -> object:
        if value is None:
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("bedrock_model_id")
    @classmethod
    def normalize_bedrock_model_id(cls, value: str) -> str:
        # Some Claude launch profiles append a "[1m]" context suffix; boto3
        # Converse expects the raw Bedrock inference profile id.
        return value.strip().removesuffix("[1m]")

    @field_validator("session_cookie_name")
    @classmethod
    def validate_cookie_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_cookie_name must not be empty")
        return normalized


@lru_cache
def get_settings() -> Settings:
    return Settings()
