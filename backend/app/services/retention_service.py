"""Retention des conversations — GL-16.

Etat mesure le 16/09/2026 sur `f78e8ad`, avant ce module :

  - `chat_logs` (le concierge public du site) **est** purge depuis le lot B5
    du 03/09 : `app/workers/retention.py`, planifie a 03:17 UTC dans
    `WorkerSettings.cron_jobs`. Le constat « `chat_log.py` ne purge pas » du
    backlog etait donc deja perime. Ce module ne le defait pas.

  - `project_conversations` — les conversations Sophie que le client tient
    reellement dans le Studio (`POST /api/projects/{id}/chat` et
    `POST /api/pm-orchestrator/executions/{id}/chat`) — n'avait **aucune**
    purge. Mesure :

        grep -rn "ProjectConversation" backend/app --include=*.py \\
          | grep -i "delete|purge|retention"

    ne rendait que la cascade `all, delete-orphan` de `Project.conversations` :
    ces messages ne disparaissaient que si le projet etait supprime. Ce sont
    pourtant les conversations les plus riches en donnees client.

Sur la duree, deux decisions se contredisent : DEC-0813-02 et DEC-0817-04
(13 et 17 aout) disent 90 jours ; D3 (03/09) dit 12 mois, et c'est elle qui
est dans le code depuis B5. Trancher est une decision humaine, pas un
correctif : ce module garde par defaut la decision la plus recente (365 jours,
alignee sur `workers/retention.RETENTION_JOURS`) et rend la duree reglable par
variable d'environnement, pour que passer a 90 jours soit une ligne de
configuration et non une modification de code.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.project_conversation import ProjectConversation

logger = logging.getLogger(__name__)

# Aligne sur `app/workers/retention.RETENTION_JOURS` (D3, 03/09/2026).
RETENTION_CONVERSATIONS_JOURS = 365

VARIABLE_DUREE = "DH_RETENTION_CONVERSATIONS_JOURS"


def retention_conversations_jours() -> int:
    """La duree de retention effective, en jours.

    Regle 6 : une valeur illisible, nulle ou negative est **refusee**, pas
    devinee. Une duree mal saisie qui deviendrait 0 purgerait toute la table a
    la premiere execution du cron ; une duree qui retomberait silencieusement
    sur le defaut ferait croire a un reglage qui n'a jamais pris.
    """
    brut = os.environ.get(VARIABLE_DUREE)
    if brut is None or brut.strip() == "":
        if brut is not None:
            raise ValueError(
                f"{VARIABLE_DUREE} est vide. Retirez la variable pour utiliser "
                f"le defaut ({RETENTION_CONVERSATIONS_JOURS} jours), ou posez "
                f"un nombre de jours strictement positif."
            )
        return RETENTION_CONVERSATIONS_JOURS

    try:
        valeur = int(brut.strip())
    except ValueError:
        raise ValueError(
            f"{VARIABLE_DUREE}={brut!r} n'est pas un nombre de jours. "
            f"Posez un entier strictement positif (ex. 90)."
        ) from None

    if valeur <= 0:
        raise ValueError(
            f"{VARIABLE_DUREE}={valeur} : une retention doit etre strictement "
            f"positive. Zero ou negatif viderait la table a la premiere purge."
        )
    return valeur


def purger_conversations_projet(
    db: Session,
    *,
    maintenant: Optional[datetime] = None,
    retention_jours: Optional[int] = None,
) -> int:
    """Supprime les `project_conversations` plus vieilles que la retention.

    Rend le nombre de lignes supprimees. Ne touche a aucune autre table : le
    concierge public a sa propre purge, sa propre table et sa propre duree.
    """
    jours = retention_jours if retention_jours is not None else retention_conversations_jours()
    maintenant = maintenant or datetime.now(timezone.utc)
    seuil = maintenant - timedelta(days=jours)

    supprimees = (
        db.query(ProjectConversation)
        .filter(ProjectConversation.created_at < seuil)
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info(
        "[RETENTION] project_conversations : %d ligne(s) supprimee(s), seuil %s (%d jours)",
        supprimees,
        seuil.isoformat(timespec="seconds"),
        jours,
    )
    return supprimees


def purger_toutes_les_conversations(db: Session) -> Dict[str, int]:
    """Les deux retentions en une passe, pour un seul point d'entree de cron.

    Le branchement sur le planificateur vit dans `app/workers/*`, attribue a
    une autre file de la vague 1 ; le diff de branchement est dans le rapport
    de la file D, non commis ici. Tant qu'il n'est pas applique, cette
    fonction existe mais n'est appelee par aucun cron — c'est dit, pas tu.
    """
    from app.workers.retention import purger_chat_logs

    return {
        "chat_logs": purger_chat_logs(db),
        "project_conversations": purger_conversations_projet(db),
    }
