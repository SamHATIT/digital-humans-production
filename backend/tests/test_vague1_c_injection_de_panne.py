"""
VAGUE 1 / FILE C — critere de sortie d'Astra.

    « Panne injectee apres chaque phase : pas de travail oublie, pas de succes
    partiel cache, pas de retry concurrent, export seul sans nouveau LLM. »

Et les tests attendus par la mission :

    « L'execution passe FAILED avec message, la reprise reprend a
    `last_completed_phase` sans rejouer, aucun appel LLM en double (compter
    dans `llm_interactions`). Deux workers : le redemarrage de l'un ne touche
    pas les executions de l'autre. »

Methode. Le transport LLM est simule : chaque appel d'agent ecrit une ligne
`llm_interactions`, comme le ferait `llm_logger`. Ce sont **ces lignes** qui
servent de preuve — pas la trace d'appel en memoire — parce que c'est la table
que la mission designe et celle que l'exploitant relit apres coup.

La panne est injectee a la fin de chaque phase, l'execution est reprise, et on
compte qui a ete rappele.
"""
import asyncio
import json

import pytest

from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.business_requirement import BusinessRequirement, BRStatus
from app.models.deliverable_item import DeliverableItem
from app.models.execution import Execution, ExecutionStatus
from app.models.llm_interaction import LLMInteraction
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import (
    CHECKPOINT_TO_RESUME_POINT,
    PMOrchestratorServiceV2,
)
from app.workers import tasks as worker_tasks


class PanneInjectee(Exception):
    """La panne que l'on provoque volontairement."""


@pytest.fixture
def projet(db_session):
    for nom in ("Sophie", "Olivia", "Emma", "Marcus", "Aisha", "Lucas", "Elena", "Jordan"):
        db_session.add(Agent(name=nom, description=f"Agent {nom}"))
    db_session.commit()

    user = User(
        email="vague1c-panne@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C panne",
        subscription_tier="team",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    project = Project(user_id=user.id, name="Injection de panne")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return {"user": user, "project": project}


def _execution(db, projet, dernier_checkpoint):
    """Une execution arretee juste apres `dernier_checkpoint`, avec en base
    tout ce que les phases precedentes ont produit."""
    execution = Execution(
        project_id=projet["project"].id,
        user_id=projet["user"].id,
        selected_agents=["pm", "ba", "architect"],
        agent_execution_status={},
        status=ExecutionStatus.FAILED,
        execution_state="failed",
        last_completed_phase=dernier_checkpoint,
        logs="[Panne injectee] le worker a ete tue",
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    db.add(
        BusinessRequirement(
            project_id=projet["project"].id,
            execution_id=execution.id,
            br_id="BR-001",
            requirement="Une exigence metier",
            order_index=0,
            status=BRStatus.VALIDATED,
        )
    )
    for idx in range(2):
        db.add(
            DeliverableItem(
                execution_id=execution.id,
                agent_id="ba",
                parent_ref="BR-001",
                item_id=f"UC-001-{idx + 1:02d}",
                item_type="use_case",
                content_parsed={"title": f"Cas d'usage {idx + 1}"},
                content_raw="{}",
                parse_success=True,
            )
        )
    emma_pk = db.query(Agent).filter(Agent.name == "Emma").first().id
    db.add(
        AgentDeliverable(
            execution_id=execution.id,
            agent_id=emma_pk,
            deliverable_type="research_analyst_uc_digest",
            content=json.dumps({
                "content": {
                    "by_requirement": {
                        "BR-001": {"summary": "digest", "use_cases": ["UC-001-01"]}
                    },
                    "total_use_cases": 2,
                },
                "metadata": {"tokens_used": 10},
            }),
        )
    )
    db.commit()
    db.refresh(execution)
    return execution


@pytest.fixture
def transport_llm(monkeypatch, db_session):
    """Simule le transport LLM : chaque appel laisse une ligne en base.

    Aucun reseau : la session hermetique refuserait et compterait la
    tentative.
    """
    def _journaliser(execution_id, agent_id):
        db_session.add(
            LLMInteraction(
                execution_id=execution_id,
                agent_id=agent_id,
                prompt=f"appel simule {agent_id}",
                response="reponse simulee",
                tokens_input=10,
                tokens_output=10,
                model="simule",
                provider="simule",
                success=True,
            )
        )
        db_session.commit()

    async def _faux_run_agent(self, agent_id, input_data=None, execution_id=None,
                              project_id=None, mode=None, **kwargs):
        _journaliser(execution_id, agent_id)
        if agent_id == "architect":
            raise PanneInjectee("arret controle : Marcus atteint")
        return {
            "success": True,
            "output": {
                "content": {
                    "business_requirements": [{"br_id": "BR-001"}],
                    "digest": "recalcule",
                },
                "metadata": {"tokens_used": 20},
            },
        }

    async def _pas_de_metadata_sf(self, execution_id, project=None):
        return {"success": False, "error": "test", "full_metadata": {}, "summary": {}}

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_agent", _faux_run_agent)
    monkeypatch.setattr(
        PMOrchestratorServiceV2, "_get_salesforce_metadata", _pas_de_metadata_sf
    )
    return db_session


def _agents_appeles(db, execution_id):
    return [
        ligne.agent_id
        for ligne in db.query(LLMInteraction)
        .filter(LLMInteraction.execution_id == execution_id)
        .order_by(LLMInteraction.id)
        .all()
    ]


# --------------------------------------------------------------------------
# Une panne apres chaque phase : la reprise ne rejoue pas l'amont
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "checkpoint, ne_doit_pas_etre_rappele",
    [
        ("phase1_pm", ["pm"]),
        ("phase2_ba", ["pm", "ba"]),
        ("phase2_5_emma", ["pm", "ba", "research_analyst"]),
    ],
)
@pytest.mark.asyncio
async def test_une_panne_apres_une_phase_ne_fait_pas_rejouer_l_amont(
    db_session, projet, transport_llm, checkpoint, ne_doit_pas_etre_rappele
):
    """Aucun appel LLM en double : la preuve est comptee dans
    `llm_interactions`, la table que la mission designe."""
    execution = _execution(db_session, projet, checkpoint)

    service = PMOrchestratorServiceV2(db_session)
    await service.execute_workflow(
        execution_id=execution.id,
        project_id=projet["project"].id,
        selected_agents=["pm", "ba", "architect"],
        resume_from=CHECKPOINT_TO_RESUME_POINT[checkpoint],
    )

    appeles = _agents_appeles(db_session, execution.id)
    for agent in ne_doit_pas_etre_rappele:
        assert agent not in appeles, (
            f"reprise apres {checkpoint} : {agent} a ete rappele (donc repaye) "
            f"— appels enregistres : {appeles}"
        )


@pytest.mark.asyncio
async def test_la_reprise_avance_vraiment(db_session, projet, transport_llm):
    """Controle positif : ne rien rappeler serait facile a obtenir en ne
    faisant rien. La chaine doit atteindre Marcus."""
    execution = _execution(db_session, projet, "phase2_5_emma")

    service = PMOrchestratorServiceV2(db_session)
    await service.execute_workflow(
        execution_id=execution.id,
        project_id=projet["project"].id,
        selected_agents=["pm", "ba", "architect"],
        resume_from="phase3",
    )

    assert _agents_appeles(db_session, execution.id) == ["architect"]


@pytest.mark.asyncio
async def test_une_panne_laisse_l_execution_failed_avec_un_message(
    db_session, projet, transport_llm, monkeypatch
):
    """« L'execution passe FAILED avec message. »

    `execute_workflow` attrape ses exceptions et rend `{"success": False}` :
    la tache ARQ ne leve donc pas. Ce que l'on verifie est ce qui compte pour
    l'exploitant et pour la reprise — l'etat en base et le motif — et le fait
    que la tache ne presente pas cet echec comme un succes.
    """
    execution = _execution(db_session, projet, "phase2_5_emma")
    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    resultat = await worker_tasks.execute_sds_task(
        {},
        execution_id=execution.id,
        project_id=projet["project"].id,
        selected_agents=["pm", "ba", "architect"],
        resume_from="phase3",
    )
    assert resultat.get("success") is False, (
        f"un echec metier rendu comme un succes : {resultat}"
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.status == ExecutionStatus.FAILED
    assert relue.execution_state == "failed"
    assert "arret controle" in (relue.logs or "") or "Marcus" in (relue.logs or ""), (
        f"l'echec ne porte pas de message exploitable : {relue.logs!r}"
    )


@pytest.mark.asyncio
async def test_le_checkpoint_ne_recule_jamais(db_session, projet, transport_llm):
    """PROD-05, dernier point : « ne jamais faire reculer le dernier checkpoint
    valide ». Une reprise qui echoue en phase 3 ne doit pas ramener le
    checkpoint a `phase1_pm`."""
    execution = _execution(db_session, projet, "phase2_5_emma")

    service = PMOrchestratorServiceV2(db_session)
    await service.execute_workflow(
        execution_id=execution.id,
        project_id=projet["project"].id,
        selected_agents=["pm", "ba", "architect"],
        resume_from="phase3",
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    ordre = [
        "phase1_pm", "phase2_ba", "phase2_5_emma", "phase3_wbs",
        "phase4_experts", "phase5_write_sds", "phase6_export",
    ]
    assert ordre.index(relue.last_completed_phase) >= ordre.index("phase2_5_emma"), (
        f"le checkpoint a recule : {relue.last_completed_phase!r}"
    )


# --------------------------------------------------------------------------
# Deux workers : le redemarrage de l'un ne touche pas les executions de l'autre
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deux_workers_le_redemarrage_de_l_un_epargne_l_autre(
    db_session, projet
):
    """Le scenario du 15/09 18:0x, joue sur Redis reel : deux executions
    actives, une seule dont le job a disparu."""
    from arq.constants import in_progress_key_prefix

    from app.workers.arq_config import ARQ_QUEUE_NAME, get_redis_pool
    from app.workers.worker import startup

    vivante = Execution(
        project_id=projet["project"].id,
        user_id=projet["user"].id,
        selected_agents=["pm"],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
        execution_state="sds_phase3_running",
        arq_job_id=f"{ARQ_QUEUE_NAME}-worker-b",
        arq_queue_name=ARQ_QUEUE_NAME,
    )
    morte = Execution(
        project_id=projet["project"].id,
        user_id=projet["user"].id,
        selected_agents=["pm"],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
        execution_state="sds_phase3_running",
        arq_job_id=f"{ARQ_QUEUE_NAME}-worker-a-mort",
        arq_queue_name=ARQ_QUEUE_NAME,
    )
    db_session.add_all([vivante, morte])
    db_session.commit()
    db_session.refresh(vivante)
    db_session.refresh(morte)

    pool = await get_redis_pool()
    cle = in_progress_key_prefix + vivante.arq_job_id
    try:
        # Le worker B execute « vivante » : ARQ pose cette cle a la prise du job.
        await pool.psetex(cle, 120_000, b"1")
        # Le worker A redemarre.
        await startup({"redis": pool})
    finally:
        await pool.delete(cle)
        await pool.aclose()

    db_session.expire_all()
    assert db_session.query(Execution).get(vivante.id).status == ExecutionStatus.RUNNING, (
        "le redemarrage du worker A a tue l'execution du worker B — c'est "
        "exactement ce qui est arrive a l'execution 179 le 15/09"
    )
    assert db_session.query(Execution).get(morte.id).status == ExecutionStatus.FAILED, (
        "l'execution reellement abandonnee n'a pas ete reconciliee"
    )


# --------------------------------------------------------------------------
# Export seul, sans nouvel appel LLM
# --------------------------------------------------------------------------

def test_un_export_a_refaire_ne_relance_aucun_agent(db_session, projet, tmp_path):
    """« Export seul sans nouveau LLM » : la decision d'export ne passe par
    aucun agent, et le livrable present se sert tel quel."""
    from app.services.pm_orchestrator_service_v2 import resolve_export_action

    livrable = tmp_path / "SDS.docx"
    livrable.write_bytes(b"un livrable")
    servir = resolve_export_action("sds_complete", str(livrable))
    assert servir["action"] == "serve"
    assert servir["resume_from"] is None, (
        "servir un livrable existant ne doit relancer aucune phase"
    )

    refaire = resolve_export_action("sds_complete", str(tmp_path / "absent.docx"))
    assert refaire["action"] == "regenerate_export"
    assert refaire["resume_from"] is None, (
        "refabriquer l'export ne doit pas relancer d'agent : les donnees sont "
        "en base"
    )
