"""
VAGUE 1 / FILE C — SEC-15 (diff de la file A) : le jeton d'acces Salesforce
finissait dans un livrable, donc dans un prompt.

`_get_salesforce_metadata` copiait integralement le resultat de
`sf org display --json` dans `metadata["org_info"]`. Ce resultat porte
`accessToken`, et selon les versions `refreshToken`, `clientId`,
`sfdxAuthUrl`. Le dictionnaire est ensuite stocke comme livrable puis injecte
dans le contexte d'analyse.

La liste blanche est `app/utils/redaction.py::filtrer_resultat_org_salesforce`
(file A). Ce test verifie son application **a ce point precis**.
"""
import json

import pytest

from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

ORG_BRUTE = {
    "id": "00D000000000001EAA",
    "username": "admin@example.test",
    "instanceUrl": "https://example.my.salesforce.com",
    "accessToken": "00D000000000001!AQEAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "refreshToken": "5Aep861_refresh_token_de_test",
    "clientId": "PlatformCLI",
    "sfdxAuthUrl": "force://PlatformCLI::5Aep861@example.my.salesforce.com",
    "apiVersion": "61.0",
}


class _Resultat:
    def __init__(self, returncode, stdout):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _resultat_sfdx(args):
    """Repond a `org display` avec le resultat brut, et fait echouer le reste.

    Les autres commandes (types de metadonnees, objets, limites) ne sont pas le
    sujet de SEC-15 ; leur echec est deja tolere par la methode.
    """
    # `sf limits api display` contient aussi « display » : on discrimine sur la
    # commande complete, sinon les limites recoivent le resultat de l'org.
    if args[:3] == ["sf", "org", "display"]:
        return _Resultat(0, json.dumps({"status": 0, "result": ORG_BRUTE}))
    return _Resultat(1, "")


def _org_configuree(monkeypatch):
    """Une org alias declaree : sans elle, la methode refuse avant d'appeler le
    CLI (« greenfield_or_not_connected ») et le test ne verifierait rien."""
    from app.salesforce_config import salesforce_config

    monkeypatch.setattr(
        salesforce_config, "require", lambda *a, **kw: None, raising=False
    )
    monkeypatch.setattr(salesforce_config, "org_alias", "org-de-test", raising=False)


@pytest.fixture
def projet(db_session):
    user = User(
        email="vague1c-sec15@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C SEC-15",
        subscription_tier="team",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    # `sf_connected` : sans lui, la methode saute la recuperation
    # (« greenfield_or_not_connected ») et le test ne verifierait rien.
    project = Project(
        user_id=user.id,
        name="SEC-15",
        description="x",
        project_type="brownfield",
        sf_connected=True,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_le_jeton_d_acces_ne_sort_pas_de_la_commande(
    db_session, projet, monkeypatch
):
    """Le coeur du constat : ce dictionnaire part ensuite dans un prompt."""
    async def _sfdx(args, timeout=30):
        return _resultat_sfdx(args)

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_sfdx_async", staticmethod(_sfdx))
    _org_configuree(monkeypatch)

    service = PMOrchestratorServiceV2(db_session)
    resultat = await service._get_salesforce_metadata(execution_id=1, project=projet)

    org_info = (resultat.get("full_metadata") or {}).get("org_info", resultat.get("org_info", {}))
    charge = json.dumps(resultat, default=str)
    for secret in ("accessToken", "refreshToken", "sfdxAuthUrl", "5Aep861"):
        assert secret not in charge, (
            f"{secret} est present dans les metadonnees rendues : il finira "
            f"dans un livrable puis dans un prompt (SEC-15). Extrait : "
            f"{charge[:300]}"
        )
    assert org_info, "toutes les informations d'org ont ete perdues"


@pytest.mark.asyncio
async def test_les_champs_utiles_restent(db_session, projet, monkeypatch):
    """Controle negatif : filtrer ne veut pas dire tout jeter — l'analyse
    d'architecture a besoin de savoir de quelle org il s'agit."""
    async def _sfdx(args, timeout=30):
        return _resultat_sfdx(args)

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_sfdx_async", staticmethod(_sfdx))
    _org_configuree(monkeypatch)

    service = PMOrchestratorServiceV2(db_session)
    resultat = await service._get_salesforce_metadata(execution_id=1, project=projet)
    charge = json.dumps(resultat, default=str)
    assert "00D000000000001EAA" in charge or "example.my.salesforce.com" in charge, (
        "l'org n'est plus identifiable du tout"
    )
