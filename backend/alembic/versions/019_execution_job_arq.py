"""Vague 1 / file C — identite du job ARQ sur l'execution (PROD-04, CAL-07)

Revision ID: 019_execution_job_arq
Revises: 015_free_50_credits_jour
Create Date: 2026-09-16

Trois colonnes nullables sur `executions` :

- `arq_job_id`      : identifiant du job ARQ courant, pose par la route avant
                      l'enfilage. Le worker ne marque plus FAILED, au demarrage,
                      qu'une execution RUNNING dont ce job est absent de Redis
                      (PROD-04 = CAL-11 : le redemarrage d'un worker tuait les
                      executions des autres).
- `arq_queue_name`  : file sur laquelle l'execution a ete enfilee, reutilisee
                      par /resume et /retry (CAL-07).
- `cancel_requested_at` : demande d'annulation cooperative, relue entre deux
                      agents (CAL-07).

Idempotente (verifie la presence des colonnes), reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "019_execution_job_arq"
down_revision = "018_budget_concierge"
branch_labels = None
depends_on = None


def _colonnes() -> set:
    return {c["name"] for c in inspect(op.get_bind()).get_columns("executions")}


def upgrade() -> None:
    presentes = _colonnes()
    if "arq_job_id" not in presentes:
        op.add_column("executions", sa.Column("arq_job_id", sa.String(64), nullable=True))
        op.create_index("ix_executions_arq_job_id", "executions", ["arq_job_id"])
    if "arq_queue_name" not in presentes:
        op.add_column("executions", sa.Column("arq_queue_name", sa.String(100), nullable=True))
    if "cancel_requested_at" not in presentes:
        op.add_column(
            "executions",
            sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    presentes = _colonnes()
    if "cancel_requested_at" in presentes:
        op.drop_column("executions", "cancel_requested_at")
    if "arq_queue_name" in presentes:
        op.drop_column("executions", "arq_queue_name")
    if "arq_job_id" in presentes:
        op.drop_index("ix_executions_arq_job_id", table_name="executions")
        op.drop_column("executions", "arq_job_id")
