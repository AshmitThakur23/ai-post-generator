"""
Configuration settings for the Data Layer Service
"""

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    # App settings
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # CORS settings
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database settings
    DATABASE_URL: str = "sqlite:///./data.db"
    DB_ECHO: bool = False

    # Service settings
    SERVICE_NAME: str = "data-layer-service"
    SERVICE_TIMEOUT: int = 30

    # API Keys (optional - fill in .env later)
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_IMAGE_MODEL: str = "gemini-2.5-flash-image"
    GEMINI_IMAGE_FALLBACK_MODEL: str = "gemini-2.0-flash-preview-image-generation"
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_IMAGE_MODEL: str = "@cf/black-forest-labs/flux-2-klein-4b"
    HUGGINGFACE_API_KEY: str = ""
    GOOGLE_TRENDS_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
