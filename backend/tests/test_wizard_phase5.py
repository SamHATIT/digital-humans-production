#!/usr/bin/env python3
"""
Tests d'intégration pour Phase 5 - Wizard Configuration

Scénarios testés:
1. Modèle Project a les nouveaux champs
2. Modèle ProjectCredential existe
3. Service encryption fonctionne
4. Routes wizard sont enregistrées
5. Validation des étapes du wizard
"""

import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')


def test_project_model_fields():
    """Test 1: Project model has wizard fields."""
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
    """Test 2: ProjectCredential model exists."""
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


def test_encryption_service():
    """Test 3: Encryption service works."""
    try:
        from app.utils.encryption import encrypt_value, decrypt_value
        
        test_value = "my-secret-token-12345"
        encrypted = encrypt_value(test_value)
        decrypted = decrypt_value(encrypted)
        
        assert encrypted != test_value, "Encryption should change the value"
        assert decrypted == test_value, "Decryption should return original value"
        assert len(encrypted) > len(test_value), "Encrypted should be longer"
        
        print("✅ Test 3: Encryption service works")
        return True
    except Exception as e:
        print(f"❌ Test 3: Error: {e}")
        return False


def test_wizard_routes_registered():
    """Test 4: Wizard routes are registered in main app."""
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
        
        print("✅ Test 4: Wizard routes registered (10 endpoints)")
        return True
    except Exception as e:
        print(f"❌ Test 4: Error: {e}")
        return False


def test_wizard_schemas():
    """Test 5: Wizard Pydantic schemas are valid."""
    try:
        from app.api.routes.wizard import (
            WizardStep1, WizardStep2, WizardStep3,
            WizardStep4, WizardStep5, WizardStep6,
            WizardProgressResponse, ConnectionTestResult
        )
        
        # Test schema instantiation
        step1 = WizardStep1(name="Test Project")
        assert step1.name == "Test Project"
        
        step2 = WizardStep2(project_type="greenfield")
        assert step2.project_type.value == "greenfield"
        
        step3 = WizardStep3(target_objective="sds_only")
        assert step3.target_objective.value == "sds_only"
        
        progress = WizardProgressResponse(
            project_id=1,
            project_name="Test",
            wizard_step=1,
            wizard_completed=False,
            status="draft"
        )
        assert progress.project_id == 1
        
        print("✅ Test 5: Wizard schemas are valid")
        return True
    except Exception as e:
        print(f"❌ Test 5: Error: {e}")
        return False


def test_database_migration():
    """Test 6: Database has new columns."""
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


# Run all tests
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 5 Integration Tests - Wizard Configuration")
    print("=" * 60)
    
    results = []
    results.append(test_project_model_fields())
    results.append(test_credential_model())
    results.append(test_encryption_service())
    results.append(test_wizard_routes_registered())
    results.append(test_wizard_schemas())
    results.append(test_database_migration())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All Phase 5 tests PASSED!")
    else:
        print("⚠️ Some tests failed")
    print("=" * 60)
