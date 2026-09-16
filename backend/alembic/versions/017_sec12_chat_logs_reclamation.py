"""SEC-12 : rattachement des conversations vitrine par revendication

Revision ID: 017_sec12_chat_logs_reclamation
Revises: 016_sec06_sds_versions_unicite
Create Date: 2026-09-16

Audit Astra du 06/09, constat SEC-12 (L221). L'export et l'effacement RGPD
selectionnaient les conversations du site vitrine sur
`chat_logs.email_collected == user.email`. Un visiteur peut saisir l'adresse
d'un tiers dans le widget public : creer ensuite le compte correspondant
donnait acces a cette conversation, en lecture comme en suppression.

Cette migration ajoute `claimed_by_user_id`, qui porte desormais le
rattachement. Elle **ne remplit pas** la colonne a partir de
`email_collected` : ce serait reconduire exactement l'assimilation que le
constat reproche. Les conversations existantes restent donc non
revendiquees jusqu'a ce que leur visiteur les revendique avec son
`session_uuid` (POST /api/account/conversations/claim).

Consequence assumee, a dire aux clients concernes : un export RGPD ne
rendra plus, tant qu'aucune revendication n'a eu lieu, les conversations
concierge anterieures. Le droit reste exercable par la revendication ou par
une demande manuelle a l'exploitant.

Idempotente et reversible.
"""
from alembic import op
import sqlalchemy as sa

revision = "017_sec12_chat_logs_reclamation"
down_revision = "016_sec06_sds_versions_unicite"
branch_labels = None
depends_on = None

TABLE = "chat_logs"
COLONNE = "claimed_by_user_id"


def _colonne_existe(bind) -> bool:
    return bool(bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = :t AND column_name = :c"
    ), {"t": TABLE, "c": COLONNE}).first())


def upgrade() -> None:
    bind = op.get_bind()
    if _colonne_existe(bind):
        return
    op.add_column(TABLE, sa.Column(COLONNE, sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_chat_logs_claimed_by_user", TABLE, "users",
        [COLONNE], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_chat_logs_claimed_by_user_id", TABLE, [COLONNE])


def downgrade() -> None:
    bind = op.get_bind()
    if not _colonne_existe(bind):
        return
    op.drop_index("ix_chat_logs_claimed_by_user_id", table_name=TABLE)
    op.drop_constraint("fk_chat_logs_claimed_by_user", TABLE, type_="foreignkey")
    op.drop_column(TABLE, COLONNE)
