"""
Shared helpers for pm_orchestrator route modules.

P4: Extracted from pm_orchestrator.py to avoid duplication across route files.
"""
import json
import re
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.execution import Execution


# ---------------------------------------------------------------------------
# VAGUE B / LOT B1-bis — le motif « credits insuffisants » rendu au client
# ---------------------------------------------------------------------------
#
# Constat mesure au lot B1 : aucun chemin HTTP ne remontait ce motif. La route
# de lancement rend 202 (le travail part dans un job ARQ) et `/progress` ne
# rendait que `status: "failed"`. Un client Free qui atteint son plafond voyait
# une execution « echouee », sans raison.
#
# Pourquoi une reconnaissance sur le texte et pas sur le type de l'exception :
# `InsufficientCreditsError` est levee dans `credit_service`, traverse
# `llm_router_service` puis `generate_llm_response`, et se fait aplatir en
# chaine par le `except Exception: return {"success": False, "error": str(e)}`
# de chaque agent (`agents/roles/salesforce_pm.py:336` par exemple), avant que
# `execute_workflow` ne l'ecrive dans `executions.logs`. Les agents sont hors
# du perimetre de ce lot ; le jour ou ils propageront le type, cette
# reconnaissance deviendra inutile et pourra tomber.
#
# Pourquoi ici et pas dans `pm_orchestrator_service_v2` : ce module-la tire
# python-docx et chromadb, et
# `tests/test_vague3_correspondance.py::test_l_api_ne_depend_pas_de_l_orchestrateur_a_l_import`
# interdit de l'importer au niveau module depuis une route. Mesure faite : la
# premiere version de ce lot l'importait la-bas et ce test est passe au rouge.
#
# La signature ci-dessous est celle du message construit par
# `credit_service.InsufficientCreditsError.__init__`. Le test
# `test_la_signature_du_refus_credits_suit_l_exception_reelle` construit une
# vraie exception et verifie qu'elle est reconnue : si ce message change
# la-bas, ce test casse ici. C'est le seul garde-fou possible sans toucher aux
# agents.

MOTIF_CREDITS_INSUFFISANTS = "insufficient_credits"

_SIGNATURE_CREDITS_INSUFFISANTS = re.compile(
    r"Insufficient credits for user (?P<user_id>\d+): "
    r"requested=(?P<requested>\d+(?:\.\d+)?), "
    r"available=(?P<available>-?\d+(?:\.\d+)?)"
)


def motif_credits_insuffisants(texte: str) -> Optional[Dict[str, Any]]:
    """Rend les valeurs du refus de credits si `texte` en porte la signature.

    Rend `None` pour tout autre echec — c'est ce qui empeche un timeout ou une
    panne de fournisseur d'etre presente au client comme un probleme de
    credits (controle negatif du lot).
    """
    if not texte:
        return None
    trouve = _SIGNATURE_CREDITS_INSUFFISANTS.search(texte)
    if not trouve:
        return None
    return {
        "user_id": int(trouve.group("user_id")),
        "requested": int(float(trouve.group("requested"))),
        "available": int(float(trouve.group("available"))),
    }


def decrire_refus_credits(db: Session, user_id: int, infos: Dict[str, Any]) -> str:
    """Phrase lisible nommant le palier et sa limite, lus en base.

    Aucune valeur n'est ecrite en dur : le palier vient de `users`, la limite
    de `tier_config`. Si la ligne `tier_config` manque, la limite n'est pas
    inventee — la phrase le dit (regle 6 : jamais de repli silencieux).
    """
    from app.models.credit import TierConfig
    from app.models.user import User
    from app.services.credit_service import resolve_credit_tier

    demande = infos.get("requested")
    restant = infos.get("available")

    utilisateur = db.query(User).filter(User.id == user_id).first()
    if utilisateur is None:
        return (
            f"Credits insuffisants : cet appel en demandait {demande}, il en "
            f"restait {restant}. Le compte {user_id} est introuvable, la limite "
            "de son palier n'a pas pu etre lue."
        )

    palier = resolve_credit_tier(utilisateur)
    config = db.query(TierConfig).filter(TierConfig.tier_name == palier).first()

    if config is not None and config.daily_credits_cap:
        limite = f"plafonne a {config.daily_credits_cap} credits par jour"
    elif config is not None and config.monthly_credits:
        limite = f"plafonne a {config.monthly_credits} credits par mois"
    else:
        limite = "sans limite lisible dans tier_config (ligne absente ou vide)"

    return (
        f"Credits insuffisants : le palier « {palier} » est {limite}. "
        f"Cet appel en demandait {demande}, il en restait {restant}. "
        "Ajoutez des credits ou passez a un palier superieur, puis relancez "
        "l'execution."
    )


def motif_echec_execution(db: Session, execution: Execution) -> Optional[Dict[str, str]]:
    """Motif lisible du dernier echec consigne dans `executions.logs`.

    `execute_workflow` y ajoute `{"type": "error", "message": str(e), ...}`.
    Rend `None` tant que l'echec n'est pas reconnu : mieux vaut ne rien dire
    que de nommer une cause devinee.

    Ne lit `logs` que pour une execution en echec : le flux SSE appelle cette
    fonction a chaque battement pendant tout un run, et `logs` grossit avec
    lui. Une execution encore en cours peut d'ailleurs porter l'erreur d'une
    tentative precedente ; la presenter comme le motif de fin serait faux.
    """
    statut = getattr(execution, "status", None)
    statut = statut.value if hasattr(statut, "value") else str(statut or "")
    if statut.lower() != "failed":
        return None

    brut = getattr(execution, "logs", None)
    if not brut:
        return None
    try:
        entrees = json.loads(brut)
    except (TypeError, ValueError):
        return None
    if not isinstance(entrees, list):
        return None

    for entree in reversed(entrees):
        if not isinstance(entree, dict):
            continue
        infos = motif_credits_insuffisants(str(entree.get("message") or ""))
        if infos:
            proprietaire = getattr(execution, "user_id", None) or infos["user_id"]
            return {
                "code": MOTIF_CREDITS_INSUFFISANTS,
                "message": decrire_refus_credits(db, proprietaire, infos),
            }
    return None


# Agent display names mapping (used in progress, SSE, WebSocket)
AGENT_NAMES = {
    "pm": "Sophie (PM)",
    "ba": "Olivia (BA)",
    "research_analyst": "Emma (Research Analyst)",
    "architect": "Marcus (Architect)",
    "apex": "Diego (Apex)",
    "lwc": "Zara (LWC)",
    "admin": "Raj (Admin)",
    "qa": "Elena (QA)",
    "devops": "Jordan (DevOps)",
    "data": "Aisha (Data)",
    "trainer": "Lucas (Trainer)",
}

# State mapping from internal to frontend format
STATUS_MAP = {
    "waiting": "pending",
    "running": "in_progress",
    "completed": "completed",
    "failed": "failed",
}


def verify_execution_access(
    execution_id: int,
    user_id: int,
    db: Session,
) -> Execution:
    """
    Verify that an execution exists and belongs to the given user.
    Raises HTTPException if not found.
    """
    execution = (
        db.query(Execution)
        .join(Project)
        .filter(Execution.id == execution_id, Project.user_id == user_id)
        .first()
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    return execution


def verify_execution_project_access(
    execution_id: int,
    user_id: int,
    db: Session,
) -> tuple:
    """
    Verify execution access and return both execution and project.
    Used by routes that need both objects.
    """
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(Project.id == execution.project_id).first()
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return execution, project


def parse_agent_status(execution: Execution) -> dict:
    """Parse agent_execution_status from execution, handling str or dict."""
    import json

    agent_status = {}
    if execution.agent_execution_status:
        if isinstance(execution.agent_execution_status, str):
            agent_status = json.loads(execution.agent_execution_status)
        else:
            agent_status = execution.agent_execution_status
    return agent_status


def parse_selected_agents(execution: Execution) -> list:
    """Parse selected_agents from execution, handling str or list."""
    import json

    selected_agents = execution.selected_agents or []
    if isinstance(selected_agents, str):
        selected_agents = json.loads(selected_agents)
    return selected_agents


def build_agent_progress(execution: Execution) -> tuple:
    """
    Build agent progress data for frontend consumption.
    Returns (agent_progress_list, overall_progress_percent, current_phase_str).
    """
    from app.models.execution import ExecutionStatus

    agent_status = parse_agent_status(execution)
    selected_agents = parse_selected_agents(execution)

    agent_progress = []
    for agent_id in selected_agents:
        status_info = agent_status.get(agent_id, {})
        state = status_info.get("state", "waiting")
        agent_progress.append({
            "agent_name": AGENT_NAMES.get(agent_id, agent_id),
            "status": STATUS_MAP.get(state, state),
            "progress": status_info.get("progress", 0),
            "current_task": status_info.get("message", ""),
            "output_summary": status_info.get("message", ""),
            "extra_data": status_info.get("extra_data", None),
        })

    total_agents = len(selected_agents)
    completed_agents = sum(
        1 for a in agent_status.values() if a.get("state") == "completed"
    )
    overall_progress = (
        int((completed_agents / total_agents) * 100) if total_agents > 0 else 0
    )

    current_phase = "Initializing..."
    if execution.current_agent:
        current_phase = f"Running {AGENT_NAMES.get(execution.current_agent, execution.current_agent)}"
    if execution.status == ExecutionStatus.COMPLETED:
        current_phase = "Completed"
        overall_progress = 100
    elif execution.status == ExecutionStatus.FAILED:
        current_phase = "Failed"
    elif execution.status == ExecutionStatus.WAITING_BR_VALIDATION:
        current_phase = "Waiting for BR Validation"
    elif execution.status == ExecutionStatus.WAITING_ARCHITECTURE_VALIDATION:
        current_phase = "Waiting for Architecture Validation"

    return agent_progress, overall_progress, current_phase
