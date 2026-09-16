"""Vague 1 / file A — BILL-05 (L701) et SEC-08 (L159).

Critere AS-05 : **toutes** les ecritures BUILD refusees pour Free/Pro —
demarrage, retry, validation de porte, appel direct de service — cote
serveur, worker compris, sans effet de bord. Perimetre decide par Sam le
15/09 : Free + Pro ouverts, BUILD ferme.

BILL-05 : les portes se posaient route par route, et plusieurs chemins
secondaires n'en portaient aucune (uploads, snapshots SDS, analyse de CR),
tandis que la porte BUILD manquait a la validation de porte et au worker.

SEC-08 : le garde-fou « jamais en production Salesforce » etait local a
SFAdminService, absent des deploiements de source, et se contentait d'une
sous-chaine (`--` dans un alias) comme preuve de non-production.

Un test par chemin. Les chemins qui vivent dans les fichiers d'une autre
file sont mesures ici par **appel direct au service**, et leur diff de route
est dans docs/missions/RAPPORT_VAGUE1_A.md.
"""
import asyncio

import pytest
from fastapi import HTTPException

from app.main import app
from app.models.execution import Execution
from app.models.project import Project
from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)


def _utilisateur(db, suffix: str, tier: str) -> User:
    user = User(
        email=f"bill05-{suffix}@example.test",
        hashed_password="pas-un-vrai-hash",
        name=f"BILL05 {suffix}",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _projet(db, user: User) -> Project:
    projet = Project(user_id=user.id, name=f"Projet de {user.email}")
    db.add(projet)
    db.commit()
    db.refresh(projet)
    return projet


@pytest.fixture
def comptes(db_session):
    out = {}
    for tier in ("free", "pro", "team"):
        user = _utilisateur(db_session, tier, tier)
        projet = _projet(db_session, user)
        execution = Execution(project_id=projet.id, user_id=user.id)
        db_session.add(execution)
        db_session.commit()
        db_session.refresh(execution)
        out[tier] = {"user": user, "projet": projet, "execution": execution}
    return out


def _authentifier(user: User):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


# ==========================================================================
# 1. La garde serveur des ecritures BUILD — appel direct, sans route
# ==========================================================================

def test_la_garde_build_refuse_free_et_pro(comptes):
    from app.utils.build_guard import ensure_build_write_allowed

    for tier in ("free", "pro"):
        with pytest.raises(HTTPException) as exc:
            ensure_build_write_allowed(comptes[tier]["user"])
        assert exc.value.status_code == 403


def test_controle_negatif_la_garde_build_laisse_passer_team(comptes):
    from app.utils.build_guard import ensure_build_write_allowed

    ensure_build_write_allowed(comptes["team"]["user"])  # ne leve pas


def test_la_garde_build_refuse_un_profil_illisible():
    """Regle 6 : profil illisible = refus, jamais « laisser passer »."""
    from app.utils.build_guard import ensure_build_write_allowed

    class _SansTier:
        pass

    for sujet in (None, _SansTier(), type("U", (), {"subscription_tier": "inconnu"})()):
        with pytest.raises(HTTPException) as exc:
            ensure_build_write_allowed(sujet)
        assert exc.value.status_code in (401, 403)


def test_la_garde_build_par_identifiant_relit_le_palier_en_base(db_session, comptes):
    """Le worker ne recoit pas d'objet User : il doit pouvoir revalider a
    partir de l'identifiant d'execution, au demarrage du job."""
    from app.utils.build_guard import ensure_build_write_allowed_for_execution

    for tier in ("free", "pro"):
        with pytest.raises(HTTPException):
            ensure_build_write_allowed_for_execution(
                comptes[tier]["execution"].id, db_session
            )
    ensure_build_write_allowed_for_execution(comptes["team"]["execution"].id, db_session)


def test_la_garde_build_refuse_une_execution_inconnue(db_session):
    """Un job orphelin ne doit pas s'executer « par defaut »."""
    from app.utils.build_guard import ensure_build_write_allowed_for_execution

    with pytest.raises(HTTPException):
        ensure_build_write_allowed_for_execution(999_999, db_session)


# ==========================================================================
# 2. SEC-08 — les ecritures Salesforce sont fermees au niveau service
# ==========================================================================

def test_les_ecritures_salesforce_sont_fermees_par_defaut():
    from app.utils.build_guard import SalesforceWritesDisabled, ensure_salesforce_write_allowed

    with pytest.raises(SalesforceWritesDisabled):
        ensure_salesforce_write_allowed("digital-humans-dev")


def test_un_alias_ne_prouve_pas_qu_une_org_n_est_pas_productive(monkeypatch):
    """`--` dans un alias suffisait a declarer l'org non productive. Un alias
    est fourni par l'appelant : ce n'est pas une preuve."""
    from app.utils import build_guard

    monkeypatch.setattr(build_guard, "_ecritures_salesforce_activees", lambda: True)
    with pytest.raises(build_guard.SalesforceOrgNonVerifiee):
        build_guard.ensure_salesforce_write_allowed("acme--preprod")
    with pytest.raises(build_guard.SalesforceOrgNonVerifiee):
        build_guard.ensure_salesforce_write_allowed(
            "acme", preuve_org={"isSandbox": "peut-etre"}
        )


def test_controle_negatif_une_preuve_authentifiee_est_acceptee(monkeypatch):
    from app.utils import build_guard

    monkeypatch.setattr(build_guard, "_ecritures_salesforce_activees", lambda: True)
    build_guard.ensure_salesforce_write_allowed(
        "acme",
        preuve_org={"isSandbox": True, "organizationId": "00D000000000001EAA"},
    )


def test_deploy_source_refuse_sans_lancer_de_sous_processus(monkeypatch):
    """SEC-08 : le deploiement de source n'utilisait aucun garde-fou."""
    from app.services.sfdx_service import SFDXService
    from app.utils.build_guard import SalesforceWritesDisabled

    service = SFDXService(target_org="acme--preprod")

    async def _interdit(*a, **k):  # pragma: no cover — ne doit jamais courir
        raise AssertionError("un sous-processus sf a ete lance malgre la garde")

    monkeypatch.setattr(service, "_run_command", _interdit)
    with pytest.raises(SalesforceWritesDisabled):
        asyncio.run(service.deploy_source("/tmp/source"))


def test_execute_anonymous_refuse_aussi(monkeypatch):
    """Apex anonyme est une ecriture : meme garde."""
    from app.services.sfdx_service import SFDXService
    from app.utils.build_guard import SalesforceWritesDisabled

    service = SFDXService(target_org="acme--preprod")

    async def _interdit(*a, **k):  # pragma: no cover
        raise AssertionError("un sous-processus sf a ete lance malgre la garde")

    monkeypatch.setattr(service, "_run_command", _interdit)
    with pytest.raises(SalesforceWritesDisabled):
        asyncio.run(service.execute_anonymous("System.debug(1);"))


def test_controle_negatif_une_lecture_salesforce_reste_permise(monkeypatch):
    """La garde vise les ECRITURES : `sf org display` doit rester possible,
    sinon on n'a pas ferme une porte, on a coupe le courant."""
    from app.services.sfdx_service import SFDXService

    service = SFDXService(target_org="acme--preprod")
    appels = []

    async def _faux(args, **kwargs):
        appels.append(args)
        return True, {"result": {"id": "00D", "username": "u", "instanceUrl": "https://x"}}

    monkeypatch.setattr(service, "_run_command", _faux)
    resultat = asyncio.run(service.check_connection())
    assert appels, "la lecture n'a pas ete transmise au CLI"
    assert resultat["connected"] is True


def test_le_deploiement_de_l_executeur_d_agents_refuse_aussi(monkeypatch):
    """`AgentExecutor._deploy_to_salesforce` appelait `subprocess.run` sans
    aucun garde-fou de production.

    L'org est rendue CONFIGUREE pour ce test : sinon le refus viendrait de
    `salesforce_config.require("org_alias")` — mesure du 16/09 dans le bac a
    sable — et le test serait vert sans qu'aucune garde n'existe (regle 2).
    Le refus doit porter le code stable de la garde.
    """
    import app.services.agent_executor as module
    from app.utils.build_guard import CODE_REFUS_ECRITURE_SALESFORCE

    def _interdit(*a, **k):  # pragma: no cover
        raise AssertionError("subprocess.run a ete appele malgre la garde")

    monkeypatch.setattr(module.subprocess, "run", _interdit)
    monkeypatch.setattr(module.salesforce_config, "require", lambda *a, **k: None)
    monkeypatch.setattr(module.salesforce_config, "org_alias", "acme--preprod", raising=False)
    executeur = module.AgentExecutor.__new__(module.AgentExecutor)
    resultat = asyncio.run(module.AgentExecutor._deploy_to_salesforce(executeur))
    assert resultat["success"] is False
    assert CODE_REFUS_ECRITURE_SALESFORCE in (resultat.get("error") or "")


# ==========================================================================
# 3. BILL-05 — chemins secondaires sans porte Free
# ==========================================================================

def test_le_snapshot_sds_porte_sa_porte_free(client, comptes):
    _authentifier(comptes["free"]["user"])
    reponse = client.post(
        f"/api/projects/{comptes['free']['projet'].id}/sds-versions",
        json={"execution_id": comptes["free"]["execution"].id},
    )
    assert reponse.status_code == 403, reponse.text


def test_controle_negatif_le_snapshot_reste_ouvert_a_pro(client, comptes, monkeypatch):
    import sys
    import types

    faux = types.ModuleType("build_sds")
    faux.build_sds = lambda _id: "<html><body>ok</body></html>"
    monkeypatch.setitem(sys.modules, "build_sds", faux)

    _authentifier(comptes["pro"]["user"])
    reponse = client.post(
        f"/api/projects/{comptes['pro']['projet'].id}/sds-versions",
        json={"execution_id": comptes["pro"]["execution"].id},
    )
    assert reponse.status_code == 201, reponse.text


def test_l_upload_de_document_porte_sa_porte_free(client, comptes):
    _authentifier(comptes["free"]["user"])
    reponse = client.post(
        f"/api/projects/{comptes['free']['projet'].id}/documents",
        files={"file": ("note.txt", b"contenu", "text/plain")},
    )
    assert reponse.status_code == 403, reponse.text


def test_controle_negatif_l_upload_reste_ouvert_a_pro(client, comptes, monkeypatch):
    """Sans ce controle, un 403 du a une autre cause (route absente, projet
    introuvable) passerait le test precedent."""
    from app.api.routes import documents as module

    monkeypatch.setattr(
        module, "ingest_document", lambda *a, **k: {"chunks": 1}, raising=False
    )
    _authentifier(comptes["pro"]["user"])
    reponse = client.post(
        f"/api/projects/{comptes['pro']['projet'].id}/documents",
        files={"file": ("note.txt", b"contenu", "text/plain")},
    )
    assert reponse.status_code != 403, reponse.text


def test_l_analyse_de_cr_porte_sa_porte_free(client, comptes):
    _authentifier(comptes["free"]["user"])
    reponse = client.post(
        f"/api/projects/{comptes['free']['projet'].id}/change-requests",
        json={"title": "T", "description": "D", "category": "other", "priority": "low"},
    )
    assert reponse.status_code == 403, reponse.text
