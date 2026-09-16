"""
VAGUE 1 / FILE C — GL-16 (diff de la file D) : la purge des conversations du
Studio doit etre planifiee.

`retention_service.purger_conversations_projet` existe et est testee (file D),
mais aucun planificateur ne l'appelait — exactement le defaut que DEC-0817-04
avait deja produit pour `chat_logs` : « le cron n'a jamais existe », et la
politique de confidentialite promettait une purge qui n'avait pas lieu.

Ces tests portent sur l'OBJET `WorkerSettings.cron_jobs`, pas sur la source :
un cron declare dans un commentaire ne purge rien.
"""
import pytest

from app.workers import retention
from app.workers.worker import WorkerSettings


def _noms_des_crons():
    noms = []
    for job in WorkerSettings.cron_jobs:
        fonction = getattr(job, "coroutine", None) or getattr(job, "func", None)
        noms.append(getattr(fonction, "__name__", str(fonction)))
    return noms


def test_la_purge_des_conversations_est_planifiee():
    assert "purge_conversations_projet_task" in _noms_des_crons(), (
        f"la purge des conversations du Studio n'est appelee par aucun "
        f"planificateur : {_noms_des_crons()}"
    )


def test_la_purge_des_chat_logs_reste_planifiee():
    """Controle negatif : ajouter un cron ne doit pas en remplacer un autre."""
    assert "purge_chat_logs_task" in _noms_des_crons()


def test_les_deux_purges_ne_tournent_pas_a_la_meme_minute():
    """Deux transactions de suppression en parallele sur la meme base, a la
    meme seconde, n'apportent rien et se genent."""
    def _normaliser(valeur):
        if valeur is None:
            return ()
        if isinstance(valeur, int):
            return (valeur,)
        return tuple(valeur)

    heures = set()
    for job in WorkerSettings.cron_jobs:
        heures.add((_normaliser(job.hour), _normaliser(job.minute)))
    assert len(heures) == len(WorkerSettings.cron_jobs), (
        f"deux crons partagent le meme horaire : {heures}"
    )


@pytest.mark.asyncio
async def test_la_tache_avale_ses_erreurs_et_les_journalise(monkeypatch, caplog):
    """Une purge nocturne en echec ne doit pas faire tomber le worker — mais
    elle doit laisser une trace, sinon elle echouerait en silence comme la
    supervision N8N (GL-15)."""
    import logging

    def _casse(db, **kw):
        raise RuntimeError("table verrouillee")

    monkeypatch.setattr(
        "app.services.retention_service.purger_conversations_projet", _casse
    )

    with caplog.at_level(logging.ERROR):
        resultat = await retention.purge_conversations_projet_task({})

    assert resultat == -1
    assert any("project_conversations" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_la_tache_rend_le_nombre_de_lignes_purgees(monkeypatch):
    """Controle positif : la tache appelle bien le service et rend son compte."""
    monkeypatch.setattr(
        "app.services.retention_service.purger_conversations_projet",
        lambda db, **kw: 7,
    )
    assert await retention.purge_conversations_projet_task({}) == 7
