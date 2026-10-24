"""Chemins reellement montes sur une application FastAPI.

Vague 2 / file B — SEC-18 : depuis la montee de fastapi 0.104.1 -> 0.162.0,
`app.routes` ne deplie plus les routeurs inclus : chaque `include_router`
y apparait comme un seul objet `_IncludedRouter` (chemin ""). Les tests qui
lisaient `{r.path for r in app.routes}` pour prouver qu'un routeur n'est PLUS
monte devenaient vrais sans rien verifier (leurs controles negatifs, eux,
sont tombes : c'est ce qui l'a montre). Cette fonction deplie les routeurs
inclus, quelle que soit la version.
"""
from __future__ import annotations

from typing import Set


def _deplier(routes, prefixe: str, chemins: Set[str]) -> None:
    """Parcours recursif des routeurs inclus : `include_context.prefix` de
    chaque inclusion, puis les routes du routeur inclus (HTTP ET websocket :
    reprise 5 de la revue 1, la route /api/pm-orchestrator/ws/{execution_id}
    manquait quand seul `effective_route_contexts()` etait lu)."""
    for route in routes:
        contexte = getattr(route, "include_context", None)
        if contexte is not None:  # fastapi >= 0.16x : _IncludedRouter
            _deplier(contexte.included_router.routes, prefixe + (contexte.prefix or ""), chemins)
        else:
            chemins.add(prefixe + getattr(route, "path", ""))


def chemins_montes(app) -> Set[str]:
    chemins: Set[str] = set()
    _deplier(app.routes, "", chemins)
    # Garde : les routes HTTP vues par FastAPI lui-meme doivent toutes y etre.
    for route in app.routes:
        contextes = getattr(route, "effective_route_contexts", None)
        if callable(contextes):
            chemins.update(getattr(ctx, "path", "") for ctx in contextes())
    return chemins
