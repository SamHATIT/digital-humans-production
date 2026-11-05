"""Tarifs credits des modeles Claude 5.5 (bascule Opus 5 -> 5.5, Sonnet 5 -> 5.5).

Revision ID: 025_modeles_5_5
Revises: 024_fusion_vague2

05/11/2026 — decision Sam : passer de 5 a 5.5 (ecart de qualite important),
au meme prix en credits que les modeles 5. Sans ligne `model_pricing`, un
modele est refuse a la reservation de credits (`UnknownModelError`) : la
bascule du YAML seule aurait coupe le palier Pro.

Opus 5.5 garde l'opt-in GL-22 (`requires_opt_in = true`) comme Opus 5.
Idempotente (UPSERT), reversible (supprime les deux lignes).
"""
import sqlalchemy as sa
from alembic import op

revision = "025_modeles_5_5"
down_revision = "024_fusion_vague2"
branch_labels = None
depends_on = None

#: (nouveau modele, modele 5 dont il reprend le tarif et les paliers)
MODELES = (
    ("claude-opus-5-5", "claude-opus-5"),
    ("claude-sonnet-5-5", "claude-sonnet-5"),
)


def upgrade() -> None:
    for nouveau, source in MODELES:
        op.execute(sa.text(
            "INSERT INTO model_pricing (model_name, credits_per_1k_input, "
            "credits_per_1k_output, allowed_tiers, requires_opt_in, is_active, updated_at) "
            "SELECT :n, credits_per_1k_input, credits_per_1k_output, allowed_tiers, "
            "requires_opt_in, true, now() FROM model_pricing WHERE model_name = :s "
            "ON CONFLICT (model_name) DO UPDATE SET "
            "credits_per_1k_input = EXCLUDED.credits_per_1k_input, "
            "credits_per_1k_output = EXCLUDED.credits_per_1k_output, "
            "allowed_tiers = EXCLUDED.allowed_tiers, "
            "requires_opt_in = EXCLUDED.requires_opt_in, "
            "is_active = true, updated_at = now()"
        ).bindparams(n=nouveau, s=source))
        # Le modele source doit exister : sinon l'INSERT ... SELECT n'ecrit rien,
        # en silence. On le verifie.
        bind = op.get_bind()
        ok = bind.execute(sa.text(
            "SELECT 1 FROM model_pricing WHERE model_name = :n"), {"n": nouveau}).first()
        if not ok:
            raise RuntimeError(
                f"025 : tarif source {source!r} introuvable — {nouveau!r} non cree")


def downgrade() -> None:
    for nouveau, _ in MODELES:
        op.execute(sa.text("DELETE FROM model_pricing WHERE model_name = :n").bindparams(n=nouveau))
