"""
VAGUE 3 — §4, contraintes 2 et 3 : la selection est persistee, relue, et rendue.

Contrainte 2 (arbitrage Sam) : « La selection doit etre persistee — en base, sur
l'execution — et non recalculee. Une reprise en `phase4` doit **relire** le
choix de Marcus, sinon elle relancerait des experts qu'il avait ecartes. »

C'est le point que la specification signale elle-meme en §3.2 : les quatre
valeurs d'experts reprennent toutes en `phase5` « si la selection par Marcus est
mise en place, ce point est a revoir : une reprise devra relire la selection en
base, pas la recalculer ».
"""
import json

import pytest

from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.business_requirement import BusinessRequirement
from app.models.deliverable_item import DeliverableItem
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2


@pytest.fixture
def execution_avec_wbs(db_session):
    """Une execution dont Marcus a fini : un WBS sans migration de donnees."""
    from app.services.agent_pk_resolver import reset_cache

    reset_cache()
    for nom in ("Sophie", "Olivia", "Emma", "Marcus", "Aisha", "Lucas", "Elena", "Jordan"):
        db_session.add(Agent(name=nom, description=f"Agent {nom}"))
    db_session.commit()

    user = User(
        email="vague3-selection@example.test",
        hashed_password="not-a-real-hash",
        name="Vague3 selection",
        subscription_tier="team",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(user_id=user.id, name="Projet sans migration")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=[],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    db_session.add(
        BusinessRequirement(
            project_id=project.id,
            execution_id=execution.id,
            br_id="BR-001",
            requirement="Automatiser la creation des comptes",
            order_index=0,
        )
    )
    db_session.add(
        DeliverableItem(
            execution_id=execution.id,
            agent_id="ba",
            parent_ref="BR-001",
            item_id="UC-001-01",
            item_type="use_case",
            content_parsed={"title": "Creation automatique"},
            content_raw="{}",
            parse_success=True,
        )
    )
    marcus_pk = db_session.query(Agent).filter(Agent.name == "Marcus").first().id
    db_session.add(
        AgentDeliverable(
            execution_id=execution.id,
            agent_id=marcus_pk,
            deliverable_type="architect_wbs",
            content=json.dumps(
                {
                    "content": {
                        "phases": [
                            {
                                "name": "Realisation",
                                "tasks": [
                                    {"name": "Trigger AccountTrigger"},
                                    {"name": "Ecran LWC de saisie"},
                                ],
                            }
                        ]
                    }
                }
            ),
        )
    )
    db_session.commit()
    db_session.refresh(execution)
    return {"user": user, "project": project, "execution": execution}


# --------------------------------------------------------------------------
# Contrainte 2 — persistee, pas recalculee
# --------------------------------------------------------------------------

def test_l_execution_porte_une_colonne_de_selection():
    """Sans colonne dediee, la seule option serait d'ecraser `selected_agents`
    — c'est-a-dire d'effacer le choix de l'utilisateur, qui doit primer."""
    assert hasattr(Execution, "expert_selection")


def test_la_selection_est_ecrite_en_base(db_session, execution_avec_wbs):
    service = PMOrchestratorServiceV2(db_session)
    execution = execution_avec_wbs["execution"]

    choix = service.decide_sds_experts(execution, artifacts_source=None)

    db_session.refresh(execution)
    assert execution.expert_selection is not None
    assert execution.expert_selection["selected"] == choix["selected"]
    assert "data" in execution.expert_selection["excluded"]


def test_une_reprise_relit_le_choix_au_lieu_de_le_recalculer(
    db_session, execution_avec_wbs
):
    """Le point que la specification signale : une reprise en `phase4` qui
    recalculerait relancerait des experts que Marcus avait ecartes."""
    service = PMOrchestratorServiceV2(db_session)
    execution = execution_avec_wbs["execution"]

    service.decide_sds_experts(execution, artifacts_source=None)

    # Marcus est passe : on efface son WBS pour prouver qu'on ne recalcule pas.
    db_session.query(AgentDeliverable).filter(
        AgentDeliverable.execution_id == execution.id
    ).delete()
    db_session.commit()

    relu = service.decide_sds_experts(execution, artifacts_source=None)

    assert relu["selected"] == execution.expert_selection["selected"]
    assert relu["decided_by"] == "resumed", (
        "une reprise doit se declarer comme telle, pas se faire passer pour une "
        "nouvelle decision de Marcus"
    )
    assert "data" in relu["excluded"]


def test_un_choix_utilisateur_est_persiste_comme_tel(db_session, execution_avec_wbs):
    """La tracabilite doit distinguer qui a decide."""
    execution = execution_avec_wbs["execution"]
    execution.selected_agents = ["pm", "ba", "architect", "data"]
    db_session.commit()

    service = PMOrchestratorServiceV2(db_session)
    choix = service.decide_sds_experts(execution, artifacts_source=None)

    assert choix["decided_by"] == "user"
    assert "data" in choix["selected"]
    db_session.refresh(execution)
    assert execution.expert_selection["decided_by"] == "user"


def test_le_choix_utilisateur_n_est_pas_ecrase(db_session, execution_avec_wbs):
    """`selected_agents` porte l'intention du client : la selection de Marcus
    vit a cote, pas a sa place."""
    execution = execution_avec_wbs["execution"]
    execution.selected_agents = ["pm", "ba", "architect", "data"]
    db_session.commit()

    service = PMOrchestratorServiceV2(db_session)
    service.decide_sds_experts(execution, artifacts_source=None)

    db_session.refresh(execution)
    assert execution.selected_agents == ["pm", "ba", "architect", "data"]


# --------------------------------------------------------------------------
# Contrainte 3 — l'expert ecarte est justifie dans le SDS
# --------------------------------------------------------------------------

def test_les_exclusions_sont_rendues_pour_le_sds(db_session, execution_avec_wbs):
    """« Un expert ecarte doit etre justifie dans le SDS, pas absent. »"""
    service = PMOrchestratorServiceV2(db_session)
    execution = execution_avec_wbs["execution"]
    service.decide_sds_experts(execution, artifacts_source=None)

    section = service.render_expert_coverage(execution)

    assert section, "la section de couverture ne doit pas etre vide"
    assert "Aisha" in section
    assert "non intervenue" in section.lower()
    assert "migration" in section.lower()


def test_la_couverture_cite_aussi_les_experts_retenus(db_session, execution_avec_wbs):
    """« Une absence justifiee est une couverture explicite » : le client doit
    voir le volet analyse, retenu comme ecarte."""
    service = PMOrchestratorServiceV2(db_session)
    execution = execution_avec_wbs["execution"]
    service.decide_sds_experts(execution, artifacts_source=None)

    section = service.render_expert_coverage(execution)
    assert "Elena" in section, "l'expert obligatoire doit apparaitre comme retenu"


def test_pas_de_section_sans_decision(db_session, execution_avec_wbs):
    """Aucune decision prise : mieux vaut rien qu'une section trompeuse."""
    service = PMOrchestratorServiceV2(db_session)
    assert service.render_expert_coverage(execution_avec_wbs["execution"]) == ""
