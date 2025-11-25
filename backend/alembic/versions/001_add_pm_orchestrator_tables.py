"""Add PM orchestrator tables

Revision ID: 001
Revises:
Create Date: 2025-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pm_orchestration table
    op.create_table('pm_orchestration',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=True),
        sa.Column('business_need', sa.Text(), nullable=False),
        sa.Column('business_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('prd_content', sa.Text(), nullable=True),
        sa.Column('user_stories', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('roadmap', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pm_status', sa.Enum('PENDING', 'GENERATING', 'COMPLETED', 'FAILED', name='pmstatus'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id')
    )
    op.create_index(op.f('ix_pm_orchestration_id'), 'pm_orchestration', ['id'], unique=False)

    # Create agent_deliverables table
    op.create_table('agent_deliverables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('execution_agent_id', sa.Integer(), nullable=True),
        sa.Column('deliverable_type', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_file_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['execution_agent_id'], ['execution_agents.id'], ),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['output_file_id'], ['outputs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_deliverables_agent_id'), 'agent_deliverables', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_deliverables_deliverable_type'), 'agent_deliverables', ['deliverable_type'], unique=False)
    op.create_index(op.f('ix_agent_deliverables_execution_id'), 'agent_deliverables', ['execution_id'], unique=False)
    op.create_index(op.f('ix_agent_deliverables_id'), 'agent_deliverables', ['id'], unique=False)

    # Create document_fusion table
    op.create_table('document_fusion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('source_deliverable_ids', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('fusion_type', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('output_file_id', sa.Integer(), nullable=True),
        sa.Column('fusion_status', sa.Enum('PENDING', 'FUSING', 'COMPLETED', 'FAILED', name='fusionstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['output_file_id'], ['outputs.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_fusion_execution_id'), 'document_fusion', ['execution_id'], unique=False)
    op.create_index(op.f('ix_document_fusion_id'), 'document_fusion', ['id'], unique=False)
    op.create_index(op.f('ix_document_fusion_project_id'), 'document_fusion', ['project_id'], unique=False)

    # Create training_content table
    op.create_table('training_content',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('training_guide', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('presentation_slides', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('training_guide_file_id', sa.Integer(), nullable=True),
        sa.Column('presentation_file_id', sa.Integer(), nullable=True),
        sa.Column('content_status', sa.Enum('PENDING', 'GENERATING', 'COMPLETED', 'FAILED', name='contentstatus'), nullable=False),
        sa.Column('formatting_status', sa.Enum('PENDING', 'FORMATTING', 'COMPLETED', 'FAILED', name='formattingstatus'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('content_generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('files_generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['presentation_file_id'], ['outputs.id'], ),
        sa.ForeignKeyConstraint(['training_guide_file_id'], ['outputs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_content_execution_id'), 'training_content', ['execution_id'], unique=False)
    op.create_index(op.f('ix_training_content_id'), 'training_content', ['id'], unique=False)

    # Create quality_gates table
    op.create_table('quality_gates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('execution_agent_id', sa.Integer(), nullable=True),
        sa.Column('gate_type', sa.String(length=100), nullable=False),
        sa.Column('expected_value', sa.Text(), nullable=True),
        sa.Column('actual_value', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('PASSED', 'FAILED', name='gatestatus'), nullable=False),
        sa.Column('validation_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['execution_agent_id'], ['execution_agents.id'], ),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quality_gates_agent_id'), 'quality_gates', ['agent_id'], unique=False)
    op.create_index(op.f('ix_quality_gates_execution_id'), 'quality_gates', ['execution_id'], unique=False)
    op.create_index(op.f('ix_quality_gates_id'), 'quality_gates', ['id'], unique=False)
    op.create_index(op.f('ix_quality_gates_status'), 'quality_gates', ['status'], unique=False)

    # Create agent_iterations table
    op.create_table('agent_iterations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('iteration_number', sa.Integer(), nullable=False),
        sa.Column('quality_gate_id', sa.Integer(), nullable=True),
        sa.Column('retry_reason', sa.Text(), nullable=True),
        sa.Column('new_deliverable_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.Enum('RETRYING', 'COMPLETED', 'FAILED', name='iterationstatus'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
        sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['new_deliverable_id'], ['agent_deliverables.id'], ),
        sa.ForeignKeyConstraint(['quality_gate_id'], ['quality_gates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_iterations_agent_id'), 'agent_iterations', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_iterations_execution_id'), 'agent_iterations', ['execution_id'], unique=False)
    op.create_index(op.f('ix_agent_iterations_id'), 'agent_iterations', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_agent_iterations_id'), table_name='agent_iterations')
    op.drop_index(op.f('ix_agent_iterations_execution_id'), table_name='agent_iterations')
    op.drop_index(op.f('ix_agent_iterations_agent_id'), table_name='agent_iterations')
    op.drop_table('agent_iterations')

    op.drop_index(op.f('ix_quality_gates_status'), table_name='quality_gates')
    op.drop_index(op.f('ix_quality_gates_id'), table_name='quality_gates')
    op.drop_index(op.f('ix_quality_gates_execution_id'), table_name='quality_gates')
    op.drop_index(op.f('ix_quality_gates_agent_id'), table_name='quality_gates')
    op.drop_table('quality_gates')

    op.drop_index(op.f('ix_training_content_id'), table_name='training_content')
    op.drop_index(op.f('ix_training_content_execution_id'), table_name='training_content')
    op.drop_table('training_content')

    op.drop_index(op.f('ix_document_fusion_project_id'), table_name='document_fusion')
    op.drop_index(op.f('ix_document_fusion_id'), table_name='document_fusion')
    op.drop_index(op.f('ix_document_fusion_execution_id'), table_name='document_fusion')
    op.drop_table('document_fusion')

    op.drop_index(op.f('ix_agent_deliverables_id'), table_name='agent_deliverables')
    op.drop_index(op.f('ix_agent_deliverables_execution_id'), table_name='agent_deliverables')
    op.drop_index(op.f('ix_agent_deliverables_deliverable_type'), table_name='agent_deliverables')
    op.drop_index(op.f('ix_agent_deliverables_agent_id'), table_name='agent_deliverables')
    op.drop_table('agent_deliverables')

    op.drop_index(op.f('ix_pm_orchestration_id'), table_name='pm_orchestration')
    op.drop_table('pm_orchestration')
