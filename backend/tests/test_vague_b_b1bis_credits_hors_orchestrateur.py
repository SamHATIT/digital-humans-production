"""
Vague B — lot B1-bis : les appels LLM d'agents hors orchestrateur.

Depuis le lot B1 (78ae68c), `generate_llm_response` refuse tout appel agent
sans proprietaire de credits (`CreditOwnerMissingError`, decision D10 du
03/09). Trois sites d'appel ne passaient ni `user_id` ni `execution_id`
resoluble et levaient donc a chaque requete :

  - `sophie_chat_service.py:188`     — chat projet de Sophie ;
  - `change_request_service.py:139`  — analyse d'impact d'une CR ;
  - `change_request_service.py:444`  — classification d'un message en CR ;
  - `hitl_routes.py:181`             — chat contextuel HITL.

Chacun a pourtant un utilisateur authentifie a portee : les routes
`project_chat.py`, `change_requests.py` et `hitl_routes.py` dependent toutes de
`get_current_user`. Les tests ci-dessous exercent les routes reelles, avec un
client authentifie, et verifient les deux choses qui comptent : l'appel
aboutit, et il est **facture** a l'appelant (une ligne `credit_transactions`).

Second point : le critere 4 du lot B1 n'etait pas atteint. B1 avait etabli par
execution qu'aucun chemin HTTP ne remontait « credits insuffisants » au client
(`test_vague_b_b1_credits.py::test_la_route_de_progression_ne_rend_pas_le_motif_du_refus`).
Les deux derniers tests couvrent le motif rendu par `/progress` et son
controle negatif.

Seul le transport reseau du routeur est simule ; les crochets de credit, les
routes et les services sont le code de production. Le nom de modele
(`MODELE_FICTIF`) est une valeur de fixture ecrite dans `model_pricing` de la
base jetable : ni URL, ni port, ni identifiant de modele reel (regle 9).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from app.models.change_request import ChangeRequest
from app.models.credit import TRANSACTION_TYPE_CHARGE, CreditTransaction
from app.models.execution import ExecutionStatus
from app.utils.auth import create_access_token

# Fixtures et constantes du lot B1 : meme socle tarifaire, meme transport
# simule. Les reimporter evite d'en tenir deux copies divergentes.
from tests.test_vague_b_b1_credits import (  # noqa: F401
    CREDITS_PAR_APPEL,
    JETONS_ENTREE,
    JETONS_SORTIE,
    MODELE_FICTIF,
    compte_free,
    socle_credits,
    transport_llm_simule,
)


def _entetes(utilisateur):
    return {
        "Authorization": f"Bearer {create_access_token({'sub': str(utilisateur.id)})}"
    }


def _lignes_de_credit(db_session, user_id: int):
    db_session.expire_all()
    return (
        db_session.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user_id,
            CreditTransaction.transaction_type == TRANSACTION_TYPE_CHARGE,
        )
        .all()
    )


# ─────────────────────────────────────────────────────────────────────
# 1. Chat projet de Sophie — sophie_chat_service.py:188
# ─────────────────────────────────────────────────────────────────────


def test_le_chat_projet_de_sophie_facture_l_utilisateur_appelant(
    db_session, client, compte_free, transport_llm_simule
):
    """`POST /api/projects/{id}/chat` aboutit et debite l'appelant.

    Avant correctif : `generate_llm_response` levait `CreditOwnerMissingError`,
    la route rendait 500 et aucune ligne de credit n'etait ecrite.
    """
    utilisateur, projet, _ = compte_free

    reponse = client.post(
        f"/api/projects/{projet.id}/chat",
        json={"message": "Bonjour Sophie, ou en est le projet ?"},
        headers=_entetes(utilisateur),
    )

    assert reponse.status_code == 200, reponse.text
    assert transport_llm_simule, "le transport LLM n'a jamais ete atteint"

    lignes = _lignes_de_credit(db_session, utilisateur.id)
    assert len(lignes) == len(transport_llm_simule), (
        f"{len(transport_llm_simule)} appel(s) LLM mais {len(lignes)} ligne(s) "
        f"credit_transactions : le chat projet n'est pas facture"
    )
    assert lignes[0].credits_consumed == CREDITS_PAR_APPEL


# ─────────────────────────────────────────────────────────────────────
# 2. Analyse d'impact d'une CR — change_request_service.py:139
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def cr_brouillon(db_session, compte_free):
    utilisateur, projet, execution = compte_free
    cr = ChangeRequest(
        project_id=projet.id,
        execution_id=execution.id,
        cr_number="CR-001",
        category="business_rule",
        title="Ajouter un champ de suivi",
        description="Le client veut un champ supplementaire sur l'objet Compte.",
        priority="medium",
        status="draft",
    )
    db_session.add(cr)
    db_session.commit()
    db_session.refresh(cr)
    return cr


def test_l_analyse_d_impact_d_une_cr_facture_l_utilisateur_appelant(
    db_session, client, compte_free, cr_brouillon, transport_llm_simule
):
    """`POST /api/projects/{pid}/change-requests/{id}/submit` debite l'appelant.

    Avant correctif : `analyze_impact` levait `CreditOwnerMissingError`, captee
    par son propre `except`, et la route rendait 500 « Analysis failed ».
    """
    utilisateur, projet, _ = compte_free

    reponse = client.post(
        f"/api/projects/{projet.id}/change-requests/{cr_brouillon.id}/submit",
        headers=_entetes(utilisateur),
    )

    assert reponse.status_code == 200, reponse.text
    assert transport_llm_simule, "le transport LLM n'a jamais ete atteint"

    lignes = _lignes_de_credit(db_session, utilisateur.id)
    assert len(lignes) == len(transport_llm_simule), (
        f"{len(transport_llm_simule)} appel(s) LLM mais {len(lignes)} ligne(s) "
        f"credit_transactions : l'analyse d'impact n'est pas facturee"
    )


# ─────────────────────────────────────────────────────────────────────
# 3. Classification d'un message en CR — change_request_service.py:444
# ─────────────────────────────────────────────────────────────────────


def test_la_classification_d_une_cr_facture_l_utilisateur_appelant(
    db_session, compte_free, transport_llm_simule
):
    """`create_from_chat` recevait deja `user_id` sans le transmettre au LLM.

    Le service est appele directement : la route HITL qui l'invoque avale
    l'echec (`except Exception: return None`), ce qui masquerait le defaut.
    """
    from app.services.change_request_service import ChangeRequestService

    utilisateur, _, execution = compte_free

    service = ChangeRequestService(db_session)
    service.create_from_chat(
        message="Il faudrait aussi un champ « date de relance » sur l'Opportunite.",
        execution_id=execution.id,
        user_id=utilisateur.id,
    )

    assert transport_llm_simule, (
        "aucun appel LLM : la classification a echoue avant d'atteindre le "
        "routeur (probablement CreditOwnerMissingError, avalee par son except)"
    )
    lignes = _lignes_de_credit(db_session, utilisateur.id)
    assert len(lignes) == len(transport_llm_simule), (
        f"{len(transport_llm_simule)} appel(s) LLM mais {len(lignes)} ligne(s) "
        f"credit_transactions : la classification n'est pas facturee"
    )


# ─────────────────────────────────────────────────────────────────────
# 4. Chat contextuel HITL — hitl_routes.py:181
# ─────────────────────────────────────────────────────────────────────


def test_le_chat_hitl_facture_l_utilisateur_appelant(
    db_session, client, compte_free, transport_llm_simule
):
    """`POST /api/pm-orchestrator/executions/{id}/chat` debite l'appelant.

    Avant correctif : `generate_llm_response` levait, la route rendait 500
    « LLM call failed ».
    """
    utilisateur, _, execution = compte_free

    reponse = client.post(
        f"/api/pm-orchestrator/executions/{execution.id}/chat",
        json={"message": "Peux-tu resumer la phase en cours ?", "agent_id": "sophie"},
        headers=_entetes(utilisateur),
    )

    assert reponse.status_code == 200, reponse.text
    assert transport_llm_simule, "le transport LLM n'a jamais ete atteint"

    lignes = _lignes_de_credit(db_session, utilisateur.id)
    assert len(lignes) == len(transport_llm_simule), (
        f"{len(transport_llm_simule)} appel(s) LLM mais {len(lignes)} ligne(s) "
        f"credit_transactions : le chat HITL n'est pas facture"
    )


# ─────────────────────────────────────────────────────────────────────
# 5. Le motif « credits insuffisants » remonte jusqu'au client HTTP
# ─────────────────────────────────────────────────────────────────────


def _consigner_echec(db_session, execution, message: str):
    """Ecrit `executions.logs` exactement comme `execute_workflow` l'ecrit.

    Bloc `except` de `pm_orchestrator_service_v2.execute_workflow` : une liste
    JSON d'entrees `{"type": "error", "message": str(e), "timestamp": ...}`.
    Le test reproduit ce format plutot que d'en inventer un, sinon il
    prouverait quelque chose sur un chemin qui n'existe pas.
    """
    execution.logs = json.dumps(
        [
            {
                "type": "error",
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )
    execution.status = ExecutionStatus.FAILED
    db_session.commit()


def test_la_progression_rend_le_motif_credits_insuffisants(
    db_session, client, compte_free
):
    """`/progress` nomme le palier et la limite quand le refus vient des credits.

    Le message consigne est celui que la chaine produit reellement : les agents
    (`agents/roles/*.py`) capturent l'exception par `except Exception` et n'en
    gardent que `str(e)`, que `execute_workflow` enveloppe dans
    « BR extraction failed: ... » avant de l'ecrire dans `executions.logs`.
    """
    from app.services.credit_service import InsufficientCreditsError

    utilisateur, _, execution = compte_free

    erreur = InsufficientCreditsError(user_id=utilisateur.id, requested=96, available=0)
    _consigner_echec(db_session, execution, f"BR extraction failed: {erreur}")

    reponse = client.get(
        f"/api/pm-orchestrator/execute/{execution.id}/progress",
        headers=_entetes(utilisateur),
    )

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    motif = corps.get("failure_reason")
    assert motif, f"aucun motif d'echec dans la reponse : {corps}"
    assert motif["code"] == "insufficient_credits"
    texte = motif["message"]
    assert "free" in texte.lower(), f"le palier n'est pas nomme : {texte}"
    assert "300" in texte, f"la limite n'est pas nommee : {texte}"


def test_la_progression_ne_rend_pas_de_motif_credits_pour_un_autre_echec(
    db_session, client, compte_free
):
    """Controle negatif : un echec ordinaire ne se voit pas etiquete credits."""
    utilisateur, _, execution = compte_free

    _consigner_echec(db_session, execution, "BR extraction failed: Timeout (10 min)")

    reponse = client.get(
        f"/api/pm-orchestrator/execute/{execution.id}/progress",
        headers=_entetes(utilisateur),
    )

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps.get("failure_reason") is None, (
        f"un echec de timeout est rendu comme un refus de credits : {corps}"
    )


def test_une_execution_en_cours_ne_rend_pas_de_motif_d_echec(
    db_session, client, compte_free
):
    """Second controle negatif : le motif ne parle que d'une execution finie.

    `logs` peut deja porter l'erreur d'une tentative precedente pendant qu'une
    reprise tourne ; la rendre comme motif de fin serait faux, et le flux SSE
    relirait `logs` a chaque battement pour rien.
    """
    from app.services.credit_service import InsufficientCreditsError

    utilisateur, _, execution = compte_free

    erreur = InsufficientCreditsError(user_id=utilisateur.id, requested=96, available=0)
    execution.logs = json.dumps(
        [{"type": "error", "message": f"BR extraction failed: {erreur}"}]
    )
    execution.status = ExecutionStatus.RUNNING
    db_session.commit()

    reponse = client.get(
        f"/api/pm-orchestrator/execute/{execution.id}/progress",
        headers=_entetes(utilisateur),
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json().get("failure_reason") is None


def test_la_signature_du_refus_credits_suit_l_exception_reelle(db_session, compte_free):
    """Garde-fou de couplage, pas de decor.

    Ni l'orchestrateur ni la route ne peuvent attraper
    `InsufficientCreditsError` par son type : les agents (`agents/roles/*.py`,
    hors perimetre de ce lot) la capturent par `except Exception` et n'en
    rendent que `str(e)`, que `execute_workflow` ecrit ensuite dans
    `executions.logs`. La reconnaissance se fait donc sur la signature du
    message. Ce test casse si ce message change dans `credit_service.py`, ce
    qui est exactement le point.
    """
    from app.api.routes.orchestrator._helpers import motif_credits_insuffisants
    from app.services.credit_service import InsufficientCreditsError

    utilisateur, _, _ = compte_free
    erreur = InsufficientCreditsError(user_id=utilisateur.id, requested=96, available=0)

    reconnu = motif_credits_insuffisants(f"BR extraction failed: {erreur}")
    assert reconnu is not None, (
        f"la signature de InsufficientCreditsError n'est plus reconnue : {erreur}"
    )
    assert reconnu["user_id"] == utilisateur.id
    assert reconnu["requested"] == 96
    assert reconnu["available"] == 0
    assert motif_credits_insuffisants("Timeout (10 min)") is None
