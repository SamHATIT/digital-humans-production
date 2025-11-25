"""
PM Orchestrator API routes.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.pm_orchestrator_service import PMOrchestratorService
from app.schemas.pm_orchestration import (
    PMOrchestrationCreate,
    PMOrchestrationUpdate,
    PMOrchestrationResponse,
    PMDialogueRequest,
    PMDialogueResponse,
    GeneratePRDRequest,
    GeneratePRDResponse,
    UserStory,
    RoadmapPhase
)

router = APIRouter(prefix="/pm", tags=["PM Orchestrator"])


@router.post("/dialogue", response_model=PMDialogueResponse)
def pm_dialogue(
    request: PMDialogueRequest,
    db: Session = Depends(get_db)
):
    """
    Handle dialogue with PM Orchestrator.

    Allows users to have a conversational interaction with the PM agent
    to refine business requirements.
    """
    service = PMOrchestratorService(db)
    try:
        return service.dialogue(request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in PM dialogue: {str(e)}"
        )


@router.post("/generate-prd", response_model=GeneratePRDResponse)
def generate_prd(
    request: GeneratePRDRequest,
    db: Session = Depends(get_db)
):
    """
    Generate Product Requirements Document (PRD).

    Uses the PM agent to create a comprehensive PRD from business requirements.
    """
    service = PMOrchestratorService(db)
    try:
        return service.generate_prd(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating PRD: {str(e)}"
        )


@router.get("/projects/{project_id}/prd", response_model=PMOrchestrationResponse)
def get_prd(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Get PRD for a project."""
    service = PMOrchestratorService(db)
    orchestration = service.get_by_project_id(project_id)

    if not orchestration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No PM orchestration found for project {project_id}"
        )

    return orchestration


@router.put("/projects/{project_id}/prd", response_model=PMOrchestrationResponse)
def update_prd(
    project_id: int,
    data: PMOrchestrationUpdate,
    db: Session = Depends(get_db)
):
    """Update PRD content."""
    service = PMOrchestratorService(db)

    try:
        if data.prd_content is not None:
            orchestration = service.update_prd(project_id, data.prd_content)
        elif data.user_stories is not None:
            orchestration = service.update_user_stories(project_id, data.user_stories)
        elif data.roadmap is not None:
            orchestration = service.update_roadmap(project_id, data.roadmap)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No update data provided"
            )

        return orchestration
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/projects/{project_id}/generate-user-stories")
def generate_user_stories(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Generate user stories from PRD."""
    service = PMOrchestratorService(db)

    try:
        user_stories = service.generate_user_stories(project_id)
        return {"user_stories": user_stories, "count": len(user_stories)}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating user stories: {str(e)}"
        )


@router.post("/projects/{project_id}/generate-roadmap")
def generate_roadmap(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Generate roadmap from user stories."""
    service = PMOrchestratorService(db)

    try:
        roadmap = service.generate_roadmap(project_id)
        return {"roadmap": roadmap}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating roadmap: {str(e)}"
        )


@router.get("/projects/{project_id}/user-stories")
def get_user_stories(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Get user stories for a project."""
    service = PMOrchestratorService(db)
    orchestration = service.get_by_project_id(project_id)

    if not orchestration or not orchestration.user_stories:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user stories found for project {project_id}"
        )

    return {
        "user_stories": orchestration.user_stories,
        "count": len(orchestration.user_stories)
    }


@router.get("/projects/{project_id}/roadmap")
def get_roadmap(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Get roadmap for a project."""
    service = PMOrchestratorService(db)
    orchestration = service.get_by_project_id(project_id)

    if not orchestration or not orchestration.roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No roadmap found for project {project_id}"
        )

    return {"roadmap": orchestration.roadmap}


@router.post("/orchestration", response_model=PMOrchestrationResponse)
def create_orchestration(
    data: PMOrchestrationCreate,
    db: Session = Depends(get_db)
):
    """Create new PM orchestration for a project."""
    service = PMOrchestratorService(db)

    # Check if orchestration already exists
    existing = service.get_by_project_id(data.project_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PM orchestration already exists for project {data.project_id}"
        )

    try:
        orchestration = service.create_orchestration(data)
        return orchestration
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating orchestration: {str(e)}"
        )
