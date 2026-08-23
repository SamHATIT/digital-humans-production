"""
Main FastAPI application entry point.
"""
# Load environment variables from .env file FIRST
from dotenv import load_dotenv
load_dotenv()

# P5: Initialize structured JSON logging before any app imports
from app.logging_config import setup_logging
setup_logging()

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import auth, pm_orchestrator, projects, analytics, artifacts, agent_tester, business_requirements, project_chat, sds_versions, change_requests, quality_dashboard, wizard, subscription, documents, hitl_routes, billing, config as config_routes, deliverables, concierge_routes
from app.api import audit  # CORE-001: Audit logging API
from app.middleware import AuditMiddleware, BuildEnabledMiddleware, ExecutionContextMiddleware  # CORE-001 + C-4 + D-2
from app.database import Base, engine, SessionLocal
from app.schema_bootstrap import encryption_posture, should_auto_create_schema
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.rate_limiter import limiter, rate_limit_exceeded_handler
from app.services.notification_service import get_notification_service, shutdown_notification_service
import asyncio
import logging

logger = logging.getLogger(__name__)

# Schema management.
#
# cla:OPS-02 / kim:PROD-05 — `Base.metadata.create_all()` used to run at import
# time. Two consequences, both real:
#   1. it creates tables from the models without stamping `alembic_version`, so
#      the first `alembic upgrade head` in production either fails or silently
#      skips columns → schema drift;
#   2. it made the process unable to even start when PostgreSQL was down, so a
#      database outage turned into "the API will not boot" instead of "the API
#      reports unhealthy".
#
# VAGUE 2 / LOT 4 — la garde etait `if settings.DEBUG:`, et LOT-G annoncait
# « boot sans create_all ». Or DEBUG vaut True par defaut (config.py) et **la
# production tourne en DEBUG=True** : create_all y tournait a chaque
# demarrage. Les requetes `pg_catalog.pg_type` vues au boot du 23/08 etaient
# la verification d'existence des enums que fait create_all(checkfirst=True) —
# pas autre chose. Le critere etait declare et non tenu.
#
# La decision ne depend plus de DEBUG : elle se demande par AUTO_CREATE_SCHEMA,
# et elle est journalisee dans les deux sens. Voir app/schema_bootstrap.py.
_create_schema, _schema_reason = should_auto_create_schema(
    debug=settings.DEBUG, auto_create=settings.AUTO_CREATE_SCHEMA
)
if _create_schema:
    logger.warning("Schema auto-creation ENABLED — %s", _schema_reason)
    Base.metadata.create_all(bind=engine)
else:
    logger.info("Schema auto-creation skipped — %s", _schema_reason)

# VAGUE 2 / LOT 4 — posture de chiffrement, annoncee a chaque demarrage.
#
# `config.validate_encryption_key` n'exige CREDENTIALS_ENCRYPTION_KEY qu'a
# DEBUG=False. En production DEBUG vaut True et la cle est absente : le
# garde-fou de LOT-E est inerte, et le chiffrement des credentials retombe sur
# une cle derivee de SECRET_KEY. Ce boot ne bascule rien — la bascule
# DEBUG=False est une decision d'exploitation (docs/audit-20260821/
# BASCULE_DEBUG_FALSE.md) — mais il refuse de se taire.
_encryption = encryption_posture(
    debug=settings.DEBUG,
    encryption_key=settings.CREDENTIALS_ENCRYPTION_KEY,
    secret_key=settings.SECRET_KEY,
)
if _encryption["ok"]:
    logger.info(_encryption["message"])
else:
    logger.critical(_encryption["message"])

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
        "http://72.61.161.222",        # Port 80 via nginx
        "http://srv1064321.hstgr.cloud",  # Port 80 via nginx
        "http://72.61.161.222:3002",
        "http://72.61.161.222:8080",
        "http://72.61.161.222:3001",
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

# D-2: ExecutionContextMiddleware — populate execution_id/request_id/agent_id
# contextvars so logging_config and downstream services attach consistent context
# to every log line and DB write. Registered after Audit so Audit records can
# include the request_id produced here.
app.add_middleware(ExecutionContextMiddleware)

# C-4: BuildEnabledMiddleware — blocks BUILD endpoints when profile=freemium.
# Registered last so it runs first (Starlette middleware stack is LIFO).
app.add_middleware(BuildEnabledMiddleware)

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

# HITL: Contextual chat, CR lifecycle, versions/diff, metrics
app.include_router(hitl_routes.router)

# CORE-001: Audit logging API
app.include_router(audit.router, prefix=settings.API_V1_PREFIX)

# Deliverables routes (architecture review, BR validation, etc.)
app.include_router(deliverables.router, prefix=settings.API_V1_PREFIX)

# Public concierge chat (Sophie on marketing site, no auth, rate-limited)
app.include_router(concierge_routes.router, prefix=settings.API_V1_PREFIX)

# BLD-01, DPL-04/05/06: Deployment & Package routes
# 22/08 — routeur deployment DEMONTE (audit croise du 21/08, EXECUTION.md §5.1).
# /promote, /rollback, /validate, /snapshot/create et /snapshots prennent un
# chemin de fichier arbitraire (source_path, snapshot_path) sans lien avec une
# ressource en base : un client authentifie pouvait promouvoir ou restaurer le
# package d'un autre. Aucun appelant (frontend, orchestrateur, JordanDeployService)
# ne les utilisait. Le fichier app/api/routes/deployment.py est conserve intact.
# A remonter quand le pipeline BUILD aura un modele de snapshots en base.
# from app.api.routes import deployment
# app.include_router(deployment.router, prefix=settings.API_V1_PREFIX)

# BLD-07: Quality Dashboard routes
app.include_router(quality_dashboard.router, prefix=settings.API_V1_PREFIX)

# Phase 5: Project Configuration Wizard
app.include_router(wizard.router, prefix=settings.API_V1_PREFIX)

# Subscription routes (Section 9)
app.include_router(subscription.router, prefix=f"{settings.API_V1_PREFIX}/subscription", tags=["subscription"])

# Phase 3.1: Billing (credits balance + usage)
app.include_router(billing.router, prefix=settings.API_V1_PREFIX)

# Leads capture
from app.api.routes import leads, blog
from app.api.routes import journal_webhook
app.include_router(leads.router, prefix=settings.API_V1_PREFIX)
app.include_router(blog.router, prefix=settings.API_V1_PREFIX)
app.include_router(journal_webhook.router, prefix=settings.API_V1_PREFIX)

# P3: Document upload routes (RAG project isolation)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)

# C-4: Config capabilities endpoint (frontend reads active profile + build_enabled)
app.include_router(config_routes.router, prefix=settings.API_V1_PREFIX)

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

    # P11: probe RAG collections so operators notice empty/misconfigured ChromaDB at boot.
    try:
        from app.services.rag_service import rag_health_check
        rag_health_check()
    except Exception as e:
        logger.error(f"[RAG HEALTH] probe crashed: {e}", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown."""
    try:
        await shutdown_notification_service()
        logger.info("NotificationService shutdown complete")
    except Exception as e:
        logger.error(f"Error shutting down NotificationService: {e}")

def _check_database() -> tuple[bool, str]:
    """Run a real SELECT 1 against PostgreSQL. Returns (ok, detail)."""
    from sqlalchemy import text

    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def _check_redis() -> tuple[bool, str]:
    """Ping Redis. Returns (ok, detail).

    VAGUE 2 / LOT 3 — Redis porte la file ARQ (`arq_config.REDIS_SETTINGS`).
    Sans lui, `enqueue_job` echoue et **aucune execution ne demarre** : SDS,
    BUILD, retry, reprise. Un `/health` qui ne le regarde pas rend 200 pendant
    que le produit est a l'arret.
    """
    import redis as redis_lib

    from app.workers.arq_config import REDIS_SETTINGS

    client = None
    try:
        client = redis_lib.Redis(
            host=REDIS_SETTINGS.host,
            port=REDIS_SETTINGS.port,
            db=REDIS_SETTINGS.database,
            password=REDIS_SETTINGS.password,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        if not client.ping():
            return False, "PING returned a falsy reply"
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def _check_chroma() -> tuple[bool, str]:
    """Count the RAG chunks. Returns (ok, detail).

    VAGUE 2 / LOT 3 — le RAG porte 70 K chunks. Un ChromaDB absent ou vide ne
    fait pas tomber le backend : **les agents tournent sans contexte Salesforce
    et rendent des livrables plausibles mais pauvres**. C'est exactement la
    panne qu'on ne voit pas sans sonde, d'ou le `chroma.count` demande par Kimi
    plutot qu'un simple « le client repond ».
    """
    try:
        from app.services.rag_service import rag_health_check

        result = rag_health_check()
        if result.get("error"):
            return False, str(result["error"])
        total = result.get("total_chunks", 0)
        if not total:
            return False, f"0 chunks at {result.get('chroma_path')}"
        return True, f"{total} chunks"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


@app.get("/health")
async def health_check(response: Response):
    """Health check endpoint.

    cla:OPS-01 / kim:OPS-01 — this used to return {"status": "healthy"}
    unconditionally, so a dead database still answered 200 to the load
    balancer while every real request failed with a 500. It now runs a
    SELECT 1 and answers 503 when the database is unreachable.

    VAGUE 2 / LOT 3 — la sonde ne couvrait que la base. Kimi demandait
    `SELECT 1` + `redis.ping` + `chroma.count` : les trois y sont desormais, et
    **une seule dependance morte suffit a rendre 503**. Une dependance
    silencieusement absente est precisement ce qui a coute des jours a cet
    audit ; un `/health` vert sur un Redis mort en est la version operationnelle.

    Les trois sondes sont synchrones et bloquantes par nature (socket, disque) :
    elles partent en fil d'execution, jamais sur la boucle d'evenements.

    The shallow probe is still available on `/` for callers that only need
    to know the process is up.
    """
    # Les sondes sont resolues a chaque appel, pas figees dans une constante de
    # module : c'est ce qui permet de les remplacer en test sans monter un
    # Redis et un ChromaDB reels.
    probes = (
        ("database", _check_database),
        ("redis", _check_redis),
        ("chroma", _check_chroma),
    )

    results = await asyncio.gather(
        *(asyncio.to_thread(probe) for _, probe in probes)
    )

    checks = {}
    down = []
    for (name, _), (ok, detail) in zip(probes, results):
        if ok:
            checks[name] = {"status": "up"}
        else:
            checks[name] = {"status": "down", "detail": detail}
            down.append(f"{name} ({detail})")

    if down:
        logger.error("Health check failed: %s", ", ".join(down))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "checks": checks}

    return {"status": "healthy", "checks": checks}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )

# kim:SEC-03 — the `GET /download/{filename}` endpoint was removed here.
# It resolved `settings.OUTPUT_DIR / filename` with no authentication and no
# path resolution, so `GET /download/..%2F..%2F..%2Fetc%2Fpasswd` read
# arbitrary server files. A repository-wide search found no caller (frontend
# or backend), so it is deleted rather than patched: authenticated deliverable
# downloads already exist under /api/deliverables and /api/pm-orchestrator.
