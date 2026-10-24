"""GL-22 : consentement Opus — trace et opt-in effectif (vague 2 / file C)

Revision ID: 023c_consentement_opus
Revises: 022_sec12_chat_logs_reclamation
Create Date: 2026-10-24

Le site promet « Opus on opt-in, cost shown before each call ». Décision Sam
du 17/09 : « on ajoute le recueil ».

1. Table ``opus_consents`` : une ligne par (exécution, modèle) — utilisateur,
   exécution, date, décision (``accepte`` / ``refuse``), montant affiché en
   crédits, version du texte de l'écran.

2. ``model_pricing.requires_opt_in`` repasse à **true** pour
   ``claude-opus-5``. La migration 016 l'avait posé à false faute de
   mécanisme de recueil (« À rebasculer à true le jour où un consentement
   explicite existe — une ligne de SQL suffit, le code l'applique ») : ce
   mécanisme est livré avec cette migration (routeur + route de lancement).

Préfixe ``023c`` : la file A de la vague 2 peut ajouter une ``023a_…`` depuis
la même tête ``022`` ; à la fusion, les deux branches donneront deux têtes
Alembic, à réunir par une migration de fusion (signalé dans le rapport).

Idempotente (table créée si absente ; UPDATE ciblé), réversible.
"""
from alembic import op
import sqlalchemy as sa

revision = "023c_consentement_opus"
down_revision = "022_sec12_chat_logs_reclamation"
branch_labels = None
depends_on = None

TABLE = "opus_consents"
MODELE_OPT_IN = "claude-opus-5"


def _table_existe(bind) -> bool:
    return sa.inspect(bind).has_table(TABLE)


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_existe(bind):
        op.create_table(
            TABLE,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("execution_id", sa.Integer(),
                      sa.ForeignKey("executions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("model_name", sa.String(50), nullable=False),
            sa.Column("decision", sa.String(16), nullable=False),
            sa.Column("credits_estimes", sa.Integer(), nullable=False),
            sa.Column("texte_version", sa.String(32), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
            sa.UniqueConstraint("execution_id", "model_name",
                                name="uq_opus_consents_execution_modele"),
            sa.CheckConstraint("decision IN ('accepte', 'refuse')",
                               name="ck_opus_consents_decision"),
            sa.CheckConstraint("credits_estimes >= 0", name="ck_opus_consents_credits"),
        )
        op.create_index("ix_opus_consents_user_id", TABLE, ["user_id"])
        op.create_index("ix_opus_consents_execution_id", TABLE, ["execution_id"])
    op.execute(
        sa.text("UPDATE model_pricing SET requires_opt_in = true, updated_at = now() "
                "WHERE model_name = :m").bindparams(m=MODELE_OPT_IN)
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE model_pricing SET requires_opt_in = false, updated_at = now() "
                "WHERE model_name = :m").bindparams(m=MODELE_OPT_IN)
    )
    bind = op.get_bind()
    if _table_existe(bind):
        op.drop_table(TABLE)
