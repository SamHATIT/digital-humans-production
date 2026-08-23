"""
VAGUE 2 — LOT 1c : garde `DATABASE_URL` dans `conftest.py`.

Le defaut, tel qu'observe le 21/08 : `conftest.py` resout sa base sur
`TEST_DATABASE_URL`, sinon `DATABASE_URL`, sinon un defaut PostgreSQL. La
fixture `db_session` fait `Base.metadata.create_all()` **puis
`Base.metadata.drop_all()` a chaque test**. Lancer `pytest` sur une machine ou
`DATABASE_URL` pointe la base de production — c'est le cas du VPS, ou le service
et le depot partagent le meme `.env` — **detruit les tables reelles**. Seule une
vue du comite l'a empeche.

La garde refuse de demarrer plutot que de laisser passer. Elle est testee ici en
tant que fonction, parce qu'une garde qui s'execute a l'import de `conftest`
n'est pas observable depuis un test de cette meme session.
"""
import pytest

from tests.db_guard import (
    ProductionDatabaseError,
    assert_not_production_database,
)


# --------------------------------------------------------------------------
# Ce qui doit etre refuse
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        # Le nom de la base de production, tel qu'il est dans CLAUDE.md et dans
        # les commandes de diagnostic du depot.
        "postgresql://dh:secret@localhost:5432/digital_humans_db",
        "postgresql+psycopg2://dh:secret@127.0.0.1:5432/digital_humans_db",
        "postgresql://dh@localhost/digital_humans_db?sslmode=require",
        # Meme base, hote distant : c'est le nom qui compte.
        "postgresql://dh:secret@72.61.161.222:5432/digital_humans_db",
    ],
)
def test_refuse_la_base_de_production(url):
    with pytest.raises(ProductionDatabaseError) as excinfo:
        assert_not_production_database(url)
    message = str(excinfo.value)
    assert "digital_humans_db" in message
    assert "TEST_DATABASE_URL" in message


@pytest.mark.parametrize(
    "url",
    [
        # Ni « test » ni « _test » dans le nom : on ne peut pas prouver que ce
        # n'est pas une base reelle, donc on refuse.
        "postgresql://dh@localhost/digital_humans",
        "postgresql://dh@localhost/production",
        "postgresql://dh@localhost/dh_prod",
    ],
)
def test_refuse_une_base_dont_le_nom_ne_prouve_rien(url):
    with pytest.raises(ProductionDatabaseError):
        assert_not_production_database(url)


def test_refuse_une_url_vide():
    """Pas d'URL du tout : la resolution a echoue, on ne devine pas."""
    with pytest.raises(ProductionDatabaseError):
        assert_not_production_database("")


# --------------------------------------------------------------------------
# Ce qui doit passer
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres@127.0.0.1:5432/digital_humans_test",
        "postgresql://dh:dh@localhost:5432/test_digital_humans",
        "postgresql+psycopg2://dh@db:5432/dh_test?sslmode=disable",
        "sqlite:///./test.db",
        "sqlite:///:memory:",
    ],
)
def test_accepte_une_base_de_test(url):
    assert_not_production_database(url)  # ne leve pas


def test_la_derogation_est_explicite_et_bruyante(monkeypatch, caplog):
    """Un contournement doit exister — mais nomme, et jamais silencieux."""
    monkeypatch.setenv("DH_ALLOW_NON_TEST_DB", "1")
    with caplog.at_level("WARNING"):
        assert_not_production_database(
            "postgresql://dh@localhost/digital_humans_db"
        )
    assert any("DH_ALLOW_NON_TEST_DB" in r.message for r in caplog.records), (
        "la derogation doit se signaler dans les journaux"
    )


# --------------------------------------------------------------------------
# La garde est reellement branchee
# --------------------------------------------------------------------------

def test_la_garde_est_appelee_par_conftest():
    """Une garde declaree mais non branchee est un repli silencieux de plus."""
    import pathlib

    source = pathlib.Path(__file__).with_name("conftest.py").read_text(
        encoding="utf-8"
    )
    assert "assert_not_production_database" in source
    assert "SQLALCHEMY_DATABASE_URL" in source
