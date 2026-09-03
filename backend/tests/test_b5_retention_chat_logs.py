"""B5 (03/09/2026) — rétention des conversations Sophie, 12 mois (D3).

Le modèle annonçait « auto-deleted after 90 days (cron job to add) » depuis le
8 juin ; le cron n a jamais existé (DEC-0817-04, rouge le 30/08 et le 02/09).
D3 retient 12 mois. Tests : une ligne antidatée disparaît, une ligne récente
reste (contrôle négatif — sans lui, un DELETE sans WHERE passerait), et la
tâche est bien planifiée sur le worker.
"""
from datetime import datetime, timedelta, timezone

from app.models.chat_log import ChatLog
from app.workers.retention import purger_chat_logs, RETENTION_JOURS
from app.workers.worker import WorkerSettings

from tests.test_credit_service import seeded_db  # noqa: F401


def _log(db, jours: int, session: str) -> None:
    db.add(ChatLog(session_uuid=session, ip_hash="h" * 8, role="user",
                   message="bonjour",
                   created_at=datetime.now(timezone.utc) - timedelta(days=jours)))
    db.commit()


def _table(db):
    ChatLog.__table__.create(bind=db.get_bind(), checkfirst=True)


def test_ligne_ancienne_est_purgee(seeded_db):
    _table(seeded_db)
    _log(seeded_db, 400, "vieille")
    assert purger_chat_logs(seeded_db) == 1
    assert seeded_db.query(ChatLog).count() == 0


def test_ligne_recente_est_conservee(seeded_db):
    """Contrôle négatif : la purge ne doit pas vider la table."""
    _table(seeded_db)
    _log(seeded_db, 30, "recente")
    assert purger_chat_logs(seeded_db) == 0
    assert seeded_db.query(ChatLog).count() == 1


def test_seuil_exact_a_douze_mois(seeded_db):
    _table(seeded_db)
    _log(seeded_db, RETENTION_JOURS + 1, "juste_avant")
    _log(seeded_db, RETENTION_JOURS - 1, "juste_apres")
    assert purger_chat_logs(seeded_db) == 1
    restant = seeded_db.query(ChatLog).one()
    assert restant.session_uuid == "juste_apres"


def test_retention_est_bien_douze_mois():
    assert RETENTION_JOURS == 365


def test_la_purge_est_planifiee_sur_le_worker():
    """Sans cron_jobs, la fonction existerait sans jamais tourner — le défaut de DEC-0817-04."""
    noms = {getattr(c.coroutine, "__name__", "") for c in getattr(WorkerSettings, "cron_jobs", [])}
    assert "purge_chat_logs_task" in noms
