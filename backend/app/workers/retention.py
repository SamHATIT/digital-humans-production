"""B5 — rétention des conversations Sophie (chat_logs).

Décision D3 (Sam, 03/09/2026) : **12 mois**. Le visiteur peut demander
l effacement avant terme via /api/public/forget (art. 17 RGPD) ; l accès aux
données est l art. 15, servi pour les comptes par /api/account/export (B4).

Le modèle chat_log.py annonçait depuis le 8 juin « auto-deleted after 90 days
(cron job to add) » : le cron n a jamais existé (DEC-0817-04, mesuré rouge le
30/08 et le 02/09). La durée retenue par Sam n est pas 90 jours mais 12 mois.

Mécanique : tâche arq planifiée chaque nuit à 03:17 UTC (heure creuse, hors
07:00 rondes et 07:30 brief du comité). Purge par `created_at`, en une seule
requête, journalisée avec le nombre de lignes. Ne lève jamais : un échec de
purge se lit dans le journal, il ne doit pas tuer le worker.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.chat_log import ChatLog

logger = logging.getLogger(__name__)

RETENTION_JOURS = 365  # D3


def purger_chat_logs(db: Session, *, maintenant: datetime | None = None,
                     retention_jours: int = RETENTION_JOURS) -> int:
    """Supprime les chat_logs plus vieux que `retention_jours`. Rend le nombre supprimé."""
    maintenant = maintenant or datetime.now(timezone.utc)
    seuil = maintenant - timedelta(days=retention_jours)
    n = db.query(ChatLog).filter(ChatLog.created_at < seuil).delete(synchronize_session=False)
    db.commit()
    logger.info("[RETENTION] chat_logs : %d ligne(s) supprimee(s), seuil %s (%d jours)",
                n, seuil.isoformat(timespec="seconds"), retention_jours)
    return n


async def purge_chat_logs_task(ctx: dict) -> int:
    """Point d entrée arq (cron). Ouvre sa propre session."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        return purger_chat_logs(db)
    except Exception as e:  # pragma: no cover — journalisé, jamais propagé
        logger.error("[RETENTION] purge chat_logs en echec : %s", e, exc_info=True)
        return -1
    finally:
        db.close()
