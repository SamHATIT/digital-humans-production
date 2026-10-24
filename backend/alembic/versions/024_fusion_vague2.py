"""Fusion des tetes Alembic de la vague 2 (023a file A, 023c file C)

Revision ID: 024_fusion_vague2
Revises: 023a_rgpd03_effacements_comptes, 023c_consentement_opus
Create Date: 2026-10-24

Les files A et C sont parties de la meme tete 022 ; chacune a ajoute sa
revision. Cette revision ne fait que les reunir en une seule tete. Aucun
changement de schema.
"""

revision = "024_fusion_vague2"
down_revision = ("023a_rgpd03_effacements_comptes", "023c_consentement_opus")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
