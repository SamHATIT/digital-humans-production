"""
LOT-E bis — org Salesforce par défaut et jetons en clair (audit croisé 21/08/2026).

  * gem:CONF-01 — `salesforce_config.py` portait un alias, un username et un
    org id RÉELS comme défauts de dataclass, et `from_project()` y retombait
    champ par champ. Un projet mal configuré travaillait donc contre la mauvaise
    org, en silence.
  * cla:SEC-03 — `jordan_deploy_service.py` acceptait un jeton Git stocké en
    clair (`ghp_...`) et le passait à git. Tant que ce repli vivait, la colonne
    `encrypted_value` gardait des secrets en clair et toute migration était à
    refaire.

Aucun de ces tests n'a besoin de base de données.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.salesforce_config import (
    IDENTITY_FIELDS,
    SalesforceConfig,
    SalesforceConfigError,
    get_sfdx_command,
    salesforce_config,
)

BACKEND_ROOT = Path(__file__).resolve().parent.parent

# Fragments of the real org identity that used to be committed here.
LEAKED_ORG_MARKERS = ("@agentforce.com", "00Dfj", "orgfarm-", "digital-humans-dev")


def _unconfigured(monkeypatch):
    """Force an environment with no default org."""
    import app.salesforce_config as mod

    for name in ("SF_ORG_ALIAS", "SF_USERNAME", "SF_ORG_ID", "SF_INSTANCE_URL"):
        monkeypatch.setattr(mod.settings, name, None, raising=False)


# ------------------------------------------------------- gem:CONF-01 : org

def test_no_real_org_identity_in_source():
    """gem:CONF-01 — the committed org identity is gone from the module."""
    source = (BACKEND_ROOT / "app/salesforce_config.py").read_text()
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    # The docstring names the removed values generically; a real address or org
    # id must not survive anywhere in the file.
    for marker in LEAKED_ORG_MARKERS:
        assert marker not in code, f"salesforce_config.py contient encore {marker!r}"


def test_identity_defaults_to_none_when_unconfigured(monkeypatch):
    """gem:CONF-01 — no identity default at all."""
    _unconfigured(monkeypatch)
    config = SalesforceConfig()
    assert config.missing_identity() == list(IDENTITY_FIELDS)
    assert config.is_configured() is False


def test_module_import_never_raises():
    """
    The singleton is built at import time by agent_executor,
    pm_orchestrator_service_v2 and agent_tester. A raising constructor would
    stop the backend from booting, so the failure must come at use time.
    """
    assert isinstance(salesforce_config, SalesforceConfig)


def test_require_raises_when_unconfigured(monkeypatch):
    _unconfigured(monkeypatch)
    config = SalesforceConfig()
    with pytest.raises(SalesforceConfigError) as exc:
        config.require()
    message = str(exc.value)
    assert "org_alias" in message
    assert "Refusing to fall back" in message


def test_require_accepts_a_configured_org(monkeypatch):
    _unconfigured(monkeypatch)
    config = SalesforceConfig(
        org_alias="fixture-org",
        username="fixture@example.invalid",
        org_id="00D000000000000AAA",
        instance_url="https://fixture.my.salesforce.com",
    )
    assert config.require() is config
    assert config.is_configured()


def test_get_sfdx_command_refuses_an_unconfigured_org(monkeypatch):
    """Never emit `--target-org None`, never silently target the dev org."""
    import app.salesforce_config as mod

    _unconfigured(monkeypatch)
    monkeypatch.setattr(mod, "salesforce_config", SalesforceConfig())
    with pytest.raises(SalesforceConfigError):
        get_sfdx_command("org display")


def test_from_project_does_not_borrow_the_default_org(monkeypatch):
    """
    gem:CONF-01, the core of it — a project that supplies only part of its
    identity must NOT have the rest filled in from the default org.
    """
    import app.salesforce_config as mod

    monkeypatch.setattr(mod.settings, "SF_ORG_ALIAS", "default-org", raising=False)
    monkeypatch.setattr(mod.settings, "SF_USERNAME", "default@example.invalid", raising=False)
    monkeypatch.setattr(mod.settings, "SF_ORG_ID", "00DDEFAULT00000AAA", raising=False)
    monkeypatch.setattr(
        mod.settings, "SF_INSTANCE_URL", "https://default.my.salesforce.com", raising=False
    )

    project = SimpleNamespace(
        id=42,
        sf_instance_url="https://client.my.salesforce.com",
        sf_username=None,   # incomplet
        sf_org_id=None,     # incomplet
    )
    config = SalesforceConfig.from_project(project)

    assert config.instance_url == "https://client.my.salesforce.com"
    # Rien n'est emprunté à l'org par défaut.
    assert config.username is None
    assert config.org_id is None
    assert config.org_alias is None


def test_from_project_refuses_a_project_without_an_org():
    project = SimpleNamespace(id=43, sf_instance_url=None, sf_username=None, sf_org_id=None)
    with pytest.raises(SalesforceConfigError) as exc:
        SalesforceConfig.from_project(project)
    assert "refusing to fall back" in str(exc.value).lower()


def test_from_project_keeps_a_fully_configured_project():
    project = SimpleNamespace(
        id=44,
        sf_instance_url="https://client.my.salesforce.com",
        sf_username="client@example.invalid",
        sf_org_id="00DCLIENT00000AAA",
    )
    config = SalesforceConfig.from_project(project)
    assert config.is_configured()
    assert config.org_alias == "00DCLIENT00000AAA"
    assert config.username == "client@example.invalid"


# --------------------------------------------- cla:SEC-03 : jetons en clair

def test_plaintext_token_detection():
    from app.utils.encryption import looks_like_plaintext_token

    for prefix in ("ghp_", "github_pat_", "glpat-", "gho_", "ghs_"):
        assert looks_like_plaintext_token(prefix + "X" * 20)
    # Un blob Fernet encodé n'est pas du clair.
    assert not looks_like_plaintext_token("Z0FBQUFBQnFpa2s...")
    assert not looks_like_plaintext_token("")
    assert not looks_like_plaintext_token(None)


def test_jordan_no_longer_accepts_a_plaintext_token():
    """
    cla:SEC-03 — le repli `git_token = brut` est supprimé. Vérifié sur la
    source : le module importe des modèles lourds, on ne l'instancie pas ici.
    """
    source = (BACKEND_ROOT / "app/services/jordan_deploy_service.py").read_text()
    tree = ast.parse(source)

    # Aucune affectation de la valeur brute au jeton.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "git_token" in targets and isinstance(node.value, ast.Name):
                assert node.value.id != "brut", (
                    "jordan_deploy_service assigne encore le jeton brut a git_token"
                )

    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    assert "looks_like_plaintext_token" in code, "le garde-fou doit etre present"
    assert 'startswith(("ghp_"' not in code, "l'ancien repli est encore la"
    # Le message doit nommer la commande de migration.
    assert "rotate_encryption_key.py" in code
    # Le nom de la variable d'environnement doit etre le bon.
    assert "CREDENTIAL_ENCRYPTION_KEY" not in code.replace("CREDENTIALS_ENCRYPTION_KEY", "")


def test_prefixes_have_a_single_definition():
    """Le script de rotation et Jordan doivent partager la meme liste."""
    from app.utils import encryption

    script = (BACKEND_ROOT / "scripts/rotate_encryption_key.py").read_text()
    assert "PLAINTEXT_TOKEN_PREFIXES = (" not in script, (
        "le script redefinit la liste au lieu de l'importer"
    )
    assert "looks_like_plaintext_token" in script
    assert encryption.PLAINTEXT_TOKEN_PREFIXES
