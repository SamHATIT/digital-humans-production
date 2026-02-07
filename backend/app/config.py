"""
Application configuration using Pydantic settings.
"""
import os
import secrets
import logging
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings."""

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/digital_humans"

    # JWT
    # SECRET_KEY: In production, must be set in .env
    # In development (DEBUG=True), auto-generates if not set
    SECRET_KEY: Optional[str] = None
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
    OPENAI_API_KEY: str = ""

    # Agents
    AGENTS_DIR: str = "/opt/digital-humans/salesforce-agents"

    # Centralized paths (P2: eliminate hardcoded absolute paths)
    PROJECT_ROOT: Path = Path("/root/workspace/digital-humans-production")
    BACKEND_ROOT: Path = Path("/root/workspace/digital-humans-production/backend")
    OUTPUT_DIR: Path = Path("/app/outputs")
    METADATA_DIR: Path = Path("/app/metadata")
    CHROMA_PATH: Path = Path("/opt/digital-humans/rag/chromadb_data")
    RAG_ENV_PATH: Path = Path("/opt/digital-humans/rag/.env")
    LLM_CONFIG_PATH: Path = Path("/root/workspace/digital-humans-production/backend/config/llm_routing.yaml")
    SFDX_PROJECT_PATH: Path = Path("/root/workspace/salesforce-workspace/digital-humans-sf")
    FORCE_APP_PATH: Path = Path("/root/workspace/salesforce-workspace/digital-humans-sf/force-app/main/default")

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @model_validator(mode="after")
    def validate_secret_key(self):
        """
        SEC-003: Validate SECRET_KEY based on environment.
        - Production (DEBUG=False): SECRET_KEY is required
        - Development (DEBUG=True): Auto-generate if not set, with warning
        """
        if self.SECRET_KEY:
            return self
        
        if not self.DEBUG:
            # Production: require explicit SECRET_KEY
            raise ValueError(
                "SECRET_KEY is required in production mode (DEBUG=False). "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # Development: auto-generate with warning
        generated_key = secrets.token_urlsafe(32)
        print(
            "\n⚠️  WARNING: SECRET_KEY not set - auto-generated for development.\n"
            "   This key will change on each restart. Set SECRET_KEY in .env for persistence.\n"
            f"   Generated: {generated_key[:8]}...{generated_key[-8:]}\n"
        )
        # Use object.__setattr__ to bypass Pydantic's frozen model protection
        object.__setattr__(self, "SECRET_KEY", generated_key)
        return self

    class Config:
        extra = "ignore"
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
