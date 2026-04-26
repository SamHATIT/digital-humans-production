"""Phase 3.1 — Credits ledger : balances + transactions + pricing + tier_config

Revision ID: 008_credits_tables
Revises: 007_conv_agent_id
Create Date: 2026-04-26

Tables created
--------------
- credit_balances     : 1 row / user, current solde
- credit_transactions : append-only log
- model_pricing       : seed (haiku / sonnet / opus)
- tier_config         : seed (free / pro / team)

Seed values mirror MASTER_PLAN_V4 §1 :
- Sonnet par défaut sur les offres payantes ; Opus opt-in (team only).
- 1 crédit = 1 000 input tokens Sonnet équivalent.
- Pro = 49 EUR/mois, 2000 crédits/mois ; Free = 300 crédits/jour cap strict.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "008_credits_tables"
down_revision = "007_conv_agent_id"
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------
    # credit_balances
    # ------------------------------------------------------------------
    op.create_table(
        "credit_balances",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("included_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overage_credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_reset_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # credit_transactions
    # ------------------------------------------------------------------
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("model_used", sa.String(length=50), nullable=True),
        sa.Column("tokens_input", sa.Integer(), nullable=True),
        sa.Column("tokens_output", sa.Integer(), nullable=True),
        sa.Column("credits_consumed", sa.Integer(), nullable=False),
        sa.Column(
            "execution_id",
            sa.Integer(),
            sa.ForeignKey("executions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_credit_transactions_user",
        "credit_transactions",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_credit_transactions_execution",
        "credit_transactions",
        ["execution_id"],
    )

    # ------------------------------------------------------------------
    # model_pricing
    # ------------------------------------------------------------------
    op.create_table(
        "model_pricing",
        sa.Column("model_name", sa.String(length=50), primary_key=True),
        sa.Column("credits_per_1k_input", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("credits_per_1k_output", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("allowed_tiers", sa.String(length=255), nullable=False),
        sa.Column("requires_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # tier_config
    # ------------------------------------------------------------------
    op.create_table(
        "tier_config",
        sa.Column("tier_name", sa.String(length=20), primary_key=True),
        sa.Column("monthly_credits", sa.Integer(), nullable=False),
        sa.Column("daily_credits_cap", sa.Integer(), nullable=True),
        sa.Column("price_eur_monthly", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )

    # ------------------------------------------------------------------
    # Seeds — model_pricing
    #
    # Note model_name normalisation : on stocke l'API model_id Anthropic
    # (avec dashes : "claude-opus-4-7") pour matcher response.model_id côté
    # router. Plus la version "x.y" pour matcher le brief humain (alias).
    # CreditService fait un fallback substring sur opus/sonnet/haiku au
    # cas où.
    # ------------------------------------------------------------------
    pricing_table = sa.table(
        "model_pricing",
        sa.column("model_name", sa.String),
        sa.column("credits_per_1k_input", sa.Numeric),
        sa.column("credits_per_1k_output", sa.Numeric),
        sa.column("allowed_tiers", sa.String),
        sa.column("requires_opt_in", sa.Boolean),
    )
    op.bulk_insert(
        pricing_table,
        [
            # Anthropic API model_ids (dashes)
            {
                "model_name": "claude-haiku-4-5",
                "credits_per_1k_input": 0.300,
                "credits_per_1k_output": 1.500,
                "allowed_tiers": "free,pro,team",
                "requires_opt_in": False,
            },
            {
                "model_name": "claude-sonnet-4-6",
                "credits_per_1k_input": 1.000,
                "credits_per_1k_output": 5.000,
                "allowed_tiers": "pro,team",
                "requires_opt_in": False,
            },
            {
                "model_name": "claude-opus-4-7",
                "credits_per_1k_input": 5.000,
                "credits_per_1k_output": 25.000,
                "allowed_tiers": "team",
                "requires_opt_in": True,
            },
            # Human-friendly aliases (dot notation)
            {
                "model_name": "claude-haiku-4.5",
                "credits_per_1k_input": 0.300,
                "credits_per_1k_output": 1.500,
                "allowed_tiers": "free,pro,team",
                "requires_opt_in": False,
            },
            {
                "model_name": "claude-sonnet-4.6",
                "credits_per_1k_input": 1.000,
                "credits_per_1k_output": 5.000,
                "allowed_tiers": "pro,team",
                "requires_opt_in": False,
            },
            {
                "model_name": "claude-opus-4.7",
                "credits_per_1k_input": 5.000,
                "credits_per_1k_output": 25.000,
                "allowed_tiers": "team",
                "requires_opt_in": True,
            },
        ],
    )

    # ------------------------------------------------------------------
    # Seeds — tier_config
    # ------------------------------------------------------------------
    tier_table = sa.table(
        "tier_config",
        sa.column("tier_name", sa.String),
        sa.column("monthly_credits", sa.Integer),
        sa.column("daily_credits_cap", sa.Integer),
        sa.column("price_eur_monthly", sa.Numeric),
        sa.column("description", sa.Text),
    )
    op.bulk_insert(
        tier_table,
        [
            {
                "tier_name": "free",
                "monthly_credits": 0,
                "daily_credits_cap": 300,
                "price_eur_monthly": 0.00,
                "description": "Decouverte — Sophie + Olivia, 300 credits/jour cap strict",
            },
            {
                "tier_name": "pro",
                "monthly_credits": 2000,
                "daily_credits_cap": None,
                "price_eur_monthly": 49.00,
                "description": "Equipe complete + upload, Sonnet par defaut, 2000 credits/mois",
            },
            {
                "tier_name": "team",
                "monthly_credits": 100000,
                "daily_credits_cap": None,
                "price_eur_monthly": 1490.00,
                "description": "Sandbox + BUILD + Opus opt-in, 100k credits/mois",
            },
        ],
    )


def downgrade():
    op.drop_table("tier_config")
    op.drop_table("model_pricing")
    op.drop_index("idx_credit_transactions_execution", table_name="credit_transactions")
    op.drop_index("idx_credit_transactions_user", table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_table("credit_balances")
