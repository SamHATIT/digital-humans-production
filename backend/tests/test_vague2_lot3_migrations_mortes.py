"""
VAGUE 2 — LOT 3 : les `migrations/*.sql` manuels sont morts (kim:PROD-05).

Ils doublonnent Alembic. Deux sources pour un meme schema, dont une seule tient
`alembic_version` : appliquer un `.sql` d'ici n'avance pas le pointeur de
revision, et le prochain `alembic upgrade head` echoue sur un objet deja
existant. C'est l'incident que PROD-05 annonce.

Les marquer morts, ce n'est pas ecrire une note que personne ne lit : c'est
poser un test qui echoue si quelqu'un en ajoute un.
"""
import pathlib

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS = BACKEND / "migrations"
ALEMBIC_VERSIONS = BACKEND / "alembic" / "versions"

#: Les quatre fichiers connus au 23/08/2026, geles. Cette liste ne doit pas
#: grandir : toute nouvelle migration passe par Alembic.
SQL_MORTS_CONNUS = {
    "006_execution_state_machine.sql",
    "freemium_and_environments.sql",
    "wbs_task_types.sql",
    "wizard_phase5.sql",
}


def test_aucune_nouvelle_migration_sql_manuelle():
    """Le garde-fou : si ce test rougit, quelqu'un a ecrit une migration hors
    d'Alembic. La reponse n'est pas d'allonger la liste, c'est de la refaire en
    revision Alembic."""
    presents = {p.name for p in MIGRATIONS.glob("*.sql")}
    nouveaux = presents - SQL_MORTS_CONNUS
    assert not nouveaux, (
        f"migrations SQL manuelles ajoutees hors Alembic : {sorted(nouveaux)}. "
        f"Voir backend/migrations/README.md — ce repertoire est mort, la source "
        f"de verite du schema est backend/alembic/versions/."
    )


def test_le_repertoire_est_marque_mort():
    """Un fichier mort sans panneau se fait rouvrir six mois plus tard."""
    readme = MIGRATIONS / "README.md"
    assert readme.exists(), "backend/migrations/README.md manquant"
    contenu = readme.read_text(encoding="utf-8")
    assert "MORT" in contenu
    assert "alembic" in contenu.lower()


def test_alembic_reste_la_source_de_verite():
    """Controle positif : les revisions Alembic sont bien la, et plus nombreuses
    que les .sql qu'elles remplacent."""
    revisions = list(ALEMBIC_VERSIONS.glob("*.py"))
    assert len(revisions) >= len(SQL_MORTS_CONNUS), (
        f"{len(revisions)} revisions Alembic pour {len(SQL_MORTS_CONNUS)} .sql manuels"
    )


def test_aucun_code_n_execute_ces_fichiers():
    """Le vrai danger n'est pas leur presence, c'est qu'un script les rejoue."""
    coupables = []
    for source in BACKEND.rglob("*.py"):
        if "venv" in source.parts or "/tests/" in str(source):
            continue
        try:
            texte = source.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for nom in SQL_MORTS_CONNUS:
            if nom in texte:
                coupables.append(f"{source.relative_to(BACKEND)} -> {nom}")

    assert not coupables, (
        f"du code Python reference une migration SQL morte : {coupables}"
    )
