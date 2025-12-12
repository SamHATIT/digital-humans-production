"""EMMA-P1-004: Add project_environments and project_git_config tables

Revision ID: 005_environments_git
Revises: 004_project_config
Create Date: 2025-12-12

Adds tables for:
- project_environments: SFDX sandbox connections per project
- project_git_config: Git repository configuration per project

Both tables store encrypted credentials for security.

Reference: SPEC_EMMA_SDS_WORKFLOW_V2.md Sections 6.2 and 6.3
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '005_environments_git'
down_revision = '004_project_config'
branch_labels = None
depends_on = None


def upgrade():
    # ========================
    # Table: project_environments
    # ========================
    op.create_table(
        'project_environments',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        
        # Identification
        sa.Column('environment_type', sa.String(50), nullable=False),  # dev, qa, uat, staging, prod
        sa.Column('alias', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        
        # Salesforce connection
        sa.Column('instance_url', sa.Text(), nullable=False),
        sa.Column('org_id', sa.String(18), nullable=True),
        sa.Column('username', sa.String(255), nullable=False),
        
        # Authentication (encrypted)
        sa.Column('auth_method', sa.String(50), nullable=False, server_default='web_login'),  # jwt, web_login, password
        sa.Column('encrypted_client_id', sa.Text(), nullable=True),
        sa.Column('encrypted_client_secret', sa.Text(), nullable=True),
        sa.Column('encrypted_private_key', sa.Text(), nullable=True),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('encrypted_security_token', sa.Text(), nullable=True),
        
        # Status
        sa.Column('connection_status', sa.String(50), server_default='not_tested'),  # not_tested, connected, failed, expired
        sa.Column('last_connection_test', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_connection_error', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Indexes for project_environments
    op.create_index('idx_project_environments_project', 'project_environments', ['project_id'])
    op.create_index('idx_project_environments_type', 'project_environments', ['environment_type'])
    
    # Unique constraints
    op.create_unique_constraint('uq_project_env_alias', 'project_environments', ['project_id', 'alias'])
    
    # ========================
    # Table: project_git_config
    # ========================
    op.create_table(
        'project_git_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        
        # Provider
        sa.Column('git_provider', sa.String(50), nullable=False),  # github, gitlab, bitbucket, azure_devops
        
        # Repository
        sa.Column('repo_url', sa.Text(), nullable=False),
        sa.Column('repo_name', sa.String(255), nullable=True),
        sa.Column('default_branch', sa.String(100), server_default='main'),
        
        # Authentication (encrypted)
        sa.Column('encrypted_access_token', sa.Text(), nullable=False),
        sa.Column('encrypted_ssh_key', sa.Text(), nullable=True),
        
        # Status
        sa.Column('connection_status', sa.String(50), server_default='not_tested'),
        sa.Column('last_connection_test', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_connection_error', sa.Text(), nullable=True),
        
        # Configuration
        sa.Column('auto_commit', sa.Boolean(), server_default='true'),
        sa.Column('commit_message_template', sa.Text(), server_default='[Digital Humans] {action}: {description}'),
        sa.Column('branch_strategy', sa.String(50), server_default='feature_branch'),  # trunk, feature_branch, gitflow
        
        # Metadata
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Indexes for project_git_config
    op.create_index('idx_project_git_config_project', 'project_git_config', ['project_id'])
    op.create_index('idx_project_git_config_provider', 'project_git_config', ['git_provider'])
    
    # Unique constraint - one git config per project
    op.create_unique_constraint('uq_project_git_project', 'project_git_config', ['project_id'])


def downgrade():
    # Drop project_git_config
    op.drop_constraint('uq_project_git_project', 'project_git_config', type_='unique')
    op.drop_index('idx_project_git_config_provider', table_name='project_git_config')
    op.drop_index('idx_project_git_config_project', table_name='project_git_config')
    op.drop_table('project_git_config')
    
    # Drop project_environments
    op.drop_constraint('uq_project_env_alias', 'project_environments', type_='unique')
    op.drop_index('idx_project_environments_type', table_name='project_environments')
    op.drop_index('idx_project_environments_project', table_name='project_environments')
    op.drop_table('project_environments')
