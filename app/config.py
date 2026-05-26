"""
Application configuration loaded from environment variables.
Uses pydantic-settings for validation and type coercion.
"""

from functools import lru_cache
from typing import Any, Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All environment variables used by the AI Incident API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "local"
    log_level: str = "INFO"
    api_port: int = 8000
    webhook_shared_secret: str = ""

    # Gemini
    ai_provider: Literal["mock", "gemini"] = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-lite"

    # GLPI REST API
    glpi_base_url: str = "http://glpi/apirest.php"
    glpi_app_token: str = ""
    glpi_user_token: str = ""
    glpi_default_entity_id: int = 0
    glpi_default_category_id: Optional[int] = None
    glpi_default_requester_id: Optional[int] = None
    glpi_default_technician_id: Optional[int] = None
    glpi_create_task: bool = True

    @field_validator(
        "glpi_default_category_id",
        "glpi_default_requester_id",
        "glpi_default_technician_id",
        mode="before",
    )
    @classmethod
    def empty_str_to_none(cls, value: Any) -> Any:
        if value == "" or value is None:
            return None
        return value

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key.strip())

    @property
    def ai_configured(self) -> bool:
        if self.ai_provider == "mock":
            return True
        return self.gemini_configured

    @property
    def glpi_configured(self) -> bool:
        return bool(self.glpi_user_token.strip())


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (reload on process restart)."""
    return Settings()
