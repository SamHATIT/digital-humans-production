#!/usr/bin/env python3
"""
Tests d'intégration pour Phase 5 - Wizard Configuration

Tests couverts:
1. P5-001: Project model has wizard fields
2. P5-001: ProjectCredential model exists
3. P5-003: CredentialEncryption service (spec 7.1)
4. P5-003: EnvironmentService (spec 7.2)
5. P5-001/P5-002: Wizard routes registered
6. P5-001: Database migration applied
"""

import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

import os
# Set env for tests
os.environ.setdefault('SECRET_KEY', 'test-secret-key-for-encryption')


def test_project_model_fields():
    """Test P5-001: Project model has wizard fields."""
    try:
        from app.models.project import Project, ProjectType, TargetObjective
        
        # Check new fields exist
        assert hasattr(Project, 'project_code'), "Missing project_code"
        assert hasattr(Project, 'client_name'), "Missing client_name"
        assert hasattr(Project, 'project_type'), "Missing project_type"
        assert hasattr(Project, 'target_objective'), "Missing target_objective"
        assert hasattr(Project, 'sf_instance_url'), "Missing sf_instance_url"
        assert hasattr(Project, 'git_repo_url'), "Missing git_repo_url"
        assert hasattr(Project, 'wizard_step'), "Missing wizard_step"
        assert hasattr(Project, 'wizard_completed'), "Missing wizard_completed"
        
        # Check enums
        assert ProjectType.GREENFIELD.value == "greenfield"
        assert TargetObjective.SDS_ONLY.value == "sds_only"
        
        print("✅ Test 1: Project model has all wizard fields")
        return True
    except Exception as e:
        print(f"❌ Test 1: Error: {e}")
        return False


def test_credential_model():
    """Test P5-001: ProjectCredential model exists."""
    try:
        from app.models.project_credential import ProjectCredential, CredentialType
        
        assert hasattr(ProjectCredential, 'project_id'), "Missing project_id"
        assert hasattr(ProjectCredential, 'credential_type'), "Missing credential_type"
        assert hasattr(ProjectCredential, 'encrypted_value'), "Missing encrypted_value"
        
        assert CredentialType.SALESFORCE_TOKEN.value == "salesforce_token"
        assert CredentialType.GIT_TOKEN.value == "git_token"
        
        print("✅ Test 2: ProjectCredential model exists")
        return True
    except Exception as e:
        print(f"❌ Test 2: Error: {e}")
        return False


def test_credential_encryption_service():
    """Test P5-003: CredentialEncryption per spec 7.1."""
    try:
        from app.utils.encryption import (
            CredentialEncryption,
            get_encryption,
            encrypt_credential,
            decrypt_credential,
            generate_encryption_key
        )
        
        # Test class exists with correct methods
        encryption = get_encryption()
        assert hasattr(encryption, 'encrypt'), "Missing encrypt method"
        assert hasattr(encryption, 'decrypt'), "Missing decrypt method"
        assert hasattr(encryption, 'fernet'), "Missing fernet property"
        
        # Test encryption/decryption
        test_value = "my-secret-access-token-12345"
        encrypted = encrypt_credential(test_value)
        decrypted = decrypt_credential(encrypted)
        
        assert encrypted != test_value, "Encryption should change the value"
        assert decrypted == test_value, "Decryption should return original value"
        
        # Test None handling
        assert encrypt_credential(None) is None, "Should handle None input"
        assert decrypt_credential(None) is None, "Should handle None input"
        
        # Test key generation utility
        new_key = generate_encryption_key()
        assert len(new_key) > 20, "Key should be substantial"
        
        print("✅ Test 3: CredentialEncryption service works (spec 7.1)")
        return True
    except Exception as e:
        print(f"❌ Test 3: Error: {e}")
        return False


def test_environment_service():
    """Test P5-003: EnvironmentService per spec 7.2."""
    try:
        from app.services.environment_service import EnvironmentService, get_environment_service
        
        # Test class exists with correct methods
        assert hasattr(EnvironmentService, 'store_credential'), "Missing store_credential"
        assert hasattr(EnvironmentService, 'get_credential'), "Missing get_credential"
        assert hasattr(EnvironmentService, 'delete_credential'), "Missing delete_credential"
        assert hasattr(EnvironmentService, 'rotate_credential'), "Missing rotate_credential"
        assert hasattr(EnvironmentService, 'get_all_credentials'), "Missing get_all_credentials"
        
        # Test connection methods
        assert hasattr(EnvironmentService, 'test_salesforce_connection'), "Missing test_salesforce_connection"
        assert hasattr(EnvironmentService, 'test_sfdx_jwt_connection'), "Missing test_sfdx_jwt_connection"
        assert hasattr(EnvironmentService, 'test_sfdx_web_connection'), "Missing test_sfdx_web_connection"
        assert hasattr(EnvironmentService, 'test_git_connection'), "Missing test_git_connection"
        
        print("✅ Test 4: EnvironmentService exists with all methods (spec 7.2)")
        return True
    except Exception as e:
        print(f"❌ Test 4: Error: {e}")
        return False


def test_wizard_routes_registered():
    """Test P5-001/P5-002: Wizard routes are registered."""
    try:
        # Check that wizard is imported in main.py
        with open('/root/workspace/digital-humans-production/backend/app/main.py', 'r') as f:
            content = f.read()
        
        assert 'wizard' in content, "wizard not imported in main.py"
        assert 'wizard.router' in content, "wizard.router not included"
        
        # Check wizard routes file has all endpoints
        with open('/root/workspace/digital-humans-production/backend/app/api/routes/wizard.py', 'r') as f:
            wizard_content = f.read()
        
        endpoints = [
            '/create',
            '/{project_id}/step/1',
            '/{project_id}/step/2',
            '/{project_id}/step/3',
            '/{project_id}/step/4',
            '/{project_id}/step/5',
            '/{project_id}/step/6',
            '/{project_id}/progress',
            '/{project_id}/test/salesforce',
            '/{project_id}/test/git'
        ]
        
        for endpoint in endpoints:
            assert endpoint in wizard_content, f"Missing endpoint: {endpoint}"
        
        # Check uses EnvironmentService
        assert 'EnvironmentService' in wizard_content or 'environment_service' in wizard_content, \
            "Should use EnvironmentService"
        
        print("✅ Test 5: Wizard routes registered (10 endpoints, uses EnvironmentService)")
        return True
    except Exception as e:
        print(f"❌ Test 5: Error: {e}")
        return False


def test_database_migration():
    """Test P5-001: Database has new columns."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="172.17.0.1",
            database="digital_humans_db",
            user="digital_humans",
            password="DH_SecurePass2025!"
        )
        cur = conn.cursor()
        
        # Check projects table columns
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'projects' 
            AND column_name IN ('wizard_step', 'wizard_completed', 'project_type', 'target_objective')
        """)
        columns = [row[0] for row in cur.fetchall()]
        
        assert 'wizard_step' in columns, "Missing wizard_step column"
        assert 'wizard_completed' in columns, "Missing wizard_completed column"
        
        # Check project_credentials table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'project_credentials'
            )
        """)
        exists = cur.fetchone()[0]
        assert exists, "project_credentials table missing"
        
        conn.close()
        
        print("✅ Test 6: Database migration applied")
        return True
    except Exception as e:
        print(f"❌ Test 6: Error: {e}")
        return False


def test_connection_validator_integration():
    """Test P5-002: ConnectionValidator integrates with routes."""
    try:
        with open('/root/workspace/digital-humans-production/backend/app/api/routes/wizard.py', 'r') as f:
            wizard_content = f.read()
        
        # Check connection_validator is used in test endpoints
        assert 'connection_validator' in wizard_content or 'environment_service' in wizard_content, \
            "Should use validation service"
        
        # Check test endpoints call real validation
        assert 'test_salesforce_connection' in wizard_content, "Should call test_salesforce_connection"
        assert 'test_git_connection' in wizard_content, "Should call test_git_connection"
        
        print("✅ Test 7: Connection validation integrated")
        return True
    except Exception as e:
        print(f"❌ Test 7: Error: {e}")
        return False


# Run all tests
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 5 Integration Tests - Wizard Configuration")
    print("  P5-001: Backend Endpoints")
    print("  P5-002: Validation Service") 
    print("  P5-003: Encryption & Environment Service")
    print("=" * 60)
    
    results = []
    results.append(test_project_model_fields())
    results.append(test_credential_model())
    results.append(test_credential_encryption_service())
    results.append(test_environment_service())
    results.append(test_wizard_routes_registered())
    results.append(test_database_migration())
    results.append(test_connection_validator_integration())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All Phase 5 Backend tests PASSED!")
    else:
        print("⚠️ Some tests failed")
    print("=" * 60)
