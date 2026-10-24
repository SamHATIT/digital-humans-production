"""RGPD-03 : tache durable d'effacement de compte, rejouable

Revision ID: 023a_rgpd03_effacements_comptes
Revises: 022_sec12_chat_logs_reclamation
Create Date: 2026-10-24

Audit Astra du 06/09, RGPD-03 (L870) : une erreur Chroma etait comptee zero
chunk, puis les lignes SQL qui designaient les chunks etaient detruites ;
l'effacement devenait partiel et definitif. Cette table porte le perimetre
d'un effacement et son etat (en_cours / partiel / termine) pour qu'il soit
complet ou rejouable.

Vague 2 : prefixe `023a` (file A). La file C peut ajouter une `023c_...`
depuis la meme tete `022_sec12_chat_logs_reclamation` : a la fusion, deux
tetes Alembic -> une revision de fusion sera necessaire.

Idempotente et reversible ; aucune donnee existante n'est touchee.
"""
from alembic import op
import sqlalchemy as sa

revision = "023a_rgpd03_effacements_comptes"
down_revision = "022_sec12_chat_logs_reclamation"
branch_labels = None
depends_on = None

TABLE = "effacements_comptes"


def _table_existe(bind) -> bool:
    return sa.inspect(bind).has_table(TABLE)


def upgrade() -> None:
    bind = op.get_bind()
    if _table_existe(bind):
        return
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("statut", sa.String(20), nullable=False, server_default="en_cours"),
        sa.Column("perimetre", sa.JSON(), nullable=False),
        sa.Column("etapes", sa.JSON(), nullable=False),
        sa.Column("erreurs", sa.JSON(), nullable=False),
        sa.Column("tentatives", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cree_le", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("maj_le", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("termine_le", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_effacements_comptes_id", TABLE, ["id"])
    op.create_index("ix_effacements_comptes_user_id", TABLE, ["user_id"])
    op.create_index("ix_effacements_comptes_statut", TABLE, ["statut"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_existe(bind):
        return
    op.drop_index("ix_effacements_comptes_statut", table_name=TABLE)
    op.drop_index("ix_effacements_comptes_user_id", table_name=TABLE)
    op.drop_index("ix_effacements_comptes_id", table_name=TABLE)
    op.drop_table(TABLE)
