"""
VAGUE 1 / FILE C — BILL-10 (diff de la file B) : l'orchestrateur ne doit plus
ecrire `executions.total_cost`.

Constat mesure par la file B le 16/09 : le meme appel LLM est compte deux fois.
`BudgetService.record_cost`, appele depuis `llm_service.generate_llm_response`,
ecrit le cout mesure ; puis `_track_tokens` / `_accumulate_cost` en rajoutent
une **estimation** par-dessus. Mesure : 0.018 devient 0.036. Le garde-fou de
30 USD arrete donc un SDS a la moitie du budget reellement depense — et un
cout mesure a 0.0 (modele local) tombait dans la branche d'estimation, qui
inventait 0.066 USD pour 10 000 jetons.

Les compteurs de JETONS par agent restent : ils ne sont pas en double.
"""
import pytest

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2


@pytest.fixture
def execution(db_session):
    user = User(
        email="vague1c-bill10@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C BILL-10",
        subscription_tier="pro",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    project = Project(user_id=user.id, name="BILL-10")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm"],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
        total_cost=0.018,  # deja ecrit par BudgetService pour cet appel
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


def _resultats(execution):
    return {
        "execution_id": execution.id,
        "metrics": {"total_tokens": 0, "tokens_by_agent": {}, "execution_times": {}},
    }


def test_track_tokens_n_ajoute_plus_de_cout(db_session, execution):
    service = PMOrchestratorServiceV2(db_session)
    resultats = _resultats(execution)

    service._track_tokens(
        "architect",
        {"metadata": {"tokens_used": 10_000, "model": "anthropic/claude-sonnet",
                      "cost_usd": 0.018}},
        resultats,
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.total_cost == pytest.approx(0.018), (
        f"le cout a ete compte deux fois : {relue.total_cost} au lieu de 0.018 "
        f"(BILL-10)"
    )


def test_track_tokens_compte_toujours_les_jetons(db_session, execution):
    """Controle negatif : retirer le cout ne doit pas retirer les compteurs de
    jetons, qui ne sont pas en double, eux."""
    service = PMOrchestratorServiceV2(db_session)
    resultats = _resultats(execution)

    service._track_tokens(
        "architect",
        {"metadata": {"tokens_used": 10_000, "model": "anthropic/claude-sonnet"}},
        resultats,
    )

    assert resultats["metrics"]["tokens_by_agent"]["architect"] == 10_000
    assert resultats["metrics"]["total_tokens"] == 10_000


def test_accumulate_cost_n_ecrit_plus_rien(db_session, execution):
    """Le cas le plus faux : un modele vide tombait sur le tarif « default »,
    niveau Sonnet (`_accumulate_cost(execution, architect_tokens, "")`)."""
    service = PMOrchestratorServiceV2(db_session)

    service._accumulate_cost(execution, 10_000, "")

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.total_cost == pytest.approx(0.018), (
        f"une estimation a ete ajoutee au cout mesure : {relue.total_cost}"
    )


def test_un_cout_mesure_a_zero_ne_devient_pas_une_estimation(db_session, execution):
    """Modele local : 0.0 est un cout CONNU, pas une absence de cout."""
    execution.total_cost = 0.0
    db_session.commit()

    service = PMOrchestratorServiceV2(db_session)
    resultats = _resultats(execution)
    service._track_tokens(
        "architect",
        {"metadata": {"tokens_used": 10_000, "model": "gpu_local/nemotron",
                      "cost_usd": 0.0}},
        resultats,
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.total_cost == pytest.approx(0.0), (
        f"un cout mesure a zero a ete remplace par une estimation : "
        f"{relue.total_cost}"
    )
