"""VAGUE 1 / file D — GL-18 : trois compteurs faux sur l'ecran d'execution.

Backlog go-live, ligne GL-18 (= DEC-0815-02, PROD-10 partiel) : « trois
compteurs faux sur l'ecran d'execution (tokens, cout, duree) ; source de
verite : `llm_interactions` ».

Mesure du 16/09 sur `f78e8ad` :

  - `ExecutionMonitoringPage` alimente `ExecutionMetrics` avec
    `(a as any).tokens_used || 0`, `.cost || 0`, `.duration_seconds || 0`,
    lus dans `agent_progress` ;
  - `agent_progress` est construit par `_helpers.build_agent_progress`, qui
    ne pose **que** `agent_name`, `status`, `progress`, `current_task`,
    `output_summary`, `extra_data`. Aucun des trois champs n'existe.

Les trois compteurs affichent donc 0, toujours, quelle que soit l'execution.

La route `/executions/{id}/metrics` existait mais lisait ailleurs :
`agent_execution_status` (un JSON tenu par l'orchestrateur, ou `tokens_used`
n'est pas toujours ecrit) et `execution.total_cost` (un cumul USD reecrit par
deux ecrivains — BILL-10). Ce fichier exige la source designee :
`llm_interactions` pour les jetons et la duree, `credit_transactions` pour ce
que le client paie reellement.

Controle negatif : une execution sans aucun appel LLM doit rendre zero, et une
execution voisine ne doit jamais compter dans le total — sinon une somme sans
filtre passerait les assertions principales.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.credit import (
    TRANSACTION_TYPE_CHARGE,
    CreditBalance,
    CreditTransaction,
)
from app.models.execution import Execution, ExecutionStatus
from app.models.llm_interaction import LLMInteraction
from app.models.project import Project
from app.models.user import User
from app.utils.auth import create_access_token


@pytest.fixture
def compte_avec_deux_executions(db_session):
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(
        email=f"gl18-{suffixe}@exemple.test",
        hashed_password="x",
        name=f"Compte GL-18 {suffixe}",
        subscription_tier="pro",
    )
    db_session.add(utilisateur)
    db_session.commit()
    db_session.refresh(utilisateur)
    db_session.add(CreditBalance(user_id=utilisateur.id, included_credits=15000, used_credits=0))

    projet = Project(user_id=utilisateur.id, name=f"Projet GL-18 {suffixe}", language="fr")
    db_session.add(projet)
    db_session.commit()
    db_session.refresh(projet)

    executions = []
    for _ in range(2):
        execution = Execution(
            project_id=projet.id,
            user_id=utilisateur.id,
            status=ExecutionStatus.COMPLETED,
            selected_agents=["pm", "ba"],
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(execution)
        db_session.commit()
        db_session.refresh(execution)
        executions.append(execution)

    return utilisateur, projet, executions[0], executions[1]


def _appel_llm(db_session, execution_id, agent_id, entree, sortie, secondes):
    db_session.add(
        LLMInteraction(
            execution_id=execution_id,
            agent_id=agent_id,
            prompt="prompt de test",
            response="reponse de test",
            tokens_input=entree,
            tokens_output=sortie,
            execution_time_seconds=secondes,
            model="modele-fictif-gl18",
            provider="fictif",
            success=True,
        )
    )
    db_session.commit()


def _entetes(utilisateur):
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(utilisateur.id)})}"
    }


def _metrics(client, utilisateur, execution):
    reponse = client.get(
        f"/api/pm-orchestrator/executions/{execution.id}/metrics",
        headers=_entetes(utilisateur),
    )
    assert reponse.status_code == 200, reponse.text
    return reponse.json()


# ─────────────────────────────────────────────────────────────────────
# 1. Les trois compteurs sont mesures
# ─────────────────────────────────────────────────────────────────────


def test_les_jetons_viennent_de_llm_interactions(
    db_session, client, compte_avec_deux_executions
):
    utilisateur, _, execution, _autre = compte_avec_deux_executions
    _appel_llm(db_session, execution.id, "pm", 1200, 800, 12.5)
    _appel_llm(db_session, execution.id, "ba", 300, 150, 4.0)

    corps = _metrics(client, utilisateur, execution)

    totaux = corps["totals"]
    assert totaux["tokens_input"] == 1500
    assert totaux["tokens_output"] == 950
    assert totaux["tokens_total"] == 2450
    assert totaux["llm_calls"] == 2


def test_la_duree_vient_de_llm_interactions(
    db_session, client, compte_avec_deux_executions
):
    utilisateur, _, execution, _autre = compte_avec_deux_executions
    _appel_llm(db_session, execution.id, "pm", 10, 10, 12.5)
    _appel_llm(db_session, execution.id, "ba", 10, 10, 4.0)

    corps = _metrics(client, utilisateur, execution)
    assert corps["totals"]["llm_seconds"] == pytest.approx(16.5)


def test_le_cout_client_vient_du_grand_livre_des_credits(
    db_session, client, compte_avec_deux_executions
):
    """Le compteur montre au client doit etre ce qu'il paie : des credits,
    ecrits dans `credit_transactions`. `execution.total_cost` est un cumul USD
    a deux ecrivains (BILL-10) ; ce n'est pas une source pour l'ecran."""
    utilisateur, projet, execution, _autre = compte_avec_deux_executions
    _appel_llm(db_session, execution.id, "pm", 1200, 800, 12.5)
    db_session.add(
        CreditTransaction(
            user_id=utilisateur.id,
            transaction_type=TRANSACTION_TYPE_CHARGE,
            execution_id=execution.id,
            project_id=projet.id,
            model_used="modele-fictif-gl18",
            tokens_input=1200,
            tokens_output=800,
            credits_consumed=3,
        )
    )
    db_session.commit()

    corps = _metrics(client, utilisateur, execution)
    assert corps["totals"]["credits"] == 3


def test_le_detail_par_agent_est_mesure(
    db_session, client, compte_avec_deux_executions
):
    utilisateur, _, execution, _autre = compte_avec_deux_executions
    _appel_llm(db_session, execution.id, "pm", 1000, 500, 10.0)
    _appel_llm(db_session, execution.id, "pm", 200, 100, 2.0)
    _appel_llm(db_session, execution.id, "ba", 300, 150, 4.0)

    corps = _metrics(client, utilisateur, execution)
    par_agent = {ligne["agent_id"]: ligne for ligne in corps["by_agent"]}

    assert par_agent["pm"]["tokens_total"] == 1800
    assert par_agent["pm"]["llm_calls"] == 2
    assert par_agent["ba"]["tokens_total"] == 450
    assert par_agent["ba"]["llm_seconds"] == pytest.approx(4.0)


# ─────────────────────────────────────────────────────────────────────
# 2. Controles negatifs
# ─────────────────────────────────────────────────────────────────────


def test_une_execution_sans_appel_llm_rend_zero_et_le_dit(
    client, compte_avec_deux_executions
):
    """Zero mesure et « pas de donnee » ne sont pas la meme chose : l'ecran
    doit pouvoir distinguer une execution qui n'a rien consomme d'une source
    muette (regle 6)."""
    utilisateur, _, execution, _autre = compte_avec_deux_executions

    corps = _metrics(client, utilisateur, execution)
    assert corps["totals"]["tokens_total"] == 0
    assert corps["totals"]["llm_calls"] == 0
    assert corps["by_agent"] == []
    assert corps["source"] == "llm_interactions"


def test_les_appels_d_une_autre_execution_ne_sont_pas_comptes(
    db_session, client, compte_avec_deux_executions
):
    """Sans ce controle, une somme sans filtre passerait tous les tests
    ci-dessus."""
    utilisateur, _, execution, autre = compte_avec_deux_executions
    _appel_llm(db_session, execution.id, "pm", 100, 50, 1.0)
    _appel_llm(db_session, autre.id, "pm", 9999, 9999, 999.0)

    corps = _metrics(client, utilisateur, execution)
    assert corps["totals"]["tokens_total"] == 150
    assert corps["totals"]["llm_calls"] == 1


def test_un_tiers_ne_lit_pas_les_compteurs(db_session, client, compte_avec_deux_executions):
    _utilisateur, _, execution, _autre = compte_avec_deux_executions
    intrus = User(
        email=f"intrus-{uuid.uuid4().hex[:8]}@exemple.test",
        hashed_password="x",
        name="Intrus",
        subscription_tier="pro",
    )
    db_session.add(intrus)
    db_session.commit()
    db_session.refresh(intrus)

    reponse = client.get(
        f"/api/pm-orchestrator/executions/{execution.id}/metrics",
        headers=_entetes(intrus),
    )
    assert reponse.status_code in (403, 404), reponse.text
