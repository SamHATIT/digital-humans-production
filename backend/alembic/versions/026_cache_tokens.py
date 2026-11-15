"""Jetons du cache Anthropic sur credit_transactions.

Revision ID: 026_cache_tokens
Revises: 025_modeles_5_5

15/11/2026 : `tokens_input` (usage.input_tokens) exclut les jetons lus et
ecrits dans le cache ; le gain du cache n'etait mesurable nulle part.
Idempotente, reversible.
"""
import sqlalchemy as sa
from alembic import op

revision = "026_cache_tokens"
down_revision = "025_modeles_5_5"
branch_labels = None
depends_on = None

COLONNES = ("cache_read_tokens", "cache_creation_tokens")


def upgrade() -> None:
    existantes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("credit_transactions")}
    for c in COLONNES:
        if c not in existantes:
            op.add_column("credit_transactions", sa.Column(c, sa.Integer(), nullable=True))


def downgrade() -> None:
    existantes = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("credit_transactions")}
    for c in COLONNES:
        if c in existantes:
            op.drop_column("credit_transactions", c)
