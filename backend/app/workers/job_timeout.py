"""Delai maximal d'un job ARQ, selon le profil de routage (VAGUE 1 / FILE C).

CAL-01, mesure du 15/09 : `WorkerSettings.job_timeout` valait 3600 pour tout le
monde. Le job de reprise de l'execution 172, demarre a 09:24:31, a ete annule a
10:24:31 en plein appel de Marcus (« Patching architecture, attempt 1 »). A
12,4 tok/s de generation — debit mesure de Muse Glimmer 30B Q8 sur le Spark —
une seule phase depasse l'heure ; en profil cloud (Sonnet/Opus), une heure est
large.

Le delai suit donc le profil de routage du worker (`DH_DEPLOYMENT_PROFILE`, la
meme variable que `LLMRouterService`), et reste surchargeable sans toucher au
code : c'est ce que la calibration a fait a la main le 15/09 en editant
`worker.py`, puis defait le 16/09.

Ce module ne depend de rien : il est importe par `WorkerSettings`, et faire
dependre le demarrage du worker du routeur LLM (donc de chromadb et
python-docx) serait un pas dans la mauvaise direction.
"""
import logging
import os

logger = logging.getLogger("arq.worker")

#: Delai par defaut, profils servis par des fournisseurs cloud.
DELAI_CLOUD = 3600

#: Delai des profils servis par des modeles locaux. 21600 s (6 h) est la valeur
#: retenue par la calibration du 15/09 apres la coupure de l'execution 172.
DELAI_LOCAL = 21600

#: Profils connus. Un profil absent de cette table prend le delai cloud, en le
#: disant : le worker doit demarrer (refuser l'empecherait de tourner sur un
#: profil legitime mais non liste), mais pas en silence.
DELAI_PAR_PROFIL = {
    "cloud": DELAI_CLOUD,
    "freemium": DELAI_CLOUD,
    "on-premise": DELAI_LOCAL,
    "gpu_local": DELAI_LOCAL,
    "test_gpu_complet": DELAI_LOCAL,
}


def job_timeout_seconds() -> int:
    """Delai maximal d'un job, en secondes.

    Ordre : `DH_JOB_TIMEOUT_SECONDS` (decision explicite de l'exploitant), puis
    le profil de routage, puis le delai cloud avec un WARNING.

    Raises:
        ValueError: si `DH_JOB_TIMEOUT_SECONDS` n'est pas un entier positif.
            Une valeur illisible n'est pas devinee (regle 6) : un delai faux se
            paierait par des jobs coupes en plein appel LLM.
    """
    brut = os.environ.get("DH_JOB_TIMEOUT_SECONDS", "").strip()
    if brut:
        try:
            valeur = int(brut)
        except ValueError:
            raise ValueError(
                f"DH_JOB_TIMEOUT_SECONDS={brut!r} : entier de secondes attendu"
            ) from None
        if valeur <= 0:
            raise ValueError(
                f"DH_JOB_TIMEOUT_SECONDS={brut!r} : un delai doit etre positif"
            )
        return valeur

    profil = os.environ.get("DH_DEPLOYMENT_PROFILE", "").strip() or "cloud"
    if profil in DELAI_PAR_PROFIL:
        return DELAI_PAR_PROFIL[profil]

    logger.warning(
        "[Worker] Profil de routage %r inconnu de DELAI_PAR_PROFIL : delai de "
        "job fixe a %s s (valeur cloud). Ajoutez-le a la table ou posez "
        "DH_JOB_TIMEOUT_SECONDS.",
        profil,
        DELAI_CLOUD,
    )
    return DELAI_CLOUD
