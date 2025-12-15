"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import auth, pm_orchestrator, projects, analytics, artifacts, agent_tester, business_requirements, project_chat, sds_versions, change_requests, deployment, quality_dashboard, wizard, subscription
from app.api import audit  # CORE-001: Audit logging API
from app.middleware import AuditMiddleware  # CORE-001: Audit middleware
from app.database import Base, engine
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.rate_limiter import limiter, rate_limit_exceeded_handler
from app.services.notification_service import get_notification_service, shutdown_notification_service
import logging

logger = logging.getLogger(__name__)

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    version="2.0.0",
    description="Digital Humans API for Salesforce specification generation"
)

# SEC-002: Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://72.61.161.222:3002",
        "http://72.61.161.222:3000", 
        "http://srv1064321.hstgr.cloud:3000",
        "http://localhost:3000",
        "http://localhost:3002",
        # Note: "*" removed for security - add specific origins as needed
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CORE-001: Audit logging middleware (logs all HTTP requests)
app.add_middleware(AuditMiddleware)

# Include routers - V1
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(pm_orchestrator.router, prefix=f"{settings.API_V1_PREFIX}/pm-orchestrator")
app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router)

# Include routers - V2 Artifacts & Orchestrator
app.include_router(artifacts.router)

# Agent Tester (Salesforce integration testing)
app.include_router(agent_tester.router, prefix=f"{settings.API_V1_PREFIX}")

# Business Requirements Validation
app.include_router(business_requirements.router)

# Post-SDS Workflow (Chat, Versions, Change Requests)
app.include_router(project_chat.router)
app.include_router(sds_versions.router)
app.include_router(change_requests.router)

# CORE-001: Audit logging API
app.include_router(audit.router, prefix=settings.API_V1_PREFIX)

# BLD-01, DPL-04/05/06: Deployment & Package routes
app.include_router(deployment.router, prefix=settings.API_V1_PREFIX)

# BLD-07: Quality Dashboard routes
app.include_router(quality_dashboard.router, prefix=settings.API_V1_PREFIX)

# Phase 5: Project Configuration Wizard
app.include_router(wizard.router, prefix=settings.API_V1_PREFIX)

# Subscription routes (Section 9)
app.include_router(subscription.router, prefix=f"{settings.API_V1_PREFIX}/subscription", tags=["subscription"])

# Environment routes (Section 6.2, 6.3, 6.4)

# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc}")
    # Handle bytes body (e.g., from form data)
    body = exc.body
    if isinstance(body, bytes):
        try:
            body = body.decode('utf-8')
        except:
            body = "<binary data>"
    
    # Sanitize errors for JSON serialization
    try:
        errors = exc.errors()
    except:
        errors = [{"msg": str(exc)}]
    
    return JSONResponse(
        status_code=422,
        content={"detail": errors, "body": body}
    )

@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {
        "message": "Digital Humans API",
        "version": "2.0.0",
        "status": "healthy",
        "features": ["V1 PM Orchestrator", "V2 Artifacts System", "V2 Orchestrator", "Audit Logging", "Deployment", "Quality Dashboard"]
    }

# PERF-001: Notification service lifecycle
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        await get_notification_service()
        logger.info("NotificationService initialized")
    except Exception as e:
        logger.warning(f"NotificationService failed to initialize (non-critical): {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown."""
    try:
        await shutdown_notification_service()
        logger.info("NotificationService shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down NotificationService: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )

# Quick download endpoint
from fastapi.responses import FileResponse
import os

@app.get("/download/{filename}")
async def download_file(filename: str):
    filepath = f"/app/outputs/{filename}"
    if os.path.exists(filepath):
        return FileResponse(filepath, filename=filename, media_type="application/octet-stream")
    return {"error": "File not found"}
