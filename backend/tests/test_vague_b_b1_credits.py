"""
Vague B — lot B1 : le compteur de credits.

Defaut mesure le 02/09 sur la production : `credit_transactions` contient 0
ligne pour 222 `llm_interactions` sur 30 jours. Cause : `LLMRequest.user_id`
valait `None` par defaut et les deux crochets de credit du routeur
(`_credit_preflight`, `_credit_post_charge`) faisaient un no-op silencieux
dans ce cas ; aucun appel de l'orchestrateur ne renseignait `user_id`.
Decision D10 (03/09) : `user_id` obligatoire sur tout appel LLM agent, le
concierge public passant par un chemin explicite.

Ce que ce fichier etablit, dans l'ordre :

  1. `test_un_appel_agent_par_l_orchestrateur_ecrit_une_ligne_de_credit`
     — chemin reel : `PMOrchestratorServiceV2._run_agent` -> `PMAgent.run`
     -> `generate_llm_response` -> `LLMRouterService.complete`. Seul le
     transport LLM est simule. Une ligne `credit_transactions` par appel.
  2. `test_un_appel_agent_sans_proprietaire_leve_une_erreur_nommant_l_appelant`
     — regle 5 : une valeur inconnue est refusee, pas devinee.
  3. `test_le_concierge_public_passe_par_le_chemin_sans_compte`
     — le concierge ne leve pas et n'ecrit aucune ligne de credit.
  4. Controles negatifs de quota : Free au-dela de 300 credits/jour, Pro
     au-dela de 15 000 credits/mois.
  5. `test_le_message_de_quota_s_arrete_a_l_orchestrateur` — jusqu'ou le
     message remonte reellement aujourd'hui.

Aucun appel reseau : `_call_provider` est monkeypatche. Le nom de modele
utilise (`MODELE_FICTIF`) est une valeur de fixture ecrite dans la table
`model_pricing` de la base jetable ; ce n'est ni une URL, ni un port, ni
l'identifiant d'un modele reel (regle 9 de la mission vague B).
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest

from app.models.credit import (
    TRANSACTION_TYPE_CHARGE,
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services import llm_router_service as routeur_mod
from app.services.llm_router_service import LLMResponse, LLMRouterService

# Valeurs de fixture, jamais des identifiants de service (regle 9).
MODELE_FICTIF = "modele-fictif-b1"
FOURNISSEUR_FICTIF = "fictif/modele-fictif-b1"

# 1 credit / 1k jetons en entree, 2 credits / 1k en sortie.
# L'appel simule consomme 1 200 + 800 jetons => 1.2 + 1.6 = 2.8 => 3 credits.
JETONS_ENTREE = 1200
JETONS_SORTIE = 800
CREDITS_PAR_APPEL = 3


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def socle_credits(db_session):
    """Tarifs et paliers dans la base jetable : Free 300/jour, Pro 15 000/mois."""
    db_session.add_all(
        [
            TierConfig(
                tier_name="free",
                monthly_credits=0,
                daily_credits_cap=300,
                price_eur_monthly=0,
                description="free",
            ),
            TierConfig(
                tier_name="pro",
                monthly_credits=15000,
                daily_credits_cap=None,
                price_eur_monthly=79,
                description="pro",
            ),
            ModelPricing(
                model_name=MODELE_FICTIF,
                credits_per_1k_input=1.0,
                credits_per_1k_output=2.0,
                allowed_tiers="free,pro,team",
                requires_opt_in=False,
                is_active=True,
            ),
        ]
    )
    db_session.commit()


def _creer_compte(db_session, palier: str):
    """Un utilisateur du palier demande, son projet et une execution en cours."""
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(
        email=f"b1-{suffixe}@exemple.test",
        hashed_password="x",
        name=f"Compte B1 {suffixe}",
        subscription_tier=palier,
    )
    db_session.add(utilisateur)
    db_session.commit()
    db_session.refresh(utilisateur)

    projet = Project(
        user_id=utilisateur.id,
        name=f"Projet B1 {suffixe}",
        description="Projet de test du lot B1",
        language="en",
    )
    db_session.add(projet)
    db_session.commit()
    db_session.refresh(projet)

    execution = Execution(
        project_id=projet.id,
        user_id=utilisateur.id,
        status=ExecutionStatus.RUNNING,
        selected_agents=["pm"],
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return utilisateur, projet, execution


@pytest.fixture
def compte_free(db_session, socle_credits):
    return _creer_compte(db_session, "free")


@pytest.fixture
def compte_pro(db_session, socle_credits):
    return _creer_compte(db_session, "pro")


@pytest.fixture
def transport_llm_simule(monkeypatch):
    """Remplace le seul transport reseau du routeur.

    Tout le reste du routeur (selection du fournisseur exclue, crochets de
    credit inclus) reste le code de production : c'est precisement ce que le
    test doit exercer.
    """
    appels = []

    async def _faux_appel(self, request, provider_str):
        appels.append(request)
        return LLMResponse(
            content=json.dumps({"business_requirements": []}),
            provider=provider_str,
            model_id=MODELE_FICTIF,
            tokens_in=JETONS_ENTREE,
            tokens_out=JETONS_SORTIE,
            cost_usd=0.01,
            latency_ms=1,
            success=True,
        )

    monkeypatch.setattr(LLMRouterService, "_call_provider", _faux_appel)
    monkeypatch.setattr(
        LLMRouterService, "_select_provider", lambda self, request: FOURNISSEUR_FICTIF
    )
    monkeypatch.setattr(
        LLMRouterService, "_get_model_id", lambda self, provider_str: MODELE_FICTIF
    )
    # Le routeur est un singleton : on le remet a zero pour que les patchs
    # s'appliquent a une instance construite apres eux.
    monkeypatch.setattr(routeur_mod, "_router_instance", None, raising=False)
    return appels


def _lignes_de_credit(db_session, user_id: int):
    return (
        db_session.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user_id,
            CreditTransaction.transaction_type == TRANSACTION_TYPE_CHARGE,
        )
        .all()
    )


# ─────────────────────────────────────────────────────────────────────
# 1. Chemin nominal — l'orchestrateur fait payer l'appel
# ─────────────────────────────────────────────────────────────────────


def test_un_appel_agent_par_l_orchestrateur_ecrit_une_ligne_de_credit(
    db_session, compte_free, transport_llm_simule
):
    """Un appel agent lance par l'orchestrateur produit une ligne de credit.

    Le chemin exerce est celui de la production :
    `PMOrchestratorServiceV2._run_agent` (methode reellement appelee a chaque
    phase de `execute_workflow`, cf. le grep colle dans le rapport du lot)
    -> `PMAgent.run` -> `app.services.llm_service.generate_llm_response`
    -> `LLMRouterService.complete` -> crochets de credit.

    L'execution complete de `execute_workflow` n'est pas jouee ici : elle
    enchaine 24 etats, le RAG, sfdx et six phases, ce qui ferait de ce test
    un test d'integration de plusieurs minutes sans rien prouver de plus sur
    la propagation du proprietaire des credits.
    """
    from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

    utilisateur, projet, execution = compte_free

    orchestrateur = PMOrchestratorServiceV2(db_session)
    resultat = asyncio.run(
        orchestrateur._run_agent(
            agent_id="pm",
            input_data={"description": "Un brief court pour le lot B1."},
            execution_id=execution.id,
            project_id=projet.id,
            mode="extract_br",
        )
    )

    assert resultat.get("success") is True, (
        f"l'agent n'a pas abouti, le test ne prouverait rien : {resultat.get('error')}"
    )
    assert transport_llm_simule, "le transport LLM n'a jamais ete atteint"

    lignes = _lignes_de_credit(db_session, utilisateur.id)
    assert len(lignes) == len(transport_llm_simule), (
        f"{len(transport_llm_simule)} appel(s) LLM mais {len(lignes)} ligne(s) "
        f"credit_transactions : le compteur ne suit pas les appels"
    )
    assert lignes[0].credits_consumed == CREDITS_PAR_APPEL
    assert lignes[0].execution_id == execution.id
    assert lignes[0].tokens_input == JETONS_ENTREE
    assert lignes[0].tokens_output == JETONS_SORTIE


def test_le_proprietaire_des_credits_vient_de_la_ligne_execution(
    db_session, compte_free, transport_llm_simule
):
    """`user_id` est celui de `executions.user_id`, pas une valeur devinee."""
    from app.services.llm_service import generate_llm_response

    utilisateur, projet, execution = compte_free

    reponse = generate_llm_response(
        prompt="Test B1",
        agent_type="pm",
        execution_id=execution.id,
        project_id=projet.id,
        max_tokens=500,
    )
    assert reponse["success"] is True

    assert transport_llm_simule, "le transport LLM n'a jamais ete atteint"
    assert transport_llm_simule[0].user_id == utilisateur.id, (
        "le routeur a recu un autre proprietaire que celui de l'execution"
    )
    assert len(_lignes_de_credit(db_session, utilisateur.id)) == 1


# ─────────────────────────────────────────────────────────────────────
# 2. Regle 5 — un appel agent sans proprietaire leve, il ne saute pas
# ─────────────────────────────────────────────────────────────────────


def test_un_appel_agent_sans_proprietaire_leve_une_erreur_nommant_l_appelant(
    db_session, socle_credits, transport_llm_simule
):
    """Sans `user_id` ni execution resoluble, l'appel echoue et se nomme."""
    from app.services.llm_service import generate_llm_response
    from app.services.llm_router_service import CreditOwnerMissingError

    with pytest.raises(CreditOwnerMissingError) as capture:
        generate_llm_response(
            prompt="Test B1 sans proprietaire",
            agent_type="pm",
            max_tokens=500,
        )

    message = str(capture.value)
    assert "pm" in message, f"l'erreur ne nomme pas l'agent : {message}"
    assert (
        "test_un_appel_agent_sans_proprietaire_leve_une_erreur_nommant_l_appelant"
        in message
    ), f"l'erreur ne nomme pas la fonction appelante : {message}"
    assert not transport_llm_simule, (
        "l'appel LLM a eu lieu malgre l'absence de proprietaire des credits"
    )


def test_le_routeur_refuse_une_requete_sans_proprietaire_et_sans_chemin_public(
    db_session, socle_credits, transport_llm_simule
):
    """Derniere barriere : `complete()` lui-meme refuse `user_id=None`."""
    from app.services.llm_router_service import (
        CreditOwnerMissingError,
        LLMRequest,
        get_llm_router,
    )

    requete = LLMRequest(prompt="Test B1", agent_type="architect")
    with pytest.raises(CreditOwnerMissingError):
        asyncio.run(get_llm_router().complete(requete))
    assert not transport_llm_simule


def test_le_routeur_refuse_la_contradiction_sans_compte_avec_proprietaire(
    db_session, compte_free, transport_llm_simule
):
    """`sans_compte=True` et un `user_id` en meme temps est une incoherence."""
    from app.services.llm_router_service import (
        CreditOwnerMissingError,
        LLMRequest,
        get_llm_router,
    )

    utilisateur, _, _ = compte_free
    requete = LLMRequest(
        prompt="Test B1", agent_type="pm", user_id=utilisateur.id, sans_compte=True
    )
    with pytest.raises(CreditOwnerMissingError):
        asyncio.run(get_llm_router().complete(requete))


# ─────────────────────────────────────────────────────────────────────
# 3. Le concierge public — chemin explicite, controle negatif
# ─────────────────────────────────────────────────────────────────────


def test_le_concierge_public_passe_par_le_chemin_sans_compte(
    db_session, socle_credits, transport_llm_simule, monkeypatch
):
    """Un tour concierge aboutit, sans compte, sans ligne de credit.

    Controle negatif du correctif : le visiteur du site n'a pas de compte ;
    il ne doit ni faire lever le garde-fou, ni produire de debit.
    """
    from app.services import sophie_concierge_service as concierge

    monkeypatch.setattr(concierge, "IP_SALT", "sel-de-test-lot-b1")

    reponse = asyncio.run(
        concierge.converse(
            db=db_session,
            session_uuid=str(uuid.uuid4()),
            visitor_ip="203.0.113.9",
            visitor_language="fr",
            user_message="Bonjour, que fait Digital Humans ?",
        )
    )

    assert transport_llm_simule, "le tour concierge n'a pas atteint le routeur"
    requete = transport_llm_simule[0]
    assert requete.sans_compte is True, (
        "le concierge n'emprunte pas le chemin explicite sans compte"
    )
    assert requete.user_id is None
    assert reponse.text, "le concierge n'a rien rendu au visiteur"

    assert db_session.query(CreditTransaction).count() == 0, (
        "un tour concierge public a produit une ligne credit_transactions"
    )


# ─────────────────────────────────────────────────────────────────────
# 4. Controles negatifs de quota
# ─────────────────────────────────────────────────────────────────────


def test_free_au_dela_du_plafond_journalier_est_refuse(
    db_session, compte_free, transport_llm_simule
):
    """Free : 300 credits/jour consommes => l'appel suivant est refuse."""
    from app.services.credit_service import InsufficientCreditsError
    from app.services.llm_service import generate_llm_response

    utilisateur, projet, execution = compte_free

    db_session.add(
        CreditTransaction(
            user_id=utilisateur.id,
            transaction_type=TRANSACTION_TYPE_CHARGE,
            model_used=MODELE_FICTIF,
            tokens_input=0,
            tokens_output=0,
            credits_consumed=300,
            note="consommation du jour, fixture B1",
        )
    )
    db_session.commit()

    with pytest.raises(InsufficientCreditsError) as capture:
        generate_llm_response(
            prompt="Test B1 quota Free",
            agent_type="pm",
            execution_id=execution.id,
            project_id=projet.id,
            max_tokens=500,
        )

    message = str(capture.value)
    assert str(utilisateur.id) in message
    assert "available=0" in message, f"message de quota peu clair : {message}"
    assert not transport_llm_simule, (
        "l'appel LLM a eu lieu alors que le plafond journalier etait atteint"
    )


def test_pro_au_dela_de_l_allocation_mensuelle_est_refuse(
    db_session, compte_pro, transport_llm_simule
):
    """Pro : 15 000 credits/mois consommes => l'appel suivant est refuse."""
    from app.services.credit_service import InsufficientCreditsError
    from app.services.llm_service import generate_llm_response

    utilisateur, projet, execution = compte_pro

    db_session.add(
        CreditBalance(
            user_id=utilisateur.id,
            included_credits=15000,
            used_credits=15000,
            overage_credits=0,
            last_reset_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    with pytest.raises(InsufficientCreditsError) as capture:
        generate_llm_response(
            prompt="Test B1 quota Pro",
            agent_type="pm",
            execution_id=execution.id,
            project_id=projet.id,
            max_tokens=500,
        )

    message = str(capture.value)
    assert str(utilisateur.id) in message
    assert "available=0" in message, f"message de quota peu clair : {message}"
    assert not transport_llm_simule


# ─────────────────────────────────────────────────────────────────────
# 5. Jusqu'ou le refus remonte reellement
# ─────────────────────────────────────────────────────────────────────


def test_le_message_de_quota_s_arrete_a_l_orchestrateur(
    db_session, compte_free, transport_llm_simule
):
    """Mesure du chemin de remontee, sans rien inventer hors perimetre.

    Ce que ce test etablit par execution :
      - `_run_agent` rend `success=False` et un message qui nomme le manque
        de credits (c'est ce que `execute_workflow` ecrit ensuite dans
        `executions.logs`) ;
      - la route `GET /api/pm-orchestrator/execute/{id}/progress` ne rend
        aucun champ portant ce message.

    Autrement dit : aujourd'hui, aucune route ne remonte le motif du refus
    au client HTTP. Le cabler releve des routes, hors du perimetre du lot.
    """
    from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

    utilisateur, projet, execution = compte_free

    db_session.add(
        CreditTransaction(
            user_id=utilisateur.id,
            transaction_type=TRANSACTION_TYPE_CHARGE,
            model_used=MODELE_FICTIF,
            tokens_input=0,
            tokens_output=0,
            credits_consumed=300,
            note="consommation du jour, fixture B1",
        )
    )
    db_session.commit()

    orchestrateur = PMOrchestratorServiceV2(db_session)
    resultat = asyncio.run(
        orchestrateur._run_agent(
            agent_id="pm",
            input_data={"description": "Un brief court pour le lot B1."},
            execution_id=execution.id,
            project_id=projet.id,
            mode="extract_br",
        )
    )

    assert resultat.get("success") is False
    assert "credit" in str(resultat.get("error", "")).lower(), (
        f"le motif du refus n'a pas survecu jusqu'a l'orchestrateur : {resultat}"
    )


def test_la_route_de_progression_rend_le_motif_du_refus(
    db_session, client, compte_free
):
    """Le motif d'un refus de credits atteint bien le client HTTP.

    Historique : ce test portait le nom inverse
    (`..._ne_rend_pas_le_motif_du_refus`) et constatait l'absence du champ.
    C'etait le constat du lot B1 : la route de lancement rend 202 (le travail
    part dans un job ARQ) et `/progress` ne rendait que `status: "failed"`.
    Le lot B1-bis a cable le motif ; l'assertion est retournee en consequence,
    et le controle negatif (un echec de timeout ne doit pas etre etiquete
    « credits ») vit dans
    `test_vague_b_b1bis_credits_hors_orchestrateur.py`.

    Le message consigne est celui que la chaine produit reellement : les agents
    aplatissent l'exception en chaine (`except Exception: str(e)`) et
    `execute_workflow` l'ecrit dans `executions.logs`.
    """
    from app.services.credit_service import InsufficientCreditsError
    from app.utils.auth import create_access_token

    utilisateur, _, execution = compte_free
    erreur = InsufficientCreditsError(user_id=utilisateur.id, requested=96, available=0)
    execution.logs = json.dumps(
        [{"type": "error", "message": f"BR extraction failed: {erreur}"}]
    )
    execution.status = ExecutionStatus.FAILED
    db_session.commit()

    entetes = {"Authorization": f"Bearer {create_access_token({'sub': str(utilisateur.id)})}"}
    reponse = client.get(
        f"/api/pm-orchestrator/execute/{execution.id}/progress", headers=entetes
    )

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["status"] == "failed"
    motif = corps.get("failure_reason")
    assert motif, f"le motif du refus ne remonte pas au client : {corps}"
    assert motif["code"] == "insufficient_credits"
    assert "free" in motif["message"].lower()
    assert "300" in motif["message"]
