-- Migration: Phase 5 - Wizard Configuration
-- Date: 2025-12-12
-- Description: Add wizard fields to projects table and create credentials table

-- 1. Add new enum types
DO $$ BEGIN
    CREATE TYPE project_type AS ENUM ('greenfield', 'existing');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE target_objective AS ENUM ('sds_only', 'sds_and_build');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE credential_type AS ENUM ('salesforce_token', 'salesforce_refresh_token', 'git_token', 'git_ssh_key');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- 2. Add new columns to projects table
ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_code VARCHAR(50);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_name VARCHAR(200);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_contact_name VARCHAR(200);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_contact_email VARCHAR(200);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_contact_phone VARCHAR(50);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS start_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS end_date TIMESTAMP WITH TIME ZONE;

-- Project type and objective
ALTER TABLE projects ADD COLUMN IF NOT EXISTS project_type project_type DEFAULT 'greenfield';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS target_objective target_objective DEFAULT 'sds_only';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE;

-- Salesforce connection
ALTER TABLE projects ADD COLUMN IF NOT EXISTS sf_instance_url VARCHAR(500);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS sf_username VARCHAR(200);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS sf_connected BOOLEAN DEFAULT FALSE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS sf_connection_date TIMESTAMP WITH TIME ZONE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS sf_org_id VARCHAR(50);

-- Git connection
ALTER TABLE projects ADD COLUMN IF NOT EXISTS git_repo_url VARCHAR(500);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS git_branch VARCHAR(100) DEFAULT 'main';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS git_connected BOOLEAN DEFAULT FALSE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS git_connection_date TIMESTAMP WITH TIME ZONE;

-- Agent configuration
ALTER TABLE projects ADD COLUMN IF NOT EXISTS selected_sds_agents JSONB DEFAULT '["qa", "devops", "data", "trainer"]';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS agent_parameters JSONB;

-- Wizard progress
ALTER TABLE projects ADD COLUMN IF NOT EXISTS wizard_step INTEGER DEFAULT 1;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS wizard_completed BOOLEAN DEFAULT FALSE;

-- 3. Create project_credentials table
CREATE TABLE IF NOT EXISTS project_credentials (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    credential_type credential_type NOT NULL,
    encrypted_value TEXT NOT NULL,
    label VARCHAR(200),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster credential lookups
CREATE INDEX IF NOT EXISTS idx_project_credentials_project_type 
ON project_credentials(project_id, credential_type);

-- 4. Update trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_project_credentials_updated_at ON project_credentials;
CREATE TRIGGER update_project_credentials_updated_at
    BEFORE UPDATE ON project_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Done
SELECT 'Migration wizard_phase5 completed' as status;
