"""Phase 3 — Pro tier nuance : Marcus en Opus + bump quota

Revision ID: 010_pro_tier_marcus_opus
Revises: 009_realign_freemium_tiers
Create Date: 2026-04-29

Décision actée 29 avril 2026 (analyse coût Exec #147) :
- Marcus reste en Opus sur Pro (vitrine technique scrutée par les clients
  Salesforce). Les autres orchestrators (Sophie/Olivia/Emma) passent en Sonnet.
- Quota Pro = 2 SDS/mois inclus (overage en packs au-delà).

Coût SDS recalibré : ~$20.87 → ~6 957 crédits Sonnet équivalent.
Pour 2 SDS + buffer chat/itérations : ~15 000 crédits/mois.

Le gating runtime (Marcus seul peut utiliser Opus en Pro) sera branché
en Phase 3 Stripe, en même temps que la propagation de subscription_tier
dans les LLMRequest. Cette migration ne fait que les changements data.

Changements DB
--------------
1. tier_config : Pro monthly_credits 2 000 → 15 000
2. model_pricing : Opus allowed_tiers 'team' → 'pro,team'
   (la restriction agent-level Marcus-only sera enforcée côté code)
"""
from alembic import op


revision = "010_pro_tier_marcus_opus"
down_revision = "009_realign_freemium_tiers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Bump Pro monthly credits to cover 2 SDS/mois + buffer
    op.execute(
        "UPDATE tier_config SET monthly_credits = 15000 "
        "WHERE tier_name = 'pro'"
    )

    # 2. Allow Opus on Pro tier (agent-level gating handled in code:
    #    only Marcus can actually use Opus on Pro — see CreditService.preflight_check
    #    after Phase 3 Stripe integration).
    op.execute(
        "UPDATE model_pricing SET allowed_tiers = 'pro,team' "
        "WHERE model_name LIKE 'claude-opus%'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE tier_config SET monthly_credits = 2000 "
        "WHERE tier_name = 'pro'"
    )
    op.execute(
        "UPDATE model_pricing SET allowed_tiers = 'team' "
        "WHERE model_name LIKE 'claude-opus%'"
    )
