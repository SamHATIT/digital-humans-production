"""
LOT-B — Authentification et cloisonnement client.

Critere de fin du lot : « utilisateur A -> 403/404 sur toute ressource de B,
un test par routeur ».

Deux utilisateurs sont crees, chacun avec son projet, son execution et ses
ressources. Pour chacun des huit routeurs du perimetre du lot, on verifie :

  1. l'appel anonyme est refuse (401) quand le routeur exigeait deja ou
     exige desormais une authentification ;
  2. A, authentifie, ne peut pas atteindre les ressources de B (403/404) ;
  3. A atteint bien ses propres ressources (non-regression : le correctif
     ne doit pas fermer la porte au proprietaire legitime).

Constats couverts : cla:SEC-01, kim:SEC-01, kim:SEC-03 (ecriture).
"""
import pytest

from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.artifact import ExecutionArtifact
from app.models.change_request import ChangeRequest
from app.models.execution import Execution
from app.models.project import Project
from app.models.project_document import ProjectDocument
from app.models.sds_version import SDSVersion
from app.models.user import User
from app.utils.auth import create_access_token, get_password_hash


# Codes acceptes par le critere de fin : la ressource d'autrui est soit
# refusee (403), soit invisible (404, choix retenu pour ne pas confirmer
# l'existence d'un id).
DENIED = (403, 404)


# ---------------------------------------------------------------- fixtures

def _make_user(db, email: str) -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("motdepasse-de-test"),
        name=email.split("@")[0],
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_tenant(db, email: str, agent: Agent) -> dict:
    """Un client complet : user + projet + execution + ressources."""
    user = _make_user(db, email)

    project = Project(user_id=user.id, name=f"Projet {user.name}")
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
        content="<html><body>SDS confidentiel</body></html>",
    )
    artifact = ExecutionArtifact(
        execution_id=execution.id,
        artifact_type="use_case",
        artifact_code="UC-001",
        title="Cas d'usage confidentiel",
        producer_agent="ba",
        content={"texte": "confidentiel"},
    )
    change_request = ChangeRequest(
        project_id=project.id,
        execution_id=execution.id,
        cr_number="CR-001",
        category="scope",
        title="Demande confidentielle",
        description="Contenu confidentiel",
        status="draft",
        created_by=user.id,
    )
    sds_version = SDSVersion(
        project_id=project.id,
        execution_id=execution.id,
        version_number=1,
        file_name="SDS_v1.html",
    )
    document = ProjectDocument(
        project_id=project.id,
        filename="cahier-des-charges.pdf",
        file_path="/tmp/cahier-des-charges.pdf",
        status="ready",
    )
    db.add_all([deliverable, artifact, change_request, sds_version, document])
    db.commit()
    for obj in (deliverable, artifact, change_request, sds_version, document):
        db.refresh(obj)

    return {
        "user": user,
        "project": project,
        "execution": execution,
        "deliverable": deliverable,
        "artifact": artifact,
        "change_request": change_request,
        "sds_version": sds_version,
        "document": document,
        "headers": {
            "Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"
        },
    }


@pytest.fixture
def tenants(db_session):
    """Deux clients etanches : A (l'attaquant) et B (la victime)."""
    agent = Agent(name="olivia-ba", description="BA de test")
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    return {
        "a": _make_tenant(db_session, "alice@example.test", agent),
        "b": _make_tenant(db_session, "bob@example.test", agent),
    }


# ---------------------------------------------------------------- outillage

def _assert_denied(response, label: str):
    assert response.status_code in DENIED, (
        f"{label} : attendu 403/404, obtenu {response.status_code} "
        f"— {response.text[:200]}"
    )


def _assert_unauthenticated(response, label: str):
    assert response.status_code == 401, (
        f"{label} : attendu 401 sans jeton, obtenu {response.status_code} "
        f"— {response.text[:200]}"
    )


# ------------------------------------------------------- 1. deliverables.py

def test_deliverables_cloisonnement(client, tenants):
    """kim:SEC-01 — routeur entierement expose : aucun get_current_user."""
    a, b = tenants["a"], tenants["b"]
    liv_b, exec_b = b["deliverable"].id, b["execution"].id

    # 1. anonyme
    _assert_unauthenticated(
        client.get(f"/api/deliverables/{liv_b}"), "GET /deliverables/{id} anonyme"
    )
    _assert_unauthenticated(
        client.get(f"/api/deliverables/{liv_b}/full"),
        "GET /deliverables/{id}/full anonyme",
    )
    _assert_unauthenticated(
        client.get(f"/api/deliverables/executions/{exec_b}/previews"),
        "GET /deliverables/executions/{id}/previews anonyme",
    )

    # 2. A vers les ressources de B
    for method, url in [
        ("get", f"/api/deliverables/{liv_b}"),
        ("get", f"/api/deliverables/{liv_b}/full"),
        ("get", f"/api/deliverables/{liv_b}/render"),
        ("get", f"/api/deliverables/executions/{exec_b}"),
        ("get", f"/api/deliverables/executions/{exec_b}/previews"),
        ("get", f"/api/deliverables/executions/{exec_b}/agents/1"),
        ("get", f"/api/deliverables/executions/{exec_b}/types/sds"),
        ("delete", f"/api/deliverables/{liv_b}"),
    ]:
        _assert_denied(
            getattr(client, method)(url, headers=a["headers"]),
            f"{method.upper()} {url} par A",
        )

    _assert_denied(
        client.put(
            f"/api/deliverables/{liv_b}",
            json={"content": "contenu injecte"},
            headers=a["headers"],
        ),
        "PUT /deliverables/{id} de B par A",
    )
    _assert_denied(
        client.post(
            "/api/deliverables/",
            json={
                "execution_id": exec_b,
                "agent_id": 1,
                "deliverable_type": "sds",
                "content": "contenu injecte",
            },
            headers=a["headers"],
        ),
        "POST /deliverables/ sur l'execution de B par A",
    )

    # 3. non-regression : A voit bien les siens
    ok = client.get(f"/api/deliverables/{a['deliverable'].id}", headers=a["headers"])
    assert ok.status_code == 200, ok.text
    ok = client.get(
        f"/api/deliverables/executions/{a['execution'].id}/previews",
        headers=a["headers"],
    )
    assert ok.status_code == 200, ok.text


# ----------------------------------------------------------- 2. artifacts.py

def test_artifacts_cloisonnement(client, tenants):
    """kim:SEC-01 — CRUD artifacts V2, gates et questions sans auth."""
    a, b = tenants["a"], tenants["b"]
    exec_b = b["execution"].id

    _assert_unauthenticated(
        client.get(f"/api/v2/artifacts?execution_id={exec_b}"),
        "GET /api/v2/artifacts anonyme",
    )
    _assert_unauthenticated(
        client.get(f"/api/v2/gates?execution_id={exec_b}"),
        "GET /api/v2/gates anonyme",
    )

    for method, url in [
        ("get", f"/api/v2/artifacts?execution_id={exec_b}"),
        ("get", f"/api/v2/artifacts/UC-001?execution_id={exec_b}"),
        ("get", f"/api/v2/artifacts/next-code/use_case?execution_id={exec_b}"),
        ("get", f"/api/v2/context/ba?execution_id={exec_b}"),
        ("get", f"/api/v2/gates?execution_id={exec_b}"),
        ("get", f"/api/v2/gates/1?execution_id={exec_b}"),
        ("post", f"/api/v2/gates/1/submit?execution_id={exec_b}"),
        ("post", f"/api/v2/gates/1/approve?execution_id={exec_b}"),
        ("get", f"/api/v2/questions?execution_id={exec_b}"),
        ("get", f"/api/v2/questions/next-code?execution_id={exec_b}"),
        ("get", f"/api/v2/graph?execution_id={exec_b}"),
    ]:
        _assert_denied(
            getattr(client, method)(url, headers=a["headers"]),
            f"{method.upper()} {url} par A",
        )

    _assert_denied(
        client.post(
            "/api/v2/gates/initialize",
            json={"execution_id": exec_b},
            headers=a["headers"],
        ),
        "POST /api/v2/gates/initialize sur l'execution de B par A",
    )
    _assert_denied(
        client.put(
            f"/api/v2/artifacts/UC-001?execution_id={exec_b}",
            json={"title": "titre injecte"},
            headers=a["headers"],
        ),
        "PUT /api/v2/artifacts/UC-001 de B par A",
    )

    ok = client.get(
        f"/api/v2/artifacts?execution_id={a['execution'].id}", headers=a["headers"]
    )
    assert ok.status_code == 200, ok.text


# ---------------------------------------------------------- 3. deployment.py

def test_deployment_cloisonnement(client, tenants):
    """kim:SEC-01 — le routeur qui execute les deploiements, sans auth."""
    a, b = tenants["a"], tenants["b"]
    exec_b = b["execution"].id

    # 1. anonyme : y compris promote / rollback, les plus dangereuses
    _assert_unauthenticated(
        client.post(
            "/api/deployment/promote",
            json={"source_path": "/tmp/x", "target_env": "production"},
        ),
        "POST /deployment/promote anonyme",
    )
    _assert_unauthenticated(
        client.post("/api/deployment/rollback", json={"snapshot_path": "/tmp/x"}),
        "POST /deployment/rollback anonyme",
    )
    _assert_unauthenticated(
        client.post(
            "/api/deployment/snapshot/create", json={"deployment_id": "DEP-1"}
        ),
        "POST /deployment/snapshot/create anonyme",
    )
    _assert_unauthenticated(
        client.get("/api/deployment/environments"),
        "GET /deployment/environments anonyme",
    )
    _assert_unauthenticated(
        client.get("/api/deployment/snapshots"), "GET /deployment/snapshots anonyme"
    )
    _assert_unauthenticated(
        client.get(f"/api/deployment/package/{exec_b}/files"),
        "GET /deployment/package/{id}/files anonyme",
    )
    _assert_unauthenticated(
        client.get(f"/api/deployment/release-notes/{exec_b}"),
        "GET /deployment/release-notes/{id} anonyme",
    )

    # 2. A vers l'execution de B
    _assert_denied(
        client.get(f"/api/deployment/package/{exec_b}/files", headers=a["headers"]),
        "GET /deployment/package/{execution de B}/files par A",
    )
    _assert_denied(
        client.get(f"/api/deployment/release-notes/{exec_b}", headers=a["headers"]),
        "GET /deployment/release-notes/{execution de B} par A",
    )
    _assert_denied(
        client.post(
            "/api/deployment/package/generate",
            json={"files": {"a.cls": "x"}, "execution_id": exec_b},
            headers=a["headers"],
        ),
        "POST /deployment/package/generate sur l'execution de B par A",
    )

    # 3. non-regression : A accede a sa propre execution (200 attendu, la
    # requete SQL ne remonte simplement aucun fichier genere)
    ok = client.get(
        f"/api/deployment/package/{a['execution'].id}/files", headers=a["headers"]
    )
    assert ok.status_code == 200, ok.text


# --------------------------------------------------- 4. quality_dashboard.py

def test_quality_dashboard_cloisonnement(client, tenants):
    """cla:SEC-01 — SQL brut sans filtre utilisateur, routeur sans auth."""
    a, b = tenants["a"], tenants["b"]

    _assert_unauthenticated(
        client.get(f"/api/quality/execution/{b['execution'].id}"),
        "GET /quality/execution/{id} anonyme",
    )
    _assert_unauthenticated(
        client.get(f"/api/quality/trends/{b['project'].id}"),
        "GET /quality/trends/{id} anonyme",
    )
    _assert_unauthenticated(client.get("/api/quality/rules"), "GET /quality/rules anonyme")

    _assert_denied(
        client.get(
            f"/api/quality/execution/{b['execution'].id}", headers=a["headers"]
        ),
        "GET /quality/execution/{execution de B} par A",
    )
    _assert_denied(
        client.get(f"/api/quality/trends/{b['project'].id}", headers=a["headers"]),
        "GET /quality/trends/{projet de B} par A",
    )

    # Non-regression : le proprietaire n'est PAS refuse par le controle
    # d'acces. On ne peut pas exiger 200 ici : la requete SQL de cette route
    # selectionne `task_executions.validation_status` et
    # `task_executions.validation_errors`, deux colonnes qui n'existent pas
    # dans le modele — la route repondait deja 500 avant le lot. Defaut
    # prealable signale, non corrige (hors constat, et le nom de colonne
    # correct ne se devine pas).
    reponse = client.get(
        f"/api/quality/execution/{a['execution'].id}", headers=a["headers"]
    )
    assert reponse.status_code not in DENIED, (
        f"le proprietaire ne doit pas etre refuse : {reponse.status_code}"
    )


# ----------------------------------------------------- 5. change_requests.py

def test_change_requests_cloisonnement(client, tenants):
    """cla:SEC-01 — routeur authentifie mais non cloisonne sur 5 routes
    (update / submit / approve / reject / delete filtraient sur project_id
    seul, sans verifier que le projet appartient a l'appelant)."""
    a, b = tenants["a"], tenants["b"]
    proj_b, cr_b = b["project"].id, b["change_request"].id

    _assert_unauthenticated(
        client.get(f"/api/projects/{proj_b}/change-requests"),
        "GET /change-requests anonyme",
    )

    for method, url, payload in [
        ("get", f"/api/projects/{proj_b}/change-requests", None),
        ("get", f"/api/projects/{proj_b}/change-requests/{cr_b}", None),
        ("put", f"/api/projects/{proj_b}/change-requests/{cr_b}", {"title": "pirate"}),
        ("post", f"/api/projects/{proj_b}/change-requests/{cr_b}/submit", None),
        ("post", f"/api/projects/{proj_b}/change-requests/{cr_b}/approve", {"notes": "x"}),
        ("post", f"/api/projects/{proj_b}/change-requests/{cr_b}/reject", None),
        ("delete", f"/api/projects/{proj_b}/change-requests/{cr_b}", None),
    ]:
        kwargs = {"headers": a["headers"]}
        if payload is not None:
            kwargs["json"] = payload
        _assert_denied(
            getattr(client, method)(url, **kwargs), f"{method.upper()} {url} par A"
        )

    # la CR de B n'a pas bouge
    assert b["change_request"].status == "draft"
    assert b["change_request"].title == "Demande confidentielle"

    ok = client.get(
        f"/api/projects/{a['project'].id}/change-requests", headers=a["headers"]
    )
    assert ok.status_code == 200, ok.text


# ------------------------------------------------------- 6. sds_versions.py

def test_sds_versions_cloisonnement(client, tenants):
    """Constat non confirme sur ce routeur : l'auth et la propriete y
    etaient deja posees sur les 7 routes. Test de non-regression."""
    a, b = tenants["a"], tenants["b"]
    proj_b = b["project"].id

    _assert_unauthenticated(
        client.get(f"/api/projects/{proj_b}/sds-versions"),
        "GET /sds-versions anonyme",
    )

    for method, url in [
        ("get", f"/api/projects/{proj_b}/sds-versions"),
        ("get", f"/api/projects/{proj_b}/sds-versions/1"),
        ("get", f"/api/projects/{proj_b}/sds-versions/1/download"),
        ("get", f"/api/projects/{proj_b}/sds-versions/1/view"),
        ("get", f"/api/projects/{proj_b}/sds-versions/current/download"),
        ("post", f"/api/projects/{proj_b}/approve-sds"),
    ]:
        _assert_denied(
            getattr(client, method)(url, headers=a["headers"]),
            f"{method.upper()} {url} par A",
        )

    _assert_denied(
        client.post(
            f"/api/projects/{proj_b}/sds-versions",
            json={"execution_id": b["execution"].id},
            headers=a["headers"],
        ),
        "POST /sds-versions sur le projet de B par A",
    )

    ok = client.get(
        f"/api/projects/{a['project'].id}/sds-versions", headers=a["headers"]
    )
    assert ok.status_code == 200, ok.text


# ---------------------------------------------------------- 7. documents.py

def test_documents_cloisonnement(client, tenants):
    """Auth et propriete deja posees (constat non confirme cote acces).
    Test de non-regression + kim:SEC-03 cote ecriture (nom de fichier)."""
    a, b = tenants["a"], tenants["b"]
    proj_b, doc_b = b["project"].id, b["document"].id

    _assert_unauthenticated(
        client.get(f"/api/projects/{proj_b}/documents"), "GET /documents anonyme"
    )
    _assert_denied(
        client.get(f"/api/projects/{proj_b}/documents", headers=a["headers"]),
        "GET /documents du projet de B par A",
    )
    _assert_denied(
        client.delete(
            f"/api/projects/{proj_b}/documents/{doc_b}", headers=a["headers"]
        ),
        "DELETE /documents/{id} de B par A",
    )
    _assert_denied(
        client.post(
            f"/api/projects/{proj_b}/documents",
            files={"file": ("note.txt", b"contenu", "text/plain")},
            headers=a["headers"],
        ),
        "POST /documents sur le projet de B par A",
    )

    ok = client.get(f"/api/projects/{a['project'].id}/documents", headers=a["headers"])
    assert ok.status_code == 200, ok.text


def test_documents_nom_de_fichier_traversant(client, tenants, tmp_path, monkeypatch):
    """kim:SEC-03 (ecriture) — `project_dir / file.filename` ecrivait hors
    du repertoire projet quand le nom contenait `../`."""
    import sys
    import types

    from app.api.routes import documents as documents_routes

    # `app.services.rag_service` importe chromadb, absent de l'environnement
    # de test. La route l'importe paresseusement : on lui substitue un
    # module minimal, l'ingestion RAG n'etant pas l'objet du test.
    faux_rag = types.ModuleType("app.services.rag_service")
    faux_rag.COLLECTIONS = {"technical": "technical"}
    faux_rag.ingest_document = lambda **kwargs: len(kwargs.get("chunks") or [])
    faux_rag.delete_project_document_chunks = lambda *args, **kwargs: 0
    monkeypatch.setitem(sys.modules, "app.services.rag_service", faux_rag)

    monkeypatch.setattr(documents_routes, "DOCUMENTS_DIR", tmp_path / "docs")
    a = tenants["a"]

    reponse = client.post(
        f"/api/projects/{a['project'].id}/documents",
        files={
            "file": ("../../evasion.txt", b"contenu malveillant", "text/plain")
        },
        headers=a["headers"],
    )
    assert reponse.status_code == 200, reponse.text

    # rien n'a ete ecrit hors du repertoire du projet
    assert not (tmp_path / "evasion.txt").exists()
    assert not (tmp_path / "docs" / "evasion.txt").exists()
    ecrits = list((tmp_path / "docs" / str(a["project"].id)).iterdir())
    assert [f.name for f in ecrits] == ["evasion.txt"]


# ----------------------------------------------------------- 8. analytics.py

def test_analytics_cloisonnement(client, tenants):
    """Constat non confirme : le routeur filtrait deja sur
    `Project.user_id == current_user.id`. Test de non-regression — les
    chiffres de A ne doivent pas contenir les projets de B."""
    a = tenants["a"]

    _assert_unauthenticated(client.get("/api/analytics"), "GET /analytics anonyme")

    reponse = client.get("/api/analytics", headers=a["headers"])
    assert reponse.status_code == 200, reponse.text

    noms = {p["name"] for p in reponse.json()["projects"]}
    assert "Projet bob" not in noms, (
        f"fuite inter-clients dans /api/analytics : {noms}"
    )
