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

    # VAGUE 2 / LOT 4 — creation du schema au demarrage, decorrelee de DEBUG.
    #
    # `main.py` faisait `if settings.DEBUG: Base.metadata.create_all()`. DEBUG
    # vaut True par defaut et la production tourne en DEBUG=True : le critere
    # de fin de LOT-G, « boot sans create_all », etait declare et non tenu.
    # La commodite reste disponible, mais elle se demande — elle ne s'herite
    # plus d'un drapeau qui veut dire autre chose.
    #
    # None = non pose (comportement par defaut : pas de create_all).
    AUTO_CREATE_SCHEMA: Optional[bool] = None

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

    # Salesforce default org (LOT-E bis / gem:CONF-01).
    #
    # These used to be hardcoded defaults on the SalesforceConfig dataclass —
    # a real org alias, a real username, a real org id. Any project that failed
    # to load its own credentials silently fell back to that org: cross-tenant
    # reads, and deployments landing in the wrong Salesforce org.
    #
    # There is no default any more. A deployment that needs a default org sets
    # these explicitly; otherwise SalesforceConfig.require() raises.
    SF_ORG_ALIAS: Optional[str] = None
    SF_USERNAME: Optional[str] = None
    SF_ORG_ID: Optional[str] = None
    SF_INSTANCE_URL: Optional[str] = None
    SF_API_VERSION: str = "67.0"

    # Credentials encryption (LOT-E / kim:SEC-06).
    # Dedicated Fernet key for `app.utils.encryption`. Required in production
    # (DEBUG=False): see `validate_encryption_key` below. Deriving the key
    # from SECRET_KEY is a DEBUG-only convenience — in production it silently
    # made every stored credential undecryptable as soon as SECRET_KEY moved.
    CREDENTIALS_ENCRYPTION_KEY: Optional[str] = None

    # Centralized paths (P2 / D-1: env-driven, PROJECT_ROOT-relative defaults).
    #
    # Every path below is derived from PROJECT_ROOT (auto-detected as the
    # parent of backend/) unless overridden via environment variables. No
    # default is an absolute machine-specific path: a checkout must be
    # runnable as-is on cloud, on-premise and developer machines.
    #
    # Deployments whose data lives outside the checkout (the VPS keeps the
    # ChromaDB store under /opt) MUST set the matching env var explicitly —
    # guessing a host-specific location is what P2 set out to remove.
    #
    # Override any of the following by setting the matching env var:
    #   DH_PROJECT_ROOT, DH_BACKEND_ROOT, DH_OUTPUT_DIR, DH_METADATA_DIR,
    #   DH_CHROMA_PATH, DH_LLM_CONFIG_PATH, DH_DELIVERABLES_DIR,
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
    CHROMA_PATH: Path = Path(
        os.environ.get("DH_CHROMA_PATH")
        or str(Path(__file__).resolve().parent.parent.parent / "rag" / "chromadb_data")
    )
    LLM_CONFIG_PATH: Path = Path(
        os.environ.get("DH_LLM_CONFIG_PATH")
        or str(Path(__file__).resolve().parent.parent / "config" / "llm_routing.yaml")
    )
    # FIX-PERSIST-001 archive location (sf_admin_service).
    DELIVERABLES_DIR: Path = Path(
        os.environ.get("DH_DELIVERABLES_DIR")
        or str(Path(__file__).resolve().parent.parent.parent / "livrables")
    )
    SFDX_PROJECT_PATH: Path = Path(
        os.environ.get("DH_SFDX_PROJECT_PATH")
        or str(Path(__file__).resolve().parent.parent.parent / "salesforce-workspace" / "digital-humans-sf")
    )
    FORCE_APP_PATH: Path = Path(
        os.environ.get("DH_FORCE_APP_PATH")
        or str(
            Path(__file__).resolve().parent.parent.parent
            / "salesforce-workspace" / "digital-humans-sf"
            / "force-app" / "main" / "default"
        )
    )
    AGENTS_DIR: str = os.environ.get("DH_AGENTS_DIR") or str(
        Path(__file__).resolve().parent.parent.parent / "salesforce-agents"
    )

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

    @model_validator(mode="after")
    def validate_encryption_key(self):
        """
        kim:SEC-06 — a dedicated credentials key is mandatory in production.

        Historically `app.utils.encryption` fell back to deriving a Fernet key
        from SECRET_KEY. Combined with the SECRET_KEY auto-generation above,
        any environment that forgot to set SECRET_KEY got a brand-new
        encryption key on every restart, silently turning every stored
        credential into an "Invalid token" error. Fail loudly instead.
        """
        if self.CREDENTIALS_ENCRYPTION_KEY or self.DEBUG:
            return self

        raise ValueError(
            "CREDENTIALS_ENCRYPTION_KEY is required in production mode "
            "(DEBUG=False). Generate one with: python -c \"from "
            "cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"\n"
            "If credentials were previously encrypted with a key derived from "
            "SECRET_KEY, re-encrypt them before switching:\n"
            "    python scripts/rotate_encryption_key.py "
            "--old-secret-key-derived --new-key <new-key>"
        )

    class Config:
        extra = "ignore"
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
