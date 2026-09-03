"""Vague B / B2 — tarif du modèle local Nemotron (D12)

Revision ID: 014_pricing_nemotron_local
Revises: 013_consent_cgv_users
Create Date: 2026-09-03

Pourquoi
--------
Depuis B1 (78ae68c), `user_id` est obligatoire sur tout appel LLM agent et le
préflight de crédits ne saute plus. Or `model_pricing` ne connaissait que les
modèles Anthropic : un appel Free routé sur `gpu_nemotron/nemotron` levait
`UnknownModelError` — règle 6, on ne facture pas ce qu on ne sait pas
tarifer — et le tier Free ne répondait plus.

Décisions Sam (docs/vague-b/DECISIONS_SAM.md, 03/09/2026)
- D2/D6 : Free sur Nemotron 3.5 Lightning, local, Spark. « On fera des tests
  et on verra le vrai rendu ; si ce n est pas au niveau on passera sur Sonnet. »
- D12 : 0,2 crédit / 1 000 jetons en entrée, 1,0 en sortie (un cinquième de
  Sonnet : 1,0 / 5,0), autorisé free,pro,team. Avec les mesures du 19/08,
  une vingtaine d échanges Sophie/Olivia par jour sous le plafond Free de 300.

`model_name` = "nemotron-lightning", l identifiant EXACT servi par vLLM sur le
Spark (/v1/models, mesuré le 03/09) et déclaré dans llm_routing.yaml depuis A9.
Le service de crédits normalise "gpu_nemotron/nemotron" en "nemotron" puis
cherche la ligne ; le test test_b2_pricing_nemotron.py couvre les deux formes.

Idempotente (INSERT … ON CONFLICT), réversible (DELETE de la seule ligne
posée). Ne pas exécuter sur la base de production sans relecture de Sam.
"""
from alembic import op

revision = "014_pricing_nemotron_local"
down_revision = "013_consent_cgv_users"
branch_labels = None
depends_on = None

_MODEL = "nemotron-lightning"


def upgrade() -> None:
    op.execute(
        "INSERT INTO model_pricing "
        "(model_name, credits_per_1k_input, credits_per_1k_output, allowed_tiers, "
        " requires_opt_in, is_active, updated_at) "
        f"VALUES ('{_MODEL}', 0.200, 1.000, 'free,pro,team', false, true, now()) "
        "ON CONFLICT (model_name) DO UPDATE SET "
        "credits_per_1k_input = EXCLUDED.credits_per_1k_input, "
        "credits_per_1k_output = EXCLUDED.credits_per_1k_output, "
        "allowed_tiers = EXCLUDED.allowed_tiers, "
        "is_active = true, updated_at = now()"
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM model_pricing WHERE model_name = '{_MODEL}'")
