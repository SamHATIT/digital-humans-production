"""Reouverture encadree des ecritures Salesforce (05/11/2026).

Avant : `ensure_salesforce_write_allowed` exigeait une preuve d'org que
personne ne fournissait (aucun appelant ne la lisait), et une Developer
Edition repond `IsSandbox = false` comme une production. Resultat : aucune
ecriture possible, nulle part — y compris vers l'org de test `sandbox-build`.

Desormais : la garde lit elle-meme la preuve DANS l'org (`Organization`),
et accepte une Developer Edition seulement si son identifiant figure dans
`DH_SALESFORCE_TEST_ORG_IDS`. Le CRM de Sam (Developer Edition, en service)
n'y figure pas : il reste refuse.
"""
import json
from types import SimpleNamespace

import pytest

from app.utils import build_guard

ORG_TEST = "00DgK00000VvwqDUAR"      # sandbox-build
ORG_CRM = "00Dfj00000VIwy9EAD"       # CRM de Sam — Developer Edition en service


def _faux_cli(org_id, is_sandbox, appels):
    def executer(cmd, **kwargs):
        appels.append(cmd)
        return SimpleNamespace(stdout=json.dumps(
            {"status": 0, "result": {"records": [{"Id": org_id, "IsSandbox": is_sandbox}]}}
        ))
    return executer


@pytest.fixture
def ecritures_ouvertes(monkeypatch):
    monkeypatch.setenv(build_guard.VARIABLE_ECRITURES_SALESFORCE, "true")
    monkeypatch.setenv(build_guard.VARIABLE_ORGS_DE_TEST, ORG_TEST[:15])


def test_une_org_de_test_declaree_est_acceptee(ecritures_ouvertes):
    build_guard.ensure_salesforce_write_allowed(
        "sandbox-build", preuve_org={"organizationId": ORG_TEST, "isSandbox": False}
    )


def test_controle_negatif_le_crm_non_declare_reste_refuse(ecritures_ouvertes):
    with pytest.raises(build_guard.SalesforceOrgNonVerifiee):
        build_guard.ensure_salesforce_write_allowed(
            "Production", preuve_org={"organizationId": ORG_CRM, "isSandbox": False}
        )


def test_sans_preuve_fournie_la_garde_la_lit_dans_l_org(ecritures_ouvertes, monkeypatch):
    """Rouge avant le 05/11 : aucun appelant ne fournissait la preuve, et la
    garde ne la cherchait pas — toute ecriture etait refusee."""
    lues = []

    def lire(cible):
        lues.append(cible)
        return {"organizationId": ORG_TEST, "isSandbox": False}

    monkeypatch.setattr(build_guard, "obtenir_preuve_org", lire)
    build_guard.ensure_salesforce_write_allowed("sandbox-build")
    assert lues == ["sandbox-build"]


def test_la_preuve_est_lue_par_une_requete_authentifiee_sur_l_org():
    appels = []
    preuve = build_guard.obtenir_preuve_org("sandbox-build", executer=_faux_cli(ORG_TEST, False, appels))
    assert preuve == {"organizationId": ORG_TEST, "isSandbox": False}
    assert appels and "--target-org" in appels[0] and "sandbox-build" in appels[0]
    assert build_guard.REQUETE_PREUVE_ORG in appels[0]


def test_une_preuve_illisible_donne_none_donc_un_refus(ecritures_ouvertes, monkeypatch):
    def casse(cmd, **kwargs):
        return SimpleNamespace(stdout='{"name":"NamedOrgNotFoundError"}')
    assert build_guard.obtenir_preuve_org("inconnue", executer=casse) is None
    monkeypatch.setattr(build_guard, "obtenir_preuve_org", lambda cible: None)
    with pytest.raises(build_guard.SalesforceOrgNonVerifiee):
        build_guard.ensure_salesforce_write_allowed("inconnue")


def test_une_sandbox_reelle_reste_acceptee_sans_declaration(monkeypatch):
    monkeypatch.setenv(build_guard.VARIABLE_ECRITURES_SALESFORCE, "true")
    monkeypatch.delenv(build_guard.VARIABLE_ORGS_DE_TEST, raising=False)
    build_guard.ensure_salesforce_write_allowed(
        "client--uat", preuve_org={"organizationId": "00D000000000001EAA", "isSandbox": True}
    )


def test_une_declaration_mal_formee_est_ignoree_et_signalee(monkeypatch, caplog):
    monkeypatch.setenv(build_guard.VARIABLE_ORGS_DE_TEST, "sandbox-build, " + ORG_TEST)
    assert build_guard._orgs_de_test_declarees() == frozenset({ORG_TEST[:15]})
    assert "sandbox-build" in caplog.text


def test_les_ecritures_restent_fermees_par_defaut(monkeypatch):
    monkeypatch.delenv(build_guard.VARIABLE_ECRITURES_SALESFORCE, raising=False)
    monkeypatch.setenv(build_guard.VARIABLE_ORGS_DE_TEST, ORG_TEST)
    with pytest.raises(build_guard.SalesforceWritesDisabled):
        build_guard.ensure_salesforce_write_allowed(
            "sandbox-build", preuve_org={"organizationId": ORG_TEST, "isSandbox": False}
        )
