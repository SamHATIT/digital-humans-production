"""État Stripe persisté : déduplication des événements et abonnement canonique (BILL-04)

Revision ID: 017_etat_stripe_persiste
Revises: 016_tarifs_modeles_servis
Create Date: 2026-09-16

Audit Astra du 06/09, BILL-04 (L683) : « L'état Stripe n'est pas robuste aux
événements désordonnés, impayés et abonnements multiples. »

Rien n'était persisté : chaque webhook écrasait `users.subscription_tier`.
Deux tables réparent cela.

`stripe_events` — un événement reçu = une ligne, clé primaire l'identifiant
Stripe. La contrainte d'unicité EST le mécanisme d'idempotence : un doublon
ne s'insère pas, donc ne recharge pas les crédits une seconde fois. Les
événements non appliqués (price inconnu, client introuvable) restent en
`pending_reconciliation` au lieu d'être acquittés en 200 et perdus.

`stripe_subscriptions` — l'abonnement canonique et sa période.
`last_event_created` porte l'horodatage Stripe du dernier événement appliqué :
un événement plus ancien est refusé (Stripe ne garantit pas l'ordre).
`grace_until` donne à `past_due` / `unpaid` l'échéance applicative qui
manquait. `initial_credits_granted_at` garantit que l'allocation initiale
n'est provisionnée qu'une fois.

Le palier du compte est désormais DÉRIVÉ de ces lignes : supprimer un ancien
abonnement ne rétrograde plus un compte qui en a un autre de payé.

Réversible : les deux tables sont créées par cette migration et détruites par
son downgrade. Aucune donnée existante n'est touchée.
"""
import sqlalchemy as sa
from alembic import op

revision = "017_etat_stripe_persiste"
down_revision = "016_tarifs_modeles_servis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("event_created", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False,
                  server_default="pending_reconciliation"),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("subscription_id", sa.String(255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_stripe_events_status", "stripe_events", ["status"])
    op.create_index("idx_stripe_events_user", "stripe_events", ["user_id"])

    op.create_table(
        "stripe_subscriptions",
        sa.Column("subscription_id", sa.String(255), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("price_id", sa.String(255), nullable=True),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_created", sa.BigInteger(), nullable=True),
        sa.Column("initial_credits_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("idx_stripe_subscriptions_user", "stripe_subscriptions", ["user_id"])
    op.create_index("idx_stripe_subscriptions_customer", "stripe_subscriptions",
                    ["customer_id"])


def downgrade() -> None:
    op.drop_index("idx_stripe_subscriptions_customer", table_name="stripe_subscriptions")
    op.drop_index("idx_stripe_subscriptions_user", table_name="stripe_subscriptions")
    op.drop_table("stripe_subscriptions")
    op.drop_index("idx_stripe_events_user", table_name="stripe_events")
    op.drop_index("idx_stripe_events_status", table_name="stripe_events")
    op.drop_table("stripe_events")
