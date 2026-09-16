"""Vague 1 / file A — SEC-05 (rapport Astra L102).

Deux recharges d'objets tiers par leur seul identifiant :

1. `POST /api/pm-orchestrator/executions/{id}/chat` verifie bien le livrable dans la
   route (filtre `execution_id`) mais passe ensuite l'identifiant brut a
   `ChangeRequestService.create_from_chat`, qui le **recharge sans filtre**.
   Les 500 premiers caracteres du livrable d'autrui entrent dans le prompt
   de classification et peuvent ressortir dans la description de la CR.
2. `ChangeRequestService.analyze_impact` recharge `cr.related_br_id` par son
   seul identifiant : une CR portant un BR d'un autre projet fait entrer le
   texte de ce BR dans le prompt d'analyse.

On teste le **prompt recu par le LLM**, pas la reponse de lecture.
"""
from unittest.mock import patch

import pytest

from app.main import app
from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.business_requirement import BusinessRequirement
from app.models.change_request import ChangeRequest
from app.models.execution import Execution
from app.models.project import Project
from app.models.user import User
from app.services.change_request_service import ChangeRequestService
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)

SECRET_B = "MARGE NEGOCIEE DU CLIENT B : 42% sur le contrat Acme"
SECRET_BR_B = "BR-B01 du client B : remise confidentielle de 37%"


def _tenant(db, suffix: str, agent: Agent, contenu: str, texte_br: str):
    user = User(
        email=f"sec05-{suffix}@example.test",
        hashed_password="pas-un-vrai-hash",
        name=f"SEC05 {suffix}",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    project = Project(user_id=user.id, name=f"Projet {suffix.upper()}")
    db.add(project)
    db.commit()
    db.refresh(project)

    execution = Execution(project_id=project.id, user_id=user.id)
    db.add(execution)
    db.commit()
    db.refresh(execution)

    deliverable = AgentDeliverable(
        execution_id=execution.id,
        agent_id=agent.id,
        deliverable_type="sds",
        content=contenu,
    )
    br = BusinessRequirement(
        project_id=project.id,
        br_id=f"BR-{suffix.upper()}01",
        requirement=texte_br,
        category="secret",
    )
    db.add_all([deliverable, br])
    db.commit()
    db.refresh(deliverable)
    db.refresh(br)

    return {
        "user": user,
        "project": project,
        "execution": execution,
        "deliverable": deliverable,
        "br": br,
    }


@pytest.fixture
def tenants(db_session):
    agent = Agent(name="sophie-pm-sec05", description="PM de test")
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    return {
        "a": _tenant(
            db_session, "a", agent,
            "Livrable du client A : rien de confidentiel ici", "BR-A01 banal",
        ),
        "b": _tenant(db_session, "b", agent, SECRET_B, SECRET_BR_B),
    }


def _authentifier(user: User):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


class _LLMEspion:
    """Capture chaque prompt envoye au routeur LLM et rend un JSON valide."""

    def __init__(self, contenu: str):
        self.prompts = []
        self._contenu = contenu

    def __call__(self, *args, **kwargs):
        self.prompts.append(f"{kwargs.get('system_prompt', '')}\n{kwargs.get('prompt', '')}")
        return {"content": self._contenu, "tokens_used": 1, "model": "faux-modele"}

    @property
    def tout(self) -> str:
        return "\n".join(self.prompts)


_CR_JSON = (
    '{"is_change_request": true, "category": "other", "title": "T",'
    ' "description": "D", "priority": "low"}'
)


# ==========================================================================
# 1. Le livrable d'autrui ne doit pas entrer dans la classification
# ==========================================================================

def test_le_livrable_d_un_autre_client_n_entre_pas_dans_le_prompt(client, db_session, tenants):
    a, b = tenants["a"], tenants["b"]
    _authentifier(a["user"])

    espion_chat = _LLMEspion("Bonjour, c'est Sophie.")
    espion_cr = _LLMEspion(_CR_JSON)
    with patch("app.services.llm_service.generate_llm_response", espion_chat), \
            patch("app.services.change_request_service.generate_llm_response", espion_cr):
        reponse = client.post(
            f"/api/pm-orchestrator/executions/{a['execution'].id}/chat",
            json={
                "message": "Peux-tu changer la regle de remise ?",
                "agent_id": "sophie",
                "deliverable_id": b["deliverable"].id,
            },
        )

    assert SECRET_B not in espion_cr.tout, (
        "le contenu du livrable du client B est entre dans le prompt de "
        "classification de la CR du client A"
    )
    assert SECRET_B not in espion_chat.tout
    assert SECRET_B not in reponse.text


def test_la_route_refuse_un_livrable_incoherent(client, db_session, tenants):
    """Un identifiant de livrable qui n'appartient pas a l'execution visee
    est une incoherence : elle se refuse, elle ne s'ignore pas en silence."""
    a, b = tenants["a"], tenants["b"]
    _authentifier(a["user"])

    espion = _LLMEspion("peu importe")
    with patch("app.services.llm_service.generate_llm_response", espion), \
            patch("app.services.change_request_service.generate_llm_response", espion):
        reponse = client.post(
            f"/api/pm-orchestrator/executions/{a['execution'].id}/chat",
            json={
                "message": "Bonjour",
                "agent_id": "sophie",
                "deliverable_id": b["deliverable"].id,
            },
        )
    assert reponse.status_code == 404, reponse.text
    assert espion.prompts == [], "un appel LLM a ete facture malgre le refus"


def test_controle_negatif_son_propre_livrable_entre_bien_dans_le_prompt(
    client, db_session, tenants
):
    """Sans ce controle, une correction qui ignorerait TOUS les livrables
    passerait le test principal."""
    a = tenants["a"]
    _authentifier(a["user"])

    espion_chat = _LLMEspion("Bonjour, c'est Sophie.")
    espion_cr = _LLMEspion(_CR_JSON)
    with patch("app.services.llm_service.generate_llm_response", espion_chat), \
            patch("app.services.change_request_service.generate_llm_response", espion_cr):
        reponse = client.post(
            f"/api/pm-orchestrator/executions/{a['execution'].id}/chat",
            json={
                "message": "Peux-tu changer la regle de remise ?",
                "agent_id": "sophie",
                "deliverable_id": a["deliverable"].id,
            },
        )

    assert reponse.status_code == 200, reponse.text
    assert "Livrable du client A" in espion_chat.tout
    assert "Livrable du client A" in espion_cr.tout


# ==========================================================================
# 2. analyze_impact ne doit pas recharger un BR hors du projet de la CR
# ==========================================================================

def _cr_avec_br(db, proprietaire, br: BusinessRequirement) -> ChangeRequest:
    cr = ChangeRequest(
        project_id=proprietaire["project"].id,
        execution_id=proprietaire["execution"].id,
        cr_number="CR-001",
        category="other",
        title="Demande",
        description="Demande de test",
        priority="low",
        status="draft",
        related_br_id=br.id,
        created_by=proprietaire["user"].id,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return cr


_IMPACT_JSON = (
    '{"summary": "s", "affected_brs": [], "affected_use_cases": [],'
    ' "affected_architecture_sections": [], "agents_to_rerun": ["ba"],'
    ' "risk_level": "low", "estimated_effort": "1j", "recommendations": [],'
    ' "dependencies": ""}'
)


def test_analyze_impact_n_utilise_pas_le_br_d_un_autre_projet(db_session, tenants):
    a, b = tenants["a"], tenants["b"]
    cr = _cr_avec_br(db_session, a, b["br"])  # CR de A pointant le BR de B

    espion = _LLMEspion(_IMPACT_JSON)
    with patch("app.services.change_request_service.generate_llm_response", espion):
        ChangeRequestService(db_session).analyze_impact(cr.id, user_id=a["user"].id)

    assert SECRET_BR_B not in espion.tout, (
        "le texte du BR du client B est entre dans le prompt d'analyse "
        "d'impact de la CR du client A"
    )


def test_controle_negatif_le_br_du_meme_projet_est_bien_utilise(db_session, tenants):
    a = tenants["a"]
    cr = _cr_avec_br(db_session, a, a["br"])

    espion = _LLMEspion(_IMPACT_JSON)
    with patch("app.services.change_request_service.generate_llm_response", espion):
        ChangeRequestService(db_session).analyze_impact(cr.id, user_id=a["user"].id)

    assert "BR-A01 banal" in espion.tout
