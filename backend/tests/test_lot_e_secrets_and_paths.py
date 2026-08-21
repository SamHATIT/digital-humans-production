"""
LOT-E regression tests — secrets and configuration (audit croisé 21/08/2026).

Covers:
  * P2  / cla:INTEG-03 / kim:P2  — no machine-specific absolute path left as a
    default in `app/config.py`, `sf_admin_service.py`, `rag_service.py`.
  * P8  / cla:SEC-03  / kim:SEC-06 — the re-encryption script exists and the
    encryption module exposes what it needs; the SECRET_KEY-derived fallback is
    refused in production.
  * P12 / gem:CONF-01 shape        — one and only one .env is authoritative:
    `rag_service.get_openai_client` no longer reads a second .env file.

These are static/behavioural checks; none of them needs a database.
"""
import ast
from pathlib import Path

import pytest

from app.config import Settings, settings

BACKEND_ROOT = Path(__file__).resolve().parent.parent

# Absolute prefixes that pinned the code to one particular machine.
FORBIDDEN_PREFIXES = ("/opt/digital-humans", "/var/lib/digital-humans", "/root/workspace")


# ---------------------------------------------------------------- P2 : paths

@pytest.mark.parametrize(
    "attr",
    [
        "PROJECT_ROOT",
        "BACKEND_ROOT",
        "OUTPUT_DIR",
        "METADATA_DIR",
        "CHROMA_PATH",
        "LLM_CONFIG_PATH",
        "DELIVERABLES_DIR",
        "SFDX_PROJECT_PATH",
        "FORCE_APP_PATH",
        "AGENTS_DIR",
    ],
)
def test_no_machine_specific_default_path(attr):
    """P2 — every configured path is derived from the checkout, not from /opt."""
    value = str(getattr(settings, attr))
    assert not value.startswith(FORBIDDEN_PREFIXES), (
        f"settings.{attr} still defaults to a machine-specific absolute path: {value}"
    )


def test_paths_are_rooted_in_the_checkout():
    """P2 — defaults must live under PROJECT_ROOT so a fresh clone just runs."""
    root = settings.PROJECT_ROOT.resolve()
    for attr in ("BACKEND_ROOT", "OUTPUT_DIR", "CHROMA_PATH", "DELIVERABLES_DIR"):
        value = Path(str(getattr(settings, attr))).resolve()
        assert value.is_relative_to(root), f"settings.{attr} ({value}) escapes PROJECT_ROOT ({root})"


@pytest.mark.parametrize(
    "relpath",
    ["app/config.py", "app/services/sf_admin_service.py", "app/utils/encryption.py"],
)
def test_no_hardcoded_absolute_path_in_source(relpath):
    """P2 — the literals themselves are gone, not merely unused."""
    source = (BACKEND_ROOT / relpath).read_text()
    # Strip comments: an explanatory mention of the old path is not a defect.
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    for prefix in FORBIDDEN_PREFIXES:
        assert prefix not in code, f"{relpath} still contains the hardcoded path {prefix}"


def test_sf_admin_persist_dir_defaults_to_settings():
    """kim:P2 — sf_admin_service no longer falls back to /var/lib/digital-humans."""
    from app.services.sf_admin_service import SFAdminService

    service = SFAdminService(target_org="lot-e-fixture")
    assert service.persist_dir == str(settings.DELIVERABLES_DIR)
    assert not service.persist_dir.startswith(FORBIDDEN_PREFIXES)


# ------------------------------------------------- P12 : a single .env wins

def _function_body(relpath: str, func_name: str) -> str:
    """
    Return a function's source, comments and docstring stripped.

    Parsed rather than imported: rag_service pulls in chromadb, which is not
    installed in every environment, and this assertion must hold regardless.
    """
    tree = ast.parse((BACKEND_ROOT / relpath).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                body = body[1:]  # drop the docstring
            return "\n".join(ast.unparse(stmt) for stmt in body)
    raise AssertionError(f"{func_name} not found in {relpath}")


def test_rag_service_does_not_read_a_second_env_file():
    """
    P12 — `get_openai_client` used to open /opt/digital-humans/rag/.env and
    parse it line by line whenever OPENAI_API_KEY was missing. Two OpenAI keys
    could coexist with no way to tell which one was live.
    """
    code = _function_body("app/services/rag_service.py", "get_openai_client")

    assert "open(" not in code, "get_openai_client still opens a file"
    assert "RAG_ENV_PATH" not in code
    assert "OPENAI_API_KEY=" not in code, "still parsing a dotenv line by line"
    assert "settings.OPENAI_API_KEY" in code, "the single .env must be the source"
    assert "return None" in code, "a missing key must fail explicitly"


def test_rag_env_path_setting_is_gone():
    """P12 — the second .env has no configuration surface left at all."""
    assert not hasattr(settings, "RAG_ENV_PATH")


def test_get_openai_client_returns_none_without_key(monkeypatch):
    """P12 — a missing key is an explicit failure, never a silent fallback."""
    pytest.importorskip("chromadb", reason="rag_service imports chromadb at module level")
    from app.services import rag_service

    monkeypatch.setattr(rag_service, "_openai_client", None)
    monkeypatch.setattr(rag_service.settings, "OPENAI_API_KEY", "")
    assert rag_service.get_openai_client() is None


# ------------------------------------------ P8 / SEC-06 : key and rotation

def test_rotation_script_exists_and_is_executable_code():
    """
    P8 — the docstring of encryption.py used to promise this script with a
    'TODO: create migration script'. A written procedure is not a capability.
    """
    script = BACKEND_ROOT / "scripts" / "rotate_encryption_key.py"
    assert script.exists(), "scripts/rotate_encryption_key.py is missing"
    compile(script.read_text(), str(script), "exec")


def test_encryption_docstring_no_longer_admits_a_missing_script():
    from app.utils import encryption

    doc = encryption.__doc__ or ""
    assert "create migration script" not in doc, (
        "encryption.py still admits the rotation script does not exist"
    )
    assert "rotate_encryption_key.py" in doc, "the procedure must point at the real script"


def test_encryption_reads_keys_from_settings_not_the_process_environment():
    """
    One .env is authoritative. Reading the process environment directly meant a
    key present in backend/.env but never exported was invisible here, silently
    falling through to the SECRET_KEY-derived key.

    Checked structurally rather than by grep so the module docstring, which
    explains the old behaviour, does not trip the assertion.
    """
    tree = ast.parse((BACKEND_ROOT / "app/utils/encryption.py").read_text())
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "os" not in imported, (
        "encryption.py must read keys through app.config.settings, not os.environ"
    )
    assert "app" in imported, "encryption.py must import app.config"


def test_encryption_exposes_key_builders_for_rotation():
    """The rotation script needs old and new keys side by side."""
    from app.utils import encryption

    assert callable(encryption.build_fernet)
    assert callable(encryption.derive_fernet_from_secret_key)


def test_round_trip_with_an_explicit_key():
    from app.utils.encryption import build_fernet, generate_encryption_key
    import base64

    fernet = build_fernet(generate_encryption_key())
    secret = "FAKE-value-for-the-test-only"
    wrapped = base64.urlsafe_b64encode(fernet.encrypt(secret.encode())).decode()
    assert fernet.decrypt(base64.urlsafe_b64decode(wrapped.encode())).decode() == secret


def test_production_requires_a_dedicated_encryption_key(monkeypatch):
    """
    kim:SEC-06 — in production, deriving the credentials key from SECRET_KEY is
    refused. Combined with SECRET_KEY auto-generation it made every stored
    credential undecryptable after a restart.
    """
    monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
    with pytest.raises(Exception) as exc:
        Settings(
            DEBUG=False,
            SECRET_KEY="a" * 40,
            CREDENTIALS_ENCRYPTION_KEY=None,
            _env_file=None,
        )
    message = str(exc.value)
    assert "CREDENTIALS_ENCRYPTION_KEY" in message
    assert "rotate_encryption_key.py" in message, "the error must name the way out"


def test_debug_still_allows_the_derived_key(monkeypatch):
    """The escape hatch stays open for local development only."""
    monkeypatch.delenv("CREDENTIALS_ENCRYPTION_KEY", raising=False)
    cfg = Settings(DEBUG=True, SECRET_KEY="b" * 40, CREDENTIALS_ENCRYPTION_KEY=None, _env_file=None)
    assert cfg.CREDENTIALS_ENCRYPTION_KEY is None
