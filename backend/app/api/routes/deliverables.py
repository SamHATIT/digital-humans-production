"""
Deliverables API routes.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.deliverable_service import DeliverableService
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
    db: Session = Depends(get_db)
):
    """Create new agent deliverable."""
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
    db: Session = Depends(get_db)
):
    """Get deliverable by ID."""
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
    db: Session = Depends(get_db)
):
    """Get full deliverable content."""
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
    db: Session = Depends(get_db)
):
    """Get all deliverables for an execution."""
    service = DeliverableService(db)
    return service.get_by_execution(execution_id)


@router.get("/executions/{execution_id}/previews", response_model=List[AgentDeliverablePreview])
def get_execution_deliverable_previews(
    execution_id: int,
    db: Session = Depends(get_db)
):
    """Get previews of all deliverables for an execution."""
    service = DeliverableService(db)
    return service.get_deliverable_previews(execution_id)


@router.get("/executions/{execution_id}/agents/{agent_id}", response_model=List[AgentDeliverableResponse])
def get_agent_deliverables(
    execution_id: int,
    agent_id: int,
    db: Session = Depends(get_db)
):
    """Get deliverables for a specific agent in an execution."""
    service = DeliverableService(db)
    return service.get_by_execution_and_agent(execution_id, agent_id)


@router.get("/executions/{execution_id}/types/{deliverable_type}", response_model=AgentDeliverableResponse)
def get_deliverable_by_type(
    execution_id: int,
    deliverable_type: str,
    db: Session = Depends(get_db)
):
    """Get deliverable by execution and type."""
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
    db: Session = Depends(get_db)
):
    """Update deliverable."""
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
    db: Session = Depends(get_db)
):
    """Delete deliverable."""
    service = DeliverableService(db)

    if not service.delete_deliverable(deliverable_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deliverable {deliverable_id} not found"
        )

    return None
