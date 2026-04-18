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

    # Logging (D-2)
    # DH_LOG_FORMAT=json → structured JSON to stderr for ELK/Loki.
    # DH_LOG_FORMAT=plain → human-readable single-line for local dev.
    LOG_FORMAT: str = os.environ.get("DH_LOG_FORMAT", "json")
    LOG_LEVEL: str = os.environ.get("DH_LOG_LEVEL", "INFO")

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Centralized paths (P2 / D-1: env-driven with sane defaults).
    #
    # Every path below is derived from PROJECT_ROOT (auto-detected as the
    # parent of backend/) unless overridden via environment variables. This
    # removes 52 hardcoded absolute paths from the codebase and keeps the
    # backend portable across cloud, on-premise and freemium deployments.
    #
    # Override any of the following by setting the matching env var:
    #   DH_PROJECT_ROOT, DH_BACKEND_ROOT, DH_OUTPUT_DIR, DH_METADATA_DIR,
    #   DH_CHROMA_PATH, DH_RAG_ENV_PATH, DH_LLM_CONFIG_PATH,
    #   DH_SFDX_PROJECT_PATH, DH_FORCE_APP_PATH, DH_AGENTS_DIR.
    PROJECT_ROOT: Path = Path(
        os.environ.get("DH_PROJECT_ROOT")
        or str(Path(__file__).resolve().parent.parent.parent)
    )
    BACKEND_ROOT: Path = Path(
        os.environ.get("DH_BACKEND_ROOT")
        or str(Path(__file__).resolve().parent.parent)
    )
    OUTPUT_DIR: Path = Path(os.environ.get("DH_OUTPUT_DIR") or str(Path(__file__).resolve().parent.parent / "outputs"))
    METADATA_DIR: Path = Path(os.environ.get("DH_METADATA_DIR") or str(Path(__file__).resolve().parent.parent / "metadata"))
    CHROMA_PATH: Path = Path(os.environ.get("DH_CHROMA_PATH") or "/opt/digital-humans/rag/chromadb_data")
    RAG_ENV_PATH: Path = Path(os.environ.get("DH_RAG_ENV_PATH") or "/opt/digital-humans/rag/.env")
    LLM_CONFIG_PATH: Path = Path(
        os.environ.get("DH_LLM_CONFIG_PATH")
        or str(Path(__file__).resolve().parent.parent / "config" / "llm_routing.yaml")
    )
    SFDX_PROJECT_PATH: Path = Path(os.environ.get("DH_SFDX_PROJECT_PATH") or "/opt/digital-humans/salesforce-workspace/digital-humans-sf")
    FORCE_APP_PATH: Path = Path(
        os.environ.get("DH_FORCE_APP_PATH")
        or "/opt/digital-humans/salesforce-workspace/digital-humans-sf/force-app/main/default"
    )
    AGENTS_DIR: str = os.environ.get("DH_AGENTS_DIR") or "/opt/digital-humans/salesforce-agents"

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
