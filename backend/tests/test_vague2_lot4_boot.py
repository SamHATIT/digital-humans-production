"""
VAGUE 2 — LOT 4 : deux defauts trouves au deploiement du 23/08, hors EXECUTION.md.

Les deux ont la meme cause racine : **`DEBUG=True` en production**.

  4.1 `create_all` au demarrage. LOT-G annonce « boot sans `create_all` ». Le
      code ne le fait qu'en `DEBUG=False`. La production tourne en `DEBUG=True`.
      Le critere est donc **declare et non tenu**.
  4.2 `config.py:172` n'exige `CREDENTIALS_ENCRYPTION_KEY` que si
      `DEBUG=False`. La cle est absente : le chiffrement retombe sur une cle
      derivee de `SECRET_KEY`, et le garde-fou de LOT-E est **inerte**.

`DEBUG=False` n'est pas bascule ici — c'est une decision de Sam, et le service
refuserait de demarrer sans la cle. Les deux correctifs doivent donc tenir
**a `DEBUG=True`**.
"""
import pytest

from app.schema_bootstrap import (
    encryption_posture,
    should_auto_create_schema,
)


# ==========================================================================
# 4.1 — le boot ne cree plus le schema, quel que soit DEBUG
# ==========================================================================

def test_le_schema_n_est_pas_cree_au_boot_en_debug():
    """Le coeur du constat. Avant : `if settings.DEBUG: create_all()`, et la
    production tourne en DEBUG=True — donc `create_all` y tournait, malgre le
    critere de fin de LOT-G."""
    ok, raison = should_auto_create_schema(debug=True, auto_create=None)
    assert ok is False, f"create_all tourne encore en DEBUG=True : {raison}"
    assert "alembic" in raison.lower()


def test_le_schema_n_est_pas_cree_au_boot_hors_debug():
    """Non-regression du critere de LOT-G tel qu'il etait ecrit."""
    ok, _ = should_auto_create_schema(debug=False, auto_create=None)
    assert ok is False


@pytest.mark.parametrize("debug", [True, False])
def test_l_auto_creation_reste_possible_mais_doit_etre_demandee(debug):
    """On ne supprime pas la commodite : on exige qu'elle soit nommee.

    Un test d'integration ou un environnement jetable peut vouloir un schema
    cree au boot. Il le demande explicitement, il ne l'herite plus de DEBUG.
    """
    ok, raison = should_auto_create_schema(debug=debug, auto_create=True)
    assert ok is True
    assert "AUTO_CREATE_SCHEMA" in raison


def test_l_auto_creation_refusee_explicitement_l_emporte_sur_debug():
    ok, _ = should_auto_create_schema(debug=True, auto_create=False)
    assert ok is False


def test_la_decision_est_toujours_motivee():
    """Regle 5 : le boot doit dire ce qu'il fait du schema, pas le taire."""
    for debug in (True, False):
        for auto in (None, True, False):
            ok, raison = should_auto_create_schema(debug=debug, auto_create=auto)
            assert isinstance(raison, str) and raison.strip(), (
                f"decision non motivee pour debug={debug} auto_create={auto}"
            )


def test_main_delegue_la_decision_et_ne_teste_plus_DEBUG():
    """Une fonction pure non branchee serait un dispositif de plus declare et
    inoperant — exactement ce que la regle 5 interdit."""
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "main.py"
    ).read_text(encoding="utf-8")

    assert "should_auto_create_schema" in source
    assert "if settings.DEBUG:\n    Base.metadata.create_all" not in source


# ==========================================================================
# 4.2 — le garde-fou de chiffrement doit se declarer inerte, pas se taire
# ==========================================================================

def test_cle_absente_en_debug_le_dit_haut_et_fort():
    """Le defaut : `validate_encryption_key` rend `self` sans un mot des que
    `DEBUG` est vrai. En production, DEBUG est vrai. Le garde-fou de LOT-E est
    donc inerte, **et silencieux** — c'est le second point qui coute."""
    posture = encryption_posture(debug=True, encryption_key=None, secret_key="s3cret")

    assert posture["ok"] is False
    assert posture["derived_from_secret_key"] is True
    assert posture["guard_active"] is False, (
        "le garde-fou de LOT-E est presente comme actif alors qu'il ne l'est pas"
    )
    assert posture["severity"] == "CRITICAL"
    # Le message doit porter la sequence, pas seulement le diagnostic.
    message = posture["message"]
    assert "rotate_encryption_key.py" in message
    assert "CREDENTIALS_ENCRYPTION_KEY" in message
    assert "DEBUG=False" in message


def test_cle_presente_en_debug_est_saine():
    posture = encryption_posture(
        debug=True, encryption_key="une-cle-fernet", secret_key="s3cret"
    )
    assert posture["ok"] is True
    assert posture["derived_from_secret_key"] is False
    assert posture["severity"] == "INFO"


def test_hors_debug_le_garde_fou_est_actif():
    """A `DEBUG=False`, `config.validate_encryption_key` refuse de demarrer :
    la posture doit le refleter."""
    posture = encryption_posture(debug=False, encryption_key=None, secret_key="s3cret")
    assert posture["guard_active"] is True
    assert posture["ok"] is False


def test_hors_debug_avec_cle_est_l_etat_vise():
    posture = encryption_posture(
        debug=False, encryption_key="une-cle-fernet", secret_key="s3cret"
    )
    assert posture["ok"] is True
    assert posture["guard_active"] is True
    assert posture["severity"] == "INFO"


def test_la_posture_est_annoncee_au_boot():
    """Un diagnostic qui ne sort pas dans les journaux n'existe pas."""
    import pathlib

    source = (
        pathlib.Path(__file__).resolve().parents[1] / "app" / "main.py"
    ).read_text(encoding="utf-8")
    assert "encryption_posture" in source


def test_la_sequence_de_bascule_est_documentee():
    """« Prepare la sequence, documente-la, ne l'execute pas. »"""
    import pathlib

    doc = (
        pathlib.Path(__file__).resolve().parents[2]
        / "docs"
        / "audit-20260821"
        / "BASCULE_DEBUG_FALSE.md"
    )
    assert doc.exists(), "la sequence de bascule DEBUG=False n'est pas documentee"
    contenu = doc.read_text(encoding="utf-8")

    # L'ordre des etapes est imperatif : rotation, puis cle dans .env, puis
    # seulement la bascule. Pris a l'envers, il rend les credentials illisibles.
    etape_rotation = contenu.index("--old-secret-key-derived")
    etape_cle = contenu.index("CREDENTIALS_ENCRYPTION_KEY=<")
    etape_bascule = contenu.index("Alors seulement")
    assert etape_rotation < etape_cle < etape_bascule, (
        "l'ordre documente ne protege pas les credentials : "
        f"rotation@{etape_rotation}, cle@{etape_cle}, bascule@{etape_bascule}"
    )

    # « documente-la, ne l'execute pas » : le document doit le dire lui-meme.
    assert "non exécutée" in contenu or "non executee" in contenu
    assert "Ne pas exécuter" in contenu or "Ne pas executer" in contenu

    # Et il doit couvrir le repli, pas seulement le chemin heureux.
    assert "Repli" in contenu or "repli" in contenu
