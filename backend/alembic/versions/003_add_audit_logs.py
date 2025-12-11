"""Add audit_logs table for CORE-001

Revision ID: 003_add_audit_logs
Revises: 002_add_artifacts_system
Create Date: 2025-12-11

CORE-001: Comprehensive audit logging system
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '003_add_audit_logs'
down_revision = '002_add_artifacts_system'
branch_labels = None
depends_on = None


def upgrade():
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        
        # When
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Who
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('actor_id', sa.String(100), nullable=True),
        sa.Column('actor_name', sa.String(200), nullable=True),
        
        # What
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('action_detail', sa.String(500), nullable=True),
        
        # On what
        sa.Column('entity_type', sa.String(50), nullable=True),
        sa.Column('entity_id', sa.String(100), nullable=True),
        sa.Column('entity_name', sa.String(500), nullable=True),
        
        # Changes
        sa.Column('old_value', postgresql.JSONB(), nullable=True),
        sa.Column('new_value', postgresql.JSONB(), nullable=True),
        
        # Context
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('execution_id', sa.Integer(), sa.ForeignKey('executions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('task_id', sa.String(50), nullable=True),
        
        # Additional metadata
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        
        # Request context
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        
        # Outcome
        sa.Column('success', sa.String(10), server_default='true'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
    )
    
    # Individual column indexes
    op.create_index('ix_audit_logs_id', 'audit_logs', ['id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_logs_actor_type', 'audit_logs', ['actor_type'])
    op.create_index('ix_audit_logs_actor_id', 'audit_logs', ['actor_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_entity_type', 'audit_logs', ['entity_type'])
    op.create_index('ix_audit_logs_entity_id', 'audit_logs', ['entity_id'])
    op.create_index('ix_audit_logs_project_id', 'audit_logs', ['project_id'])
    op.create_index('ix_audit_logs_execution_id', 'audit_logs', ['execution_id'])
    op.create_index('ix_audit_logs_task_id', 'audit_logs', ['task_id'])
    
    # Composite indexes for common queries
    op.create_index('ix_audit_project_timestamp', 'audit_logs', ['project_id', 'timestamp'])
    op.create_index('ix_audit_execution_timestamp', 'audit_logs', ['execution_id', 'timestamp'])
    op.create_index('ix_audit_actor_action', 'audit_logs', ['actor_type', 'action'])
    op.create_index('ix_audit_entity', 'audit_logs', ['entity_type', 'entity_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_audit_entity', 'audit_logs')
    op.drop_index('ix_audit_actor_action', 'audit_logs')
    op.drop_index('ix_audit_execution_timestamp', 'audit_logs')
    op.drop_index('ix_audit_project_timestamp', 'audit_logs')
    op.drop_index('ix_audit_logs_task_id', 'audit_logs')
    op.drop_index('ix_audit_logs_execution_id', 'audit_logs')
    op.drop_index('ix_audit_logs_project_id', 'audit_logs')
    op.drop_index('ix_audit_logs_entity_id', 'audit_logs')
    op.drop_index('ix_audit_logs_entity_type', 'audit_logs')
    op.drop_index('ix_audit_logs_action', 'audit_logs')
    op.drop_index('ix_audit_logs_actor_id', 'audit_logs')
    op.drop_index('ix_audit_logs_actor_type', 'audit_logs')
    op.drop_index('ix_audit_logs_timestamp', 'audit_logs')
    op.drop_index('ix_audit_logs_id', 'audit_logs')
    
    # Drop table
    op.drop_table('audit_logs')
