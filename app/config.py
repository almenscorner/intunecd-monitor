import json
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — supports sqlite:///./app.db or postgresql://user:pass@host/db
    DATABASE_URL: str = "sqlite:///./app.db"

    SECRET_KEY: str

    # Azure Entra ID / MSAL
    AZURE_CLIENT_ID: str
    AZURE_CLIENT_SECRET: str
    AZURE_TENANT_ID: str
    SCOPE: list[str]
    REDIRECT_PATH: str = "/authorized"

    # Authorization
    ADMIN_ROLE: str

    # Application
    COMPANY_NAME: str = ""
    TIMEZONE: str = "UTC"
    SESSION_LIFETIME_HOURS: int = 3
    APP_VERSION: str = "3.0.0"

    SERVER_NAME: str = ""
    HTTPS_ONLY: bool = False

    # Celery / Redis
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    REDIS_SESSION_URL: str = "redis://redis:6379/1"
    BEAT_DB_URI: Optional[str] = None

    # Optional documentation feature
    DOCUMENTATION_FILE_NAME: Optional[str] = None
    DOCUMENTATION_MAX_LENGTH: Optional[int] = None

    @field_validator("SCOPE", mode="before")
    @classmethod
    def parse_scope(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @property
    def AUTHORITY(self) -> str:
        return f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
