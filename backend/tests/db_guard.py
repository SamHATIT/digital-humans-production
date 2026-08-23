"""
Garde de base de donnees pour la suite de tests.

VAGUE 2 / LOT 1c — audit croise du 21/08/2026.

`conftest.py` resout sa base sur `TEST_DATABASE_URL`, sinon `DATABASE_URL`,
sinon un defaut PostgreSQL. La fixture `db_session` cree les tables puis les
**supprime** apres chaque test (`Base.metadata.drop_all`). Sur le VPS, ou le
service backend et le depot lisent le meme `backend/.env`, `DATABASE_URL`
pointe la base de production : un `pytest` lance depuis l'arbre de travail
deployé y detruit les tables reelles. Le 21/08 seule une vue du comite l'a
empeche.

La garde refuse de demarrer. Elle ne repare rien, elle empeche.
"""
import logging
import os
import re

logger = logging.getLogger(__name__)


class ProductionDatabaseError(RuntimeError):
    """La base visee par la suite de tests n'est pas une base de test."""


#: Noms de bases connus comme reels. Liste explicite : ce qui est nomme ici est
#: refuse meme si le nom contient par ailleurs « test ».
KNOWN_PRODUCTION_DATABASES = frozenset({
    "digital_humans_db",
    "digital_humans",
    "digital_humans_prod",
})

#: Marqueur qui autorise une base dont le nom ne prouve pas qu'elle est jetable.
#: Ni « test » ni « _test » dans le nom : on refuse par defaut.
_TEST_NAME = re.compile(r"(^|[_\-.])te?sts?([_\-.]|$)|^test|test$", re.IGNORECASE)

#: Derogation, volontairement penible a poser et bruyante a l'usage.
OVERRIDE_ENV_VAR = "DH_ALLOW_NON_TEST_DB"


def _database_name(url: str) -> str:
    """Nom de la base porte par une URL SQLAlchemy, sans dependance externe."""
    # On coupe la query string puis on prend le dernier segment de chemin.
    without_query = url.split("?", 1)[0]
    without_scheme = without_query.split("://", 1)[-1]
    if "/" not in without_scheme:
        return ""
    return without_scheme.rsplit("/", 1)[1]


def assert_not_production_database(url: str) -> None:
    """Leve `ProductionDatabaseError` si `url` n'est pas manifestement une base
    de test.

    Le critere est volontairement conservateur : **on refuse tout ce qu'on ne
    peut pas prouver jetable**, plutot que d'accepter tout ce qu'on n'a pas su
    reconnaitre comme reel. Une liste de noms interdits laisserait passer la
    prochaine base de production, qui portera un autre nom.
    """
    override = os.environ.get(OVERRIDE_ENV_VAR, "").strip().lower()
    allowed = override in {"1", "true", "yes", "on"}

    if not url:
        problem = (
            "aucune URL de base de donnees n'a pu etre resolue "
            "(ni TEST_DATABASE_URL, ni DATABASE_URL)"
        )
    else:
        name = _database_name(url)
        if not name:
            problem = f"l'URL ne porte pas de nom de base : {url!r}"
        elif name.lower() in KNOWN_PRODUCTION_DATABASES:
            problem = (
                f"la base visee est {name!r}, connue comme base reelle "
                f"(voir KNOWN_PRODUCTION_DATABASES)"
            )
        elif name.startswith(":memory:") or name == ":memory:":
            problem = ""
        elif _TEST_NAME.search(name):
            problem = ""
        else:
            problem = (
                f"le nom de base {name!r} ne prouve pas qu'il s'agit d'une base "
                f"de test (attendu : un nom contenant « test »)"
            )

    if not problem:
        return

    if allowed:
        logger.warning(
            "[garde base de test] %s. Passage force par %s=%s — "
            "la suite va CREER puis SUPPRIMER les tables de cette base.",
            problem,
            OVERRIDE_ENV_VAR,
            override,
        )
        return

    raise ProductionDatabaseError(
        f"Refus de lancer la suite de tests : {problem}.\n"
        f"\n"
        f"  URL resolue : {url or '(vide)'}\n"
        f"\n"
        f"La fixture `db_session` execute `Base.metadata.drop_all()` apres "
        f"chaque test. Sur une base reelle, cela detruit les donnees.\n"
        f"\n"
        f"Poser une base dediee :\n"
        f"    export TEST_DATABASE_URL="
        f"postgresql://user:pass@127.0.0.1:5432/digital_humans_test\n"
        f"\n"
        f"En dernier recours, et en connaissance de cause :\n"
        f"    export {OVERRIDE_ENV_VAR}=1\n"
    )
