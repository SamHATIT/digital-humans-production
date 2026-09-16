"""
Vague 1 / file B — BILL-10 (audit Astra du 06/09/2026, L793).

« Les coûts USD sont écrits plusieurs fois et le local reçoit un coût fictif. »

Trois mécanismes distincts, mesurés ici :

1. **Deux écrivains pour la même métrique.** ``llm_service.generate_llm_response``
   enregistre le coût via ``BudgetService.record_cost`` ; l'orchestrateur
   rajoute ensuite sa propre estimation (``_track_tokens`` / ``_accumulate_cost``).
   ``executions.total_cost`` compte donc l'appel deux fois. Le garde-fou de
   30 USD peut arrêter un SDS alors que les crédits du client sont disponibles.
   *Le correctif côté orchestrateur appartient à la file C : le diff est dans
   le rapport, pas dans ce commit. Le test ci-dessous porte sur l'écrivain de
   ce périmètre.*

2. **Zéro et inconnu confondus.** Le zéro d'un modèle local est un coût
   CONNU et nul. ``_resolve_pricing`` rendait le tarif « default »
   (niveau Sonnet) pour tout ce qu'il ne connaissait pas : un appel local
   gratuit se voyait facturer un coût cloud fictif.

3. **Estimation préférée à la mesure.** Le routeur rend un ``cost_usd``
   mesuré ; ``record_cost`` le recalculait depuis une table de prix.

Aucun appel réseau.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.budget_service import (
    BudgetService,
    UnknownPricingError,
    _resolve_pricing,
)


@pytest.fixture
def execution(db_session):
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(email=f"bill10-{suffixe}@exemple.test", hashed_password="x",
                       name=f"Compte BILL-10 {suffixe}", subscription_tier="pro")
    db_session.add(utilisateur)
    db_session.commit()
    projet = Project(user_id=utilisateur.id, name=f"Projet BILL-10 {suffixe}",
                     description="test", language="fr")
    db_session.add(projet)
    db_session.commit()
    execution = Execution(project_id=projet.id, user_id=utilisateur.id,
                          status=ExecutionStatus.RUNNING, selected_agents=["pm"])
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


# ─────────────────────────────────────────────────────────────────────
# 1. Zéro connu ≠ inconnu
# ─────────────────────────────────────────────────────────────────────


def test_un_modele_local_a_un_cout_connu_et_nul(db_session):
    """Le local est gratuit : 0.0, et c'est une valeur CONNUE."""
    tarif = _resolve_pricing("local/mistral:7b-instruct")
    assert tarif == {"input": 0.0, "output": 0.0}


def test_un_modele_inconnu_ne_recoit_pas_le_tarif_sonnet(db_session):
    """Cœur du volet 2 : un modèle inconnu n'est pas tarifé « par défaut »
    au niveau Sonnet — il est refusé, et l'appelant décide."""
    with pytest.raises(UnknownPricingError):
        _resolve_pricing("modele-jamais-vu-bill10")


def test_un_cout_mesure_a_zero_est_conserve(db_session, execution):
    """Contrôle de la distinction : un coût mesuré à 0.0 (local) est écrit
    tel quel, il n'est pas pris pour « coût absent » puis remplacé."""
    service = BudgetService(db_session)
    cout = service.record_cost(execution.id, "nemotron-lightning",
                               input_tokens=5000, output_tokens=5000,
                               cost_usd=0.0)
    assert cout == 0.0
    db_session.refresh(execution)
    assert execution.total_cost == 0.0
    assert execution.total_tokens_used == 10000


def test_un_cout_inconnu_et_non_mesure_est_refuse(db_session, execution):
    """Contrôle négatif du précédent : sans coût mesuré ET sans tarif connu,
    on ne devine pas — l'appel est refusé au lieu d'inventer un montant."""
    service = BudgetService(db_session)
    with pytest.raises(UnknownPricingError):
        service.record_cost(execution.id, "modele-jamais-vu-bill10",
                            input_tokens=1000, output_tokens=1000)


# ─────────────────────────────────────────────────────────────────────
# 2. La mesure prime sur l'estimation
# ─────────────────────────────────────────────────────────────────────


def test_le_cout_mesure_prime_sur_l_estimation(db_session, execution):
    """Quand le routeur a mesuré le coût, c'est lui qui est écrit — pas un
    recalcul depuis une table de prix qui peut diverger."""
    service = BudgetService(db_session)
    mesure = 0.1234
    cout = service.record_cost(execution.id, "claude-sonnet-5",
                               input_tokens=1000, output_tokens=1000,
                               cost_usd=mesure)
    assert cout == pytest.approx(mesure)
    db_session.refresh(execution)
    assert execution.total_cost == pytest.approx(mesure)


def test_sans_mesure_l_estimation_reste_disponible(db_session, execution):
    """Contrôle positif : un modèle connu sans coût mesuré reste estimé.
    Sans ce test, un refus systématique passerait le contrôle négatif."""
    service = BudgetService(db_session)
    cout = service.record_cost(execution.id, "anthropic/claude-sonnet",
                               input_tokens=1_000_000, output_tokens=0)
    assert cout == pytest.approx(3.0)


# ─────────────────────────────────────────────────────────────────────
# 3. Un seul écrivain : l'appel est compté une fois
# ─────────────────────────────────────────────────────────────────────


def test_le_wrapper_llm_ecrit_le_cout_une_seule_fois(db_session, execution, monkeypatch):
    """`generate_llm_response` est le seul écrivain de `total_cost` sur son
    propre appel : deux appels → deux montants, pas quatre."""
    from app.services import llm_service

    def _faux_generate(self, prompt, **kwargs):
        return {
            "content": "ok", "model": "claude-sonnet-5",
            "provider": "anthropic/claude-sonnet",
            "tokens_used": 2000, "input_tokens": 1000, "output_tokens": 1000,
            "cost_usd": 0.05, "latency_ms": 1, "success": True,
            "error": None, "stop_reason": "end_turn", "continuations": 0,
        }

    from app.services.llm_router_service import LLMRouterService
    monkeypatch.setattr(LLMRouterService, "generate", _faux_generate)

    for _ in range(2):
        llm_service.generate_llm_response(
            prompt="x", agent_type="pm", execution_id=execution.id,
            db_session=db_session, user_id=execution.user_id,
        )

    db_session.refresh(execution)
    assert execution.total_cost == pytest.approx(0.10), (
        "le cout de l'appel est compte plus d'une fois"
    )
