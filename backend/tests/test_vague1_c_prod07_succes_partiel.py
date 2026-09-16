"""
VAGUE 1 / FILE C — PROD-07 : des echecs de production, de QA et de persistance
deviennent un « SDS termine ».

Astra L478. Les cas cites : un lot BA echoue est ignore si d'autres UC
existent ; l'echec d'Emma Validate devient `completed` ; l'echec d'Elena
n'empeche pas le SDS final ; un echec d'ecriture de livrable est journalise
puis avale.

Critere de sortie de la file (Astra) : « pas de succes partiel cache ».

Arbitrage retenu ici, et ses limites — lire le rapport de file :
- une **persistance** echouee interdit la finalisation. Un SDS annonce termine
  dont le livrable n'est pas en base n'est pas un SDS termine ;
- un echec d'expert reste non fatal (choix produit, H21) mais cesse d'etre
  invisible : il est trace sur l'execution (`degraded`) et expose par l'API ;
- aucun statut nouveau n'est introduit : `partial` changerait le contrat lu par
  le frontend, qui appartient a une autre file. La trace est **additive**.
"""
import pytest

from app.models.agent import Agent
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

PROGRESS_URL = "/api/pm-orchestrator/execute/{eid}/progress"


@pytest.fixture
def contexte(db_session):
    for nom in ("Sophie", "Olivia", "Emma", "Marcus", "Elena"):
        db_session.add(Agent(name=nom, description=f"Agent {nom}"))
    user = User(
        email="vague1c-prod07@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C PROD-07",
        subscription_tier="pro",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    project = Project(user_id=user.id, name="PROD-07")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba", "qa"],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
        execution_state="sds_phase4_running",
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return {"user": user, "project": project, "execution": execution}


# --------------------------------------------------------------------------
# Une persistance echouee ne se tait plus
# --------------------------------------------------------------------------

def test_un_livrable_non_persiste_est_signale(db_session, contexte):
    """« Un echec d'ecriture de livrable est journalise puis avale. »"""
    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]

    class _Inserialisable:
        pass

    ok = service._save_deliverable(
        execution.id, "research_analyst", "sds_document",
        {"content": _Inserialisable(), "metadata": {}},
    )

    assert ok is False, (
        "l'echec de persistance est rendu comme un succes : l'appelant ne peut "
        "pas savoir que le livrable n'existe pas"
    )
    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    motifs = [d.get("motif") for d in (relue.degraded or [])]
    assert "deliverable_not_persisted" in motifs, (
        f"rien ne trace la perte du livrable : {relue.degraded!r}"
    )


def test_un_livrable_persiste_ne_signale_rien(db_session, contexte):
    """Controle negatif : le chemin nominal ne doit rien tracer, sinon la
    trace ne voudrait plus rien dire."""
    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]

    ok = service._save_deliverable(
        execution.id, "research_analyst", "sds_document",
        {"content": {"texte": "un vrai livrable"}, "metadata": {"tokens_used": 3}},
    )

    assert ok is True
    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert not (relue.degraded or [])


# --------------------------------------------------------------------------
# La finalisation refuse un livrable manquant
# --------------------------------------------------------------------------

def test_la_finalisation_refuse_un_sds_non_persiste(db_session, contexte):
    """Une etape obligatoire ratee interdit `completed` (Astra : « une etape
    obligatoire ou une persistance echouee interdit la finalisation »)."""
    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]
    service._tracer_degradation(
        execution.id, "deliverable_not_persisted",
        "research_analyst_sds_document : boom",
    )

    with pytest.raises(Exception) as echec:
        service._verifier_finalisation_possible(execution.id)

    assert "sds_document" in str(echec.value) or "persist" in str(echec.value).lower()


def test_la_finalisation_accepte_une_degradation_non_bloquante(db_session, contexte):
    """Controle negatif : un expert manquant ou un RAG tombe n'interdisent pas
    de livrer — ils doivent etre visibles, pas bloquants. Un correctif qui
    bloquerait sur toute degradation fermerait la porte a des SDS livrables."""
    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]
    service._tracer_degradation(execution.id, "rag_unavailable", "collection technical")
    service._tracer_degradation(execution.id, "expert_failed", "qa : timeout")

    service._verifier_finalisation_possible(execution.id)  # ne leve pas


# --------------------------------------------------------------------------
# Les echecs non fatals sont visibles dans l'API
# --------------------------------------------------------------------------

def test_un_expert_en_echec_est_trace(db_session, contexte):
    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]

    service._tracer_degradation(execution.id, "expert_failed", "qa (Elena) : timeout")

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    traces = [d for d in (relue.degraded or []) if d["motif"] == "expert_failed"]
    assert traces and "qa" in traces[0]["detail"]


def test_la_progression_expose_les_degradations(client, db_session, contexte):
    """« Les omissions explicitement acceptables doivent etre visibles dans
    l'API. » Champ additif : aucune cle existante n'est touchee."""
    from app.main import app
    from app.utils.dependencies import (
        get_current_user,
        get_current_user_from_token_or_header,
    )

    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]
    service._tracer_degradation(execution.id, "expert_failed", "qa (Elena) : timeout")

    async def _override():
        return contexte["user"]

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override

    r = client.get(PROGRESS_URL.format(eid=execution.id))
    assert r.status_code == 200, r.text
    charge = r.json()

    for cle in ("execution_id", "status", "overall_progress", "agent_progress"):
        assert cle in charge, f"contrat d'API casse : {cle} a disparu"

    assert "degraded" in charge, (
        "les degradations ne sont pas exposees : le client voit un SDS termine "
        "sans savoir ce qui a manque"
    )
    assert any(d["motif"] == "expert_failed" for d in charge["degraded"])


def test_une_execution_saine_expose_une_liste_vide(client, db_session, contexte):
    """Controle negatif : le champ existe toujours et vaut une liste vide —
    l'absence de degradation se lit, elle ne se devine pas."""
    from app.main import app
    from app.utils.dependencies import (
        get_current_user,
        get_current_user_from_token_or_header,
    )

    async def _override():
        return contexte["user"]

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override

    r = client.get(PROGRESS_URL.format(eid=contexte["execution"].id))
    assert r.status_code == 200, r.text
    assert r.json()["degraded"] == []
