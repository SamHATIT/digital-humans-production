#!/usr/bin/env python3
"""
Tests d'intégration pour Phase 6 - Types de Tâches WBS

Tests couverts:
1. WBSTaskType enum existe avec tous les types
2. WBSTaskExecutor enum existe
3. TASK_TYPE_CONFIG mapping est complet
4. Inference de type fonctionne
5. Filtrage automatisable vs manuel
6. TaskExecution model a les nouvelles colonnes
7. Marcus WBS prompt inclut task_type
"""

import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')


def test_wbs_task_type_enum():
    """Test 1: WBSTaskType enum exists with all types."""
    try:
        from app.models.wbs_task_type import WBSTaskType
        
        # Check key types exist
        assert WBSTaskType.SETUP_ENVIRONMENT.value == "setup_environment"
        assert WBSTaskType.DEV_APEX.value == "dev_apex"
        assert WBSTaskType.DEV_LWC.value == "dev_lwc"
        assert WBSTaskType.CONFIG_PROFILES.value == "config_profiles"
        assert WBSTaskType.TEST_UNIT.value == "test_unit"
        assert WBSTaskType.DEPLOY_EXECUTE.value == "deploy_execute"
        assert WBSTaskType.DOC_TRAINING.value == "doc_training"
        
        # Count total types
        total = len(list(WBSTaskType))
        assert total >= 20, f"Expected at least 20 task types, got {total}"
        
        print(f"✅ Test 1: WBSTaskType enum exists ({total} types)")
        return True
    except Exception as e:
        print(f"❌ Test 1: Error: {e}")
        return False


def test_wbs_task_executor_enum():
    """Test 2: WBSTaskExecutor enum exists."""
    try:
        from app.models.wbs_task_type import WBSTaskExecutor
        
        assert WBSTaskExecutor.MANUAL.value == "manual"
        assert WBSTaskExecutor.DIEGO.value == "diego"
        assert WBSTaskExecutor.ZARA.value == "zara"
        assert WBSTaskExecutor.RAJ.value == "raj"
        assert WBSTaskExecutor.ELENA.value == "elena"
        assert WBSTaskExecutor.JORDAN.value == "jordan"
        assert WBSTaskExecutor.LUCAS.value == "lucas"
        
        print("✅ Test 2: WBSTaskExecutor enum exists (8 executors)")
        return True
    except Exception as e:
        print(f"❌ Test 2: Error: {e}")
        return False


def test_task_type_config():
    """Test 3: TASK_TYPE_CONFIG mapping is complete."""
    try:
        from app.models.wbs_task_type import (
            WBSTaskType, TASK_TYPE_CONFIG, get_task_config
        )
        
        # Every task type should have a config
        for task_type in WBSTaskType:
            config = get_task_config(task_type)
            assert "executor" in config, f"{task_type.value} missing executor"
            assert "can_automate" in config, f"{task_type.value} missing can_automate"
            assert "validation" in config, f"{task_type.value} missing validation"
        
        print(f"✅ Test 3: TASK_TYPE_CONFIG complete ({len(TASK_TYPE_CONFIG)} mappings)")
        return True
    except Exception as e:
        print(f"❌ Test 3: Error: {e}")
        return False


def test_task_type_inference():
    """Test 4: Task type inference works."""
    try:
        from app.models.wbs_task_type import infer_task_type, WBSTaskType
        
        # Test inference
        assert infer_task_type("Create Customer object") == WBSTaskType.DEV_DATA_MODEL
        assert infer_task_type("Develop Apex trigger") == WBSTaskType.DEV_APEX
        assert infer_task_type("Build LWC component") == WBSTaskType.DEV_LWC
        assert infer_task_type("Configure profiles") == WBSTaskType.CONFIG_PROFILES
        assert infer_task_type("Run unit tests") == WBSTaskType.TEST_UNIT
        assert infer_task_type("Execute deployment") == WBSTaskType.DEPLOY_EXECUTE
        assert infer_task_type("Write user guide") == WBSTaskType.DOC_USER
        
        # Unknown should return GENERIC
        assert infer_task_type("Do something random") == WBSTaskType.GENERIC
        
        print("✅ Test 4: Task type inference works")
        return True
    except Exception as e:
        print(f"❌ Test 4: Error: {e}")
        return False


def test_automatable_filtering():
    """Test 5: Automatable vs manual filtering works."""
    try:
        from app.models.wbs_task_type import (
            WBSTaskType, is_automatable, 
            get_automatable_task_types, get_manual_task_types
        )
        
        # Check specific types
        assert is_automatable(WBSTaskType.DEV_APEX) == True
        assert is_automatable(WBSTaskType.DEV_LWC) == True
        assert is_automatable(WBSTaskType.SETUP_ENVIRONMENT) == False
        assert is_automatable(WBSTaskType.TEST_UAT) == False
        
        # Get lists
        automatable = get_automatable_task_types()
        manual = get_manual_task_types()
        
        assert len(automatable) > 0
        assert len(manual) > 0
        assert len(automatable) + len(manual) == len(list(WBSTaskType))
        
        print(f"✅ Test 5: Automatable filtering works ({len(automatable)} auto, {len(manual)} manual)")
        return True
    except Exception as e:
        print(f"❌ Test 5: Error: {e}")
        return False


def test_task_execution_model():
    """Test 6: TaskExecution model has new columns."""
    try:
        from app.models.task_execution import TaskExecution
        
        assert hasattr(TaskExecution, 'task_type'), "Missing task_type column"
        assert hasattr(TaskExecution, 'is_automatable'), "Missing is_automatable column"
        
        print("✅ Test 6: TaskExecution model has task_type and is_automatable")
        return True
    except Exception as e:
        print(f"❌ Test 6: Error: {e}")
        return False


def test_marcus_wbs_prompt():
    """Test 7: Marcus WBS prompt includes task_type."""
    try:
        with open('/root/workspace/digital-humans-production/backend/agents/roles/salesforce_solution_architect.py', 'r') as f:
            content = f.read()
        
        assert '"task_type"' in content, "task_type not in WBS prompt structure"
        assert 'TASK TYPES' in content, "TASK TYPES section not in prompt"
        assert 'dev_data_model' in content, "dev_data_model example not in prompt"
        
        print("✅ Test 7: Marcus WBS prompt includes task_type")
        return True
    except Exception as e:
        print(f"❌ Test 7: Error: {e}")
        return False


def test_database_columns():
    """Test 8: Database has new columns."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="172.17.0.1",
            database="digital_humans_db",
            user="digital_humans",
            password="DH_SecurePass2025!"
        )
        cur = conn.cursor()
        
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'task_executions' 
            AND column_name IN ('task_type', 'is_automatable')
        """)
        columns = [row[0] for row in cur.fetchall()]
        
        conn.close()
        
        assert 'task_type' in columns, "Missing task_type column"
        assert 'is_automatable' in columns, "Missing is_automatable column"
        
        print("✅ Test 8: Database has task_type and is_automatable columns")
        return True
    except Exception as e:
        print(f"❌ Test 8: Error: {e}")
        return False


# Run all tests
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 6 Integration Tests - WBS Task Types")
    print("=" * 60)
    
    results = []
    results.append(test_wbs_task_type_enum())
    results.append(test_wbs_task_executor_enum())
    results.append(test_task_type_config())
    results.append(test_task_type_inference())
    results.append(test_automatable_filtering())
    results.append(test_task_execution_model())
    results.append(test_marcus_wbs_prompt())
    results.append(test_database_columns())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All Phase 6 tests PASSED!")
    else:
        print("⚠️ Some tests failed")
    print("=" * 60)
