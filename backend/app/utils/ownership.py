"""
Verifications de propriete (cloisonnement client) — LOT-B de l'audit croise
du 21/08/2026 (cla:SEC-01, kim:SEC-01).

`Depends(get_current_user)` ne prouve que l'authentification. Ces helpers
prouvent la **propriete** : la ressource demandee remonte-t-elle bien, via
son execution ou son projet, jusqu'a l'utilisateur qui appelle ?

Fichier neuf, cree pour le LOT-B afin de ne pas toucher
`app/api/routes/orchestrator/_helpers.py` (perimetre d'un autre lot) qui
porte deja un helper equivalent pour les routes orchestrateur.

Convention de code de retour : **404** et non 403 sur une ressource
appartenant a autrui, afin de ne pas confirmer son existence (pas
d'enumeration d'IDs). Le critere de fin du lot accepte 403 ou 404.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.agent_deliverable import AgentDeliverable
from app.models.execution import Execution
from app.models.project import Project

_NOT_FOUND = status.HTTP_404_NOT_FOUND


def verify_project_access(project_id: int, user_id: int, db: Session) -> Project:
    """Le projet existe et appartient a l'utilisateur, sinon 404."""
    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.user_id == user_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=_NOT_FOUND, detail="Project not found")
    return project


def verify_execution_access(execution_id: int, user_id: int, db: Session) -> Execution:
    """L'execution existe et son projet appartient a l'utilisateur, sinon 404."""
    execution = (
        db.query(Execution)
        .join(Project, Execution.project_id == Project.id)
        .filter(Execution.id == execution_id, Project.user_id == user_id)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=_NOT_FOUND, detail="Execution not found")
    return execution


def verify_deliverable_access(
    deliverable_id: int, user_id: int, db: Session
) -> AgentDeliverable:
    """Le livrable existe et remonte, via son execution, a l'utilisateur."""
    deliverable = (
        db.query(AgentDeliverable)
        .join(Execution, AgentDeliverable.execution_id == Execution.id)
        .join(Project, Execution.project_id == Project.id)
        .filter(AgentDeliverable.id == deliverable_id, Project.user_id == user_id)
        .first()
    )
    if not deliverable:
        raise HTTPException(
            status_code=_NOT_FOUND,
            detail=f"Deliverable {deliverable_id} not found",
        )
    return deliverable
