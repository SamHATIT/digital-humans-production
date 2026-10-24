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


def chemins_montes(app) -> Set[str]:
    chemins: Set[str] = set()
    for route in app.routes:
        contextes = getattr(route, "effective_route_contexts", None)
        if callable(contextes):  # fastapi >= 0.16x : routeur inclus paresseusement
            for ctx in contextes():
                chemins.add(getattr(ctx, "path", ""))
        else:
            chemins.add(getattr(route, "path", ""))
    return chemins
