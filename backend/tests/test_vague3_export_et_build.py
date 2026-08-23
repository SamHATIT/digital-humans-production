"""
VAGUE 3 — §3.3 (export conditionnel) et §3.4 (bascule BUILD).

§3.3 — `phase6_export` ne doit **pas** entrer dans `execute_workflow` : c'est le
seul cas ou une reprise ne relance aucun agent. La decision se lit sur deux
signaux, tous deux disponibles : l'etat de la machine, et
`execution.sds_document_path`.

    etat                    sds_document_path   action
    sds_complete            .docx / .pdf        mettre a disposition
    sds_complete            .md seul            regenerer l'export
    sds_phase4_complete     —                   regenerer : Emma reprend
    avant phase4_complete   —                   reprise amont

**Le Markdown n'est pas un livrable.** La ligne 3426 le renseigne en repli quand
l'export DOCX echoue ; il sert la vue HTML. Un `sds_document_path` en `.md`
signifie donc que l'export a echoue ou n'a pas eu lieu.

§3.4 — `deploy` et `build` ne sont pas des points de reprise SDS. Ils partent
vers `execute_build_task`, exactement comme `build_tasks` en vague 2 (`57ee795`).
"""
import pytest

from app.services.pm_orchestrator_service_v2 import resolve_export_action


# ==========================================================================
# §3.3 — les quatre lignes du tableau
# ==========================================================================

@pytest.mark.parametrize(
    "chemin",
    [
        "/deliverables/sds_142.docx",
        "/deliverables/sds_142.pdf",
        "/deliverables/SDS_142.DOCX",
        "/deliverables/sds_142.PDF",
    ],
)
def test_sds_complete_avec_un_livrable_se_met_a_disposition(chemin):
    """Ne rien relancer : le document existe, il suffit de le rendre."""
    action = resolve_export_action(state="sds_complete", sds_document_path=chemin)
    assert action["action"] == "serve"
    assert action["path"] == chemin
    assert action["resume_from"] is None


@pytest.mark.parametrize(
    "chemin", ["/tmp/sds_142.md", "/tmp/SDS_142.MD"]
)
def test_sds_complete_avec_du_markdown_seul_regenere(chemin):
    """Le Markdown n'est pas un livrable : c'est la trace d'un export rate.

    Le servir rendrait un fichier que le client ne peut pas ouvrir dans Word,
    en pretendant que tout va bien.
    """
    action = resolve_export_action(state="sds_complete", sds_document_path=chemin)
    assert action["action"] == "regenerate_export"
    assert action["resume_from"] is None, (
        "regenerer l'export ne relance aucun agent : les donnees sont la"
    )


def test_sds_complete_sans_chemin_regenere():
    """Etat final atteint mais aucun document : l'export n'a pas eu lieu."""
    action = resolve_export_action(state="sds_complete", sds_document_path=None)
    assert action["action"] == "regenerate_export"


def test_phase4_complete_fait_reprendre_emma():
    """Tout le contenu est la, le SDS n'est pas ecrit. C'est le critere du point
    de reprise `phase5` (arbitrage Sam), a ne pas confondre avec la
    finalisation du document."""
    action = resolve_export_action(state="sds_phase4_complete", sds_document_path=None)
    assert action["action"] == "resume_workflow"
    assert action["resume_from"] == "phase5"


@pytest.mark.parametrize(
    "etat",
    [
        "sds_phase2_running",
        "sds_phase2_complete",
        "sds_phase3_running",
        "sds_phase3_complete",
        "sds_phase4_running",
        "queued",
    ],
)
def test_avant_phase4_complete_ce_n_est_pas_un_cas_d_export(etat):
    """« pas un cas d'export — reprise amont ». Il faut le dire, pas fabriquer
    un export sur un contenu incomplet."""
    action = resolve_export_action(state=etat, sds_document_path=None)
    assert action["action"] == "resume_upstream"
    assert action["resume_from"] != "phase5", (
        "reprendre a l'ecriture du SDS alors que le contenu n'est pas pret "
        "produirait un document creux"
    )


def test_l_extension_prime_sur_la_presence_du_chemin():
    """« Verifier l'extension, pas seulement la presence du chemin. »"""
    servi = resolve_export_action("sds_complete", "/x/sds.docx")["action"]
    regenere = resolve_export_action("sds_complete", "/x/sds.md")["action"]
    assert servi != regenere


def test_une_extension_inconnue_ne_se_sert_pas():
    """Un `.txt` ou un `.json` n'est pas davantage un livrable qu'un `.md`."""
    for chemin in ("/x/sds.txt", "/x/sds.json", "/x/sds"):
        action = resolve_export_action("sds_complete", chemin)
        assert action["action"] == "regenerate_export", chemin


def test_chaque_decision_porte_sa_raison():
    """Regle 5 : une decision d'export qui ne dit pas pourquoi est
    indistinguable d'un repli."""
    for etat, chemin in (
        ("sds_complete", "/x/sds.docx"),
        ("sds_complete", "/x/sds.md"),
        ("sds_phase4_complete", None),
        ("sds_phase2_complete", None),
    ):
        action = resolve_export_action(etat, chemin)
        assert action.get("reason"), f"decision non motivee : {etat} / {chemin}"


# ==========================================================================
# §3.4 — deploy et build partent vers le worker BUILD
# ==========================================================================

from app.main import app  # noqa: E402
from app.models.execution import Execution, ExecutionStatus  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.user import User  # noqa: E402
from app.utils.dependencies import (  # noqa: E402
    get_current_user,
    get_current_user_from_token_or_header,
)

GATE_URL = "/api/pm-orchestrator/execute/{eid}/validation-gate/submit"


def _make_user(db):
    user = User(
        email="vague3-gate@example.test",
        hashed_password="not-a-real-hash",
        name="Vague3 gate",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user, status=ExecutionStatus.WAITING_BUILD_VALIDATION):
    project = Project(user_id=user.id, name="Vague3 gate")
    db.add(project)
    db.commit()
    db.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=status,
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
        job_id = "test-job"

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            calls.append({"name": name, "kwargs": kw})
            return _Job()

    async def _get_pool():
        return _Pool()

    monkeypatch.setattr(
        "app.api.routes.orchestrator.validation_gate_routes.get_redis_pool",
        _get_pool,
        raising=False,
    )
    return calls


@pytest.fixture
def porte_after_build_code(monkeypatch):
    """Neutralise le service de portes : ce lot teste l'aiguillage, pas la porte."""
    def _submit(self, execution_id, approved, annotations=None):
        return {"success": True, "gate": "after_build_code"}

    from app.services.validation_gate_service import ValidationGateService

    monkeypatch.setattr(ValidationGateService, "submit_validation", _submit)


def test_approuver_after_build_code_ne_rejoue_pas_le_sds(
    client, db_session, enfiles, porte_after_build_code
):
    """Le defaut le plus couteux de la specification, dans le chemin nominal du
    client : approuver la porte emettait `deploy`, non reconnu, donc rejouait
    toute la chaine SDS depuis la phase 2. Une validation humaine relancait le
    travail qu'elle venait de valider."""
    user = _make_user(db_session)
    execution = _make_execution(db_session, user)
    _authenticate_as(user)

    r = client.post(
        GATE_URL.format(eid=execution.id), json={"approved": True}
    )
    assert r.status_code == 200, r.text

    assert len(enfiles) == 1, f"un seul job attendu : {enfiles}"
    job = enfiles[0]
    assert job["name"] == "execute_build_task", (
        f"la porte BUILD doit reprendre le BUILD, pas le SDS : {job['name']} "
        f"(kwargs={job['kwargs']})"
    )
    assert "resume_from" not in job["kwargs"], (
        "la reprise BUILD se porte par l'etat des TaskExecution, pas par "
        "resume_from — meme mecanique qu'en vague 2 (57ee795)"
    )
    assert job["kwargs"]["execution_id"] == execution.id


@pytest.fixture
def porte(monkeypatch):
    """Fabrique une porte nommee : ce lot teste l'aiguillage, pas la porte."""
    def _fabrique(nom):
        def _submit(self, execution_id, approved, annotations=None):
            return {"success": True, "gate": nom}

        from app.services.validation_gate_service import ValidationGateService

        monkeypatch.setattr(ValidationGateService, "submit_validation", _submit)

    return _fabrique


def test_rejeter_after_build_code_repart_aussi_sur_le_build(
    client, db_session, enfiles, porte
):
    """Le rejet emettait `build`, mort lui aussi. Meme chaine que l'approbation."""
    porte("after_build_code")
    user = _make_user(db_session)
    execution = _make_execution(db_session, user)
    _authenticate_as(user)

    r = client.post(
        GATE_URL.format(eid=execution.id),
        json={"approved": False, "annotations": "revoir le trigger"},
    )
    assert r.status_code == 200, r.text
    assert enfiles[0]["name"] == "execute_build_task"


def test_approuver_after_expert_specs_part_en_sds_canonique(
    client, db_session, enfiles, porte
):
    """`phase5_sds` etait morte : approuver les specs d'experts rejouait depuis
    la phase 2 au lieu de faire ecrire le SDS."""
    porte("after_expert_specs")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_EXPERT_VALIDATION
    )
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 200, r.text

    assert enfiles[0]["name"] == "execute_sds_task"
    assert enfiles[0]["kwargs"]["resume_from"] == "phase5"


def test_rejeter_after_expert_specs_rejoue_les_experts(
    client, db_session, enfiles, porte
):
    """`phase4_experts` -> `phase4` : c'est bien les experts qu'on rejoue."""
    porte("after_expert_specs")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_EXPERT_VALIDATION
    )
    _authenticate_as(user)

    r = client.post(
        GATE_URL.format(eid=execution.id),
        json={"approved": False, "annotations": "specs incompletes"},
    )
    assert r.status_code == 200, r.text
    assert enfiles[0]["kwargs"]["resume_from"] == "phase4"


def test_approuver_after_sds_generation_sert_le_livrable_sans_rien_relancer(
    client, db_session, enfiles, porte
):
    """§3.3, premiere ligne du tableau : le DOCX existe, aucun agent ne repart.
    C'etait `phase6_export`, morte, donc un rejeu complet du SDS."""
    porte("after_sds_generation")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_SDS_VALIDATION
    )
    execution.execution_state = "sds_complete"
    execution.sds_document_path = "/deliverables/sds_42.docx"
    db_session.commit()
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 200, r.text

    assert enfiles == [], f"aucun job ne devait etre enfile : {enfiles}"
    assert r.json()["document_path"] == "/deliverables/sds_42.docx"


def test_approuver_after_sds_generation_regenere_si_markdown_seul(
    client, db_session, enfiles, porte
):
    """Deuxieme ligne : le `.md` est la trace d'un export rate, pas un livrable."""
    porte("after_sds_generation")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_SDS_VALIDATION
    )
    execution.execution_state = "sds_complete"
    execution.sds_document_path = "/tmp/sds_42.md"
    db_session.commit()
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 200, r.text

    assert len(enfiles) == 1
    assert enfiles[0]["kwargs"]["resume_from"] == "phase5"


def test_approuver_l_export_trop_tot_est_refuse_et_le_dit(
    client, db_session, enfiles, porte
):
    """Quatrieme ligne : « pas un cas d'export — reprise amont ». Fabriquer un
    document sur un contenu incomplet produirait une coquille remise au client."""
    porte("after_sds_generation")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_SDS_VALIDATION
    )
    execution.execution_state = "sds_phase2_complete"
    db_session.commit()
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})

    assert r.status_code == 409, r.text
    assert "export" in r.json()["detail"].lower()
    assert enfiles == []


def test_une_porte_inconnue_est_refusee(client, db_session, enfiles, porte):
    """Regle 5 : `resume_map.get()` rendait `None`, qui partait tel quel dans le
    job. Une porte inconnue doit se voir, pas produire un job muet."""
    porte("after_something_else")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_SDS_VALIDATION
    )
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})

    assert r.status_code == 400, r.text
    assert enfiles == []
