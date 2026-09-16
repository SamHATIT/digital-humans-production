"""Vague 1 / file A — SEC-19 (rapport Astra L360).

Trois surfaces, deux perimetres :

* `hitl_routes.list_available_agents` (GET
  /api/pm-orchestrator/executions/{id}/agents) : authentifie mais non
  cloisonne — on observait les agents disponibles d'une execution tierce.
* `DeliverableService.create_deliverable` / `update_deliverable` : les
  references secondaires `output_file_id` et `execution_agent_id` n'etaient
  pas verifiees. La route valide bien l'execution ; l'existence d'une FK ne
  prouve pas la coherence de tenant, et un proprietaire pouvait rattacher
  son livrable a l'artefact d'une autre execution.
* `execution_routes.get_execution_budget` : lecture **anonyme** des couts.
  Ce fichier appartient a une autre file (integrateur unique) : le test et
  le diff sont dans docs/missions/RAPPORT_VAGUE1_A.md, non commis.
"""
from unittest.mock import patch

import pytest

from app.main import app
from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.execution import Execution
from app.models.execution_agent import ExecutionAgent
from app.models.output import Output
from app.models.project import Project
from app.models.user import User
from app.schemas.deliverable import AgentDeliverableCreate, AgentDeliverableUpdate
from app.services.deliverable_service import DeliverableService
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)


def _tenant(db, suffix: str, agent: Agent):
    user = User(
        email=f"sec19-{suffix}@example.test",
        hashed_password="pas-un-vrai-hash",
        name=f"SEC19 {suffix}",
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

    execution_agent = ExecutionAgent(execution_id=execution.id, agent_id=agent.id)
    output = Output(
        project_id=project.id,
        execution_id=execution.id,
        agent_id=agent.id,
        file_name=f"SDS_{suffix}.docx",
        file_path=f"/tmp/sds_{suffix}.docx",
    )
    deliverable = AgentDeliverable(
        execution_id=execution.id,
        agent_id=agent.id,
        deliverable_type="sds",
        content=f"Livrable du client {suffix.upper()}",
    )
    db.add_all([execution_agent, output, deliverable])
    db.commit()
    for obj in (execution_agent, output, deliverable):
        db.refresh(obj)

    return {
        "user": user,
        "project": project,
        "execution": execution,
        "execution_agent": execution_agent,
        "output": output,
        "deliverable": deliverable,
        "agent": agent,
    }


@pytest.fixture
def tenants(db_session):
    agent = Agent(name="olivia-ba-sec19", description="BA de test")
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    return {
        "a": _tenant(db_session, "a", agent),
        "b": _tenant(db_session, "b", agent),
    }


def _authentifier(user: User):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


# ==========================================================================
# 1. Lecture des agents d'une execution tierce
# ==========================================================================

def test_les_agents_d_une_execution_tierce_ne_sont_pas_lisibles(client, tenants):
    a, b = tenants["a"], tenants["b"]
    _authentifier(a["user"])
    reponse = client.get(f"/api/pm-orchestrator/executions/{b['execution'].id}/agents")
    assert reponse.status_code == 404, reponse.text


def test_controle_negatif_ses_propres_agents_restent_lisibles(client, tenants):
    a = tenants["a"]
    _authentifier(a["user"])
    reponse = client.get(f"/api/pm-orchestrator/executions/{a['execution'].id}/agents")
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["agents"], reponse.text


# ==========================================================================
# 2. References secondaires d'un livrable
# ==========================================================================

def test_creation_refuse_un_output_file_id_d_une_autre_execution(db_session, tenants):
    a, b = tenants["a"], tenants["b"]
    service = DeliverableService(db_session)
    with pytest.raises(ValueError):
        service.create_deliverable(AgentDeliverableCreate(
            execution_id=a["execution"].id,
            agent_id=a["agent"].id,
            deliverable_type="sds",
            content="tentative",
            output_file_id=b["output"].id,
        ))


def test_creation_refuse_un_execution_agent_id_d_une_autre_execution(db_session, tenants):
    a, b = tenants["a"], tenants["b"]
    service = DeliverableService(db_session)
    with pytest.raises(ValueError):
        service.create_deliverable(AgentDeliverableCreate(
            execution_id=a["execution"].id,
            agent_id=a["agent"].id,
            deliverable_type="sds",
            content="tentative",
            execution_agent_id=b["execution_agent"].id,
        ))


def test_mise_a_jour_refuse_un_output_file_id_d_une_autre_execution(db_session, tenants):
    a, b = tenants["a"], tenants["b"]
    service = DeliverableService(db_session)
    with pytest.raises(ValueError):
        service.update_deliverable(
            a["deliverable"].id,
            AgentDeliverableUpdate(output_file_id=b["output"].id),
        )
    db_session.refresh(a["deliverable"])
    assert a["deliverable"].output_file_id is None, "effet de bord malgre le refus"


def test_controle_negatif_les_references_de_la_meme_execution_sont_acceptees(
    db_session, tenants
):
    """Sans ce controle, un refus systematique passerait les trois tests
    precedents."""
    a = tenants["a"]
    service = DeliverableService(db_session)

    cree = service.create_deliverable(AgentDeliverableCreate(
        execution_id=a["execution"].id,
        agent_id=a["agent"].id,
        deliverable_type="hld",
        content="nominal",
        output_file_id=a["output"].id,
        execution_agent_id=a["execution_agent"].id,
    ))
    assert cree.output_file_id == a["output"].id
    assert cree.execution_agent_id == a["execution_agent"].id

    maj = service.update_deliverable(
        cree.id, AgentDeliverableUpdate(output_file_id=a["output"].id)
    )
    assert maj.output_file_id == a["output"].id


def test_controle_negatif_un_livrable_sans_reference_reste_creable(db_session, tenants):
    a = tenants["a"]
    cree = DeliverableService(db_session).create_deliverable(AgentDeliverableCreate(
        execution_id=a["execution"].id,
        agent_id=a["agent"].id,
        deliverable_type="uc",
        content="sans reference",
    ))
    assert cree.id is not None
    assert cree.output_file_id is None
