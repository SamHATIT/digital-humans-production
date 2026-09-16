"""VAGUE 1 / file D — BILL-11 : un refus de credits n'est pas une analyse reussie.

Constat d'Astra (06/09, L807), volet serveur : « l'analyse CR capture meme
`InsufficientCreditsError`, remplace l'analyse par un fallback et retourne
`success=True` ; la route ne restitue pas toujours `fallback_used` ».

Mesure du 16/09 sur `f78e8ad`, `change_request_service.py:212-220` :

    except Exception as e:
        ...
        impact_data = self._fallback_impact_analysis(cr)
        cr.status = "analyzed"
        ...
        return {"success": True, ..., "fallback_used": True}

Un `except Exception` nu attrape donc aussi le refus de credits. Trois
consequences mesurables : la CR passe en `analyzed` alors qu'aucune analyse
n'a eu lieu, la route repond 200 « CR submitted and analyzed » sans jamais
transmettre `fallback_used`, et le client ne sait pas que son solde est
epuise — exactement le defaut que BILL-11 decrit cote ecran d'execution.

Le volet interface (motif lu et affiche, rejeu non propose) est couvert par
`frontend/tests/executionFailure.test.ts`.

Controle negatif indispensable : une panne **autre** que le credit doit
continuer a produire le fallback documente. Sans lui, « refuser sur credits »
se confondrait avec « ne plus jamais se replier ».
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.change_request import ChangeRequest
from app.models.credit import CreditBalance
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.credit_service import InsufficientCreditsError
from app.utils.auth import create_access_token

from tests.test_vague_b_b1_credits import socle_credits  # noqa: F401


@pytest.fixture
def cr_a_analyser(db_session, socle_credits):
    """Un compte, son projet, une execution et une CR soumise."""
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(
        email=f"bill11-{suffixe}@exemple.test",
        hashed_password="x",
        name=f"Compte BILL-11 {suffixe}",
        subscription_tier="pro",
    )
    db_session.add(utilisateur)
    db_session.commit()
    db_session.refresh(utilisateur)
    db_session.add(CreditBalance(user_id=utilisateur.id, included_credits=15000, used_credits=0))

    projet = Project(user_id=utilisateur.id, name=f"Projet {suffixe}", language="fr")
    db_session.add(projet)
    db_session.commit()
    db_session.refresh(projet)

    execution = Execution(
        project_id=projet.id,
        user_id=utilisateur.id,
        status=ExecutionStatus.COMPLETED,
        selected_agents=["pm"],
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    cr = ChangeRequest(
        project_id=projet.id,
        execution_id=execution.id,
        cr_number="CR-011",
        category="business_rule",
        title="Ajouter un champ de suivi",
        description="Le client veut un champ supplementaire sur l'objet Compte.",
        priority="medium",
        # `POST .../submit` n'accepte qu'une CR en brouillon.
        status="draft",
    )
    db_session.add(cr)
    db_session.commit()
    db_session.refresh(cr)
    return utilisateur, projet, cr


def _refuser_les_credits(monkeypatch, user_id: int):
    """Le routeur leve `InsufficientCreditsError`, comme quand le solde est a sec."""
    from app.services import change_request_service as module

    def _lever(*args, **kwargs):
        raise InsufficientCreditsError(user_id=user_id, requested=96, available=0)

    monkeypatch.setattr(module, "generate_llm_response", _lever)


def _paner_le_fournisseur(monkeypatch):
    """Une panne qui n'a rien a voir avec les credits."""
    from app.services import change_request_service as module

    def _lever(*args, **kwargs):
        raise RuntimeError("upstream timeout")

    monkeypatch.setattr(module, "generate_llm_response", _lever)


# ─────────────────────────────────────────────────────────────────────
# 1. Le service
# ─────────────────────────────────────────────────────────────────────


def test_un_refus_de_credits_n_est_pas_une_analyse_reussie(
    db_session, cr_a_analyser, monkeypatch
):
    from app.services.change_request_service import ChangeRequestService

    utilisateur, _, cr = cr_a_analyser
    _refuser_les_credits(monkeypatch, utilisateur.id)

    resultat = ChangeRequestService(db_session).analyze_impact(cr.id, user_id=utilisateur.id)

    assert resultat["success"] is False, resultat
    assert resultat.get("code") == "insufficient_credits", resultat
    assert "credit" in str(resultat.get("error", "")).lower()


def test_la_cr_ne_passe_pas_en_analysee_sur_un_refus_de_credits(
    db_session, cr_a_analyser, monkeypatch
):
    """Le defaut le plus couteux : la CR portait `analyzed` et une estimation
    de cout alors qu'aucune analyse n'avait eu lieu."""
    from app.services.change_request_service import ChangeRequestService

    utilisateur, _, cr = cr_a_analyser
    _refuser_les_credits(monkeypatch, utilisateur.id)

    ChangeRequestService(db_session).analyze_impact(cr.id, user_id=utilisateur.id)

    db_session.refresh(cr)
    assert cr.status != "analyzed", "une CR non analysee est annoncee analysee"
    assert cr.analyzed_at is None
    assert not cr.impact_analysis


def test_controle_negatif_une_panne_de_fournisseur_garde_le_repli(
    db_session, cr_a_analyser, monkeypatch
):
    """Sans ce controle, « ne plus avaler le refus de credits » pourrait se
    confondre avec « ne plus jamais se replier ». Le repli documente reste
    valable pour une panne qui n'est pas un probleme de solde."""
    from app.services.change_request_service import ChangeRequestService

    utilisateur, _, cr = cr_a_analyser
    _paner_le_fournisseur(monkeypatch)

    resultat = ChangeRequestService(db_session).analyze_impact(cr.id, user_id=utilisateur.id)

    assert resultat["success"] is True, resultat
    assert resultat.get("fallback_used") is True, resultat
    db_session.refresh(cr)
    assert cr.status == "analyzed"


# ─────────────────────────────────────────────────────────────────────
# 2. La route — ce que le client lit reellement
# ─────────────────────────────────────────────────────────────────────


def test_la_route_de_soumission_dit_au_client_que_les_credits_manquent(
    client, db_session, cr_a_analyser, monkeypatch
):
    utilisateur, projet, cr = cr_a_analyser
    _refuser_les_credits(monkeypatch, utilisateur.id)

    entetes = {
        "Authorization": f"Bearer {create_access_token({'sub': str(utilisateur.id)})}"
    }
    reponse = client.post(
        f"/api/projects/{projet.id}/change-requests/{cr.id}/submit", headers=entetes
    )

    assert reponse.status_code == 402, reponse.text
    detail = reponse.json()["detail"]
    assert detail["error"] == "insufficient_credits"
    assert "credit" in detail["message"].lower()
    assert detail.get("upgrade_url")


def test_la_route_restitue_le_repli_quand_il_a_servi(
    client, db_session, cr_a_analyser, monkeypatch
):
    """« la route ne restitue pas toujours `fallback_used` » : le client doit
    savoir que ce qu'il lit est une estimation par categorie, pas une analyse."""
    utilisateur, projet, cr = cr_a_analyser
    _paner_le_fournisseur(monkeypatch)

    entetes = {
        "Authorization": f"Bearer {create_access_token({'sub': str(utilisateur.id)})}"
    }
    reponse = client.post(
        f"/api/projects/{projet.id}/change-requests/{cr.id}/submit", headers=entetes
    )

    assert reponse.status_code == 200, reponse.text
    assert reponse.json().get("fallback_used") is True, reponse.text
