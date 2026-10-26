from typing import Any, List, Union
import json
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "HookPulse"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Security & Defaults
    SECRET_KEY: str = "supersecretkey-hookpulse-change-in-production-32bytes"
    DEFAULT_ENDPOINT_SLUG: str = "ep_taxguard_prod"
    DEFAULT_ENDPOINT_NAME: str = "TaxGuard Fiscal Batch Webhook"
    DEFAULT_SIGNING_SECRET: str = "whsec_taxguard_secure_token_secret_123"
    DEFAULT_TARGET_URL: str = "http://backend:8000/api/v1/simulator/mock-target?behavior=success"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://hookpulse:hookpulse_secret@localhost:5432/hookpulse_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        elif isinstance(v, list):
            return v
        raise ValueError("Invalid format for BACKEND_CORS_ORIGINS")


settings = Settings()
