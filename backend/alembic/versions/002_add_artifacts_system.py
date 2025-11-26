"""Add artifacts system tables

Revision ID: 002_add_artifacts_system
Revises: b959e26248d5
Create Date: 2025-11-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '002_add_artifacts_system'
down_revision = 'b959e26248d5'
branch_labels = None
depends_on = None


def upgrade():
    # Table execution_artifacts
    op.create_table(
        'execution_artifacts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('artifact_type', sa.String(50), nullable=False),
        sa.Column('artifact_code', sa.String(20), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('producer_agent', sa.String(20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('content', postgresql.JSONB(), nullable=False),
        sa.Column('parent_refs', postgresql.JSONB()),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('status_changed_at', sa.DateTime(timezone=True)),
        sa.Column('status_changed_by', sa.String(50)),
        sa.Column('rejection_reason', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "artifact_type IN ('requirement', 'business_req', 'use_case', 'question', 'adr', 'spec', 'code', 'config', 'test', 'doc')",
            name='valid_artifact_type'
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'pending_review', 'approved', 'rejected', 'superseded')",
            name='valid_artifact_status'
        ),
        sa.UniqueConstraint('execution_id', 'artifact_code', 'version', name='unique_artifact_version')
    )
    
    op.create_index('idx_artifacts_execution', 'execution_artifacts', ['execution_id'])
    op.create_index('idx_artifacts_type', 'execution_artifacts', ['artifact_type'])
    op.create_index('idx_artifacts_code', 'execution_artifacts', ['artifact_code'])
    op.create_index('idx_artifacts_status', 'execution_artifacts', ['status'])
    op.create_index('idx_artifacts_current', 'execution_artifacts', ['execution_id', 'is_current'], postgresql_where=sa.text('is_current = true'))
    op.create_index('idx_artifacts_content', 'execution_artifacts', ['content'], postgresql_using='gin')
    op.create_index('idx_artifacts_refs', 'execution_artifacts', ['parent_refs'], postgresql_using='gin')

    # Table validation_gates
    op.create_table(
        'validation_gates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('gate_number', sa.Integer(), nullable=False),
        sa.Column('gate_name', sa.String(50), nullable=False),
        sa.Column('phase', sa.String(50), nullable=False),
        sa.Column('artifact_types', postgresql.JSONB(), nullable=False),
        sa.Column('artifacts_count', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('submitted_at', sa.DateTime(timezone=True)),
        sa.Column('validated_at', sa.DateTime(timezone=True)),
        sa.Column('validated_by', sa.String(50)),
        sa.Column('rejection_reason', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('gate_number >= 1 AND gate_number <= 6', name='valid_gate_number'),
        sa.CheckConstraint("status IN ('pending', 'ready', 'approved', 'rejected')", name='valid_gate_status'),
        sa.UniqueConstraint('execution_id', 'gate_number', name='unique_gate_per_execution')
    )
    
    op.create_index('idx_gates_execution', 'validation_gates', ['execution_id'])
    op.create_index('idx_gates_status', 'validation_gates', ['status'])

    # Table agent_questions
    op.create_table(
        'agent_questions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_code', sa.String(20), nullable=False),
        sa.Column('from_agent', sa.String(20), nullable=False),
        sa.Column('to_agent', sa.String(20), nullable=False),
        sa.Column('context', sa.Text(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('related_artifacts', postgresql.JSONB()),
        sa.Column('answer', sa.Text()),
        sa.Column('recommendation', sa.Text()),
        sa.Column('answered_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'answered')", name='valid_question_status'),
        sa.UniqueConstraint('execution_id', 'question_code', name='unique_question_code')
    )
    
    op.create_index('idx_questions_execution', 'agent_questions', ['execution_id'])
    op.create_index('idx_questions_status', 'agent_questions', ['status'])
    op.create_index('idx_questions_to_agent', 'agent_questions', ['to_agent', 'status'])


def downgrade():
    op.drop_table('agent_questions')
    op.drop_table('validation_gates')
    op.drop_table('execution_artifacts')
