"""N92: Ensure project_conversations.agent_id is indexed + backfilled to sophie.

Revision ID: 007_conv_agent_id
Revises: 006_validation_gates
Create Date: 2026-04-18

Context (Agent B — Contracts refonte):
- The ProjectConversation model already defines ``agent_id`` with a default of
  ``sophie``, but the HITL chat insert used to omit the column entirely. Rows
  created before the fix therefore have ``agent_id = NULL`` (or, on some older
  environments, no column at all if the model was deployed before the DDL).
- The chat history endpoint filters on ``agent_id == agent_id`` so those NULL
  rows are invisible — that's the root of the "chat history vide" bug.

This migration:
1. Adds the column if missing (idempotent; server_default = 'sophie').
2. Creates an index on ``agent_id`` BEFORE the mass UPDATE (performance on
   large installs).
3. Backfills NULLs with ``'sophie'`` — historically the only agent with chat.
"""

from alembic import op
import sqlalchemy as sa

revision = "007_conv_agent_id"
down_revision = "006_validation_gates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("project_conversations")}
    if "agent_id" not in existing_columns:
        op.add_column(
            "project_conversations",
            sa.Column("agent_id", sa.String(length=30), server_default="sophie", nullable=True),
        )

    existing_indexes = {i["name"] for i in inspector.get_indexes("project_conversations")}
    if "idx_conv_agent_id" not in existing_indexes:
        # CONCURRENTLY not possible inside the transactional Alembic runner;
        # DBAs can replace with CREATE INDEX CONCURRENTLY on very large tables.
        op.create_index(
            "idx_conv_agent_id",
            "project_conversations",
            ["agent_id"],
        )

    op.execute(
        "UPDATE project_conversations SET agent_id = 'sophie' "
        "WHERE agent_id IS NULL OR agent_id = ''"
    )


def downgrade() -> None:
    op.drop_index("idx_conv_agent_id", table_name="project_conversations")
    # agent_id column is kept — dropping it would be destructive and is not
    # necessary to revert the bug fix.
