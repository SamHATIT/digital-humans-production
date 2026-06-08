"""AGENT-FK-001 — résolution clé agent (string/alias) → agents.id (FK int).

L'orchestrateur manipule des clés agent en chaîne (``qa``, ``data``,
``architect``, ``research_analyst`` ...). La colonne
``agent_deliverables.agent_id`` est un FK entier vers ``agents.id``.
Historiquement les write sites posaient ``agent_id=None`` (la clé string
n'étant pas compatible avec le FK Integer), ce qui imposait un band-aid
défensif (OUTER JOIN) à chaque lecture (commit 9262a96).

Ce module ferme le band-aid à la source : il mappe la clé/alias vers le nom
canonique de l'agent (via ``agents_registry``) puis vers la PK ``agents.id``.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.services import agents_registry

logger = logging.getLogger(__name__)

# Cache nom canonique -> agents.id (stable pour la durée de vie du process).
_NAME_TO_PK: dict[str, int] = {}


def resolve_agent_pk(db: Session, agent_key: Optional[str]) -> Optional[int]:
    """Retourne ``agents.id`` pour une clé/alias d'agent, ou ``None`` si non résolvable.

    Ne lève jamais : un échec de résolution ne doit pas bloquer l'écriture d'un
    deliverable (on retombe sur le comportement legacy NULL, sans régression).
    """
    if not agent_key:
        return None
    try:
        canonical = agents_registry.try_resolve_agent_id(agent_key)
        if not canonical:
            logger.warning("[AGENT-FK-001] clé agent inconnue %r — agent_id laissé NULL", agent_key)
            return None
        name = agents_registry.get_agent(canonical).get("name")
        if not name:
            return None
        if name in _NAME_TO_PK:
            return _NAME_TO_PK[name]
        row = db.query(Agent).filter(Agent.name == name).first()
        if not row:
            logger.warning("[AGENT-FK-001] aucune ligne agents pour name=%r (clé %r)", name, agent_key)
            return None
        _NAME_TO_PK[name] = row.id
        return row.id
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning("[AGENT-FK-001] résolution échouée pour %r: %s", agent_key, exc)
        return None


def reset_cache() -> None:
    """Vide le cache nom→PK (tests / hot reload)."""
    _NAME_TO_PK.clear()
