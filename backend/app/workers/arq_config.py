"""ARQ Worker configuration for Digital Humans.

VAGUE 0 / AS-02 (OPS-05, 16/09/2026) — la connexion Redis et le nom de la file
etaient en dur (localhost, DB 1, "digital-humans" a sept endroits : routes,
retry, worker). Une suite de tests enfilait donc ses jobs sur la file reelle.

Une seule source, lue ici : DH_REDIS_HOST, DH_REDIS_PORT, DH_REDIS_DB,
DH_ARQ_QUEUE_NAME. Les defauts sont ceux de la production ; la suite de tests
les remplace avant tout import (tests/hermetic.py). Une valeur non entiere
pour le port ou la base fait echouer l'import, elle n'est pas devinee.
"""
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


async def get_redis_pool():
    """Create and return an ARQ Redis connection pool."""
    return await create_pool(REDIS_SETTINGS)
