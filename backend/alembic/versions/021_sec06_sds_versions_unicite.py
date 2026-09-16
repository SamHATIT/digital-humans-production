"""SEC-06 : unicite (project_id, version_number) sur sds_versions

Revision ID: 021_sec06_sds_versions_unicite
Revises: 015_free_50_credits_jour
Create Date: 2026-09-16

Audit Astra du 06/09, constat SEC-06 (L127). Deux snapshots concurrents du
meme projet calculaient le meme `max(version_number)+1` : rien n'empechait le
doublon. La route alloue desormais le numero sous verrou consultatif ; cette
contrainte ferme la course restante, y compris entre processus (worker,
orchestrateur) qui ne prendraient pas ce verrou.

**Collisions deja presentes** : la migration les examine AVANT de poser la
contrainte et s'arrete en les nommant plutot que de les reparer toute seule.
Reparer automatiquement supposerait de decider quel snapshot garde son
numero — c'est une decision d'exploitant, pas de migration (regle « jamais de
repli silencieux »). Requete de diagnostic :

    SELECT project_id, version_number, count(*), array_agg(id)
    FROM sds_versions GROUP BY 1, 2 HAVING count(*) > 1;

Reversible : le downgrade retire la contrainte.
"""
from alembic import op
import sqlalchemy as sa

revision = "021_sec06_sds_versions_unicite"
down_revision = "020_execution_degraded"
branch_labels = None
depends_on = None

NOM = "uq_sds_versions_project_version"


def upgrade() -> None:
    bind = op.get_bind()

    doublons = bind.execute(sa.text(
        "SELECT project_id, version_number, count(*) AS n "
        "FROM sds_versions GROUP BY project_id, version_number "
        "HAVING count(*) > 1 ORDER BY project_id, version_number"
    )).fetchall()
    if doublons:
        detail = ", ".join(
            f"projet {d.project_id} v{d.version_number} ({d.n} lignes)" for d in doublons
        )
        raise RuntimeError(
            "SEC-06 : des couples (project_id, version_number) sont deja en "
            f"double, la contrainte ne peut pas etre posee : {detail}. "
            "Choisissez le snapshot qui garde son numero et renumerotez les "
            "autres avant de relancer cette migration."
        )

    existe = bind.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conname = :nom"
    ), {"nom": NOM}).first()
    if not existe:
        op.create_unique_constraint(NOM, "sds_versions", ["project_id", "version_number"])


def downgrade() -> None:
    bind = op.get_bind()
    existe = bind.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conname = :nom"
    ), {"nom": NOM}).first()
    if existe:
        op.drop_constraint(NOM, "sds_versions", type_="unique")
