"""EMMA-P1-003: Add project configuration fields for wizard

Revision ID: 004_project_config
Revises: 003_add_audit_logs
Create Date: 2025-12-12

Adds fields for:
- Client information (name, contact, logo)
- Project type (greenfield/existing) and goal (sds_only/sds_and_build)
- Salesforce configuration (edition, org_id, instance_url)
- Wizard state tracking

Reference: SPEC_EMMA_SDS_WORKFLOW_V2.md Section 6.1
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '004_project_config'
down_revision = '003_add_audit_logs'
branch_labels = None
depends_on = None


def upgrade():
    # Client information
    op.add_column('projects', sa.Column('client_name', sa.String(255), nullable=True))
    op.add_column('projects', sa.Column('client_contact_name', sa.String(255), nullable=True))
    op.add_column('projects', sa.Column('client_contact_email', sa.String(255), nullable=True))
    op.add_column('projects', sa.Column('client_logo_url', sa.Text(), nullable=True))
    
    # Project type and goal
    op.add_column('projects', sa.Column('project_type', sa.String(50), server_default='greenfield', nullable=True))
    op.add_column('projects', sa.Column('project_goal', sa.String(50), server_default='sds_only', nullable=True))
    
    # Salesforce configuration
    op.add_column('projects', sa.Column('sf_edition', sa.String(50), nullable=True))
    op.add_column('projects', sa.Column('sf_org_id', sa.String(18), nullable=True))
    op.add_column('projects', sa.Column('sf_instance_url', sa.Text(), nullable=True))
    
    # Language and template
    op.add_column('projects', sa.Column('language', sa.String(10), server_default='fr', nullable=True))
    op.add_column('projects', sa.Column('sds_template_id', sa.String(50), server_default='default', nullable=True))
    
    # Wizard state tracking
    op.add_column('projects', sa.Column('wizard_completed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('projects', sa.Column('wizard_current_step', sa.Integer(), server_default='1', nullable=True))
    
    # Add indexes for common queries
    op.create_index('idx_projects_client_name', 'projects', ['client_name'], unique=False)
    op.create_index('idx_projects_project_type', 'projects', ['project_type'], unique=False)
    op.create_index('idx_projects_project_goal', 'projects', ['project_goal'], unique=False)


def downgrade():
    # Remove indexes
    op.drop_index('idx_projects_project_goal', table_name='projects')
    op.drop_index('idx_projects_project_type', table_name='projects')
    op.drop_index('idx_projects_client_name', table_name='projects')
    
    # Remove columns
    op.drop_column('projects', 'wizard_current_step')
    op.drop_column('projects', 'wizard_completed_at')
    op.drop_column('projects', 'sds_template_id')
    op.drop_column('projects', 'language')
    op.drop_column('projects', 'sf_instance_url')
    op.drop_column('projects', 'sf_org_id')
    op.drop_column('projects', 'sf_edition')
    op.drop_column('projects', 'project_goal')
    op.drop_column('projects', 'project_type')
    op.drop_column('projects', 'client_logo_url')
    op.drop_column('projects', 'client_contact_email')
    op.drop_column('projects', 'client_contact_name')
    op.drop_column('projects', 'client_name')
