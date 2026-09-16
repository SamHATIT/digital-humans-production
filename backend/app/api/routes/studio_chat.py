"""Dialogue authentifie hors projet — BILL-06.

Constat d'Astra du 06/09 (L717) : « fermer les projets Free casse le seul
parcours de dialogue authentifie disponible ». Les deux portes existantes
exigent un objet que le Free n'a pas le droit de creer :

  - `POST /api/projects/{id}/chat`                  -> exige un projet ;
  - `POST /api/pm-orchestrator/executions/{id}/chat` -> exige une execution ;
  - matrice serveur du Free : `chat_sophie`/`chat_olivia` vrais,
    `max_projects: 0`.

Le concierge public (`/api/public/concierge/talk`) ne remplace pas ce service :
il ne debite pas les credits du compte (`sans_compte=True`) et repond a un
visiteur anonyme, pas a un abonne.

Ce que cette route ajoute, et rien de plus :

  - le palier est resolu **cote serveur** depuis l'utilisateur authentifie —
    jamais lu dans le corps de la requete ;
  - l'acces a un agent est controle par la matrice : Sophie et Olivia pour
    tout le monde (`chat_sophie` / `chat_olivia`), le reste de l'ensemble
    derriere `chat_full_team`. Le controle a lieu **avant** l'appel LLM :
    un refus ne se paie pas ;
  - l'appel est facture normalement (`user_id`, decision D10 du 03/09) ;
  - aucune memoire serveur. Le Free annonce « sessions stateless »
    (`persistent_memory: False`) ; la reponse porte `memory` pour que le
    client sache ce qu'il en est plutot que de le supposer. La memoire
    persistante des paliers payants reste a faire — elle demande une table,
    donc une migration : voir le rapport de la file D.

Aucun projet technique cache n'est cree pour contourner la regle commerciale
(le rapport d'Astra l'excluait explicitement).
"""
from __future__ import annotations

import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.agents_registry import (
    AgentNotFoundError,
    get_chat_profile,
    resolve_agent_id,
)
from app.utils.dependencies import get_current_user
from app.utils.feature_access import ensure_feature, resolve_tier

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/studio", tags=["studio-chat"])

# Agents joignables sans `chat_full_team`. C'est exactement ce que le palier
# Free annonce ; tout autre agent passe par la porte payante.
AGENTS_DE_BASE = {
    "sophie": "chat_sophie",
    "olivia": "chat_olivia",
}

# Bornes de l'historique fourni par le client. Le dialogue est sans etat
# serveur : sans ces bornes, l'appelant choisirait la taille du prompt qu'il
# nous fait payer.
TOURS_MAX = 10
CARACTERES_PAR_TOUR = 4000


class StudioChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=CARACTERES_PAR_TOUR)


class StudioChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=CARACTERES_PAR_TOUR)
    agent_id: str = Field("sophie", max_length=40)
    history: List[StudioChatTurn] = Field(default_factory=list)


class StudioChatResponse(BaseModel):
    agent_id: str
    agent_name: str
    response: str
    tokens_used: int = 0
    tier: str
    # « session » : rien n'est conserve au-dela de cet echange. Dit
    # explicitement pour que l'interface n'ait pas a le deviner.
    memory: Literal["session"] = "session"


def _rendre_historique(history: List[StudioChatTurn], agent_label: str) -> str:
    """Les `TOURS_MAX` derniers tours, dans l'ordre de lecture."""
    recents = history[-TOURS_MAX:]
    lignes = []
    for tour in recents:
        etiquette = "Client" if tour.role == "user" else agent_label
        lignes.append(f"\n{etiquette}: {tour.content}\n")
    return "".join(lignes)


@router.post("/chat", response_model=StudioChatResponse)
def chat_sans_projet(
    payload: StudioChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Un tour de dialogue avec un agent, sans projet ni execution."""
    try:
        agent_id = resolve_agent_id(payload.agent_id)
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown agent_id: {payload.agent_id}",
        )

    # Controle de capacite AVANT l'appel LLM : un refus ne se paie pas.
    capacite = AGENTS_DE_BASE.get(agent_id, "chat_full_team")
    ensure_feature(current_user, capacite)

    profile = get_chat_profile(agent_id)
    agent_label = profile["name"]

    # `system_prompt` du registre attend un nom de projet. Il n'y en a pas
    # ici, et en inventer un serait un repli silencieux : on dit ce qui est.
    try:
        system_prompt = profile["system_prompt"].format(
            project_name="(aucun projet — dialogue de cadrage)"
        )
    except (KeyError, IndexError):
        system_prompt = profile["system_prompt"]

    prompt = (
        f"{_rendre_historique(payload.history, agent_label)}"
        f"\nClient: {payload.message}\n\n{agent_label}:"
    )

    tier = resolve_tier(current_user)

    from app.services.llm_service import generate_llm_response

    try:
        reponse = generate_llm_response(
            prompt=prompt,
            agent_type=profile["agent_type"],
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.7,
            # Le palier vient du serveur, jamais du corps de la requete.
            subscription_tier=tier.value,
            # D10 : tout appel d'agent est facture a un proprietaire connu.
            user_id=current_user.id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[Studio chat] appel LLM en echec : %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"L'agent n'a pas pu repondre : {exc}",
        )

    contenu = (reponse.get("content") or "").strip()
    if not reponse.get("success", True) or not contenu:
        # Regle 6 : un echec LLM ne devient jamais un 200 vide (le 03/09, un
        # 404 de fournisseur est arrive au client comme une reponse de Sophie
        # de zero caractere).
        motif = reponse.get("error") or "reponse vide"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"L'agent n'a pas pu repondre : {motif}",
        )

    return StudioChatResponse(
        agent_id=agent_id,
        agent_name=agent_label,
        response=contenu,
        tokens_used=reponse.get("tokens_used", 0) or 0,
        tier=tier.value,
    )


@router.get("/chat/agents")
def agents_joignables(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Les agents que **ce** compte peut joindre hors projet.

    Rendu au frontend pour qu'il n'affiche pas des interlocuteurs qui
    repondront 403 : c'est le defaut corrige par le lot 3 de la vague 2, et il
    se reproduirait ici si l'interface devinait la liste.
    """
    from app.services.agents_registry import iter_chat_profiles
    from app.models.subscription import has_feature

    tier = resolve_tier(current_user)
    agents = []
    for profile in iter_chat_profiles():
        capacite = AGENTS_DE_BASE.get(profile["agent_id"], "chat_full_team")
        agents.append(
            {
                "agent_id": profile["agent_id"],
                "name": profile["name"],
                "role": profile["role"],
                "color": profile["color"],
                "available": has_feature(tier, capacite),
                "required_feature": capacite,
            }
        )
    return {"tier": tier.value, "agents": agents, "memory": "session"}
