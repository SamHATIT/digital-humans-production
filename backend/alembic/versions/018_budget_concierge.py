"""Budget opérationnel du concierge, indépendant des messages (BILL-09)

Revision ID: 018_budget_concierge
Revises: 017_etat_stripe_persiste
Create Date: 2026-09-16

Audit Astra du 06/09, BILL-09 (L777) : le plafond de 20 USD/jour du concierge
public était la somme de `chat_logs.cost_usd`, et `POST /forget` supprime ces
lignes. Le garde-fou de dépense reposait donc sur des données que le visiteur
peut effacer — en exerçant un droit légitime.

Cette table porte le compteur de dépense, **sans aucune donnée personnelle** :
un total et un nombre de tours par jour. L'effacement RGPD n'a aucune raison
de la toucher, et ne la touche pas.

Elle sert aussi de point de sérialisation : la vérification du plafond et la
dépense se font sous verrou de la ligne du jour.

Réversible ; aucune donnée existante n'est touchée.
"""
import sqlalchemy as sa
from alembic import op

revision = "018_budget_concierge"
down_revision = "017_etat_stripe_persiste"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concierge_budget_jours",
        sa.Column("jour", sa.Date(), primary_key=True),
        sa.Column("cout_micro_usd", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("requetes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("concierge_budget_jours")
