"""Vague 1 / file C — trace des degradations sur l'execution (GL-10)

Revision ID: 017_execution_degraded
Revises: 016_execution_job_arq
Create Date: 2026-09-16

`executions.degraded` : liste des degradations subies pendant l'execution.
Le 15/09, le RAG documentaire est tombe toute la journee (429 OpenAI) ; les
agents ont continue sans corpus et rien ne l'a trace. Le soir, il etait
impossible de dire quelles executions rejouer.

Forme : [{"motif": "rag_unavailable", "detail": "...", "at": "<iso8601>"}].

Idempotente, reversible.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = "017_execution_degraded"
down_revision = "016_execution_job_arq"
branch_labels = None
depends_on = None


def _colonnes() -> set:
    return {c["name"] for c in inspect(op.get_bind()).get_columns("executions")}


def upgrade() -> None:
    if "degraded" not in _colonnes():
        op.add_column(
            "executions",
            sa.Column("degraded", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    if "degraded" in _colonnes():
        op.drop_column("executions", "degraded")
