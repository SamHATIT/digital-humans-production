"""Free : 50 crédits par jour (Sam, 05/09/2026)

Revision ID: 015_free_50_credits_jour
Revises: 014_pricing_nemotron_local
Create Date: 2026-09-05

Mesure du 05/09, premier parcours Free réel : un échange Sophie sur Nemotron
(≈ 620 jetons entrée / 65 sortie) coûte 0,19 crédit au tarif de la 014, mais
`credit_transactions.credits_consumed` est un entier arrondi vers le haut :
1 crédit par message. Le plafond de 300 valait donc ≈ 300 messages/jour.

Sam : « 300 c est un peu beaucoup ; si la qualité est là, allons-y pour 50.
J ai aussi envie de convertir. » → 50 crédits/jour ≈ 50 échanges, et une
raison de passer Pro. Une seule source (tier_config, D9) : Pricing.tsx et le
prompt de Sophie suivent sans modification.

Idempotente, réversible (retour à 300). Ne pas exécuter sur prod sans relecture.
"""
from alembic import op

revision = "015_free_50_credits_jour"
down_revision = "014_pricing_nemotron_local"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE tier_config SET daily_credits_cap = 50, "
        "description = 'Découverte — Sophie + Olivia, 50 crédits/jour cap strict' "
        "WHERE tier_name = 'free'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tier_config SET daily_credits_cap = 300, "
        "description = 'Découverte — Sophie + Olivia, 300 crédits/jour cap strict' "
        "WHERE tier_name = 'free'"
    )
