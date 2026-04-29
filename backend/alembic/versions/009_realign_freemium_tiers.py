"""Phase 3 — Réalignement freemium 4-tier : free / pro / team / enterprise

Revision ID: 009_realign_freemium_tiers
Revises: 008_credits_tables
Create Date: 2026-04-29

Contexte
--------
Le code historique utilisait un modèle 3-tier (free / premium / enterprise) avec
Premium à 99 EUR incluant le BUILD. Les décisions du brief consolidé (26 + 29
avril 2026) actent un modèle 4-tier :

  Free        — Sophie + Olivia chat seul (Haiku)
  Pro    49€  — Équipe complète + SDS livrable, PAS de BUILD ni déploiement
  Team 1490€  — Pipeline complet jusqu'à sandbox, PAS de mise en prod
  Enterprise  — On-premise sur devis, prod négociée au contrat

Changements DB
--------------
1. Migrer les valeurs ``users.subscription_tier`` :
     'premium'    → 'team'        (Premium incluait le BUILD → équivalent à Team)
     'enterprise' → 'team' (par défaut, sauf override manuel pour vrais
                            contrats on-premise — à reclasser à la main)

2. Aucune contrainte CHECK n'existe sur la colonne (validation au niveau
   application via ``SubscriptionTier`` enum), donc rien à recréer.

3. ``tier_config`` et ``model_pricing`` sont déjà seedés correctement par 008
   (free / pro / team avec les bons prix et allowed_tiers). Aucune correction
   nécessaire.

Au moment où cette migration a été générée (29 avril 2026, env de dev), il
y avait 4 users en ``free`` et 0 en ``premium`` ou ``enterprise``. La migration
est donc un no-op en dev. Elle reste défensive pour tout autre environnement
(staging, prod future) où d'anciens comptes pourraient subsister.
"""
from alembic import op


# revision identifiers, used by Alembic
revision = "009_realign_freemium_tiers"
down_revision = "008_credits_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Migrate legacy 'premium' users → 'team' (preserves BUILD access semantics)
    op.execute(
        "UPDATE users SET subscription_tier = 'team' "
        "WHERE subscription_tier = 'premium'"
    )

    # Migrate legacy hosted 'enterprise' users → 'team'
    # NOTE : if some users were on a real on-premise contract, they should
    # have been reclassified manually before applying this migration.
    # The new 'enterprise' tier is reserved for on-premise / custom deals.
    op.execute(
        "UPDATE users SET subscription_tier = 'team' "
        "WHERE subscription_tier = 'enterprise'"
    )


def downgrade() -> None:
    # Best-effort rollback : we can't distinguish between users who were
    # originally 'premium' vs originally 'team', so we collapse both back to
    # 'premium' (the closest legacy equivalent for BUILD-enabled accounts).
    op.execute(
        "UPDATE users SET subscription_tier = 'premium' "
        "WHERE subscription_tier = 'team'"
    )
