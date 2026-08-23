"""
VAGUE 2 — LOT 2 : cloisonnement et coherence (EXECUTION.md §5.2 et §5.4).

Cinq defauts distincts, cinq preuves distinctes.

  2.1 `audit_service.get_logs()` sans notion de proprietaire — le cloisonnement
      vit dans la route, pas dans le service.
  2.2 `change_requests.py` : `related_br_id` non valide — fuite de texte de BR
      entre projets.
  2.3 `kim:PROD-10` : deux chemins d'ecriture incompatibles pour le secret
      Salesforce, et lecture sans dechiffrement.
  2.4 `pm_orchestrator_service_v2._get_salesforce_metadata` : repli sur la
      config globale quand aucun projet n'a pu etre resolu.
  2.5 `quality_dashboard.py` `/execution/{id}` : 500 meme au proprietaire.
"""
import pytest

from app.main import app
from app.models.audit import ActorType, ActionCategory
from app.models.business_requirement import BusinessRequirement
from app.models.change_request import ChangeRequest
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.project_credential import ProjectCredential, CredentialType
from app.models.user import User
from app.services.audit_service import audit_service
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _make_user(db, suffix: str, tier: str = "team") -> User:
    user = User(
        email=f"vague2-lot2-{suffix}@example.test",
        hashed_password="not-a-real-hash",
        name=f"Vague2 LOT2 {suffix}",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_project(db, user: User, name: str) -> Project:
    project = Project(user_id=user.id, name=name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _make_execution(db, project: Project, user: User) -> Execution:
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm"],
        agent_execution_status={},
        status=ExecutionStatus.COMPLETED,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _make_br(db, project: Project, br_id: str, text: str) -> BusinessRequirement:
    br = BusinessRequirement(
        project_id=project.id,
        br_id=br_id,
        requirement=text,
        category="secret",
    )
    db.add(br)
    db.commit()
    db.refresh(br)
    return br


def _authenticate_as(user: User):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


@pytest.fixture
def tenants(db_session):
    """Deux clients etanches, chacun avec projet, execution et BR."""
    out = {}
    for key in ("a", "b"):
        user = _make_user(db_session, key)
        project = _make_project(db_session, user, f"Projet {key.upper()}")
        execution = _make_execution(db_session, project, user)
        br = _make_br(
            db_session,
            project,
            f"BR-{key.upper()}01",
            f"SECRET DU CLIENT {key.upper()} : marge negociee a 42%",
        )
        out[key] = {
            "user": user,
            "project": project,
            "execution": execution,
            "br": br,
        }
    return out


# ==========================================================================
# 2.1 — audit_service.get_logs() doit porter le cloisonnement
# ==========================================================================

def test_get_logs_exige_un_proprietaire(db_session, tenants):
    """Un appelant qui n'a pas dit a qui appartiennent les journaux ne doit pas
    obtenir un journal global par defaut."""
    with pytest.raises(TypeError):
        audit_service.get_logs(project_id=tenants["a"]["project"].id, db=db_session)


def test_get_logs_ne_rend_que_les_lignes_du_proprietaire(db_session, tenants):
    """Le coeur du defaut : le service rendait les lignes d'autrui des lors que
    l'appelant demandait le bon project_id."""
    a, b = tenants["a"], tenants["b"]

    for tenant in (a, b):
        audit_service.log(
            actor_type=ActorType.USER,
            actor_id=str(tenant["user"].id),
            action=ActionCategory.EXECUTION_START,
            entity_type="execution",
            entity_id=str(tenant["execution"].id),
            project_id=tenant["project"].id,
            execution_id=tenant["execution"].id,
            db=db_session,
        )

    # A demande explicitement le projet de B : le service doit rendre vide.
    vus = audit_service.get_logs(
        owner_user_id=a["user"].id, project_id=b["project"].id, db=db_session
    )
    assert vus == [], (
        "le service a rendu des lignes du projet d'un autre client "
        f"({[l.project_id for l in vus]})"
    )

    # Controle positif : sur son propre projet, A voit sa ligne.
    siens = audit_service.get_logs(
        owner_user_id=a["user"].id, project_id=a["project"].id, db=db_session
    )
    assert len(siens) == 1
    assert siens[0].project_id == a["project"].id


def test_get_logs_filtre_dans_le_sql_pas_apres(db_session, tenants):
    """Le filtre doit etre dans la requete, sinon `limit`/`offset` mentent :
    une page pleine de lignes d'autrui, filtree apres coup, rend une page vide
    alors qu'il restait des lignes a rendre."""
    a, b = tenants["a"], tenants["b"]

    for _ in range(5):
        audit_service.log(
            actor_type=ActorType.USER,
            actor_id=str(b["user"].id),
            action=ActionCategory.EXECUTION_START,
            entity_type="execution",
            entity_id=str(b["execution"].id),
            project_id=b["project"].id,
            db=db_session,
        )
    for _ in range(3):
        audit_service.log(
            actor_type=ActorType.USER,
            actor_id=str(a["user"].id),
            action=ActionCategory.EXECUTION_START,
            entity_type="execution",
            entity_id=str(a["execution"].id),
            project_id=a["project"].id,
            db=db_session,
        )

    page = audit_service.get_logs(
        owner_user_id=a["user"].id, limit=3, offset=0, db=db_session
    )
    assert len(page) == 3, (
        "limit compte des lignes rendues, pas des lignes lues puis jetees"
    )
    assert all(log.project_id == a["project"].id for log in page)


def test_get_logs_derogation_systeme_explicite(db_session, tenants):
    """Un appelant systeme peut lire tout le journal — mais il doit le dire."""
    from app.services.audit_service import ALL_OWNERS

    audit_service.log(
        actor_type=ActorType.SYSTEM,
        actor_id="orchestrator",
        action=ActionCategory.EXECUTION_START,
        entity_type="execution",
        entity_id="1",
        project_id=tenants["a"]["project"].id,
        db=db_session,
    )
    tout = audit_service.get_logs(owner_user_id=ALL_OWNERS, db=db_session)
    assert len(tout) >= 1


def test_timeline_et_historique_portent_aussi_le_proprietaire(db_session, tenants):
    """Les deux facades du service ne doivent pas rouvrir la porte."""
    a, b = tenants["a"], tenants["b"]
    audit_service.log(
        actor_type=ActorType.USER,
        actor_id=str(b["user"].id),
        action=ActionCategory.EXECUTION_START,
        entity_type="execution",
        entity_id=str(b["execution"].id),
        project_id=b["project"].id,
        execution_id=b["execution"].id,
        db=db_session,
    )

    vus = audit_service.get_execution_timeline(
        execution_id=b["execution"].id, owner_user_id=a["user"].id, db=db_session
    )
    assert vus == []


def test_route_audit_logs_reste_cloisonnee(client, db_session, tenants):
    """Controle de non-regression : la route continue de refuser le projet
    d'autrui, et de rendre le sien."""
    a, b = tenants["a"], tenants["b"]
    _authenticate_as(a["user"])

    r = client.get(f"/api/audit/logs?project_id={b['project'].id}")
    assert r.status_code == 404, r.text

    r = client.get(f"/api/audit/logs?project_id={a['project'].id}")
    assert r.status_code == 200, r.text


# ==========================================================================
# 2.2 — change_requests : related_br_id doit appartenir au projet
# ==========================================================================

CR_URL = "/api/projects/{pid}/change-requests"


def test_creation_refuse_un_br_d_un_autre_projet(client, db_session, tenants):
    """Le defaut : on pointait le BR d'un autre client, et son texte ressortait
    dans `related_br_text`."""
    a, b = tenants["a"], tenants["b"]
    _authenticate_as(a["user"])

    r = client.post(
        CR_URL.format(pid=a["project"].id),
        json={
            "category": "evolution",
            "title": "CR fuite",
            "description": "pointe le BR du voisin",
            "related_br_id": b["br"].id,
        },
    )

    assert r.status_code in (400, 404), (
        f"un BR d'un autre projet doit etre refuse, obtenu {r.status_code} — {r.text[:200]}"
    )
    assert "42%" not in r.text


def test_creation_accepte_un_br_du_meme_projet(client, db_session, tenants):
    """Controle positif : le cas legitime doit continuer de passer."""
    a = tenants["a"]
    _authenticate_as(a["user"])

    r = client.post(
        CR_URL.format(pid=a["project"].id),
        json={
            "category": "evolution",
            "title": "CR legitime",
            "description": "pointe son propre BR",
            "related_br_id": a["br"].id,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["related_br_id"] == a["br"].id


def test_creation_sans_br_reste_possible(client, db_session, tenants):
    a = tenants["a"]
    _authenticate_as(a["user"])
    r = client.post(
        CR_URL.format(pid=a["project"].id),
        json={"category": "evolution", "title": "CR nue", "description": "sans BR"},
    )
    assert r.status_code == 200, r.text


def test_mise_a_jour_refuse_un_br_d_un_autre_projet(client, db_session, tenants):
    """La meme porte, cote update — elle etait grande ouverte."""
    a, b = tenants["a"], tenants["b"]
    cr = ChangeRequest(
        project_id=a["project"].id,
        cr_number="CR-001",
        category="evolution",
        title="CR a detourner",
        description="x",
        priority="medium",
        status="draft",
        created_by=a["user"].id,
    )
    db_session.add(cr)
    db_session.commit()
    db_session.refresh(cr)

    _authenticate_as(a["user"])
    r = client.put(
        f"{CR_URL.format(pid=a['project'].id)}/{cr.id}",
        json={"related_br_id": b["br"].id},
    )
    assert r.status_code in (400, 404), (
        f"attendu un refus, obtenu {r.status_code} — {r.text[:200]}"
    )

    db_session.refresh(cr)
    assert cr.related_br_id != b["br"].id, "la CR pointe le BR d'un autre projet"


def test_le_texte_du_br_d_autrui_ne_ressort_pas_en_lecture(client, db_session, tenants):
    """Defense en profondeur : meme une ligne deja corrompue en base — ecrite
    avant ce correctif — ne doit pas rendre le texte du BR d'autrui."""
    a, b = tenants["a"], tenants["b"]
    cr = ChangeRequest(
        project_id=a["project"].id,
        cr_number="CR-002",
        category="evolution",
        title="CR heritee",
        description="x",
        priority="medium",
        status="draft",
        created_by=a["user"].id,
        related_br_id=b["br"].id,
    )
    db_session.add(cr)
    db_session.commit()
    db_session.refresh(cr)

    _authenticate_as(a["user"])
    r = client.get(f"{CR_URL.format(pid=a['project'].id)}/{cr.id}")
    assert r.status_code == 200, r.text
    assert "42%" not in r.text, (
        f"le texte du BR d'un autre client est ressorti : {r.text[:300]}"
    )

    r = client.get(CR_URL.format(pid=a["project"].id))
    assert r.status_code == 200, r.text
    assert "42%" not in r.text


# ==========================================================================
# 2.3 — kim:PROD-10 : un seul chemin d'ecriture pour le secret Salesforce
# ==========================================================================

SETTINGS_URL = "/api/projects/{pid}/settings"


def _stored_credential(db, project_id, cred_type):
    return (
        db.query(ProjectCredential)
        .filter(
            ProjectCredential.project_id == project_id,
            ProjectCredential.credential_type == cred_type,
        )
        .first()
    )


def test_le_secret_salesforce_est_chiffre_a_l_ecriture(client, db_session, tenants):
    """Le defaut : `routes/projects.py` posait le secret en clair dans
    `encrypted_value`, la ou `wizard.py` passait par EnvironmentService et le
    chiffrait. Deux chemins, deux formats, une colonne."""
    from app.utils.encryption import decrypt_credential

    a = tenants["a"]
    _authenticate_as(a["user"])

    r = client.put(
        SETTINGS_URL.format(pid=a["project"].id),
        json={
            "sf_consumer_key": "3MVG9consumerkey",
            "sf_consumer_secret": "SECRET-EN-CLAIR-1234567890",
        },
    )
    assert r.status_code == 200, r.text

    cred = _stored_credential(db_session, a["project"].id, CredentialType.SALESFORCE_TOKEN)
    assert cred is not None
    assert cred.encrypted_value != "SECRET-EN-CLAIR-1234567890", (
        "le secret est stocke en clair dans project_credentials.encrypted_value"
    )
    assert decrypt_credential(cred.encrypted_value) == "SECRET-EN-CLAIR-1234567890"
    assert cred.label == "3MVG9consumerkey"


def test_le_jeton_git_est_chiffre_a_l_ecriture(client, db_session, tenants):
    """Meme colonne, meme defaut : LOT-E bis refuse desormais un jeton en clair
    au deploiement, mais cette route continuait d'en ecrire."""
    from app.utils.encryption import decrypt_credential

    a = tenants["a"]
    _authenticate_as(a["user"])

    r = client.put(
        SETTINGS_URL.format(pid=a["project"].id),
        json={"git_token": "ghp_unjetongithubencleair0000000000000000"},
    )
    assert r.status_code == 200, r.text

    cred = _stored_credential(db_session, a["project"].id, CredentialType.GIT_TOKEN)
    assert cred is not None
    assert not cred.encrypted_value.startswith("ghp_"), (
        "jeton GitHub stocke en clair — exactement ce que LOT-E bis refuse en aval"
    )
    assert (
        decrypt_credential(cred.encrypted_value)
        == "ghp_unjetongithubencleair0000000000000000"
    )


def test_mettre_a_jour_la_cle_seule_ne_perd_pas_le_secret(client, db_session, tenants):
    """Piege du chemin unifie : `store_credential` remplace la ligne entiere.
    Modifier la seule cle ne doit pas effacer le secret."""
    from app.utils.encryption import decrypt_credential

    a = tenants["a"]
    _authenticate_as(a["user"])

    client.put(
        SETTINGS_URL.format(pid=a["project"].id),
        json={"sf_consumer_key": "cle-1", "sf_consumer_secret": "secret-1"},
    )
    r = client.put(
        SETTINGS_URL.format(pid=a["project"].id),
        json={"sf_consumer_key": "cle-2"},
    )
    assert r.status_code == 200, r.text

    cred = _stored_credential(db_session, a["project"].id, CredentialType.SALESFORCE_TOKEN)
    assert cred.label == "cle-2"
    assert decrypt_credential(cred.encrypted_value) == "secret-1"


def test_la_lecture_dechiffre_ce_que_wizard_a_ecrit(db_session, tenants):
    """Le troisieme volet de PROD-10 : la lecture. `test-salesforce` prenait
    `cred.encrypted_value` tel quel — donc du Fernet passe a Salesforce comme
    `client_secret` des lors que le wizard avait ecrit la ligne."""
    from app.api.routes.projects import _read_salesforce_oauth_credentials
    from app.services.environment_service import get_environment_service

    a = tenants["a"]
    env = get_environment_service(db_session)
    env.store_credential(
        a["project"].id,
        CredentialType.SALESFORCE_TOKEN,
        "secret-ecrit-par-le-wizard",
        label="cle-du-wizard",
    )

    key, secret = _read_salesforce_oauth_credentials(db_session, a["project"].id)
    assert key == "cle-du-wizard"
    assert secret == "secret-ecrit-par-le-wizard"


# ==========================================================================
# 2.4 — pas de repli sur la config Salesforce globale sans projet
# ==========================================================================

@pytest.mark.asyncio
async def test_metadata_refuse_quand_aucun_projet_n_est_resolu(db_session):
    """`_get_salesforce_metadata` gardait `sf_cfg = salesforce_config` quand
    `project` restait None. Il n'emprunte plus d'identite depuis LOT-E bis,
    mais doit refuser explicitement au lieu d'essayer."""
    from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

    service = PMOrchestratorServiceV2(db_session)
    # execution_id inexistant : aucun projet ne peut etre resolu.
    result = await service._get_salesforce_metadata(execution_id=999999, project=None)

    assert result["success"] is False
    assert result["error"] == "no_project_resolved"
    assert result["full_metadata"] == {}


# ==========================================================================
# 2.5 — quality_dashboard /execution/{id} ne doit plus rendre 500
# ==========================================================================

def test_quality_execution_repond_200_au_proprietaire(client, db_session, tenants):
    """Le SQL selectionnait `validation_status` et `validation_errors`,
    absentes de `task_executions` : 500 systematique, meme au proprietaire."""
    a = tenants["a"]
    _authenticate_as(a["user"])

    r = client.get(f"/api/quality/execution/{a['execution'].id}")
    assert r.status_code == 200, f"attendu 200, obtenu {r.status_code} — {r.text[:300]}"
    body = r.json()
    assert body["success"] is True
    assert body["execution_id"] == a["execution"].id
    assert "summary" in body


def test_quality_execution_analyse_les_fichiers_generes(client, db_session, tenants):
    """Controle positif : la route rend bien une analyse, pas une coquille."""
    from app.models.task_execution import TaskExecution, TaskStatus

    a = tenants["a"]
    task = TaskExecution(
        execution_id=a["execution"].id,
        task_id="TASK-001",
        task_name="AccountTrigger",
        assigned_agent="diego",
        status=TaskStatus.COMPLETED,
        generated_files={
            "force-app/main/default/classes/AccountService.cls": (
                "public with sharing class AccountService {\n"
                "    public static void run() {\n"
                "        System.debug('x');\n"
                "    }\n"
                "}\n"
            )
        },
    )
    db_session.add(task)
    db_session.commit()

    _authenticate_as(a["user"])
    r = client.get(f"/api/quality/execution/{a['execution'].id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summary"]["total_files"] == 1
    assert body["files"][0]["task_id"] == "TASK-001"


def test_quality_execution_reste_cloisonnee(client, db_session, tenants):
    """Non-regression du LOT-B : le voisin reste dehors."""
    a, b = tenants["a"], tenants["b"]
    _authenticate_as(a["user"])
    r = client.get(f"/api/quality/execution/{b['execution'].id}")
    assert r.status_code in (403, 404), r.text
