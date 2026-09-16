"""
VAGUE 0 / AS-02 — environnement de correction sûr (OPS-05, audit Astra du 06/09/2026).

Le défaut, mesuré le 16/09 : `conftest.py` protège **sa propre** URL
(`TEST_DATABASE_URL`, sinon `DATABASE_URL`) mais `app.main` charge ensuite
`backend/.env` et `settings.DATABASE_URL`, `app.database.engine`, ainsi que
trois modules qui lisent `os.getenv("DATABASE_URL")` directement, restent sur
la base réelle. Dix-sept fichiers de tests importent `app.main` ou l'engine.
Redis, Chroma, les répertoires de sortie et les clés d'API réelles de `.env`
sont lus tels quels. Rien n'empêche un test de sortir sur le réseau.

Critère de sortie d'Astra, mot pour mot : « Les suites et agents de
développement ne peuvent joindre aucune base, file, org ou clé de production. »

Chaque test ci-dessous porte une des cinq exigences de la mission
(docs/missions/VAGUE0_AS02_ENVIRONNEMENT_DE_CORRECTION_SUR.md, §3). Les deux
contrôles négatifs lancent un pytest enfant dans un environnement construit
de zéro : une garde qui s'exécute à l'import de `conftest` n'est observable
que depuis l'extérieur de la session qu'elle protège.
"""
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[1]

#: Un fichier de tests rapide, sans base : ce qu'un pytest enfant collecte
#: quand la garde le laisse passer.
PETITE_SUITE = "tests/test_vague2_lot1_garde_database_url.py"

#: Répertoires que la mission interdit d'écrire pendant un test.
CHEMINS_INTERDITS = ("/opt/digital-humans", "/root/workspace")

#: Traces d'une tentative de connexion PostgreSQL. Leur absence dans la sortie
#: d'un pytest refusé prouve que le refus a eu lieu AVANT toute connexion.
TRACES_DE_CONNEXION = (
    "OperationalError",
    "Connection refused",
    "connection refused",
    "could not connect",
    "psycopg2",
)


def _pytest_enfant(env_supplementaire, args=(PETITE_SUITE,), timeout=240, quiet=True):
    """Lance un pytest dans un environnement minimal, construit de zéro.

    Rien n'est hérité du processus courant : ni `DATABASE_URL`, ni
    `TEST_DATABASE_URL`, ni les valeurs factices posées par le bootstrap.
    Seul ce que le test passe explicitement existe dans l'enfant.
    """
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.update(env_supplementaire)
    return subprocess.run(
        [sys.executable, "-m", "pytest", *(["-q"] if quiet else []), "-p", "no:cacheprovider", *args],
        cwd=str(BACKEND),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _sans_commentaires(relpath):
    source = (BACKEND / relpath).read_text(encoding="utf-8")
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


@pytest.fixture(scope="module")
def hermetic():
    """Le module de bootstrap. Son absence est le premier rouge de la mission."""
    from tests import hermetic as module

    return module


@pytest.fixture(scope="module")
def contexte(hermetic):
    ctx = hermetic.current()
    assert ctx is not None, "le bootstrap hermétique n'a pas été exécuté par conftest"
    return ctx


# ---------------------------------------------------------------------------
# Exigence 1 — une seule source pour la base de test, imposée avant tout
# import applicatif
# ---------------------------------------------------------------------------

def test_settings_engine_et_conftest_pointent_la_meme_base():
    """OPS-05 tel quel : trois lecteurs, une seule base autorisée."""
    from app.config import settings
    from app.database import engine
    from tests import conftest

    attendu = make_url(conftest.SQLALCHEMY_DATABASE_URL)
    assert make_url(settings.DATABASE_URL) == attendu, (
        f"settings.DATABASE_URL={settings.DATABASE_URL!r} "
        f"≠ conftest={conftest.SQLALCHEMY_DATABASE_URL!r}"
    )
    assert engine.url == attendu, (
        f"app.database.engine={engine.url.render_as_string(hide_password=False)!r} "
        f"≠ conftest={conftest.SQLALCHEMY_DATABASE_URL!r}"
    )


def test_les_lecteurs_directs_de_DATABASE_URL_voient_la_base_de_test():
    """Trois modules lisent `os.getenv("DATABASE_URL")` à l'import, hors
    `settings` (commit 628cd24 du 16/09). Ils doivent voir la même base."""
    from app.api.routes import blog
    from app.services import document_generator, sds_template_generator
    from tests import conftest

    attendu = make_url(conftest.SQLALCHEMY_DATABASE_URL)
    for module in (blog, document_generator, sds_template_generator):
        assert make_url(module.DATABASE_URL) == attendu, (
            f"{module.__name__}.DATABASE_URL={module.DATABASE_URL!r}"
        )


def test_l_environnement_du_processus_porte_la_base_de_test():
    """`DATABASE_URL` de l'environnement est la base de test elle-même : tout
    code qui la relirait plus tard (sous-processus, `load_dotenv`, `os.getenv`)
    retombe sur la base jetable, jamais sur la réelle."""
    from tests import conftest
    from tests.db_guard import assert_not_production_database

    assert make_url(os.environ["DATABASE_URL"]) == make_url(conftest.SQLALCHEMY_DATABASE_URL)
    assert make_url(os.environ["TEST_DATABASE_URL"]) == make_url(conftest.SQLALCHEMY_DATABASE_URL)
    assert_not_production_database(os.environ["DATABASE_URL"])  # ne lève pas


def test_la_base_de_session_est_jetable_et_reellement_celle_qui_repond(contexte):
    from app.database import engine

    assert contexte.run_id in contexte.database_name
    assert "test" in contexte.database_name.lower()
    assert contexte.database_name != contexte.base_database_name, (
        "la base nommée dans TEST_DATABASE_URL est un gabarit ; la session ne "
        "doit jamais y faire create_all/drop_all"
    )
    assert engine.url.database == contexte.database_name
    with engine.connect() as connection:
        reponse = connection.execute(text("select current_database()")).scalar()
    assert reponse == contexte.database_name


# ---------------------------------------------------------------------------
# Exigence 2 — Redis, Chroma, stockage fichiers séparés
# ---------------------------------------------------------------------------

def test_les_chemins_d_ecriture_sont_sous_le_repertoire_temporaire_de_session(contexte):
    from app.config import settings

    tmp = Path(contexte.tmp_dir).resolve()
    assert tmp.is_dir()
    for attr in (
        "OUTPUT_DIR", "METADATA_DIR", "CHROMA_PATH", "DELIVERABLES_DIR",
        "UPLOAD_DIR", "SFDX_PROJECT_PATH", "FORCE_APP_PATH",
    ):
        valeur = Path(str(getattr(settings, attr))).resolve()
        assert valeur.is_relative_to(tmp), f"settings.{attr} = {valeur} hors de {tmp}"
        for interdit in CHEMINS_INTERDITS:
            assert not str(valeur).startswith(interdit), f"settings.{attr} = {valeur}"


def test_le_service_agents_ecrit_ses_sorties_sous_le_repertoire_de_session(contexte, tmp_path):
    """`AgentIntegrationService.output_dir` était `backend/outputs` en dur —
    sur le VPS, c'est l'arbre de travail déployé."""
    from app.services.agent_integration import AgentIntegrationService

    service = AgentIntegrationService(agents_path=str(tmp_path))
    sortie = Path(service.output_dir).resolve()
    assert sortie.is_relative_to(Path(contexte.tmp_dir).resolve()), str(sortie)


def test_redis_et_file_arq_sont_separes_de_la_production(contexte):
    from app.workers import arq_config
    from app.workers.worker import WorkerSettings

    assert arq_config.REDIS_SETTINGS.database != 1, "DB 1 est la file ARQ de production"
    assert arq_config.REDIS_SETTINGS.database != 0, "DB 0 est le cache de production"
    assert arq_config.ARQ_QUEUE_NAME != "digital-humans"
    assert arq_config.ARQ_QUEUE_NAME.startswith("test-")
    assert contexte.run_id in arq_config.ARQ_QUEUE_NAME
    assert WorkerSettings.queue_name == arq_config.ARQ_QUEUE_NAME
    assert WorkerSettings.redis_settings is arq_config.REDIS_SETTINGS


@pytest.mark.parametrize(
    "relpath",
    [
        "app/api/routes/orchestrator/execution_routes.py",
        "app/api/routes/orchestrator/retry_routes.py",
        "app/workers/worker.py",
    ],
)
def test_aucun_nom_de_file_arq_en_dur(relpath):
    """Sept `_queue_name="digital-humans"` en dur : une file de test qui ne
    serait posée que dans `WorkerSettings` laisserait les routes enfiler sur
    la file réelle."""
    code = _sans_commentaires(relpath)
    for litteral in ('"digital-humans"', "'digital-humans'", "arq:queue:digital-humans"):
        assert litteral not in code, f"{relpath} porte encore {litteral}"


# ---------------------------------------------------------------------------
# Exigence 3 — aucune clé réelle, aucun appel réseau sortant
# ---------------------------------------------------------------------------

def test_les_secrets_sont_factices_dans_le_processus_de_test(hermetic):
    assert hermetic.SECRET_VARS, "la liste des secrets à neutraliser est vide"
    for nom in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "STRIPE_SECRET_KEY",
                "STRIPE_WEBHOOK_SECRET", "GHOST_ADMIN_KEY", "GIT_TOKEN",
                "SALESFORCE_TOKEN", "TELEGRAM_BOT_TOKEN"):
        assert nom in hermetic.SECRET_VARS, nom
    for nom in hermetic.SECRET_VARS:
        valeur = os.environ.get(nom)
        assert valeur is not None, f"{nom} n'est pas posé : load_dotenv() le lirait dans backend/.env"
        assert valeur == hermetic.FAKE_SECRETS[nom], f"{nom} n'a pas la valeur factice"
        assert not hermetic.looks_like_a_real_secret(nom, valeur), f"{nom} ressemble à une vraie clé"


def test_le_fichier_env_reel_n_est_pas_la_source_de_la_configuration():
    """`load_dotenv()` et `Settings(env_file=".env")` doivent lire `.env.test`,
    pas `backend/.env` — même quand ce dernier existe."""
    from app.config import settings

    assert os.environ.get("DH_ENV_FILE", "").endswith(".env.test")
    assert Path(os.environ["DH_ENV_FILE"]).resolve() == (BACKEND / ".env.test").resolve()
    # `.env.test` pose DH_LOG_FORMAT=plain ; `.env.example` (et le .env du VPS)
    # posent json. Si `settings` lisait `.env`, la valeur serait json.
    assert settings.LOG_FORMAT == "plain"


def test_un_appel_reseau_sortant_est_refuse(hermetic):
    # 192.0.2.1 : bloc TEST-NET-1 (RFC 5737), jamais routé — sans la garde,
    # l'appel tomberait en timeout, pas en refus explicite.
    with pytest.raises(hermetic.OutboundNetworkBlocked):
        socket.create_connection(("192.0.2.1", 443), timeout=3)
    tentatives = hermetic.consume_blocked_attempts()
    assert tentatives and "192.0.2.1" in tentatives[-1]


def test_un_appel_httpx_sortant_est_refuse(hermetic):
    import httpx

    with pytest.raises(hermetic.OutboundNetworkBlocked):
        httpx.get("http://192.0.2.1/", timeout=3)
    assert hermetic.consume_blocked_attempts()


def test_un_appel_sortant_avale_par_le_code_fait_quand_meme_echouer_le_test(contexte, tmp_path):
    """Le cas dangereux : le service attrape `Exception` et se replie. Le test
    serait vert et l'appel réel parti. La session doit le compter."""
    fichier = BACKEND / "tests" / "_tmp_vague0_reseau_avale.py"
    fichier.write_text(
        "import socket\n"
        "def test_avale():\n"
        "    try:\n"
        "        socket.create_connection(('192.0.2.1', 443), timeout=3)\n"
        "    except Exception:\n"
        "        pass\n"
        "    assert True\n",
        encoding="utf-8",
    )
    try:
        resultat = _pytest_enfant(
            {"TEST_DATABASE_URL": contexte.base_database_url},
            args=(str(fichier.relative_to(BACKEND)),),
        )
    finally:
        fichier.unlink(missing_ok=True)
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "192.0.2.1" in sortie, sortie
    bilan = sortie.strip().splitlines()[-1]
    assert "error" in bilan or "failed" in bilan, bilan


def test_psycopg2_refuse_une_base_reelle_avant_de_se_connecter(contexte):
    """libpq (C) ne passe pas par `socket.socket` : la garde doit tenir sur
    l'appel Python `psycopg2.connect`, avant toute connexion."""
    import psycopg2
    from sqlalchemy.engine import make_url

    from tests.db_guard import ProductionDatabaseError

    url = make_url(contexte.base_database_url)
    with pytest.raises(ProductionDatabaseError):
        psycopg2.connect(
            host=url.host, port=url.port or 5432, user=url.username,
            password=url.password, dbname="digital_humans_db",
        )
    dsn_prod = url.set(database="digital_humans_db").render_as_string(hide_password=False)
    with pytest.raises(ProductionDatabaseError):
        psycopg2.connect(dsn_prod)
    with pytest.raises(hermetic_module().OutboundNetworkBlocked):
        psycopg2.connect(host="192.0.2.1", port=5432, user="x", password="x", dbname="dh_test")
    hermetic_module().consume_blocked_attempts()


def hermetic_module():
    from tests import hermetic

    return hermetic


def test_la_boucle_locale_reste_joignable():
    from app.database import engine

    with engine.connect() as connection:
        assert connection.execute(text("select 1")).scalar() == 1


# ---------------------------------------------------------------------------
# Exigence 4 — parallélisme : une base par exécution, créée et détruite par
# la session
# ---------------------------------------------------------------------------

def test_une_execution_enfant_a_sa_propre_base_et_la_detruit_en_sortant(contexte, hermetic):
    identifiant = f"enfant{os.getpid()}"
    resultat = _pytest_enfant(
        {"TEST_DATABASE_URL": contexte.base_database_url, "DH_TEST_RUN_ID": identifiant},
        quiet=False,  # l'en-tête de session (nom de la base) n'apparaît pas en -q
    )
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode == 0, sortie
    assert " passed" in sortie, sortie

    nom_enfant = hermetic.database_name_for(contexte.base_database_name, identifiant)
    assert identifiant in nom_enfant and nom_enfant != contexte.database_name
    assert nom_enfant in sortie, f"l'en-tête pytest de l'enfant doit nommer sa base : {sortie}"

    existantes = hermetic.list_databases(contexte.base_database_url)
    assert contexte.database_name in existantes, "la base de cette session a disparu"
    assert nom_enfant not in existantes, "la base de l'enfant n'a pas été détruite"


# ---------------------------------------------------------------------------
# Exigence 5 — contrôles négatifs : refus à la collecte, avant toute connexion
# ---------------------------------------------------------------------------

def test_controle_negatif_base_de_prod_sans_TEST_DATABASE_URL():
    # Port 1 : rien n'écoute. Si le refus venait APRÈS une tentative de
    # connexion, « Connection refused » apparaîtrait dans la sortie.
    prod = "postgresql://dh:x@127.0.0.1:1/digital_humans_db"
    resultat = _pytest_enfant({"DATABASE_URL": prod})
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "TEST_DATABASE_URL" in sortie, "le message doit dire quoi exporter"
    assert "digital_humans_db" in sortie, "le message doit nommer la base refusée"
    for trace in TRACES_DE_CONNEXION:
        assert trace not in sortie, f"{trace!r} : une connexion a été tentée avant le refus"
    assert " passed" not in sortie and "collected" not in sortie, "rien ne doit être collecté"


def test_controle_negatif_aucune_url_du_tout():
    resultat = _pytest_enfant({})
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "TEST_DATABASE_URL" in sortie
    assert " passed" not in sortie and "collected" not in sortie


def test_controle_negatif_cle_anthropic_reelle(contexte):
    # Forme d'une vraie clé, construite ici pour que le test des secrets en
    # dur du dépôt ne la prenne pas pour une fuite.
    cle = "sk-ant-api03-" + "A" * 40
    resultat = _pytest_enfant(
        {"TEST_DATABASE_URL": contexte.base_database_url, "ANTHROPIC_API_KEY": cle},
    )
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "ANTHROPIC_API_KEY" in sortie, "le message doit nommer la variable refusée"
    assert cle not in sortie, "la valeur refusée ne doit pas être recopiée dans la sortie"
    assert " passed" not in sortie and "collected" not in sortie
    for trace in TRACES_DE_CONNEXION:
        assert trace not in sortie


def test_controle_negatif_cle_stripe_reelle(contexte):
    cle = "sk_live_" + "B" * 32
    resultat = _pytest_enfant(
        {"TEST_DATABASE_URL": contexte.base_database_url, "STRIPE_SECRET_KEY": cle},
    )
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode != 0, sortie
    assert "STRIPE_SECRET_KEY" in sortie
    assert cle not in sortie
    assert " passed" not in sortie and "collected" not in sortie


def test_controle_positif_TEST_DATABASE_URL_seule_suffit(contexte):
    """Le pendant des refus : avec la seule variable documentée, la suite
    se collecte et passe, sans `DATABASE_URL`, sans `.env`, sans clé."""
    resultat = _pytest_enfant({"TEST_DATABASE_URL": contexte.base_database_url})
    sortie = resultat.stdout + resultat.stderr
    assert resultat.returncode == 0, sortie
    assert " passed" in sortie, sortie


# ---------------------------------------------------------------------------
# La garde est réellement branchée, et avant tout import applicatif
# ---------------------------------------------------------------------------

def test_conftest_appelle_le_bootstrap_avant_tout_import_applicatif():
    source = (BACKEND / "tests" / "conftest.py").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )
    position_bootstrap = code.find("bootstrap_hermetic_environment(")
    position_app = code.find("from app.")
    assert position_bootstrap != -1, "conftest n'appelle pas le bootstrap"
    assert position_app != -1
    assert position_bootstrap < position_app, "le bootstrap doit précéder le premier import de `app`"
