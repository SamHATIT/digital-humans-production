-- Migration: Freemium Model & Multi-Environment Support
-- Sections: 6.2, 6.3, 6.4, 9
-- Date: 2025-12-12

-- =====================================================
-- Section 9: Subscription Tier on Users
-- =====================================================

-- Create enum type for subscription tier
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscriptiontier') THEN
        CREATE TYPE subscriptiontier AS ENUM ('free', 'premium', 'enterprise');
    END IF;
END $$;

-- Add subscription columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier subscriptiontier DEFAULT 'free' NOT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_started_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);

-- Index for subscription queries
CREATE INDEX IF NOT EXISTS idx_users_subscription_tier ON users(subscription_tier);

-- =====================================================
-- Section 6.2: Project Environments (SFDX)
-- =====================================================

-- Create enum types
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'environmenttype') THEN
        CREATE TYPE environmenttype AS ENUM ('dev', 'qa', 'uat', 'staging', 'prod');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'authmethod') THEN
        CREATE TYPE authmethod AS ENUM ('jwt', 'web_login', 'password', 'access_token');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'connectionstatus') THEN
        CREATE TYPE connectionstatus AS ENUM ('not_tested', 'connected', 'failed', 'expired');
    END IF;
END $$;

-- Create project_environments table
CREATE TABLE IF NOT EXISTS project_environments (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identification
    environment_type environmenttype NOT NULL,
    alias VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    
    -- Salesforce Connection
    instance_url TEXT NOT NULL,
    org_id VARCHAR(18),
    username VARCHAR(255) NOT NULL,
    
    -- Authentication
    auth_method authmethod NOT NULL DEFAULT 'web_login',
    client_id_label VARCHAR(100),
    private_key_label VARCHAR(100),
    refresh_token_label VARCHAR(100),
    
    -- Connection Status
    connection_status connectionstatus DEFAULT 'not_tested',
    last_connection_test TIMESTAMP,
    last_connection_error TEXT,
    
    -- Metadata
    is_default BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(project_id, alias)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_project_environments_project ON project_environments(project_id);
CREATE INDEX IF NOT EXISTS idx_project_environments_type ON project_environments(environment_type);

-- =====================================================
-- Section 6.3: Project Git Config
-- =====================================================

-- Create enum types
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gitprovider') THEN
        CREATE TYPE gitprovider AS ENUM ('github', 'gitlab', 'bitbucket', 'azure_devops');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'branchstrategy') THEN
        CREATE TYPE branchstrategy AS ENUM ('trunk', 'feature_branch', 'gitflow');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'gitconnectionstatus') THEN
        CREATE TYPE gitconnectionstatus AS ENUM ('not_tested', 'connected', 'failed');
    END IF;
END $$;

-- Create project_git_config table
CREATE TABLE IF NOT EXISTS project_git_config (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Provider
    git_provider gitprovider NOT NULL,
    
    -- Repository
    repo_url TEXT NOT NULL,
    repo_name VARCHAR(255),
    default_branch VARCHAR(100) DEFAULT 'main',
    
    -- Authentication
    access_token_label VARCHAR(100),
    ssh_key_label VARCHAR(100),
    
    -- Connection Status
    connection_status gitconnectionstatus DEFAULT 'not_tested',
    last_connection_test TIMESTAMP,
    last_connection_error TEXT,
    
    -- Configuration
    auto_commit BOOLEAN DEFAULT TRUE,
    commit_message_template TEXT DEFAULT '[Digital Humans] {action}: {description}',
    branch_strategy branchstrategy DEFAULT 'feature_branch',
    feature_branch_prefix VARCHAR(50) DEFAULT 'feature/dh-',
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints (one config per project)
    UNIQUE(project_id)
);

-- Index
CREATE INDEX IF NOT EXISTS idx_project_git_config_project ON project_git_config(project_id);

-- =====================================================
-- Section 6.4: SDS Templates
-- =====================================================

-- Create sds_templates table
CREATE TABLE IF NOT EXISTS sds_templates (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(50) UNIQUE NOT NULL,
    
    -- Basic info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    language VARCHAR(10) DEFAULT 'fr',
    
    -- Template structure (JSON)
    template_structure JSONB NOT NULL,
    
    -- Styling
    header_logo_url TEXT,
    primary_color VARCHAR(7) DEFAULT '#1F4E79',
    secondary_color VARCHAR(7) DEFAULT '#2E75B6',
    font_family VARCHAR(100) DEFAULT 'Calibri',
    
    -- Document settings
    include_toc BOOLEAN DEFAULT TRUE,
    include_cover_page BOOLEAN DEFAULT TRUE,
    include_version_history BOOLEAN DEFAULT TRUE,
    page_numbering BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    is_default BOOLEAN DEFAULT FALSE,
    is_system BOOLEAN DEFAULT TRUE,
    created_by INTEGER REFERENCES users(id),
    organization_id INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX IF NOT EXISTS idx_sds_templates_template_id ON sds_templates(template_id);

-- Insert default templates
INSERT INTO sds_templates (template_id, name, description, language, template_structure, is_default, is_system)
VALUES 
    ('default', 'Template Standard', 'Template standard pour les documents SDS', 'fr', 
     '{"sections": [
        {"id": "1", "title": "Résumé Exécutif", "required": true},
        {"id": "2", "title": "Contexte Métier", "required": true},
        {"id": "3", "title": "Exigences Métier", "required": true},
        {"id": "4", "title": "Spécifications Fonctionnelles", "required": true},
        {"id": "5", "title": "Architecture Technique", "required": true},
        {"id": "6", "title": "Plan d''Implémentation", "required": true},
        {"id": "7", "title": "Stratégie de Test", "required": false},
        {"id": "8", "title": "Déploiement et Opérations", "required": false},
        {"id": "9", "title": "Formation et Adoption", "required": false},
        {"id": "A", "title": "Annexes", "required": true}
    ]}'::jsonb, TRUE, TRUE),
    
    ('default_en', 'Standard Template', 'Standard template for SDS documents', 'en',
     '{"sections": [
        {"id": "1", "title": "Executive Summary", "required": true},
        {"id": "2", "title": "Business Context", "required": true},
        {"id": "3", "title": "Business Requirements", "required": true},
        {"id": "4", "title": "Functional Specifications", "required": true},
        {"id": "5", "title": "Technical Architecture", "required": true},
        {"id": "6", "title": "Implementation Plan", "required": true},
        {"id": "7", "title": "Testing Strategy", "required": false},
        {"id": "8", "title": "Deployment & Operations", "required": false},
        {"id": "9", "title": "Training & Adoption", "required": false},
        {"id": "A", "title": "Appendices", "required": true}
    ]}'::jsonb, FALSE, TRUE),
    
    ('minimal', 'Template Minimal', 'Template simplifié pour petits projets', 'fr',
     '{"sections": [
        {"id": "1", "title": "Résumé", "required": true},
        {"id": "2", "title": "Exigences", "required": true},
        {"id": "3", "title": "Solution", "required": true},
        {"id": "4", "title": "Planning", "required": true}
    ]}'::jsonb, FALSE, TRUE)
ON CONFLICT (template_id) DO NOTHING;

-- =====================================================
-- Done
-- =====================================================
SELECT 'Migration freemium_and_environments completed' as status;
