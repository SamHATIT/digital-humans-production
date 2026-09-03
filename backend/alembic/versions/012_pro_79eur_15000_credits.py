"""Vague A / lot A3 — Pro : 79 EUR/mois, description crédits réalignée

Revision ID: 012_pro_79eur_15000_credits
Revises: 011_expert_selection
Create Date: 2026-09-02

Décision Sam, `docs/vague-a/DECISIONS_SAM.md` :
- D1 (02/09) : Pro inclut 15 000 crédits/mois (mesure du 28/08 : SDS moyen
  ≈ 1 200 crédits, gros SDS ≈ 6 500-8 000, rentabilité à ≈ 38 SDS). La
  description "2000 crédits/mois" portée par `tier_config` (seedée en 008) est
  périmée et doit être réécrite.
- D4 (02/09) : mutation `tier_config.pro.price` → 79.00 — migration à
  **produire et tester, pas à exécuter sur prod**.

Ce que cette migration change réellement
-----------------------------------------
`monthly_credits` de la ligne `pro` est **déjà** à 15000 depuis la migration
010 (`010_pro_tier_marcus_opus`, 29 avril 2026, "Quota Pro = 2 SDS/mois +
buffer"). Cette migration-ci ne fait donc que :
1. porter `price_eur_monthly` de 49.00 à 79.00 (D4) ;
2. réécrire `description`, qui citait encore "2000 credits/mois" alors que la
   colonne `monthly_credits` elle-même vaut 15000 depuis 010 — la description
   n'avait jamais été mise à jour en même temps que le chiffre (D1).
`monthly_credits = 15000` est réaffirmé explicitement ci-dessous par
défensivité (état attendu, pas une valeur nouvelle) : si une base n'a pas
appliqué 010 pour une raison quelconque, cette migration ne doit pas laisser
Pro à 2000 crédits sous un prix à 79 EUR.

Ne pas exécuter sur la base de production sans relecture de Sam.
"""
from alembic import op


# revision identifiers, used by Alembic
# NB : alembic_version.version_num est un varchar(32) (défaut Alembic) — un
# identifiant de 33 caractères ou plus fait échouer le stamp avec
# StringDataRightTruncation (mesuré ici : "012_pro_tier_79_eur_15000_credits"
# fait 33 caractères et échoue ; "012_pro_79eur_15000_credits" en fait 27).
revision = "012_pro_79eur_15000_credits"
down_revision = "011_expert_selection"
branch_labels = None
depends_on = None


_NEW_DESCRIPTION = "Equipe complete + upload, Sonnet par defaut, 15000 credits/mois inclus"
_OLD_DESCRIPTION = "Equipe complete + upload, Sonnet par defaut, 2000 credits/mois"


def upgrade() -> None:
    op.execute(
        "UPDATE tier_config SET "
        "price_eur_monthly = 79.00, "
        "monthly_credits = 15000, "
        f"description = '{_NEW_DESCRIPTION}' "
        "WHERE tier_name = 'pro'"
    )


def downgrade() -> None:
    # Ne restaure PAS monthly_credits = 2000 : cette valeur a été portée à
    # 15000 par la migration 010, en amont de celle-ci dans la chaîne, et ce
    # n'est pas cette migration qui l'a changée. La défaire ici défairait 010
    # au passage. Seuls price_eur_monthly et description, effectivement
    # modifiés par upgrade() ci-dessus, sont restaurés.
    op.execute(
        "UPDATE tier_config SET "
        "price_eur_monthly = 49.00, "
        "monthly_credits = 15000, "
        f"description = '{_OLD_DESCRIPTION}' "
        "WHERE tier_name = 'pro'"
    )
