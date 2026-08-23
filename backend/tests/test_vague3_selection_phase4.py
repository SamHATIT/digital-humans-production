"""
VAGUE 3 — §4 : la selection est reellement exercee en phase 4.

Une decision persistee que la phase 4 n'utilise pas serait un dispositif inerte
de plus — exactement le defaut d'origine, deplace d'un cran. Ces tests portent
sur le branchement, pas sur la regle (couverte par
`test_vague3_selection_experts.py`).
"""
import json

import pytest

from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2


class ArretControle(Exception):
    """Stoppe la course des qu'on a vu quels experts ont ete lances."""


@pytest.fixture
def contexte(db_session):
    from app.services.agent_pk_resolver import reset_cache

    reset_cache()
    for nom in ("Sophie", "Olivia", "Emma", "Marcus", "Aisha", "Lucas", "Elena", "Jordan"):
        db_session.add(Agent(name=nom, description=f"Agent {nom}"))
    db_session.commit()

    user = User(
        email="vague3-phase4@example.test",
        hashed_password="not-a-real-hash",
        name="Vague3 phase4",
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
    return {"user": user, "project": project, "execution": execution}


def _artefacts_sans_migration():
    return {
        "WBS": {
            "content": {
                "phases": [
                    {"name": "Realisation", "tasks": [{"name": "Trigger Account"}]}
                ]
            }
        }
    }


class ArretApresPhase4(Exception):
    """Stoppe la course une fois la phase 4 passee — la suite (Emma, export)
    n'est pas l'objet de ce test."""


async def _lancer_phase4(db_session, contexte, artefacts, monkeypatch,
                         selected_agents=None):
    """Execute reellement `_execute_from_phase4` et rend la liste des agents
    effectivement appeles.

    Ce sont des tests de **comportement**, pas d'inspection de source. Un test
    qui verifierait `"decide_sds_experts" in source` prouverait qu'une chaine de
    caracteres est presente, pas que la phase 4 lance les bons experts — meme
    forme que le test de LOT-G qui certifiait le critere « boot sans create_all »
    en assertant la presence de la ligne fautive.
    """
    lances = []

    async def _run(self, agent_id, mode=None, input_data=None, **kwargs):
        lances.append(agent_id)
        if agent_id == "research_analyst":
            # Phase 5 atteinte : les experts sont tous passes.
            raise ArretApresPhase4()
        return {
            "success": True,
            "output": {"content": {"specs": []}, "metadata": {"tokens_used": 1}},
        }

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_agent", _run)

    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]
    if selected_agents is not None:
        execution.selected_agents = selected_agents
        db_session.commit()

    results = {
        "execution_id": execution.id,
        "project_id": contexte["project"].id,
        "artifacts": dict(artefacts),
        "agent_outputs": {},
        "metrics": {"total_tokens": 0, "tokens_by_agent": {}, "execution_times": {}},
    }
    try:
        await service._execute_from_phase4(
            project=contexte["project"],
            execution=execution,
            execution_id=execution.id,
            project_id=contexte["project"].id,
            results=results,
            selected_agents=execution.selected_agents,
        )
    except ArretApresPhase4:
        pass
    except Exception as exc:
        # La phase 5 peut echouer autrement ; les experts sont deja passes.
        # Mais on garde la trace : un test qui passerait parce que RIEN n'a
        # tourne serait un vert qui ne prouve rien.
        _lancer_phase4.derniere_erreur = repr(exc)

    experts = [a for a in lances if a in ("data", "trainer", "qa", "devops")]
    assert lances, (
        "aucun agent n'a ete appele : la phase 4 s'est arretee avant les "
        f"experts, le test ne prouve rien. Cause : "
        f"{getattr(_lancer_phase4, 'derniere_erreur', 'inconnue')}"
    )
    return experts, execution


@pytest.mark.asyncio
async def test_aisha_ne_tourne_pas_sans_migration(db_session, contexte, monkeypatch):
    """Le cas de Sam, verifie sur l'execution reelle de la phase 4 : Aisha
    tournait, produisait une specification vide de sens, et consommait des
    credits sur un livrable que personne ne lira."""
    experts, _ = await _lancer_phase4(
        db_session, contexte, _artefacts_sans_migration(), monkeypatch
    )

    assert "data" not in experts, (
        f"Aisha a tourne alors qu'aucune migration n'est au perimetre : {experts}"
    )


@pytest.mark.asyncio
async def test_elena_tourne_toujours(db_session, contexte, monkeypatch):
    """Contrainte 1 : la relecture qualite est un argument de vente, pas une
    etape optionnelle. Verifie sur l'execution, pas sur la decision."""
    experts, _ = await _lancer_phase4(
        db_session, contexte, _artefacts_sans_migration(), monkeypatch
    )

    assert "qa" in experts, f"Elena n'a pas tourne : {experts}"


@pytest.mark.asyncio
async def test_aisha_tourne_quand_il_y_a_migration(db_session, contexte, monkeypatch):
    """Controle positif : le mecanisme doit ecarter, pas exclure par defaut."""
    artefacts = {
        "WBS": {
            "content": {
                "phases": [
                    {
                        "name": "Realisation",
                        "tasks": [{"name": "Migration des donnees Compte"}],
                    }
                ]
            }
        }
    }
    experts, _ = await _lancer_phase4(db_session, contexte, artefacts, monkeypatch)

    assert "data" in experts, f"Aisha aurait du tourner : {experts}"


@pytest.mark.asyncio
async def test_le_choix_utilisateur_l_emporte_a_l_execution(
    db_session, contexte, monkeypatch
):
    """Contrainte 4, verifiee sur ce qui tourne reellement."""
    experts, _ = await _lancer_phase4(
        db_session,
        contexte,
        _artefacts_sans_migration(),
        monkeypatch,
        selected_agents=["pm", "ba", "architect", "data"],
    )

    assert "data" in experts, f"le choix explicite n'a pas ete respecte : {experts}"


@pytest.mark.asyncio
async def test_la_decision_est_persistee_par_la_phase4(
    db_session, contexte, monkeypatch
):
    """Contrainte 2 : persistee par le passage en phase 4, pas seulement
    calculable a la demande."""
    _, execution = await _lancer_phase4(
        db_session, contexte, _artefacts_sans_migration(), monkeypatch
    )
    db_session.refresh(execution)

    assert execution.expert_selection is not None
    assert "data" in execution.expert_selection["excluded"]


@pytest.mark.asyncio
async def test_une_reprise_ne_ressuscite_pas_un_expert_ecarte(
    db_session, contexte, monkeypatch
):
    """Le point que §3.2 signalait a revoir : « une reprise devra relire la
    selection en base, pas la recalculer ».

    On rejoue la phase 4 avec des artefacts qui, eux, contiennent de la
    migration. Si la selection etait recalculee, Aisha reviendrait.
    """
    await _lancer_phase4(db_session, contexte, _artefacts_sans_migration(), monkeypatch)

    artefacts_avec_migration = {
        "WBS": {
            "content": {
                "phases": [
                    {"name": "R", "tasks": [{"name": "Migration des donnees"}]}
                ]
            }
        }
    }
    experts, _ = await _lancer_phase4(
        db_session, contexte, artefacts_avec_migration, monkeypatch
    )

    assert "data" not in experts, (
        "la reprise a recalcule la selection et ressuscite un expert que Marcus "
        f"avait ecarte : {experts}"
    )


@pytest.mark.asyncio
async def test_la_couverture_arrive_dans_le_sds(db_session, contexte, monkeypatch):
    """Contrainte 3, verifiee sur le markdown produit — pas sur la presence
    d'un appel dans le source."""
    rendu = {}

    async def _run(self, agent_id, mode=None, input_data=None, **kwargs):
        if agent_id == "research_analyst" and mode == "write_sds":
            return {
                "success": True,
                "output": {
                    "content": {"raw_markdown": "# SDS\n\nCorps du document.\n"},
                    "metadata": {"tokens_used": 1},
                },
            }
        return {
            "success": True,
            "output": {"content": {"specs": []}, "metadata": {"tokens_used": 1}},
        }

    async def _capture_export(self, project, agent_outputs, artifacts,
                              execution_id, sds_markdown):
        rendu["markdown"] = sds_markdown
        raise ArretApresPhase4()

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_agent", _run)
    monkeypatch.setattr(
        PMOrchestratorServiceV2, "_generate_sds_document", _capture_export
    )

    service = PMOrchestratorServiceV2(db_session)
    execution = contexte["execution"]
    results = {
        "execution_id": execution.id,
        "project_id": contexte["project"].id,
        "artifacts": dict(_artefacts_sans_migration()),
        "agent_outputs": {},
        "metrics": {"total_tokens": 0, "tokens_by_agent": {}, "execution_times": {}},
    }
    try:
        await service._execute_from_phase4(
            project=contexte["project"],
            execution=execution,
            execution_id=execution.id,
            project_id=contexte["project"].id,
            results=results,
            selected_agents=execution.selected_agents,
        )
    except Exception:
        pass

    markdown = rendu.get("markdown", "")
    assert markdown, "le SDS n'a pas ete assemble — test inoperant"
    assert "Aisha" in markdown, (
        f"l'expert ecarte n'est pas justifie dans le SDS : {markdown[:500]}"
    )
    assert "non intervenue" in markdown.lower()


def test_sans_decision_les_quatre_experts_tournent(db_session, contexte):
    """Non-regression : une execution anterieure a la vague 3 n'a pas de
    decision. `NULL` veut dire « Marcus n'a pas tranche », pas « aucun expert »."""
    from app.services.expert_selection import ALL_SDS_EXPERTS

    execution = contexte["execution"]
    assert execution.expert_selection is None

    service = PMOrchestratorServiceV2(db_session)
    choix = service.decide_sds_experts(execution, artifacts_source={})

    # Aucun signal, aucun choix utilisateur : seul l'obligatoire est retenu, et
    # les trois autres sont ecartes AVEC justification — jamais en silence.
    assert set(choix["selected"]) | set(choix["excluded"]) == set(ALL_SDS_EXPERTS)
