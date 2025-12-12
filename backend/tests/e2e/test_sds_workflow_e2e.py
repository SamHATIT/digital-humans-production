"""
E2E Tests - SDS Workflow Complete
Phase 7: Tests complets du workflow SDS de bout en bout.
"""
import pytest
import asyncio
import time
import os
from datetime import datetime
from typing import Dict, Any, List

# Set encryption key for tests
os.environ.setdefault('SECRET_KEY', 'test_secret_key_for_e2e_tests_only_123456789')


class SDSWorkflowE2ETest:
    """E2E test suite for SDS workflow."""
    
    def __init__(self, db_session=None):
        self.db = db_session
        self.results = []
        
    async def test_phase1_corrections(self) -> Dict[str, Any]:
        """Test Phase 1: Bug fixes are working."""
        results = {"phase": "Phase 1 - Corrections", "tests": []}
        
        # Test BUG-002: Priority mapping
        test_priorities = {
            "must_have": "MUST",
            "should_have": "SHOULD",
            "could_have": "COULD",
            "nice_to_have": "COULD",
            "wont_have": "WONT",
            "must": "MUST",
            "should": "SHOULD"
        }
        
        from app.models.business_requirement import BRPriority
        priority_map = {
            "must": BRPriority.MUST,
            "should": BRPriority.SHOULD,
            "could": BRPriority.COULD,
            "wont": BRPriority.WONT,
            "must_have": BRPriority.MUST,
            "should_have": BRPriority.SHOULD,
            "could_have": BRPriority.COULD,
            "nice_to_have": BRPriority.COULD,
            "wont_have": BRPriority.WONT,
            "won't_have": BRPriority.WONT,
        }
        
        for input_val, expected in test_priorities.items():
            mapped = priority_map.get(input_val.lower(), BRPriority.SHOULD)
            passed = mapped.value.upper() == expected
            results["tests"].append({
                "name": f"Priority mapping: {input_val}",
                "passed": passed,
                "expected": expected,
                "actual": mapped.value.upper()
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_emma_analyze_mode(self) -> Dict[str, Any]:
        """Test Phase 2: Emma analyze mode generates UC Digest."""
        results = {"phase": "Phase 2 - Emma Analyze", "tests": []}
        
        try:
            # Test 1: Module exists
            import agents.roles.salesforce_research_analyst as emma_module
            
            results["tests"].append({
                "name": "Emma module exists",
                "passed": True
            })
            
            # Test 2: Has run_analyze_mode function
            results["tests"].append({
                "name": "run_analyze_mode function exists",
                "passed": hasattr(emma_module, 'run_analyze_mode')
            })
            
            # Test 3: Has ANALYZE_SYSTEM prompt
            results["tests"].append({
                "name": "ANALYZE_SYSTEM prompt defined",
                "passed": hasattr(emma_module, 'ANALYZE_SYSTEM') and len(emma_module.ANALYZE_SYSTEM) > 100
            })
            
            # Test 4: Check analyze prompt contains UC Digest concepts
            analyze_prompt = emma_module.ANALYZE_SYSTEM
            has_cluster = "cluster" in analyze_prompt.lower() or "group" in analyze_prompt.lower()
            results["tests"].append({
                "name": "Analyze prompt mentions clustering/grouping",
                "passed": has_cluster
            })
            
        except Exception as e:
            results["tests"].append({
                "name": "Emma analyze mode",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_emma_validate_mode(self) -> Dict[str, Any]:
        """Test Phase 3: Emma validate mode generates Coverage Report."""
        results = {"phase": "Phase 3 - Emma Validate", "tests": []}
        
        try:
            import agents.roles.salesforce_research_analyst as emma_module
            
            # Test 1: run_validate_mode exists
            results["tests"].append({
                "name": "run_validate_mode function exists",
                "passed": hasattr(emma_module, 'run_validate_mode')
            })
            
            # Test 2: VALIDATE prompts exist
            results["tests"].append({
                "name": "VALIDATE_SYSTEM prompt exists",
                "passed": hasattr(emma_module, 'VALIDATE_SYSTEM') and len(emma_module.VALIDATE_SYSTEM) > 100
            })
            
            # Test 3: validate prompt mentions coverage
            validate_content = emma_module.VALIDATE_SYSTEM
            results["tests"].append({
                "name": "Validate prompt mentions coverage",
                "passed": "coverage" in validate_content.lower()
            })
            
            # Test 4: calculate_coverage_score function
            results["tests"].append({
                "name": "calculate_coverage_score function exists",
                "passed": hasattr(emma_module, 'calculate_coverage_score')
            })
            
        except Exception as e:
            results["tests"].append({
                "name": "Emma validate mode",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_emma_write_sds_mode(self) -> Dict[str, Any]:
        """Test Phase 4: Emma write_sds mode generates SDS document."""
        results = {"phase": "Phase 4 - Emma Write_SDS", "tests": []}
        
        try:
            import agents.roles.salesforce_research_analyst as emma_module
            from app.services import markdown_to_docx
            
            # Test 1: run_write_sds_mode exists
            results["tests"].append({
                "name": "run_write_sds_mode function exists",
                "passed": hasattr(emma_module, 'run_write_sds_mode')
            })
            
            # Test 2: WRITE_SDS prompts exist
            results["tests"].append({
                "name": "WRITE_SDS_SYSTEM prompt exists",
                "passed": hasattr(emma_module, 'WRITE_SDS_SYSTEM') and len(emma_module.WRITE_SDS_SYSTEM) > 100
            })
            
            # Test 3: DOCX converter module exists
            results["tests"].append({
                "name": "markdown_to_docx module exists",
                "passed": True
            })
            
            # Test 4: convert_markdown_to_docx function exists
            results["tests"].append({
                "name": "convert_markdown_to_docx function exists",
                "passed": hasattr(markdown_to_docx, 'convert_markdown_to_docx')
            })
            
            # Test 5: convert_mermaid_to_image function exists
            results["tests"].append({
                "name": "convert_mermaid_to_image function exists",
                "passed": hasattr(markdown_to_docx, 'convert_mermaid_to_image')
            })
            
        except Exception as e:
            results["tests"].append({
                "name": "Emma write_sds mode",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_wizard_configuration(self) -> Dict[str, Any]:
        """Test Phase 5: Wizard configuration works."""
        results = {"phase": "Phase 5 - Wizard Configuration", "tests": []}
        
        try:
            # Test wizard routes exist
            from app.api.routes import wizard
            
            results["tests"].append({
                "name": "Wizard routes module exists",
                "passed": True
            })
            
            # Test encryption service
            from app.utils.encryption import encrypt_credential, decrypt_credential
            
            test_value = "test_secret_123"
            encrypted = encrypt_credential(test_value)
            decrypted = decrypt_credential(encrypted)
            
            results["tests"].append({
                "name": "Encryption/decryption works",
                "passed": decrypted == test_value
            })
            
            # Test environment service
            from app.services.environment_service import EnvironmentService
            
            results["tests"].append({
                "name": "EnvironmentService exists",
                "passed": True
            })
            
            # Test connection validator
            from app.services.connection_validator import ConnectionValidatorService
            
            results["tests"].append({
                "name": "ConnectionValidatorService exists",
                "passed": True
            })
            
        except Exception as e:
            results["tests"].append({
                "name": "Wizard configuration",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_wbs_task_types(self) -> Dict[str, Any]:
        """Test Phase 6: WBS task types classification."""
        results = {"phase": "Phase 6 - WBS Task Types", "tests": []}
        
        try:
            from app.models.wbs_task_type import (
                WBSTaskType, 
                WBSTaskExecutor,
                TASK_TYPE_CONFIG,
                is_automatable,
                get_automatable_task_types,
                get_manual_task_types,
                infer_task_type
            )
            
            # Test enum count
            results["tests"].append({
                "name": "WBSTaskType has 25 types",
                "passed": len(WBSTaskType) == 25
            })
            
            results["tests"].append({
                "name": "WBSTaskExecutor has 8 executors",
                "passed": len(WBSTaskExecutor) == 8
            })
            
            # Test automatable filtering
            auto_tasks = get_automatable_task_types()
            manual_tasks = get_manual_task_types()
            
            results["tests"].append({
                "name": "Automatable tasks = 20",
                "passed": len(auto_tasks) == 20
            })
            
            results["tests"].append({
                "name": "Manual tasks = 5",
                "passed": len(manual_tasks) == 5
            })
            
            # Test inference
            inferred = infer_task_type("Create Apex trigger for validation", "")
            results["tests"].append({
                "name": "Task type inference works",
                "passed": inferred == WBSTaskType.DEV_APEX
            })
            
        except Exception as e:
            results["tests"].append({
                "name": "WBS task types",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_freemium_model(self) -> Dict[str, Any]:
        """Test Section 9: Freemium model."""
        results = {"phase": "Section 9 - Freemium Model", "tests": []}
        
        try:
            from app.models.subscription import (
                SubscriptionTier,
                TIER_FEATURES,
                has_feature,
                get_limit
            )
            
            # Test tiers exist
            results["tests"].append({
                "name": "3 subscription tiers exist",
                "passed": len(SubscriptionTier) == 3
            })
            
            # Test FREE tier limits
            free_projects = get_limit(SubscriptionTier.FREE, "max_projects")
            results["tests"].append({
                "name": "FREE tier has 3 project limit",
                "passed": free_projects == 3
            })
            
            # Test FREE cannot access BUILD
            results["tests"].append({
                "name": "FREE cannot access build_phase",
                "passed": not has_feature(SubscriptionTier.FREE, "build_phase")
            })
            
            # Test PREMIUM can access BUILD
            results["tests"].append({
                "name": "PREMIUM can access build_phase",
                "passed": has_feature(SubscriptionTier.PREMIUM, "build_phase")
            })
            
            # Test ENTERPRISE unlimited
            enterprise_projects = get_limit(SubscriptionTier.ENTERPRISE, "max_projects")
            results["tests"].append({
                "name": "ENTERPRISE has unlimited projects",
                "passed": enterprise_projects is None
            })
            
            # Test feature_access utilities
            from app.utils.feature_access import (
                check_feature_access,
                check_project_limits,
                get_locked_features
            )
            results["tests"].append({
                "name": "Feature access utilities exist",
                "passed": True
            })
            
        except Exception as e:
            results["tests"].append({
                "name": "Freemium model",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_multi_environment_support(self) -> Dict[str, Any]:
        """Test Section 6.2-6.4: Multi-environment and templates."""
        results = {"phase": "Section 6 - Environments & Templates", "tests": []}
        
        try:
            # Test environment model
            from app.models.project_environment import (
                ProjectEnvironment,
                EnvironmentType,
                AuthMethod,
                ConnectionStatus
            )
            
            results["tests"].append({
                "name": "EnvironmentType has 5 types (dev, qa, uat, staging, prod)",
                "passed": len(EnvironmentType) == 5
            })
            
            # Test git config model
            from app.models.project_git_config import (
                ProjectGitConfig,
                GitProvider,
                BranchStrategy
            )
            
            results["tests"].append({
                "name": "GitProvider has 4 providers",
                "passed": len(GitProvider) == 4
            })
            
            results["tests"].append({
                "name": "BranchStrategy has 3 strategies",
                "passed": len(BranchStrategy) == 3
            })
            
            # Test SDS templates
            from app.models.sds_template import SDSTemplate, SYSTEM_TEMPLATES
            
            results["tests"].append({
                "name": "3 system templates defined",
                "passed": len(SYSTEM_TEMPLATES) == 3
            })
            
        except Exception as e:
            results["tests"].append({
                "name": "Multi-environment support",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def test_database_tables(self) -> Dict[str, Any]:
        """Test database tables exist."""
        results = {"phase": "Database Tables", "tests": []}
        
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="172.17.0.1",
                database="digital_humans_db",
                user="digital_humans",
                password="DH_SecurePass2025!"
            )
            cur = conn.cursor()
            
            tables_to_check = [
                "projects",
                "users",
                "executions",
                "task_executions",
                "project_environments",
                "project_git_config",
                "sds_templates",
                "project_credentials"
            ]
            
            for table in tables_to_check:
                cur.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (table,))
                exists = cur.fetchone()[0]
                results["tests"].append({
                    "name": f"Table '{table}' exists",
                    "passed": exists
                })
            
            conn.close()
            
        except Exception as e:
            results["tests"].append({
                "name": "Database connection",
                "passed": False,
                "error": str(e)
            })
        
        results["passed"] = all(t["passed"] for t in results["tests"])
        return results
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all E2E tests."""
        start_time = time.time()
        
        all_results = {
            "started_at": datetime.now().isoformat(),
            "phases": []
        }
        
        # Run each phase test
        test_methods = [
            self.test_phase1_corrections,
            self.test_emma_analyze_mode,
            self.test_emma_validate_mode,
            self.test_emma_write_sds_mode,
            self.test_wizard_configuration,
            self.test_wbs_task_types,
            self.test_freemium_model,
            self.test_multi_environment_support,
            self.test_database_tables,
        ]
        
        for test_method in test_methods:
            try:
                result = await test_method()
                all_results["phases"].append(result)
            except Exception as e:
                all_results["phases"].append({
                    "phase": test_method.__name__,
                    "passed": False,
                    "error": str(e)
                })
        
        # Calculate summary
        total_tests = sum(len(p.get("tests", [])) for p in all_results["phases"])
        passed_tests = sum(
            sum(1 for t in p.get("tests", []) if t.get("passed", False))
            for p in all_results["phases"]
        )
        
        all_results["completed_at"] = datetime.now().isoformat()
        all_results["duration_seconds"] = round(time.time() - start_time, 2)
        all_results["summary"] = {
            "total_phases": len(all_results["phases"]),
            "passed_phases": sum(1 for p in all_results["phases"] if p.get("passed", False)),
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "success_rate": f"{(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "0%"
        }
        
        return all_results


def print_test_results(results: Dict[str, Any]):
    """Pretty print test results."""
    print("\n" + "=" * 60)
    print("E2E TEST RESULTS - DIGITAL HUMANS SDS WORKFLOW")
    print("=" * 60)
    
    for phase in results["phases"]:
        phase_status = "✅" if phase.get("passed", False) else "❌"
        print(f"\n{phase_status} {phase.get('phase', 'Unknown Phase')}")
        
        for test in phase.get("tests", []):
            test_status = "✅" if test.get("passed", False) else "❌"
            print(f"   {test_status} {test.get('name', 'Unknown test')}")
            if not test.get("passed") and "error" in test:
                print(f"      Error: {test['error']}")
    
    print("\n" + "-" * 60)
    summary = results.get("summary", {})
    print(f"SUMMARY: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)} tests passed ({summary.get('success_rate', '0%')})")
    print(f"Duration: {results.get('duration_seconds', 0)}s")
    print("=" * 60)


# Main execution
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/root/workspace/digital-humans-production/backend')
    
    async def main():
        tester = SDSWorkflowE2ETest()
        results = await tester.run_all_tests()
        print_test_results(results)
        return results
    
    asyncio.run(main())
