"""
Rate limiting configuration for Digital Humans API.
Uses slowapi for request rate limiting.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request: Request) -> str:
    """Get client IP, considering X-Forwarded-For header for proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=["200/minute"],  # Default limit for all routes
    headers_enabled=True,  # Add X-RateLimit-* headers
    strategy="fixed-window"
)


# Rate limit presets for different endpoint types
class RateLimits:
    """Rate limit constants for different endpoint categories."""
    # Auth endpoints - strict to prevent brute force
    AUTH_LOGIN = "5/minute"
    AUTH_REGISTER = "3/minute"
    AUTH_PASSWORD_RESET = "3/minute"
    
    # Standard API endpoints
    API_DEFAULT = "100/minute"
    API_READ = "200/minute"      # GET requests
    API_WRITE = "50/minute"      # POST/PUT/DELETE
    
    # Project operations
    PROJECT_CREATE = "10/minute"
    PROJECT_UPDATE = "30/minute"
    
    # Expensive LLM operations - very strict
    EXECUTE_SDS = "10/hour"       # SDS generation (costs tokens)
    EXECUTE_BUILD = "5/hour"      # BUILD phase (even more expensive)
    
    # File operations
    FILE_UPLOAD = "20/minute"
    FILE_DOWNLOAD = "50/minute"


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded errors."""
    logger.warning(
        f"Rate limit exceeded: {exc.detail} for {get_client_ip(request)} on {request.url.path}"
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down.",
            "error": "rate_limit_exceeded",
            "retry_after": exc.detail.split("per")[0].strip() if exc.detail else "60 seconds"
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": exc.detail or "unknown"
        }
    )
