"""
Audit Middleware - Automatically logs all HTTP requests.
CORE-001: Captures API activity for security and debugging.
"""
import time
import uuid
import asyncio
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.models.audit import ActorType, ActionCategory
import logging

logger = logging.getLogger(__name__)

# Paths to exclude from audit logging
EXCLUDED_PATHS = {
    "/health",
    "/api/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}

# Low-priority paths (GET only)
LOW_PRIORITY_PATHS = {
    "/api/agents",
}


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs HTTP requests to audit_logs.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if request.url.path in EXCLUDED_PATHS:
            return await call_next(request)
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Extract client info
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")[:500]
        
        # Record start time
        start_time = time.time()
        
        # Process request
        response = None
        error_message = None
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Determine success
            status_code = response.status_code if response else 500
            success = "true" if 200 <= status_code < 400 else "false"
            
            # Only log non-GET or failed requests
            should_log = (
                request.method != "GET" or 
                success == "false" or
                request.url.path not in LOW_PRIORITY_PATHS
            )
            
            if should_log:
                # Log in background to not slow down response
                try:
                    # Import here to avoid circular imports at startup
                    from app.services.audit_service import audit_service
                    
                    action = self._method_to_action(request.method)
                    entity_type, entity_id = self._parse_path(request.url.path)
                    project_id = self._extract_id_from_path(request.url.path, "projects")
                    execution_id = self._extract_id_from_path(request.url.path, "executions")
                    
                    # Set request context
                    audit_service.set_request_context(
                        request_id=request_id,
                        ip_address=ip_address,
                        user_agent=user_agent
                    )
                    
                    # Log synchronously but in try/except
                    audit_service.log(
                        actor_type=ActorType.API,
                        actor_id=ip_address,
                        action=action,
                        action_detail=f"{request.method} {request.url.path}",
                        entity_type=entity_type,
                        entity_id=entity_id,
                        project_id=project_id,
                        execution_id=execution_id,
                        success=success,
                        error_message=error_message,
                        duration_ms=duration_ms,
                        extra_data={
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": status_code,
                        }
                    )
                    
                    audit_service.clear_request_context()
                except Exception as e:
                    logger.error(f"Audit middleware failed: {e}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract real client IP"""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        return request.client.host if request.client else "unknown"
    
    def _method_to_action(self, method: str) -> ActionCategory:
        """Map HTTP method to action category"""
        mapping = {
            "GET": ActionCategory.OTHER,
            "POST": ActionCategory.DATA_CREATE,
            "PUT": ActionCategory.DATA_UPDATE,
            "PATCH": ActionCategory.DATA_UPDATE,
            "DELETE": ActionCategory.DATA_DELETE,
        }
        return mapping.get(method, ActionCategory.OTHER)
    
    def _parse_path(self, path: str) -> tuple[str | None, str | None]:
        """Extract entity type and ID from path"""
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "api":
            entity_type = parts[1].rstrip("s")
            entity_id = parts[2] if len(parts) > 2 and parts[2].isdigit() else None
            return entity_type, entity_id
        return None, None
    
    def _extract_id_from_path(self, path: str, resource: str) -> int | None:
        """Extract numeric ID for a specific resource"""
        parts = path.strip("/").split("/")
        try:
            if resource in parts:
                idx = parts.index(resource)
                if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                    return int(parts[idx + 1])
        except (ValueError, IndexError):
            pass
        return None
