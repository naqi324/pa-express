from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .engines.catalog import method_support
from .schemas import (
    BedrockCredentials,
    ClaudeAuthMethod,
    ClaudeModelId,
    OpenAiGptAuthMethod,
    OpenAiGptModelId,
    ReasoningEffort,
)


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables only."""

    model_config = SettingsConfigDict(env_prefix="PA_EXPRESS_", extra="ignore")

    hosted_mode: bool = False
    claude_enabled: bool = True
    openai_gpt_enabled: bool = True
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
    # Anthropic Claude. Model ids are the first-party ids; the Bedrock method
    # maps them to regional inference profiles (see engines/catalog.py).
    claude_auth_method: ClaudeAuthMethod = "cli"
    claude_model_id: ClaudeModelId = "claude-opus-5-5"
    claude_effort: Optional[ReasoningEffort] = "high"
    claude_max_tokens: int = Field(default=16000, ge=1024, le=64000)
    claude_command: str = "claude"
    # Runtime-only secrets (never a committed default). The settings form keeps
    # them in server memory for one session.
    anthropic_api_key: SecretStr = SecretStr("")
    bedrock_region: str = "us-west-2"
    bedrock_credentials: BedrockCredentials = "profile"
    # Empty means the standard boto3 credential chain (no named profile).
    aws_profile: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    # OpenAI GPT.
    openai_gpt_auth_method: OpenAiGptAuthMethod = "cli"
    openai_gpt_model_id: OpenAiGptModelId = "gpt-6-astra"
    openai_gpt_effort: Optional[ReasoningEffort] = "high"
    codex_command: str = "codex"
    openai_api_key: SecretStr = SecretStr("")
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

    @field_validator("session_cookie_name")
    @classmethod
    def validate_cookie_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("session_cookie_name must not be empty")
        return normalized

    @model_validator(mode="after")
    def check_efforts_against_catalog(self) -> "Settings":
        # Fail at startup on an effort the model does not take. A model without
        # an effort setting (Claude Haiku 4.5) quietly drops the default effort.
        self.claude_effort = _catalog_effort(
            "anthropic_claude", self.claude_model_id, self.claude_auth_method, self.claude_effort
        )
        self.openai_gpt_effort = _catalog_effort(
            "openai_gpt",
            self.openai_gpt_model_id,
            self.openai_gpt_auth_method,
            self.openai_gpt_effort,
        )
        return self


def _catalog_effort(
    engine_id: str, model_id: str, method: str, effort: Optional[ReasoningEffort]
) -> Optional[ReasoningEffort]:
    support = method_support(engine_id, model_id, method)
    if support is None:
        raise ValueError(f"{model_id} is not offered through the {method} auth method")
    if not support.efforts:
        return None
    if effort is None:
        return support.default_effort
    if effort not in support.efforts:
        raise ValueError(f"{model_id} through {method} does not take the {effort} effort")
    return effort


@lru_cache
def get_settings() -> Settings:
    return Settings()
