"""VAGUE 1 / file D — GL-16 : retention des conversations Sophie.

Le backlog dit : « Retention des conversations Sophie : 90 jours tranches ;
le code (`chat_log.py`) ne purge pas ». Mesure du 16/09 sur `f78e8ad`, avant
tout correctif :

  1. **Constat partiellement infirme.** `chat_logs` (le concierge public) EST
     purge depuis le lot B5 du 03/09 : `app/workers/retention.py`, planifie a
     03:17 UTC dans `WorkerSettings.cron_jobs`, et
     `pytest tests/test_b5_retention_chat_logs.py` -> 5 passed.

  2. **Trou reel.** Les conversations Sophie que le client tient dans le
     Studio ne sont pas dans `chat_logs` : elles sont dans
     `project_conversations` (`POST /api/projects/{id}/chat`,
     `POST /api/pm-orchestrator/executions/{id}/chat`). Mesure :

         grep -rn "ProjectConversation" backend/app --include=*.py \\
           | grep -i "delete|purge|retention"

     ne rend qu'une ligne, la cascade `all, delete-orphan` de
     `Project.conversations` : ces messages ne disparaissent **que** si le
     projet est supprime. Aucune purge par age, nulle part. Ce sont pourtant
     les conversations les plus riches en donnees client.

  3. **Duree.** Deux decisions se contredisent : DEC-0813-02 / 0817-04
     (13 et 17/08) disent 90 jours ; D3 (03/09, `docs/vague-b/EXECUTION.md`)
     dit 12 mois, et c'est elle qui est dans le code (`RETENTION_JOURS = 365`).
     Trancher est une decision humaine : ce lot ne la prend pas, il rend la
     duree **configurable** pour que passer a 90 jours soit un reglage, et
     garde par defaut la decision la plus recente.

Controles negatifs indispensables : une conversation recente doit survivre
(sinon un DELETE sans WHERE passerait), et la purge d'une table ne doit pas
emporter l'autre.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.project import Project
from app.models.project_conversation import ProjectConversation
from app.models.user import User


@pytest.fixture
def projet(db_session):
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(
        email=f"gl16-{suffixe}@exemple.test",
        hashed_password="x",
        name=f"Compte GL-16 {suffixe}",
        subscription_tier="pro",
    )
    db_session.add(utilisateur)
    db_session.commit()
    db_session.refresh(utilisateur)

    projet = Project(user_id=utilisateur.id, name=f"Projet GL-16 {suffixe}", language="fr")
    db_session.add(projet)
    db_session.commit()
    db_session.refresh(projet)
    return projet


def _message(db_session, projet, jours: int, texte: str) -> ProjectConversation:
    ligne = ProjectConversation(
        project_id=projet.id,
        role="user",
        message=texte,
        created_at=datetime.now(timezone.utc) - timedelta(days=jours),
    )
    db_session.add(ligne)
    db_session.commit()
    return ligne


# ─────────────────────────────────────────────────────────────────────
# 1. La purge des conversations de projet
# ─────────────────────────────────────────────────────────────────────


def test_une_conversation_de_projet_ancienne_est_purgee(db_session, projet):
    from app.services.retention_service import purger_conversations_projet

    _message(db_session, projet, 400, "message tres ancien")
    assert purger_conversations_projet(db_session) == 1
    assert db_session.query(ProjectConversation).count() == 0


def test_controle_negatif_une_conversation_recente_survit(db_session, projet):
    """Sans ce test, un DELETE sans clause passerait le precedent."""
    from app.services.retention_service import purger_conversations_projet

    _message(db_session, projet, 30, "message recent")
    assert purger_conversations_projet(db_session) == 0
    assert db_session.query(ProjectConversation).count() == 1


def test_le_seuil_est_exact(db_session, projet):
    from app.services.retention_service import (
        RETENTION_CONVERSATIONS_JOURS,
        purger_conversations_projet,
    )

    _message(db_session, projet, RETENTION_CONVERSATIONS_JOURS + 1, "juste avant")
    _message(db_session, projet, RETENTION_CONVERSATIONS_JOURS - 1, "juste apres")

    assert purger_conversations_projet(db_session) == 1
    restant = db_session.query(ProjectConversation).one()
    assert restant.message == "juste apres"


def test_la_duree_est_configurable_sans_toucher_au_code(db_session, projet, monkeypatch):
    """GL-16 oppose deux decisions (90 jours en aout, 12 mois le 03/09).
    Trancher est humain ; le code doit rendre le reglage possible."""
    from app.services import retention_service

    monkeypatch.setenv("DH_RETENTION_CONVERSATIONS_JOURS", "90")
    assert retention_service.retention_conversations_jours() == 90

    _message(db_session, projet, 120, "plus vieux que 90 jours")
    assert retention_service.purger_conversations_projet(db_session) == 1


def test_une_duree_illisible_est_refusee_pas_devinee(monkeypatch):
    """Regle 6 : une valeur inconnue se refuse. Une duree mal saisie ne doit
    pas silencieusement devenir « purge tout » ni « ne purge rien »."""
    from app.services import retention_service

    for valeur in ("zero", "-5", "0", ""):
        monkeypatch.setenv("DH_RETENTION_CONVERSATIONS_JOURS", valeur)
        with pytest.raises(ValueError):
            retention_service.retention_conversations_jours()


# ─────────────────────────────────────────────────────────────────────
# 2. Les deux tables sont distinctes
# ─────────────────────────────────────────────────────────────────────


def test_purger_les_conversations_de_projet_n_emporte_pas_les_chat_logs(db_session, projet):
    """Controle negatif croise : deux retentions, deux tables, deux comptes."""
    from app.models.chat_log import ChatLog
    from app.services.retention_service import purger_conversations_projet

    ChatLog.__table__.create(bind=db_session.get_bind(), checkfirst=True)
    db_session.add(
        ChatLog(
            session_uuid="visiteur",
            ip_hash="h" * 8,
            role="user",
            message="bonjour",
            created_at=datetime.now(timezone.utc) - timedelta(days=400),
        )
    )
    db_session.commit()

    _message(db_session, projet, 400, "message ancien de projet")
    assert purger_conversations_projet(db_session) == 1
    assert db_session.query(ChatLog).count() == 1, (
        "la purge des conversations de projet a emporte les chat_logs du concierge"
    )


def test_la_purge_du_concierge_reste_celle_du_lot_b5():
    """Non-regression : B5 (03/09) purge `chat_logs` a 12 mois, planifie sur le
    worker. Ce lot ne le defait pas — il le complete."""
    from app.workers.retention import RETENTION_JOURS, purger_chat_logs
    from app.workers.worker import WorkerSettings

    assert callable(purger_chat_logs)
    assert RETENTION_JOURS == 365
    noms = {
        getattr(c.coroutine, "__name__", "")
        for c in getattr(WorkerSettings, "cron_jobs", [])
    }
    assert "purge_chat_logs_task" in noms


def test_la_purge_des_conversations_expose_un_point_d_entree_planifiable():
    """La fonction doit etre appelable par le cron du worker. Le branchement
    lui-meme vit dans `app/workers/*`, attribue a une autre file de la vague 1 :
    le diff est dans le rapport, non commis ici."""
    from app.services import retention_service

    assert callable(retention_service.purger_conversations_projet)
    assert callable(retention_service.purger_toutes_les_conversations)
