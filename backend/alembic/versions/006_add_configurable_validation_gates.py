"""P2-Full: Add configurable validation gates columns

Revision ID: 006_validation_gates
Revises: 005_environments_git
Create Date: 2026-02-09

Adds:
- projects.validation_gates: JSONB config for which gates are enabled
- executions.pending_validation: JSONB for current pending gate info
- executions.validation_history: JSONB array of past validation decisions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic
revision = '006_validation_gates'
down_revision = '005_environments_git'
branch_labels = None
depends_on = None


def upgrade():
    # Project-level: which validation gates are enabled
    op.add_column('projects', sa.Column(
        'validation_gates', JSONB, server_default='{}', nullable=True
    ))

    # Execution-level: current pending validation gate (null = not paused)
    op.add_column('executions', sa.Column(
        'pending_validation', JSONB, nullable=True
    ))

    # Execution-level: history of all validation decisions
    op.add_column('executions', sa.Column(
        'validation_history', JSONB, server_default='[]', nullable=True
    ))


def downgrade():
    op.drop_column('executions', 'validation_history')
    op.drop_column('executions', 'pending_validation')
    op.drop_column('projects', 'validation_gates')
