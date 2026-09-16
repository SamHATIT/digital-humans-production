"""
VAGUE 1 / FILE C — GL-10 : le RAG documentaire tombe en silence.

Mesure du 15/09 : les trois collections OpenAI (`technical`, `operations`,
`business`) ont repondu `429 credit_balance_exhausted` toute la journee. 146
requetes RAG ont echoue — worker principal des 09:24, workers de calibration
des 12:16 — et les agents ont continue sans corpus avec un simple avertissement
dans le journal. Personne ne l'a su avant le soir ; quatre SDS ont ete produits
sans documentation.

Regle de Sam (15/09) : **alerte admin immediate** (Telegram + journal + tableau
de bord), **pas de message client**, et l'execution marquee
`degraded: rag_unavailable` pour pouvoir la rejouer ensuite.

Ces tests simulent le transport : aucun appel reseau reel n'est fait (la
session hermetique les refuserait, et le compterait).
"""
import pytest

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def execution(db_session):
    user = User(
        email="vague1c-gl10@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C GL-10",
        subscription_tier="pro",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    project = Project(user_id=user.id, name="GL-10")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


@pytest.fixture
def alertes(monkeypatch):
    """Double du transport d'alerte : on compte, on n'envoie rien."""
    from app.services import admin_alert_service

    envoyees = []

    def _faux_transport(sujet, corps, **kw):
        envoyees.append({"sujet": sujet, "corps": corps, **kw})
        return True

    monkeypatch.setattr(admin_alert_service, "_envoyer_telegram", _faux_transport)
    admin_alert_service.reinitialiser_deduplication()
    return envoyees


@pytest.fixture
def rag_en_panne(monkeypatch, db_session, execution):
    """Le cas du 15/09 : l'API d'embeddings repond 429."""
    from app.services import rag_service
    from app.services.execution_context import poser_execution_courante

    def _429(*a, **kw):
        raise RuntimeError("Error code: 429 - credit_balance_exhausted")

    monkeypatch.setattr(rag_service, "get_openai_embedding", _429)
    monkeypatch.setattr(rag_service, "get_collection", lambda k: object())
    monkeypatch.setattr(rag_service, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    jeton = poser_execution_courante(execution.id)
    yield
    from app.services.execution_context import reprendre_execution_courante

    reprendre_execution_courante(jeton)


def test_une_panne_rag_marque_l_execution_degradee(
    db_session, execution, alertes, rag_en_panne
):
    from app.services.rag_service import query_collection

    docs, metas = query_collection("technical", "une question")
    assert docs == [] and metas == []

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    degradations = relue.degraded or []
    assert any(d.get("motif") == "rag_unavailable" for d in degradations), (
        f"l'execution ne porte pas la trace de la panne : {degradations!r} — "
        f"impossible de savoir, ensuite, lesquelles rejouer"
    )
    trace = [d for d in degradations if d["motif"] == "rag_unavailable"][0]
    assert "technical" in str(trace.get("detail", "")), trace
    assert trace.get("at")


def test_une_panne_rag_alerte_l_administrateur(
    db_session, execution, alertes, rag_en_panne
):
    from app.services.rag_service import query_collection

    query_collection("technical", "une question")

    assert alertes, (
        "aucune alerte admin : la panne du 15/09 est restee invisible toute la "
        "journee, c'est precisement ce que GL-10 demande de corriger"
    )
    corps = alertes[0]["corps"]
    assert str(execution.id) in corps, f"l'execution concernee n'est pas nommee : {corps}"
    assert "429" in corps or "credit_balance_exhausted" in corps, (
        f"la cause n'est pas dite : {corps}"
    )
    assert "technical" in corps


def test_la_panne_n_est_pas_dite_au_client(db_session, execution, alertes, rag_en_panne):
    """« Pas de message client » (Sam, 15/09) : le contexte rendu aux agents
    est vide, il ne porte pas de texte d'erreur qui finirait dans un prompt
    puis dans un livrable."""
    from app.services.rag_service import get_salesforce_context

    contexte = get_salesforce_context("une question", agent_type="architect")
    assert contexte == "", f"un texte a ete injecte dans le prompt : {contexte!r}"


def test_cent_requetes_en_panne_ne_font_pas_cent_alertes(
    db_session, execution, alertes, rag_en_panne
):
    """146 requetes ont echoue le 15/09. Une alerte par requete rendrait le
    canal inutilisable — et une alerte noyee est une alerte perdue."""
    from app.services.rag_service import query_collection

    for _ in range(20):
        query_collection("technical", "une question")

    assert len(alertes) == 1, (
        f"{len(alertes)} alertes pour une meme panne, une seule attendue"
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    motifs = [d for d in (relue.degraded or []) if d["motif"] == "rag_unavailable"]
    assert len(motifs) == 1, f"la marque est dupliquee : {motifs}"


def test_une_autre_collection_donne_une_autre_alerte(
    db_session, execution, alertes, rag_en_panne
):
    """Controle negatif de la deduplication : elle ne doit pas masquer une
    panne differente. Le 15/09, les trois collections OpenAI sont tombees."""
    from app.services.rag_service import query_collection

    query_collection("technical", "une question")
    query_collection("operations", "une question")

    assert len(alertes) == 2


def test_sans_panne_rien_n_est_signale(db_session, execution, alertes, monkeypatch):
    """Controle negatif : un RAG qui repond ne degrade rien et n'alerte
    personne."""
    from app.services import rag_service
    from app.services.execution_context import (
        poser_execution_courante,
        reprendre_execution_courante,
    )

    class _Collection:
        def query(self, **kw):
            return {"documents": [["un document"]], "metadatas": [[{"source": "x"}]]}

    monkeypatch.setattr(rag_service, "get_collection", lambda k: _Collection())
    monkeypatch.setattr(rag_service, "get_openai_embedding", lambda t: [0.0])
    monkeypatch.setattr(rag_service, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    jeton = poser_execution_courante(execution.id)
    try:
        docs, _ = rag_service.query_collection("technical", "une question")
    finally:
        reprendre_execution_courante(jeton)

    assert docs == ["un document"]
    assert alertes == []
    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert not (relue.degraded or [])


def test_une_panne_hors_execution_alerte_quand_meme(db_session, alertes, monkeypatch):
    """Controle negatif : une panne survenue hors execution (indexation,
    concierge) n'a pas d'execution a marquer — elle doit tout de meme alerter,
    sinon la moitie des pannes resterait invisible."""
    from app.services import rag_service

    def _429(*a, **kw):
        raise RuntimeError("Error code: 429 - credit_balance_exhausted")

    monkeypatch.setattr(rag_service, "get_openai_embedding", _429)
    monkeypatch.setattr(rag_service, "get_collection", lambda k: object())
    monkeypatch.setattr(rag_service, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    rag_service.query_collection("technical", "une question")
    assert len(alertes) == 1


def test_l_alerte_ne_fait_pas_echouer_l_appelant(
    db_session, execution, rag_en_panne, monkeypatch
):
    """Une alerte qui casse la chaine serait pire que la panne qu'elle
    signale."""
    from app.services import admin_alert_service
    from app.services.rag_service import query_collection

    def _transport_casse(*a, **kw):
        raise RuntimeError("Telegram injoignable")

    monkeypatch.setattr(admin_alert_service, "_envoyer_telegram", _transport_casse)
    admin_alert_service.reinitialiser_deduplication()

    docs, metas = query_collection("technical", "une question")
    assert docs == [] and metas == []


def test_sans_jeton_telegram_aucun_envoi_n_est_tente(monkeypatch, caplog):
    """Regle 6 : le dispositif dit qu'il est inerte au lieu de le taire. En
    test, le jeton est vide — aucun appel sortant ne doit partir (la session
    hermetique le compterait comme une tentative reseau)."""
    import logging

    from app.services import admin_alert_service

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    admin_alert_service.reinitialiser_deduplication()

    with caplog.at_level(logging.ERROR):
        envoye = admin_alert_service.alerter_admin(
            "RAG indisponible", "corps de test", cle_deduplication="test-sans-jeton"
        )

    assert envoye is False
    assert any("corps de test" in r.getMessage() for r in caplog.records), (
        "l'alerte doit au moins exister dans le journal quand le transport "
        "n'est pas configure"
    )
