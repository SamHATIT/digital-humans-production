"""
Decisions de demarrage : schema et posture de chiffrement.

VAGUE 2 / LOT 4 — audit croise du 21/08/2026, deux defauts trouves au
deploiement du 23/08 et absents d'EXECUTION.md.

Les deux ont **la meme cause racine** : la production tourne en `DEBUG=True`,
et deux dispositifs de securite sont conditionnes a `DEBUG=False`. Ils sont
donc declares dans le code, annonces dans les rapports, et inoperants sur la
machine qui sert les clients.

Ce module sort les deux decisions du corps de `main.py` pour qu'elles soient
testables sans demarrer un processus, et pour qu'elles soient **motivees** :
chacune rend, avec sa reponse, la raison de cette reponse, destinee aux
journaux de boot. Un dispositif qui s'active ou se desactive sans le dire est
exactement ce que la regle 5 interdit.
"""
from typing import Any, Dict, Optional, Tuple


def should_auto_create_schema(
    debug: bool, auto_create: Optional[bool]
) -> Tuple[bool, str]:
    """Faut-il executer `Base.metadata.create_all()` au demarrage ?

    **Le defaut corrige ici.** `main.py` faisait :

        if settings.DEBUG:
            Base.metadata.create_all(bind=engine)

    Le commentaire au-dessus expliquait, a juste titre, pourquoi `create_all`
    au boot est nuisible : il cree les tables sans poser `alembic_version`, si
    bien que le premier `alembic upgrade head` echoue ou saute des colonnes.
    Le critere de fin de LOT-G l'annoncait tenu : « boot sans `create_all` ».

    Sauf que `DEBUG` vaut `True` par defaut (`config.py:31`), que
    `.env.example` livre `DEBUG=True`, et que **la production tourne en
    `DEBUG=True`**. Les requetes `pg_catalog.pg_type` observees au boot du
    23/08 sont la verification d'existence des enums que fait `create_all`
    avec `checkfirst=True` : ce n'etait pas autre chose, c'etait bien
    `create_all`. Le critere etait declare et non tenu.

    Correctif : la creation du schema **ne depend plus de `DEBUG`**. Elle
    devient une demande explicite, `AUTO_CREATE_SCHEMA`, par defaut absente.
    Corriger par `DEBUG=False` aurait ete l'autre voie, mais la bascule est une
    decision d'exploitation (le service refuserait de demarrer sans
    `CREDENTIALS_ENCRYPTION_KEY`) : le correctif devait tenir a `DEBUG=True`.

    Args:
        debug: `settings.DEBUG`. N'entre plus dans la decision — l'argument
            reste pour que la raison rendue puisse le nommer.
        auto_create: `settings.AUTO_CREATE_SCHEMA`. `None` = non pose.

    Returns:
        (creer, raison). La raison part dans les journaux de boot.
    """
    if auto_create is True:
        return True, (
            "AUTO_CREATE_SCHEMA=true : creation du schema demandee "
            "explicitement. A reserver aux bases jetables — sur une base "
            "suivie par Alembic, cela cree des tables sans poser "
            "alembic_version et le premier 'alembic upgrade head' echouera."
        )

    if auto_create is False:
        return False, (
            "AUTO_CREATE_SCHEMA=false : creation du schema refusee "
            "explicitement. Le schema appartient a Alembic "
            "('alembic upgrade head')."
        )

    return False, (
        f"AUTO_CREATE_SCHEMA non pose (DEBUG={debug}) : pas de create_all au "
        f"boot. Le schema appartient a Alembic ('alembic upgrade head', lance "
        f"par le deploiement). Poser AUTO_CREATE_SCHEMA=true pour une base "
        f"jetable."
    )


def encryption_posture(
    debug: bool, encryption_key: Optional[str], secret_key: Optional[str]
) -> Dict[str, Any]:
    """Etat reel du chiffrement des credentials, et du garde-fou cense le tenir.

    **Le defaut constate.** `config.validate_encryption_key` (`config.py:172`)
    exige `CREDENTIALS_ENCRYPTION_KEY` — mais seulement si `DEBUG=False` :

        if self.CREDENTIALS_ENCRYPTION_KEY or self.DEBUG:
            return self

    En production, `DEBUG` vaut `True` et la cle est absente. Le garde-fou de
    LOT-E ne s'oppose donc a rien, et `app.utils.encryption` retombe sur une
    cle **derivee de `SECRET_KEY`**. Consequences : le secret qui signe les
    JWT est aussi celui qui chiffre les credentials Salesforce et Git, et toute
    rotation de `SECRET_KEY` rend l'ensemble des credentials illisibles d'un
    coup.

    Ce qui coute le plus n'est pas que le garde-fou soit inactif — c'est qu'il
    soit inactif **en silence**, et rapporte comme tenu. Cette fonction rend la
    posture reelle ; `main.py` la journalise a chaque demarrage.

    Elle ne bascule rien et ne fait echouer aucun boot : la bascule
    `DEBUG=False` est une decision d'exploitation, decrite pas a pas dans
    `docs/audit-20260821/BASCULE_DEBUG_FALSE.md`.

    Returns:
        dict avec `ok`, `derived_from_secret_key`, `guard_active`, `severity`,
        `message`.
    """
    has_key = bool(encryption_key)
    guard_active = not debug  # config.py n'exige la cle qu'a DEBUG=False

    if has_key:
        return {
            "ok": True,
            "derived_from_secret_key": False,
            "guard_active": guard_active,
            "severity": "INFO",
            "message": (
                "Chiffrement des credentials : cle dediee "
                "(CREDENTIALS_ENCRYPTION_KEY) en place."
            ),
        }

    if guard_active:
        # A DEBUG=False sans cle, config.validate_encryption_key leve : ce boot
        # n'arrivera pas jusqu'ici. La branche existe pour que la fonction
        # decrive les quatre etats et reste lisible seule.
        return {
            "ok": False,
            "derived_from_secret_key": False,
            "guard_active": True,
            "severity": "CRITICAL",
            "message": (
                "CREDENTIALS_ENCRYPTION_KEY absente a DEBUG=False : le "
                "demarrage est refuse par config.validate_encryption_key."
            ),
        }

    return {
        "ok": False,
        "derived_from_secret_key": bool(secret_key),
        "guard_active": False,
        "severity": "CRITICAL",
        "message": (
            "GARDE-FOU DE CHIFFREMENT INERTE. CREDENTIALS_ENCRYPTION_KEY est "
            "absente et DEBUG=True : config.validate_encryption_key ne l'exige "
            "qu'a DEBUG=False, il ne s'oppose donc a rien. Les credentials "
            "Salesforce et Git sont chiffres avec une cle DERIVEE de "
            "SECRET_KEY — le meme secret signe les JWT, et toute rotation de "
            "SECRET_KEY rend l'ensemble des credentials illisibles d'un coup.\n"
            "Sequence de sortie, l'ordre est imperatif (details dans "
            "docs/audit-20260821/BASCULE_DEBUG_FALSE.md) :\n"
            "  1. generer une cle Fernet ;\n"
            "  2. python scripts/rotate_encryption_key.py "
            "--old-secret-key-derived --new-key <cle> --apply ;\n"
            "  3. poser CREDENTIALS_ENCRYPTION_KEY dans backend/.env ;\n"
            "  4. redemarrer et verifier ;\n"
            "  5. alors seulement, DEBUG=False."
        ),
    }
