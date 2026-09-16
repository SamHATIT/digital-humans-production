"""Enfilage identifie d'une execution (VAGUE 1 / FILE C).

Deux defauts mesures ont la meme cause : une execution enfilee ne gardait
aucune trace du job ARQ qui la porte.

- **PROD-04 = CAL-11** — au demarrage, un worker ne pouvait juger une execution
  RUNNING que sur son statut SQL, et les marquait toutes FAILED, y compris
  celles d'un autre worker (mesure 15/09 18:0x : l'execution 179 tuee alors que
  son job continuait). Le nettoyage a besoin de l'identifiant du job pour
  demander a Redis s'il vit encore.
- **CAL-07** — les reprises enfilaient toujours sur la file du worker courant,
  donc changeaient de worker et de profil de modele en cours de route (174
  reprise sur Muse au lieu de DeepSeek Flash).

L'ordre des ecritures compte : l'identifiant est **ecrit puis commite avant**
l'appel a `enqueue_job`. Une panne entre les deux laisse une execution dont le
job est connu mais absent de Redis — cas que le demarrage sait reconcilier.
L'ordre inverse laisserait une execution dont personne ne connait le job.
"""
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.execution import Execution
from app.workers.arq_config import ARQ_QUEUE_NAME

logger = logging.getLogger(__name__)


class EnfilageImpossible(RuntimeError):
    """ARQ a refuse l'enfilage (identifiant deja pris, Redis en erreur).

    Levee au lieu d'un repli silencieux : une execution RUNNING sans job est
    exactement ce que PROD-03 decrit et que PROD-04 ne peut plus rattraper si
    personne ne le dit.
    """


def file_de_reprise(execution: Execution) -> str:
    """CAL-07 — la file du lancement, sinon celle du worker courant.

    Une execution d'avant la colonne (`arq_queue_name` a NULL) n'a pas de file
    memorisee : on prend celle de ce deploiement, sans rien inventer.
    """
    return execution.arq_queue_name or ARQ_QUEUE_NAME


def nouvel_identifiant_de_job(execution_id: int) -> str:
    """Un identifiant par tentative, lisible dans Redis et dans les journaux.

    Chaque reprise est une tentative distincte : reutiliser l'identifiant du
    job mort ferait juger la nouvelle tentative sur l'ancien job (et ARQ
    refuserait l'enfilage tant que le resultat precedent est conserve).
    """
    return f"exec{execution_id}-{uuid.uuid4().hex[:12]}"


async def enfiler_execution(
    pool,
    db: Session,
    execution: Execution,
    nom_tache: str,
    *,
    file: Optional[str] = None,
    **kwargs,
) -> str:
    """Note le job sur l'execution, puis enfile. Rend l'identifiant du job.

    Args:
        pool: pool ARQ (`get_redis_pool()`).
        db: session portant `execution`.
        execution: l'execution a enfiler.
        nom_tache: nom de la tache ARQ (`execute_sds_task`, ...).
        file: file cible. Par defaut celle du worker courant ; les reprises
            passent `file_de_reprise(execution)`.
        **kwargs: arguments de la tache.

    Raises:
        EnfilageImpossible: si ARQ n'a pas accepte le job.
    """
    file_cible = file or ARQ_QUEUE_NAME
    job_id = nouvel_identifiant_de_job(execution.id)

    execution.arq_job_id = job_id
    execution.arq_queue_name = file_cible
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    job = await pool.enqueue_job(
        nom_tache, **kwargs, _queue_name=file_cible, _job_id=job_id
    )
    if job is None:
        raise EnfilageImpossible(
            f"ARQ a refuse le job {job_id!r} pour l'execution {execution.id} "
            f"sur la file {file_cible!r} : un job de meme identifiant existe "
            f"deja. L'execution n'est pas enfilee."
        )

    logger.info(
        f"[ARQ] Job {job.job_id} enfile pour l'execution {execution.id} "
        f"({nom_tache}) sur la file {file_cible!r}"
    )
    return job_id
