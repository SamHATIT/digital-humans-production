"""
VAGUE 3 — §3.2 : table de correspondance des valeurs emises.

Les quatre appelants emettent un vocabulaire qui n'est pas celui
d'`execute_workflow`. §3.5 les refuse desormais au lieu de les deviner ; §3.1 a
cree les points d'entree qui manquaient. Reste a traduire.

La traduction vit **au bord**, dans `resolve_resume_point()`, et les routes
enfilent une valeur canonique. `execute_workflow` continue donc de n'accepter
que son propre vocabulaire : la table ne l'affaiblit pas, elle l'alimente.
"""
import pytest

from app.services.pm_orchestrator_service_v2 import (
    SDS_RESUME_POINTS,
    resolve_resume_point,
)


# --------------------------------------------------------------------------
# La table de §3.2, ligne par ligne
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "emise, attendue, pourquoi",
    [
        ("phase_ba", "phase2_5", "Olivia a fini les UC"),
        ("phase_architect", "phase4", "Marcus a fini"),
        ("phase_data", "phase5", "un expert a fini"),
        ("phase_trainer", "phase5", "un expert a fini"),
        ("phase_qa", "phase5", "un expert a fini"),
        ("phase_devops", "phase5", "un expert a fini"),
        ("phase4_experts", "phase4", "rejeu des experts demande"),
        ("phase5_sds", "phase5", "SDS ecrit, ou a reecrire"),
        ("phase2_ba", "phase2", "reprise apres validation des BR"),
    ],
)
def test_chaque_valeur_emise_a_sa_reprise(emise, attendue, pourquoi):
    assert resolve_resume_point(emise) == attendue, pourquoi


def test_toutes_les_cibles_sont_des_points_valides():
    """Une traduction qui produirait une valeur refusee par `execute_workflow`
    remplacerait un repli silencieux par un plantage systematique."""
    for emise in (
        "phase_ba", "phase_architect", "phase_data", "phase_trainer",
        "phase_qa", "phase_devops", "phase4_experts", "phase5_sds", "phase2_ba",
    ):
        assert resolve_resume_point(emise) in SDS_RESUME_POINTS


@pytest.mark.parametrize("canonique", sorted(SDS_RESUME_POINTS))
def test_une_valeur_deja_canonique_traverse_sans_changer(canonique):
    """La traduction doit etre idempotente : les routes qui emettent deja du
    canonique (`phase1` de `retry_routes`) ne doivent pas etre traduites."""
    assert resolve_resume_point(canonique) == canonique


def test_none_reste_none():
    """Pas de reprise demandee : ce n'est pas une valeur a traduire."""
    assert resolve_resume_point(None) is None


# --------------------------------------------------------------------------
# Ce que la table ne traduit pas
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valeur", ["deploy", "build", "build_tasks"])
def test_les_reprises_build_ne_sont_pas_traduites_en_sds(valeur):
    """§3.4 — elles partent vers `execute_build_task`, elles n'ont pas
    d'equivalent SDS. Les traduire serait recreer le defaut d'origine."""
    with pytest.raises(ValueError) as excinfo:
        resolve_resume_point(valeur)
    assert "execute_build_task" in str(excinfo.value)


def test_l_export_n_est_pas_une_reprise_de_workflow():
    """§3.3 — `phase6_export` ne relance aucun agent. Il se traite avant, sur
    l'etat et le document produit, pas en entrant dans le workflow."""
    with pytest.raises(ValueError) as excinfo:
        resolve_resume_point("phase6_export")
    assert "export" in str(excinfo.value).lower()


@pytest.mark.parametrize("valeur", ["phase42", "phase_inconnu", ""])
def test_une_valeur_hors_table_est_refusee(valeur):
    """La table ne doit pas devenir un nouveau repli silencieux."""
    with pytest.raises(ValueError) as excinfo:
        resolve_resume_point(valeur)
    assert repr(valeur) in str(excinfo.value) or valeur in str(excinfo.value)


# --------------------------------------------------------------------------
# Les routes enfilent du canonique, pas leur dialecte
# --------------------------------------------------------------------------
#
# Une table de traduction que personne n'appelle serait un dispositif inerte de
# plus. Ces tests verifient qu'elle est branchee la ou les valeurs naissent.

import pytest as _pytest

from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)

RETRY_URL = "/api/pm-orchestrator/execute/{eid}/retry"
RESUME_URL = "/api/pm-orchestrator/execute/{eid}/resume"


def _make_user(db, tier="team"):
    user = User(
        email=f"vague3-corresp-{tier}@example.test",
        hashed_password="not-a-real-hash",
        name="Vague3 correspondance",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user, agent_status, status=ExecutionStatus.FAILED):
    project = Project(user_id=user.id, name="Vague3 correspondance")
    db.add(project)
    db.commit()
    db.refresh(project)

    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status=agent_status,
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


@_pytest.fixture
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

    for module in (
        "app.api.routes.orchestrator.retry_routes",
        "app.api.routes.orchestrator.execution_routes",
    ):
        monkeypatch.setattr(f"{module}.get_redis_pool", _get_pool, raising=False)
    return calls


@_pytest.mark.parametrize(
    "agent_fini, emise_avant, attendu",
    [
        # `phase_order = [pm, ba, architect, data, trainer, qa, devops]` et la
        # route prend l'agent SUIVANT le dernier termine.
        ("pm", "phase_ba", "phase2_5"),          # Sophie a fini -> Olivia doit tourner
        ("ba", "phase_architect", "phase4"),     # Olivia a fini -> Marcus... 
        ("architect", "phase_data", "phase5"),   # Marcus a fini -> les experts
        ("data", "phase_trainer", "phase5"),
        ("qa", "phase_devops", "phase5"),
    ],
)
def test_retry_enfile_un_point_de_reprise_canonique(
    client, db_session, enfiles, agent_fini, emise_avant, attendu
):
    """`retry_routes` construisait `f"phase_{agent suivant}"` — six valeurs,
    toutes mortes. Elle doit enfiler du canonique."""
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, {agent_fini: {"state": "completed"}}
    )
    _authenticate_as(user)

    r = client.post(RETRY_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text

    assert len(enfiles) == 1
    enfile = enfiles[0]["kwargs"]["resume_from"]
    from app.services.pm_orchestrator_service_v2 import SDS_RESUME_POINTS

    assert enfile in SDS_RESUME_POINTS, (
        f"la route enfile {enfile!r}, qu'execute_workflow refuse "
        f"(valeur morte historique : {emise_avant!r})"
    )
    assert enfile == attendu


def test_retry_sans_agent_termine_reste_sur_phase1(client, db_session, enfiles):
    """Controle de non-regression : rien de termine, on repart du debut."""
    user = _make_user(db_session)
    execution = _make_execution(db_session, user, {})
    _authenticate_as(user)

    r = client.post(RETRY_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert enfiles[0]["kwargs"]["resume_from"] == "phase1"


def test_l_api_ne_depend_pas_de_l_orchestrateur_a_l_import():
    """`pm_orchestrator_service_v2` tire python-docx et chromadb.

    Les routes l'importent **dans le corps des fonctions**, deliberement : le
    monter au niveau module ferait dependre le demarrage de l'API de ces deux
    paquets lourds. La vague 2 avait constate qu'`app.main` s'importe sans eux
    (c'est ainsi que le defaut 1b avait ete reproduit) — cabler la table de
    correspondance ne doit pas le changer.
    """
    import pathlib

    racine = pathlib.Path(__file__).resolve().parents[1] / "app" / "api" / "routes"
    fautifs = []
    for source in racine.rglob("*.py"):
        for numero, ligne in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            nu = ligne.rstrip()
            if not nu.startswith(("from app.services.pm_orchestrator_service_v2",
                                  "import app.services.pm_orchestrator_service_v2")):
                continue
            fautifs.append(f"{source.name}:{numero}")

    assert not fautifs, (
        "import de l'orchestrateur au niveau module dans une route — le "
        f"demarrage de l'API dependrait de python-docx/chromadb : {fautifs}"
    )
