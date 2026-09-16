"""Execution courante du fil d'exécution (VAGUE 1 / FILE C).

GL-10 : quand le RAG tombe, il faut marquer **l'exécution concernée**
(`degraded: rag_unavailable`) et la nommer dans l'alerte admin. Or
`rag_service` est appelé par les agents, qui ne lui passent que `project_id` ;
faire descendre `execution_id` jusqu'à `get_salesforce_context` supposerait de
modifier les onze agents et leurs signatures.

On reprend donc le mécanisme déjà utilisé pour le propriétaire des crédits
(`llm_service.set_credit_owner`, vague B / lot B1) : une variable de contexte,
posée par l'orchestrateur autour de chaque agent et lue par les services
appelés en aval. Elle suit le fil d'exécution asyncio sans traverser aucune
signature.

Valeur absente = appel hors exécution (indexation, concierge, script) : c'est
un cas normal, pas un défaut — les appelants doivent le traiter, pas le
deviner.
"""
from contextvars import ContextVar, Token
from typing import Optional

_execution_courante: ContextVar[Optional[int]] = ContextVar(
    "dh_execution_courante", default=None
)


def poser_execution_courante(execution_id: Optional[int]) -> Token:
    """Déclare l'exécution à laquelle appartient le travail en cours."""
    return _execution_courante.set(execution_id)


def reprendre_execution_courante(jeton: Token) -> None:
    """Restaure la valeur précédente. À appeler dans un `finally`."""
    try:
        _execution_courante.reset(jeton)
    except ValueError:
        # Jeton posé dans un autre contexte (thread, tâche) : la valeur y est
        # déjà retombée d'elle-même.
        pass


def execution_courante() -> Optional[int]:
    """L'exécution en cours dans ce fil, ou None hors exécution."""
    return _execution_courante.get()
