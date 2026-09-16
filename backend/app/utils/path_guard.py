"""Validation des chemins d'ecriture — SEC-03 (audit Astra L53).

Les noms de fichiers produits par les agents servaient de chemins d'ecriture,
et la « normalisation » en place ne refusait ni `..` ni tous les chemins
absolus. **Le modele n'est pas une frontiere de confiance** : une sortie
orientee par un brief client peut viser un fichier accessible au service. Le
retrait de `shell=True` (LOT-C) ne corrige pas cette classe : il n'y a pas
d'interpreteur a tromper, seulement un chemin a suivre.

La validation est faite **au point d'ecriture**, pas au point de generation :
c'est le seul endroit qui connait la racine reelle de l'execution.

Trois interdits cumules, dans cet ordre :

1. chemin absolu ou remontee — la cible resolue doit rester sous la racine ;
2. `.git` — un chemin peut rester dans le depot et rester dangereux :
   `.git/config` reecrit les remotes, `.git/hooks/*` s'execute au commit ;
3. extension hors liste, quand l'appelant en fournit une.

La resolution passe par `Path.resolve()`, qui suit les liens : un repertoire
de la racine qui serait un lien vers l'exterieur est donc refuse, et pas
seulement les `..` litteraux.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional, Union

logger = logging.getLogger(__name__)


class CheminInterdit(ValueError):
    """Le chemin demande sort de la racine autorisee, ou vise une zone interdite."""


#: Repertoires jamais inscriptibles, meme sous la racine.
SEGMENTS_INTERDITS = {".git"}


def resoudre_sous_racine(
    racine: Union[str, Path],
    chemin_relatif: str,
    *,
    extensions: Optional[Iterable[str]] = None,
) -> Path:
    """Rend la cible absolue si elle est sure, leve `CheminInterdit` sinon.

    Ne cree rien : l'appelant reste maitre de l'ecriture (et de ses droits).
    """
    if not isinstance(chemin_relatif, str) or not chemin_relatif.strip():
        raise CheminInterdit("Chemin de livrable interdit : chemin vide.")

    propose = Path(chemin_relatif.strip())
    if propose.is_absolute():
        raise CheminInterdit(
            f"Chemin de livrable interdit : {chemin_relatif!r} est absolu."
        )

    if any(part == ".." for part in propose.parts):
        raise CheminInterdit(
            f"Chemin de livrable interdit : {chemin_relatif!r} contient une remontee."
        )

    interdits = {part for part in propose.parts} & SEGMENTS_INTERDITS
    if interdits:
        raise CheminInterdit(
            f"Chemin de livrable interdit : {chemin_relatif!r} vise "
            f"{', '.join(sorted(interdits))} (configuration et hooks git s'executent)."
        )

    if not propose.name or propose.name in {".", ".."}:
        raise CheminInterdit(
            f"Chemin de livrable interdit : {chemin_relatif!r} ne nomme aucun fichier."
        )

    if extensions is not None:
        permises = tuple(e.lower() for e in extensions)
        if propose.suffix.lower() not in permises:
            raise CheminInterdit(
                f"Chemin de livrable interdit : extension {propose.suffix!r} hors "
                f"liste ({', '.join(permises)})."
            )

    base = Path(racine).resolve()
    cible = (base / propose).resolve()
    try:
        cible.relative_to(base)
    except ValueError:
        logger.warning(
            "[PathGuard] ecriture refusee : %s resout hors de %s", chemin_relatif, base
        )
        raise CheminInterdit(
            f"Chemin de livrable interdit : {chemin_relatif!r} resout hors de la "
            f"racine d'execution."
        )

    return cible
