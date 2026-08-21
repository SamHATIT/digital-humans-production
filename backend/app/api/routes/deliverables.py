"""
Deliverables API routes.

LOT-B (cla:SEC-01, kim:SEC-01) : ce routeur etait integralement expose —
aucune route ne portait `Depends(get_current_user)`. Chaque route porte
desormais l'authentification ET la verification de propriete
(deliverable -> execution -> project -> user).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.deliverable_service import DeliverableService
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)
from app.utils.ownership import verify_deliverable_access, verify_execution_access
from app.schemas.deliverable import (
    AgentDeliverableCreate,
    AgentDeliverableUpdate,
    AgentDeliverableResponse,
    AgentDeliverablePreview,
    AgentDeliverableFull
)

router = APIRouter(prefix="/deliverables", tags=["Deliverables"])


@router.post("/", response_model=AgentDeliverableResponse, status_code=status.HTTP_201_CREATED)
def create_deliverable(
    data: AgentDeliverableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create new agent deliverable."""
    verify_execution_access(data.execution_id, current_user.id, db)
    service = DeliverableService(db)

    try:
        deliverable = service.create_deliverable(data)
        return deliverable
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating deliverable: {str(e)}"
        )


@router.get("/{deliverable_id}", response_model=AgentDeliverableResponse)
def get_deliverable(
    deliverable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get deliverable by ID."""
    verify_deliverable_access(deliverable_id, current_user.id, db)
    service = DeliverableService(db)
    deliverable = service.get_by_id(deliverable_id)

    if not deliverable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable {deliverable_id} not found"
        )

    return deliverable


@router.get("/{deliverable_id}/full", response_model=AgentDeliverableFull)
def get_deliverable_full(
    deliverable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get full deliverable content."""
    verify_deliverable_access(deliverable_id, current_user.id, db)
    service = DeliverableService(db)
    deliverable = service.get_full_deliverable(deliverable_id)

    if not deliverable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable {deliverable_id} not found"
        )

    return deliverable


@router.get("/executions/{execution_id}", response_model=List[AgentDeliverableResponse])
def get_execution_deliverables(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all deliverables for an execution."""
    verify_execution_access(execution_id, current_user.id, db)
    service = DeliverableService(db)
    return service.get_by_execution(execution_id)


@router.get("/executions/{execution_id}/previews", response_model=List[AgentDeliverablePreview])
def get_execution_deliverable_previews(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get previews of all deliverables for an execution."""
    verify_execution_access(execution_id, current_user.id, db)
    service = DeliverableService(db)
    return service.get_deliverable_previews(execution_id)


@router.get("/executions/{execution_id}/agents/{agent_id}", response_model=List[AgentDeliverableResponse])
def get_agent_deliverables(
    execution_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get deliverables for a specific agent in an execution."""
    verify_execution_access(execution_id, current_user.id, db)
    service = DeliverableService(db)
    return service.get_by_execution_and_agent(execution_id, agent_id)


@router.get("/executions/{execution_id}/types/{deliverable_type}", response_model=AgentDeliverableResponse)
def get_deliverable_by_type(
    execution_id: int,
    deliverable_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get deliverable by execution and type."""
    verify_execution_access(execution_id, current_user.id, db)
    service = DeliverableService(db)
    deliverable = service.get_by_type(execution_id, deliverable_type)

    if not deliverable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable of type '{deliverable_type}' not found for execution {execution_id}"
        )

    return deliverable


@router.put("/{deliverable_id}", response_model=AgentDeliverableResponse)
def update_deliverable(
    deliverable_id: int,
    data: AgentDeliverableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update deliverable."""
    verify_deliverable_access(deliverable_id, current_user.id, db)
    service = DeliverableService(db)

    try:
        deliverable = service.update_deliverable(deliverable_id, data)
        return deliverable
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating deliverable: {str(e)}"
        )


@router.delete("/{deliverable_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deliverable(
    deliverable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete deliverable."""
    verify_deliverable_access(deliverable_id, current_user.id, db)
    service = DeliverableService(db)

    if not service.delete_deliverable(deliverable_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable {deliverable_id} not found"
        )

    return None

@router.get("/{deliverable_id}/render", response_class=HTMLResponse)
def render_deliverable_html(
    deliverable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """Render the deliverable as standalone HTML (for SDS documents).

    Unwraps the JSON wrapper produced by Emma's _execute_write_sds and
    returns the inner HTML directly with Content-Type: text/html so the
    browser renders it instead of showing it as text.

    LOT-B : route ouverte dans un onglet par le frontend (navigation, pas
    de header possible) — elle accepte donc le jeton en header OU en query
    param, comme les telechargements de sds_versions.py. Le jeton en URL
    reste un defaut connu (kim:SEC-07), traite hors de ce lot.
    """
    import json
    verify_deliverable_access(deliverable_id, current_user.id, db)
    service = DeliverableService(db)
    deliverable = service.get_full_deliverable(deliverable_id)

    if not deliverable:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable {deliverable_id} not found"
        )

    raw = deliverable.content or ""

    # Try to unwrap the JSON wrapper {"content": {"raw_html": "..."}, ...}
    html = raw
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            inner = parsed.get("content", {})
            if isinstance(inner, dict):
                # Prefer raw_html, fallback raw_markdown (which since iter 8 also contains HTML)
                html = inner.get("raw_html") or inner.get("raw_markdown") or raw
    except (json.JSONDecodeError, TypeError):
        # Content is not JSON-wrapped — return as-is
        pass

    # If the content is already a complete HTML document, return it directly
    if html.lstrip().lower().startswith("<!doctype html") or html.lstrip().lower().startswith("<html"):
        return HTMLResponse(content=html)

    # Otherwise wrap in a minimal HTML shell (for markdown/text content)
    wrapped = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Deliverable {deliverable_id}</title>
<style>body{{font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.6}}
pre{{background:#f4f4f4;padding:1rem;border-radius:4px;overflow-x:auto}}</style></head>
<body><pre>{html}</pre></body></html>"""
    return HTMLResponse(content=wrapped)
