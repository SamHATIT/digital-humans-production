"""ARQ Worker configuration for Digital Humans.

VAGUE 0 / AS-02 (OPS-05, 16/09/2026) — la connexion Redis et le nom de la file
etaient en dur (localhost, DB 1, "digital-humans" a sept endroits : routes,
retry, worker). Une suite de tests enfilait donc ses jobs sur la file reelle.

Une seule source, lue ici : DH_REDIS_HOST, DH_REDIS_PORT, DH_REDIS_DB,
DH_ARQ_QUEUE_NAME. Les defauts sont ceux de la production ; la suite de tests
les remplace avant tout import (tests/hermetic.py). Une valeur non entiere
pour le port ou la base fait echouer l'import, elle n'est pas devinee.
"""
import asyncio
import os

from arq import create_pool
from arq.connections import RedisSettings


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name}={raw!r} : entier attendu") from None


REDIS_SETTINGS = RedisSettings(
    host=os.environ.get("DH_REDIS_HOST", "").strip() or "localhost",
    port=_int_env("DH_REDIS_PORT", 6379),
    database=_int_env("DH_REDIS_DB", 1),  # DB 1 for ARQ (DB 0 for general cache)
)

#: Nom de la file ARQ, partage par le worker et par toutes les routes qui
#: enfilent (`_queue_name=ARQ_QUEUE_NAME`).
ARQ_QUEUE_NAME = os.environ.get("DH_ARQ_QUEUE_NAME", "").strip() or "digital-humans"


#: Vague 2 / file B — OPS-02 (Astra L924) : chaque appel creait un pool,
#: jamais ferme par les appelants (routes d'enfilage, sonde worker). Un pool
#: par processus et par boucle d'evenements, ferme a l'arret (`app.main`).
#: La boucle est retenue parce qu'un pool asyncio ne se reutilise pas d'une
#: boucle a l'autre (TestClient en ouvre une par requete hors `with`).
_pool = None
_pool_boucle = None


async def get_redis_pool():
    """Pool ARQ partage du processus (cree au premier appel de la boucle)."""
    global _pool, _pool_boucle
    boucle = asyncio.get_running_loop()
    if _pool is not None and _pool_boucle is boucle:
        return _pool
    nouveau = await create_pool(REDIS_SETTINGS)
    if _pool is not None and _pool_boucle is boucle:
        # Un autre appel concurrent l'a cree pendant notre attente.
        await nouveau.aclose()
        return _pool
    _pool, _pool_boucle = nouveau, boucle
    return _pool


async def close_redis_pool() -> None:
    """Ferme le pool partage (arret de l'application). Idempotent."""
    global _pool, _pool_boucle
    pool, boucle = _pool, _pool_boucle
    _pool, _pool_boucle = None, None
    if pool is not None and boucle is asyncio.get_running_loop():
        await pool.aclose()


def _reinitialiser_pool_pour_tests() -> None:
    """Oublie le pool partage sans le fermer (tests uniquement)."""
    global _pool, _pool_boucle
    _pool, _pool_boucle = None, None
