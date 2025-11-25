"""
Application configuration using Pydantic settings.
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import validator


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/digital_humans"

    # JWT
    # SECRET_KEY must be set in .env - no default value to prevent security issues
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # API
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Digital Humans API"
    DEBUG: bool = True

    # CORS - Autoriser toutes les origines pour débogage
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # File Upload
    MAX_FILE_SIZE: int = 10485760  # 10MB
    UPLOAD_DIR: str = "./uploads"


    # OpenAI
    OPENAI_API_KEY: str

        # Agents
    AGENTS_DIR: str = "/opt/digital-humans/salesforce-agents"

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    class Config:
        extra = "ignore"
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
