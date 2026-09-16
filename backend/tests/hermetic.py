"""
Bootstrap hermétique de la suite de tests.

VAGUE 0 / AS-02 — constat OPS-05 de l'audit Astra du 06/09/2026.

Le défaut : `conftest.py` (vague 2, lot 1c) protégeait **sa propre** URL de
base, mais `app.main` chargeait ensuite `backend/.env` ; `settings.DATABASE_URL`,
`app.database.engine` et trois modules lisant `os.getenv("DATABASE_URL")`
restaient sur la base réelle. Redis, Chroma, les répertoires de sortie et les
clés d'API de `.env` étaient lus tels quels, et rien n'empêchait un test de
sortir sur le réseau. Dix-sept fichiers de tests importaient l'engine réel.

Ce module s'exécute **avant tout import applicatif** (voir `conftest.py`) et
impose, dans l'ordre :

1. aucun secret réel dans l'environnement du processus (refus sinon) ;
2. `TEST_DATABASE_URL` obligatoire — jamais de repli sur `DATABASE_URL` — et
   passée par la garde de `db_guard` ;
3. une base **par exécution**, nommée d'après un identifiant de run, créée par
   la session et détruite à la fin (`create_run_database` / `drop_run_database`) ;
4. `DATABASE_URL` et `TEST_DATABASE_URL` de l'environnement remplacées par
   cette base, pour que `settings`, l'engine et les lecteurs directs voient la
   même chose ;
5. `backend/.env.test` comme seul fichier d'environnement (`DH_ENV_FILE`) ;
   `backend/.env` n'est jamais lu ;
6. Redis sur une base dédiée et une file ARQ `test-<run_id>` ; Chroma, sorties,
   livrables, uploads et espace SFDX sous un répertoire temporaire de session ;
7. un garde réseau : toute connexion TCP hors boucle locale est refusée et
   comptée, et `psycopg2.connect` refuse une base connue comme réelle.

Chaque refus dit quoi exporter. Aucune valeur inconnue n'est devinée.
"""
from __future__ import annotations

import atexit
import dataclasses
import ipaddress
import logging
import os
import re
import shutil
import socket
import tempfile
import uuid
from pathlib import Path
from typing import Iterable, List, Optional

from tests.db_guard import assert_not_production_database

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ENV_TEST_FILE = BACKEND_ROOT / ".env.test"

#: Préfixe qui rend une valeur de secret manifestement factice.
FAKE_PREFIX = "dh-test-fake-"

#: Variables qui portent un secret ou un jeton réel quelque part dans le code
#: (`grep -rhoE "(KEY|TOKEN|SECRET|PASSWORD)"` sur app/, agents/, tools/,
#: scripts/ le 16/09). Chacune DOIT être définie dans `.env.test`, vide ou
#: préfixée par FAKE_PREFIX. Une valeur pré-existante différente dans
#: l'environnement fait refuser la session.
SECRET_VARS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PUBLISHABLE_KEY",
    "GHOST_ADMIN_KEY",
    "GHOST_CONTENT_KEY",
    "GIT_TOKEN",
    "GITTOKEN",
    "GITHUB_TOKEN",
    "GIT_SSH_KEY",
    "SALESFORCE_TOKEN",
    "SALESFORCE_REFRESH_TOKEN",
    "SMTP_PASSWORD",
    "JOURNAL_WEBHOOK_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "CHAT_IP_SALT",
    "SECRET_KEY",
    "CREDENTIALS_ENCRYPTION_KEY",
)

#: Clés de `.env.test` que l'exécutant peut poser lui-même dans son shell
#: (adresse de Redis, dérogations explicites). Tout le reste vient du fichier.
RUNNER_MAY_OVERRIDE = frozenset({
    "DH_REDIS_HOST",
    "DH_REDIS_PORT",
    "DH_TEST_ALLOW_HOSTS",
    "DH_TEST_KEEP",
})

#: Bases Redis réservées à la production (DB 0 : cache, DB 1 : file ARQ).
PRODUCTION_REDIS_DBS = frozenset({0, 1})

#: Longueur maximale d'un identifiant PostgreSQL (NAMEDATALEN - 1).
_PG_NAME_MAX = 63

_RUN_ID_ALLOWED = re.compile(r"[^a-z0-9]")


class HermeticEnvironmentError(RuntimeError):
    """L'environnement de test ne peut pas être rendu hermétique : on refuse."""


class OutboundNetworkBlocked(RuntimeError):
    """Une connexion TCP hors boucle locale a été tentée pendant un test."""


@dataclasses.dataclass(frozen=True)
class HermeticContext:
    run_id: str
    base_database_url: str
    base_database_name: str
    database_url: str
    database_name: str
    tmp_dir: str
    redis_db: int
    queue_name: str
    env_file: str
    replaced_database_url_name: Optional[str]
    allowed_hosts: tuple


_CONTEXT: Optional[HermeticContext] = None
_DATABASE_CREATED = False
_CLEANED_UP = False
#: Valeurs factices effectivement posées pour SECRET_VARS (lues dans .env.test).
FAKE_SECRETS: dict = {}
_blocked_attempts: List[str] = []
_original_socket_connect = socket.socket.connect
_original_socket_connect_ex = socket.socket.connect_ex
_original_psycopg2_connect = None


def current() -> Optional[HermeticContext]:
    """Le contexte posé par `bootstrap_hermetic_environment`, ou None."""
    return _CONTEXT


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

def looks_like_a_real_secret(name: str, value: Optional[str]) -> bool:
    """Vrai si `value` n'est ni vide ni manifestement factice.

    On ne reconnaît pas les vraies clés à leur forme (la prochaine aura une
    autre forme) : on ne reconnaît que les fausses, à leur préfixe.
    """
    if value is None or value == "":
        return False
    return not value.startswith(FAKE_PREFIX)


def _read_env_test() -> dict:
    if not ENV_TEST_FILE.is_file():
        raise HermeticEnvironmentError(
            f"Refus de lancer la suite de tests : {ENV_TEST_FILE} est absent.\n"
            f"Ce fichier est versionné et ne contient aucun secret ; "
            f"restaurez-le avec `git checkout -- backend/.env.test`."
        )
    from dotenv import dotenv_values

    values = {k: (v if v is not None else "") for k, v in dotenv_values(ENV_TEST_FILE).items()}
    for forbidden in ("DATABASE_URL", "TEST_DATABASE_URL", "DH_ARQ_QUEUE_NAME"):
        if forbidden in values:
            raise HermeticEnvironmentError(
                f"{ENV_TEST_FILE} ne doit pas définir {forbidden} : cette valeur "
                f"est dérivée de TEST_DATABASE_URL et de l'identifiant de run."
            )
    missing = [name for name in SECRET_VARS if name not in values]
    if missing:
        raise HermeticEnvironmentError(
            f"{ENV_TEST_FILE} doit définir (vide ou factice) : {', '.join(missing)}"
        )
    for name in SECRET_VARS:
        if looks_like_a_real_secret(name, values[name]):
            raise HermeticEnvironmentError(
                f"{ENV_TEST_FILE} porte pour {name} une valeur qui n'est ni vide "
                f"ni préfixée par {FAKE_PREFIX!r} : refus."
            )
    return values


def _refuse_real_secrets(fakes: dict) -> None:
    offenders = [
        name
        for name in SECRET_VARS
        if os.environ.get(name) not in (None, "", fakes[name])
        and looks_like_a_real_secret(name, os.environ.get(name))
    ]
    if offenders:
        names = ", ".join(offenders)
        raise HermeticEnvironmentError(
            f"Refus de lancer la suite de tests : l'environnement porte une valeur "
            f"réelle pour {names}.\n"
            f"La suite n'accepte aucune clé venant de l'extérieur : les valeurs "
            f"factices viennent de backend/.env.test.\n"
            f"Relancez sans ces variables, par exemple :\n"
            f"    env {' '.join('-u ' + n for n in offenders)} python -m pytest -q\n"
        )


# ---------------------------------------------------------------------------
# Base de données par exécution
# ---------------------------------------------------------------------------

def _database_name(url: str) -> str:
    from sqlalchemy.engine import make_url

    return make_url(url).database or ""


def sanitize_run_id(raw: str) -> str:
    cleaned = _RUN_ID_ALLOWED.sub("_", raw.strip().lower()).strip("_")
    if not cleaned:
        raise HermeticEnvironmentError(
            f"DH_TEST_RUN_ID={raw!r} ne contient aucun caractère utilisable "
            f"([a-z0-9], le reste devient '_')."
        )
    return cleaned


def generate_run_id() -> str:
    return f"{os.getpid()}{uuid.uuid4().hex[:6]}"


def database_name_for(base_name: str, run_id: str) -> str:
    name = f"{base_name}_{run_id}"
    if len(name) > _PG_NAME_MAX:
        raise HermeticEnvironmentError(
            f"le nom de base dérivé {name!r} dépasse {_PG_NAME_MAX} caractères : "
            f"raccourcissez le nom de base de TEST_DATABASE_URL ou DH_TEST_RUN_ID."
        )
    return name


def _resolve_base_database_url() -> str:
    base = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not base:
        ignored = os.environ.get("DATABASE_URL", "").strip()
        detail = (
            f"DATABASE_URL est posée (base {_database_name(ignored)!r}) mais la "
            f"suite ne se replie JAMAIS dessus : c'est ce repli qui pointait la "
            f"base réelle (OPS-05).\n"
            if ignored
            else "Ni TEST_DATABASE_URL ni DATABASE_URL ne sont posées.\n"
        )
        raise HermeticEnvironmentError(
            "Refus de lancer la suite de tests : TEST_DATABASE_URL est absente.\n"
            + detail
            + "Posez un gabarit de base jetable (la session en dérive une base par "
            "exécution, la crée et la détruit) :\n"
            "    export TEST_DATABASE_URL="
            "postgresql://dh_test:dh_test@127.0.0.1:5432/digital_humans_test\n"
            "Le rôle doit avoir CREATEDB. Voir backend/tests/README.md.\n"
        )
    assert_not_production_database(base)
    return base


def _maintenance_connection(base_url: str):
    """Connexion autocommit à la base `postgres` du même serveur, avec les
    mêmes identifiants. C'est par elle que la session crée et détruit sa base."""
    import psycopg2
    from sqlalchemy.engine import make_url

    url = make_url(base_url)
    connect = _original_psycopg2_connect or psycopg2.connect
    try:
        conn = connect(
            host=url.host or "127.0.0.1",
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            dbname="postgres",
            connect_timeout=10,
        )
    except Exception as exc:  # noqa: BLE001 — on veut le message d'origine
        raise HermeticEnvironmentError(
            f"Impossible de joindre le serveur PostgreSQL de TEST_DATABASE_URL "
            f"(base de maintenance 'postgres') : {type(exc).__name__}: {exc}\n"
            f"Le serveur doit être démarré et le rôle doit pouvoir s'y connecter."
        ) from exc
    conn.autocommit = True
    return conn


def list_databases(base_url: str) -> set:
    conn = _maintenance_connection(base_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT datname FROM pg_database WHERE NOT datistemplate")
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()


def create_run_database(ctx: HermeticContext) -> None:
    """Crée la base de la session. Une base homonyme (run précédent interrompu
    avec le même DH_TEST_RUN_ID) est détruite d'abord : elle est à nous."""
    global _DATABASE_CREATED
    assert_not_production_database(ctx.database_url)
    conn = _maintenance_connection(ctx.base_database_url)
    try:
        with conn.cursor() as cur:
            _drop(cur, ctx.database_name)
            try:
                cur.execute(f'CREATE DATABASE "{ctx.database_name}"')
                _DATABASE_CREATED = True
            except Exception as exc:  # noqa: BLE001
                raise HermeticEnvironmentError(
                    f"CREATE DATABASE {ctx.database_name} a échoué : "
                    f"{type(exc).__name__}: {exc}\n"
                    f"Le rôle de TEST_DATABASE_URL doit avoir le droit CREATEDB :\n"
                    f"    ALTER ROLE <role> CREATEDB;\n"
                ) from exc
    finally:
        conn.close()


def _drop(cur, name: str) -> None:
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = %s AND pid <> pg_backend_pid()",
        (name,),
    )
    cur.execute(f'DROP DATABASE IF EXISTS "{name}"')


def drop_run_database(ctx: HermeticContext) -> None:
    conn = _maintenance_connection(ctx.base_database_url)
    try:
        with conn.cursor() as cur:
            _drop(cur, ctx.database_name)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Garde réseau
# ---------------------------------------------------------------------------

def _host_is_allowed(host: str, allowed: Iterable[str]) -> bool:
    if host in allowed:
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _address_is_allowed(sock_family, address, allowed) -> bool:
    if sock_family not in (socket.AF_INET, socket.AF_INET6):
        return True  # AF_UNIX et autres : local par construction
    if not isinstance(address, tuple) or not address:
        return True
    return _host_is_allowed(str(address[0]), allowed)


def _record_and_refuse(address) -> None:
    description = f"{address[0]}:{address[1]}" if isinstance(address, tuple) and len(address) > 1 else repr(address)
    _blocked_attempts.append(description)
    raise OutboundNetworkBlocked(
        f"Connexion réseau sortante refusée pendant les tests : {description}. "
        f"Seule la boucle locale est joignable (DH_TEST_ALLOW_HOSTS pour une "
        f"dérogation explicite et journalisée)."
    )


def install_network_guard(allowed_hosts: Iterable[str]) -> None:
    allowed = frozenset(allowed_hosts)

    def guarded_connect(self, address):
        if not _address_is_allowed(self.family, address, allowed):
            _record_and_refuse(address)
        return _original_socket_connect(self, address)

    def guarded_connect_ex(self, address):
        if not _address_is_allowed(self.family, address, allowed):
            _record_and_refuse(address)
        return _original_socket_connect_ex(self, address)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex

    # psycopg2 (libpq, en C) ne passe pas par socket.socket : on garde l'appel
    # Python qui le précède. Une base réelle ou un hôte distant sont refusés
    # avant toute connexion.
    global _original_psycopg2_connect
    try:
        import psycopg2
    except ImportError:  # pragma: no cover — psycopg2 est dans requirements.txt
        return
    if _original_psycopg2_connect is None:
        _original_psycopg2_connect = psycopg2.connect

    def guarded_psycopg2_connect(dsn=None, connection_factory=None, cursor_factory=None, **kwargs):
        host, dbname = _psycopg2_target(dsn, kwargs)
        if dbname:
            assert_not_production_database(f"postgresql://{host or '127.0.0.1'}/{dbname}")
        if host and not _host_is_allowed(host, allowed):
            _record_and_refuse((host, kwargs.get("port", "5432")))
        return _original_psycopg2_connect(
            dsn, connection_factory=connection_factory, cursor_factory=cursor_factory, **kwargs
        )

    psycopg2.connect = guarded_psycopg2_connect


def _psycopg2_target(dsn, kwargs):
    host = kwargs.get("host")
    dbname = kwargs.get("dbname") or kwargs.get("database")
    if dsn:
        if "://" in dsn:
            from sqlalchemy.engine import make_url

            url = make_url(dsn)
            host = host or url.host
            dbname = dbname or url.database
        else:
            for key, value in re.findall(r"(\w+)\s*=\s*'?([^\s']+)'?", dsn):
                if key == "host":
                    host = host or value
                elif key == "dbname":
                    dbname = dbname or value
    return host, dbname


def blocked_attempts_count() -> int:
    return len(_blocked_attempts)


def blocked_attempts_since(index: int) -> List[str]:
    return list(_blocked_attempts[index:])


def consume_blocked_attempts() -> List[str]:
    """Rend et oublie les tentatives enregistrées : pour un test qui a
    volontairement provoqué un refus et ne doit pas échouer au démontage."""
    attempts = list(_blocked_attempts)
    _blocked_attempts.clear()
    return attempts


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def bootstrap_hermetic_environment() -> HermeticContext:
    """Idempotent : le second appel rend le contexte du premier."""
    global _CONTEXT
    if _CONTEXT is not None:
        return _CONTEXT

    from sqlalchemy.engine import make_url

    fakes = {name: value for name, value in _read_env_test().items()}
    _refuse_real_secrets({name: fakes[name] for name in SECRET_VARS})

    base_url = _resolve_base_database_url()
    base_name = _database_name(base_url)
    raw_run_id = os.environ.get("DH_TEST_RUN_ID", "").strip()
    run_id = sanitize_run_id(raw_run_id) if raw_run_id else generate_run_id()
    database_name = database_name_for(base_name, run_id)
    run_url = make_url(base_url).set(database=database_name).render_as_string(hide_password=False)
    assert_not_production_database(run_url)

    replaced = os.environ.get("DATABASE_URL", "").strip()
    replaced_name = _database_name(replaced) if replaced else None

    # 1. Base : une seule source, dans l'environnement, avant tout import.
    os.environ["DH_TEST_BASE_DATABASE_URL"] = base_url
    os.environ["DH_TEST_RUN_ID"] = run_id
    os.environ["TEST_DATABASE_URL"] = run_url
    os.environ["DATABASE_URL"] = run_url

    # 2. Fichier d'environnement : .env.test, et lui seul.
    os.environ["DH_ENV_FILE"] = str(ENV_TEST_FILE)
    for key, value in fakes.items():
        if key in RUNNER_MAY_OVERRIDE and key in os.environ:
            continue
        if value == "" and key not in SECRET_VARS:
            # Une valeur vide non secrète documente une absence (AUTO_CREATE_SCHEMA,
            # SF_ORG_ALIAS...) : on ne la pose pas, pydantic ne saurait pas la lire.
            os.environ.pop(key, None)
            continue
        os.environ[key] = value
    for name in SECRET_VARS:
        os.environ[name] = fakes[name]
        FAKE_SECRETS[name] = fakes[name]

    # 3. Redis et file ARQ.
    try:
        redis_db = int(os.environ.get("DH_REDIS_DB", ""))
    except ValueError:
        raise HermeticEnvironmentError(
            "DH_REDIS_DB doit être un entier (posé par backend/.env.test)."
        ) from None
    if redis_db in PRODUCTION_REDIS_DBS:
        raise HermeticEnvironmentError(
            f"DH_REDIS_DB={redis_db} est une base Redis de production (0 : cache, "
            f"1 : file ARQ). Choisissez-en une autre dans backend/.env.test."
        )
    queue_name = f"test-{run_id}"
    os.environ["DH_ARQ_QUEUE_NAME"] = queue_name

    # 4. Fichiers : tout sous un répertoire temporaire de session.
    tmp_dir = tempfile.mkdtemp(prefix=f"dh-test-{run_id}-", dir=os.environ.get("DH_TEST_TMP_ROOT") or None)
    tmp = Path(tmp_dir)
    paths = {
        "DH_OUTPUT_DIR": tmp / "outputs",
        "DH_METADATA_DIR": tmp / "metadata",
        "DH_CHROMA_PATH": tmp / "chroma",
        "DH_DELIVERABLES_DIR": tmp / "livrables",
        "UPLOAD_DIR": tmp / "uploads",
        "DH_SFDX_PROJECT_PATH": tmp / "sfdx",
        "DH_FORCE_APP_PATH": tmp / "sfdx" / "force-app" / "main" / "default",
    }
    for key, path in paths.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    os.environ["DH_TEST_TMP"] = tmp_dir

    # 5. Réseau : boucle locale, serveur de base, Redis, dérogations nommées.
    allowed = {"localhost", "127.0.0.1", "::1"}
    for host in (make_url(base_url).host, os.environ.get("DH_REDIS_HOST")):
        if host:
            allowed.add(host)
    extra = [h.strip() for h in os.environ.get("DH_TEST_ALLOW_HOSTS", "").split(",") if h.strip()]
    if extra:
        logger.warning("[hermetic] dérogation réseau explicite DH_TEST_ALLOW_HOSTS=%s", ",".join(extra))
        allowed.update(extra)
    install_network_guard(allowed)

    # Repli de nettoyage : si un import applicatif échoue après ce point,
    # conftest n'est jamais enregistré et `pytest_unconfigure` ne tourne pas.
    atexit.register(_cleanup_at_exit)

    _CONTEXT = HermeticContext(
        run_id=run_id,
        base_database_url=base_url,
        base_database_name=base_name,
        database_url=run_url,
        database_name=database_name,
        tmp_dir=tmp_dir,
        redis_db=redis_db,
        queue_name=queue_name,
        env_file=str(ENV_TEST_FILE),
        replaced_database_url_name=replaced_name,
        allowed_hosts=tuple(sorted(allowed)),
    )
    return _CONTEXT


def verify_application_sources(ctx: HermeticContext) -> None:
    """Après les imports applicatifs : les trois lecteurs voient la base de
    session, sinon la session s'arrête ici (avant tout test)."""
    from sqlalchemy.engine import make_url

    from app.api.routes import blog
    from app.config import settings
    from app.database import engine
    from app.services import document_generator, sds_template_generator

    expected = make_url(ctx.database_url)
    seen = {
        "settings.DATABASE_URL": make_url(settings.DATABASE_URL),
        "app.database.engine": engine.url,
        "app.api.routes.blog.DATABASE_URL": make_url(blog.DATABASE_URL),
        "app.services.document_generator.DATABASE_URL": make_url(document_generator.DATABASE_URL),
        "app.services.sds_template_generator.DATABASE_URL": make_url(sds_template_generator.DATABASE_URL),
    }
    divergent = {k: v for k, v in seen.items() if v != expected}
    if divergent:
        lines = "\n".join(
            f"  {k} -> base {v.database!r} sur {v.host}:{v.port}" for k, v in divergent.items()
        )
        raise HermeticEnvironmentError(
            f"Divergence de base entre le bootstrap et l'application : la session "
            f"de tests s'arrête avant tout test.\n"
            f"  attendu -> base {expected.database!r}\n{lines}\n"
            f"Une valeur a été posée après le bootstrap ou un module lit une autre "
            f"source que l'environnement."
        )


def report_header_lines(ctx: HermeticContext) -> List[str]:
    replaced = (
        f"DATABASE_URL remplacée (était : base {ctx.replaced_database_url_name!r})"
        if ctx.replaced_database_url_name
        else "DATABASE_URL posée par le bootstrap (absente avant)"
    )
    return [
        f"hermetic (vague 0 / AS-02) : run_id={ctx.run_id} base={ctx.database_name} "
        f"(créée par la session, détruite à la fin ; gabarit {ctx.base_database_name})",
        f"hermetic : {replaced} ; env={Path(ctx.env_file).name} ; "
        f"redis db={ctx.redis_db} file={ctx.queue_name} ; tmp={ctx.tmp_dir}",
        f"hermetic : réseau sortant refusé sauf {', '.join(ctx.allowed_hosts)}",
    ]


def teardown(ctx: HermeticContext, engines: Iterable = ()) -> None:
    """Ferme les pools, détruit la base de session et le répertoire temporaire.
    `DH_TEST_KEEP=1` conserve les deux pour inspection, en le disant."""
    global _CLEANED_UP
    for engine in engines:
        try:
            engine.dispose()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[hermetic] dispose() a échoué : %s", exc)
    if _CLEANED_UP:
        return
    _CLEANED_UP = True
    if os.environ.get("DH_TEST_KEEP", "").strip().lower() in {"1", "true", "yes", "on"}:
        logger.warning(
            "[hermetic] DH_TEST_KEEP posé : base %s et répertoire %s conservés",
            ctx.database_name, ctx.tmp_dir,
        )
        return
    if _DATABASE_CREATED:
        drop_run_database(ctx)
    shutil.rmtree(ctx.tmp_dir, ignore_errors=True)


def _cleanup_at_exit() -> None:
    if _CONTEXT is not None and not _CLEANED_UP:
        try:
            teardown(_CONTEXT)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[hermetic] nettoyage de sortie incomplet : %s", exc)
