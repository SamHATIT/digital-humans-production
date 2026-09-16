"""
VAGUE 1 / FILE C — PROD-06 : les portes HITL perdent la decision ou bouclent.

Trois defauts distincts, Astra L460 :

1. **La decision est perdue.** `pause_for_validation` ecrit
   `pending_validation` et le statut, puis demande la transition. Si celle-ci
   est refusee, `transition_to` fait un `rollback()` — qui annule les deux
   ecritures precedentes. Le service force ensuite `execution_state` seul :
   la porte est « posee » sans son contenu, et l'ecran n'a rien a afficher.
2. **La porte est consommee avant qu'on sache si la reprise est possible.**
   `submit_validation` commite la decision et efface `pending_validation` ;
   la faisabilite n'est examinee qu'ensuite. Pour `after_sds_generation`,
   l'etat reel au moment de la decision est `waiting_sds_validation`, que
   `resolve_export_action` ne connait pas : 409 **apres** consommation. La
   porte ne peut plus etre soumise a nouveau — elle n'existe plus.
3. **La porte se repose sur le meme contenu.** La reprise repasse par
   `should_pause`, qui ne tient pas compte d'une approbation deja donnee :
   nouvelle pause sur la meme porte, sur le meme livrable.
"""
import pytest

from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import resolve_export_action
from app.services.validation_gate_service import ValidationGateService
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)

GATE_URL = "/api/pm-orchestrator/execute/{eid}/validation-gate/submit"


def _make_user(db, suffixe=""):
    user = User(
        email=f"vague1c-prod06{suffixe}@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C PROD-06",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user, etat, status, gates=None, chemin=None):
    project = Project(user_id=user.id, name="PROD-06")
    if gates is not None:
        project.validation_gates = gates
    db.add(project)
    db.commit()
    db.refresh(project)

    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=status,
        execution_state=etat,
        sds_document_path=chemin,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _authenticate_as(user):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


@pytest.fixture
def enfiles(monkeypatch):
    calls = []

    class _Job:
        def __init__(self, job_id):
            self.job_id = job_id

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            calls.append({"name": name, "kwargs": kw})
            return _Job(kw.get("_job_id", "double"))

    async def _get_pool():
        return _Pool()

    monkeypatch.setattr(
        "app.api.routes.orchestrator.validation_gate_routes.get_redis_pool", _get_pool
    )
    return calls


# --------------------------------------------------------------------------
# 1. La pause ne perd pas la decision, meme si la transition est refusee
# --------------------------------------------------------------------------

def test_la_pause_conserve_le_contenu_de_la_porte(db_session):
    """Le cas nominal, qui etait deja casse : la porte `after_sds_generation`
    est posee depuis `sds_phase5_running`."""
    user = _make_user(db_session, "-pause")
    execution = _make_execution(
        db_session, user, "sds_phase5_running", ExecutionStatus.RUNNING
    )
    service = ValidationGateService(db_session)

    service.pause_for_validation(
        execution_id=execution.id,
        gate_name="after_sds_generation",
        deliverables_summary={"sds_length": 42000, "phase": "Phase 5"},
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.pending_validation, (
        "la porte est posee sans son contenu : l'ecran de validation n'a rien "
        "a afficher, et la reprise ne sait plus quelle porte franchir"
    )
    assert relue.pending_validation["gate"] == "after_sds_generation"
    assert relue.status == ExecutionStatus.WAITING_SDS_VALIDATION
    assert relue.execution_state == "waiting_sds_validation"


def test_la_pause_conserve_le_contenu_meme_depuis_un_etat_inattendu(db_session):
    """Controle negatif du meme mecanisme : depuis un etat d'ou la transition
    est refusee, la decision doit quand meme etre persistee — c'est justement
    le cas ou le rollback la detruisait."""
    user = _make_user(db_session, "-pause2")
    execution = _make_execution(
        db_session, user, "sds_phase2_running", ExecutionStatus.RUNNING
    )
    service = ValidationGateService(db_session)

    service.pause_for_validation(
        execution_id=execution.id,
        gate_name="after_sds_generation",
        deliverables_summary={"sds_length": 1},
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.pending_validation is not None
    assert relue.status == ExecutionStatus.WAITING_SDS_VALIDATION


# --------------------------------------------------------------------------
# 2. Une porte dont la reprise est impossible n'est pas consommee
# --------------------------------------------------------------------------

def test_l_etat_d_attente_de_validation_du_sds_est_un_cas_d_export(db_session):
    """`resolve_export_action` ne connaissait pas `waiting_sds_validation`,
    qui est pourtant l'etat REEL au moment ou le client approuve la porte
    `after_sds_generation` : toute approbation tombait en `resume_upstream`,
    donc en 409."""
    decision = resolve_export_action(
        state="waiting_sds_validation", sds_document_path=None
    )
    assert decision["action"] != "resume_upstream", (
        f"approuver la porte du SDS mene a {decision['action']!r} : "
        f"{decision['reason']}"
    )
    assert decision["reason"]


def test_une_porte_dont_la_reprise_est_impossible_reste_soumettable(
    client, db_session, enfiles
):
    """Si la reprise n'est pas possible, la reponse doit le dire AVANT d'avoir
    consomme la porte : sinon la decision est perdue et la porte n'existe
    plus."""
    user = _make_user(db_session, "-409")
    execution = _make_execution(
        db_session,
        user,
        "sds_phase2_complete",  # contenu incomplet : ce n'est pas un cas d'export
        ExecutionStatus.WAITING_SDS_VALIDATION,
    )
    execution.pending_validation = {
        "gate": "after_sds_generation",
        "gate_label": "SDS Document Review",
        "deliverables": {"sds_length": 10},
        "paused_at": "2026-09-16T10:00:00+00:00",
    }
    db_session.commit()
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 409, r.text

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.pending_validation is not None, (
        "la porte a ete consommee alors que la reprise a echoue : le client ne "
        "peut plus la soumettre"
    )
    assert not (relue.validation_history or []), (
        "une decision a ete enregistree alors que la reprise a ete refusee"
    )
    assert relue.status == ExecutionStatus.WAITING_SDS_VALIDATION


def test_une_porte_dont_la_reprise_est_possible_est_bien_consommee(
    client, db_session, enfiles
):
    """Controle positif : le chemin nominal doit continuer de consommer la
    porte et d'enfiler la suite."""
    user = _make_user(db_session, "-ok")
    execution = _make_execution(
        db_session,
        user,
        "waiting_sds_validation",
        ExecutionStatus.WAITING_SDS_VALIDATION,
    )
    execution.pending_validation = {
        "gate": "after_sds_generation",
        "gate_label": "SDS Document Review",
        "deliverables": {"sds_length": 42000},
        "paused_at": "2026-09-16T10:00:00+00:00",
    }
    db_session.commit()
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 200, r.text

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.pending_validation is None
    assert len(relue.validation_history or []) == 1
    assert relue.validation_history[0]["approved"] is True
    assert enfiles, "rien n'a ete enfile apres une approbation reussie"


# --------------------------------------------------------------------------
# 3. Une porte franchie ne se repose pas sur le meme contenu
# --------------------------------------------------------------------------

def test_une_porte_deja_approuvee_ne_se_repose_pas_sur_le_meme_contenu(db_session):
    """« La reprise apres experts repasse par `should_pause`, qui ne tient pas
    compte d'une approbation deja donnee pour cette version. »"""
    user = _make_user(db_session, "-boucle")
    execution = _make_execution(
        db_session,
        user,
        "sds_phase4_complete",
        ExecutionStatus.RUNNING,
        gates={"after_expert_specs": True},
    )
    service = ValidationGateService(db_session)
    livrable = {"completed_experts": ["qa", "data"], "phase": "Phase 4"}

    assert service.should_pause(execution.id, "after_expert_specs", livrable) is True
    service.pause_for_validation(
        execution_id=execution.id,
        gate_name="after_expert_specs",
        deliverables_summary=livrable,
    )
    service.submit_validation(execution_id=execution.id, approved=True)

    assert service.should_pause(execution.id, "after_expert_specs", livrable) is False, (
        "la porte se repose sur un livrable deja approuve : la reprise boucle"
    )


def test_une_porte_se_repose_si_le_contenu_a_change(db_session):
    """Controle negatif : l'approbation vaut pour une version, pas pour la
    porte en general. Un livrable regenere doit etre revalide."""
    user = _make_user(db_session, "-boucle2")
    execution = _make_execution(
        db_session,
        user,
        "sds_phase4_complete",
        ExecutionStatus.RUNNING,
        gates={"after_expert_specs": True},
    )
    service = ValidationGateService(db_session)

    service.pause_for_validation(
        execution_id=execution.id,
        gate_name="after_expert_specs",
        deliverables_summary={"completed_experts": ["qa"], "phase": "Phase 4"},
    )
    service.submit_validation(execution_id=execution.id, approved=True)

    nouveau = {"completed_experts": ["qa", "data", "devops"], "phase": "Phase 4"}
    assert service.should_pause(execution.id, "after_expert_specs", nouveau) is True


def test_une_porte_rejetee_se_repose(db_session):
    """Controle negatif : seul un accord ferme la porte. Un rejet doit la
    reposer, sinon le rejeu passerait sans validation."""
    user = _make_user(db_session, "-rejet")
    execution = _make_execution(
        db_session,
        user,
        "sds_phase4_complete",
        ExecutionStatus.RUNNING,
        gates={"after_expert_specs": True},
    )
    service = ValidationGateService(db_session)
    livrable = {"completed_experts": ["qa"], "phase": "Phase 4"}

    service.pause_for_validation(
        execution_id=execution.id,
        gate_name="after_expert_specs",
        deliverables_summary=livrable,
    )
    service.submit_validation(
        execution_id=execution.id, approved=False, annotations="a revoir"
    )

    assert service.should_pause(execution.id, "after_expert_specs", livrable) is True


def test_sans_empreinte_le_comportement_d_origine_tient(db_session):
    """Controle negatif : appelee sans livrable, `should_pause` ne peut rien
    comparer — elle repond comme avant, sur la configuration seule. Un
    correctif qui fermerait la porte par defaut sauterait des validations."""
    user = _make_user(db_session, "-sansempreinte")
    execution = _make_execution(
        db_session,
        user,
        "sds_phase4_complete",
        ExecutionStatus.RUNNING,
        gates={"after_expert_specs": True},
    )
    service = ValidationGateService(db_session)
    service.pause_for_validation(
        execution_id=execution.id,
        gate_name="after_expert_specs",
        deliverables_summary={"completed_experts": ["qa"]},
    )
    service.submit_validation(execution_id=execution.id, approved=True)

    assert service.should_pause(execution.id, "after_expert_specs") is True
