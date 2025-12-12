"""
WBS Task Types and Configuration
Based on SPEC Section 8 - Types de Tâches WBS

Each WBS task is classified to enable:
1. Correct execution (appropriate agent or manual)
2. Appropriate validation
3. Progress tracking
"""
import enum
from typing import Dict, Any, List


class WBSTaskType(str, enum.Enum):
    """Classification of WBS tasks by type."""
    
    # Setup tasks - Manual or semi-automatic
    SETUP_ENVIRONMENT = "setup_environment"      # Sandbox config, SFDX
    SETUP_REPOSITORY = "setup_repository"        # Git config
    SETUP_PERMISSIONS = "setup_permissions"      # Users, profiles creation
    
    # Development tasks - Technical agents
    DEV_DATA_MODEL = "dev_data_model"           # Objects, fields, relations
    DEV_APEX = "dev_apex"                       # Apex classes, triggers
    DEV_LWC = "dev_lwc"                         # Lightning components
    DEV_FLOW = "dev_flow"                       # Flows, Process Builder
    DEV_VALIDATION = "dev_validation"           # Validation rules
    DEV_FORMULA = "dev_formula"                 # Formula fields
    
    # Configuration tasks - Raj (Admin)
    CONFIG_PROFILES = "config_profiles"         # Profiles, permission sets
    CONFIG_SHARING = "config_sharing"           # Sharing rules, OWD
    CONFIG_LAYOUTS = "config_layouts"           # Page layouts, record types
    CONFIG_APPS = "config_apps"                 # Lightning apps
    CONFIG_REPORTS = "config_reports"           # Reports, dashboards
    
    # Test tasks - Elena (QA)
    TEST_UNIT = "test_unit"                     # Unit tests Apex
    TEST_INTEGRATION = "test_integration"       # Integration tests
    TEST_UAT = "test_uat"                       # User acceptance tests
    TEST_PERFORMANCE = "test_performance"       # Load tests
    
    # Deployment tasks - Jordan (DevOps)
    DEPLOY_PREPARE = "deploy_prepare"           # Package preparation
    DEPLOY_EXECUTE = "deploy_execute"           # Deployment
    DEPLOY_VALIDATE = "deploy_validate"         # Post-deploy smoke tests
    
    # Documentation tasks - Lucas (Trainer) / Manual
    DOC_TECHNICAL = "doc_technical"             # Technical documentation
    DOC_USER = "doc_user"                       # User documentation
    DOC_TRAINING = "doc_training"               # Training materials
    
    # Generic/Unknown
    GENERIC = "generic"                         # Uncategorized task


class WBSTaskExecutor(str, enum.Enum):
    """Who/what executes a WBS task."""
    
    MANUAL = "manual"                           # Manual task
    DIEGO = "diego"                             # Apex Developer
    ZARA = "zara"                               # LWC Developer
    RAJ = "raj"                                 # Admin
    ELENA = "elena"                             # QA
    JORDAN = "jordan"                           # DevOps
    LUCAS = "lucas"                             # Trainer
    AISHA = "aisha"                             # Data Migration


# Mapping Type → Executor → Validation
TASK_TYPE_CONFIG: Dict[WBSTaskType, Dict[str, Any]] = {
    # ========================================
    # SETUP Tasks - Mostly manual
    # ========================================
    WBSTaskType.SETUP_ENVIRONMENT: {
        "executor": WBSTaskExecutor.MANUAL,
        "can_automate": False,
        "validation": {
            "method": "sfdx_connection_test",
            "criteria": ["Connection successful", "Org ID retrieved"]
        },
        "prerequisites": ["Salesforce org access", "Admin credentials"],
        "deliverables": ["Connected sandbox", "SFDX alias configured"]
    },
    WBSTaskType.SETUP_REPOSITORY: {
        "executor": WBSTaskExecutor.MANUAL,
        "can_automate": False,
        "validation": {
            "method": "git_connection_test",
            "criteria": ["Repository accessible", "Push permission verified"]
        },
        "prerequisites": ["Git provider account", "Access token"],
        "deliverables": ["Repository URL", "Branch created"]
    },
    WBSTaskType.SETUP_PERMISSIONS: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["Profiles deployed", "Permission sets deployed"]
        },
        "prerequisites": ["SETUP_ENVIRONMENT completed"],
        "deliverables": ["Profiles", "Permission sets", "Permission set groups"]
    },
    
    # ========================================
    # DEV Tasks - Automated by agents
    # ========================================
    WBSTaskType.DEV_DATA_MODEL: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "sfdx_push_and_describe",
            "criteria": ["Source pushed successfully", "Objects exist in org"]
        },
        "prerequisites": ["SETUP_ENVIRONMENT completed"],
        "deliverables": ["Custom objects", "Custom fields", "Relationships"]
    },
    WBSTaskType.DEV_APEX: {
        "executor": WBSTaskExecutor.DIEGO,
        "can_automate": True,
        "validation": {
            "method": "apex_test_run",
            "criteria": ["Code compiled", "Tests pass with 75%+ coverage"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed"],
        "deliverables": ["Apex classes", "Apex triggers", "Test classes"]
    },
    WBSTaskType.DEV_LWC: {
        "executor": WBSTaskExecutor.ZARA,
        "can_automate": True,
        "validation": {
            "method": "sfdx_push_and_lint",
            "criteria": ["Components deployed", "No ESLint errors"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed", "DEV_APEX completed"],
        "deliverables": ["LWC components", "CSS styles", "Jest tests"]
    },
    WBSTaskType.DEV_FLOW: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "flow_deploy_and_activate",
            "criteria": ["Flow deployed", "Flow activated"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed"],
        "deliverables": ["Flow definitions", "Flow versions"]
    },
    WBSTaskType.DEV_VALIDATION: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["Validation rules deployed", "Active status confirmed"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed"],
        "deliverables": ["Validation rules"]
    },
    WBSTaskType.DEV_FORMULA: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["Formula fields deployed", "Formulas compile"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed"],
        "deliverables": ["Formula fields"]
    },
    
    # ========================================
    # CONFIG Tasks
    # ========================================
    WBSTaskType.CONFIG_PROFILES: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["Profiles deployed", "Field permissions set"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed"],
        "deliverables": ["Profile configurations", "Field-level security"]
    },
    WBSTaskType.CONFIG_SHARING: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["Sharing rules deployed", "OWD configured"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed", "CONFIG_PROFILES completed"],
        "deliverables": ["Sharing rules", "OWD settings"]
    },
    WBSTaskType.CONFIG_LAYOUTS: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["Layouts deployed", "Assigned to profiles"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed", "DEV_LWC completed"],
        "deliverables": ["Page layouts", "Lightning pages", "Record types"]
    },
    WBSTaskType.CONFIG_APPS: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["App deployed", "Tabs configured"]
        },
        "prerequisites": ["CONFIG_LAYOUTS completed"],
        "deliverables": ["Lightning apps", "App configuration"]
    },
    WBSTaskType.CONFIG_REPORTS: {
        "executor": WBSTaskExecutor.RAJ,
        "can_automate": True,
        "validation": {
            "method": "metadata_deploy",
            "criteria": ["Reports deployed", "Dashboards deployed"]
        },
        "prerequisites": ["DEV_DATA_MODEL completed"],
        "deliverables": ["Reports", "Dashboards", "Report types"]
    },
    
    # ========================================
    # TEST Tasks
    # ========================================
    WBSTaskType.TEST_UNIT: {
        "executor": WBSTaskExecutor.ELENA,
        "can_automate": True,
        "validation": {
            "method": "apex_test_run",
            "criteria": ["All tests pass", "Coverage >= 75%"]
        },
        "prerequisites": ["DEV_APEX completed"],
        "deliverables": ["Test results", "Coverage report"]
    },
    WBSTaskType.TEST_INTEGRATION: {
        "executor": WBSTaskExecutor.ELENA,
        "can_automate": True,
        "validation": {
            "method": "integration_test_run",
            "criteria": ["All scenarios pass", "No errors in logs"]
        },
        "prerequisites": ["All DEV tasks completed"],
        "deliverables": ["Integration test results"]
    },
    WBSTaskType.TEST_UAT: {
        "executor": WBSTaskExecutor.MANUAL,
        "can_automate": False,
        "validation": {
            "method": "manual_signoff",
            "criteria": ["Client approval received"]
        },
        "prerequisites": ["All DEV tasks completed", "TEST_UNIT passed"],
        "deliverables": ["UAT report", "Signoff document"]
    },
    WBSTaskType.TEST_PERFORMANCE: {
        "executor": WBSTaskExecutor.MANUAL,
        "can_automate": False,
        "validation": {
            "method": "performance_benchmark",
            "criteria": ["Response times acceptable", "No governor limit issues"]
        },
        "prerequisites": ["All DEV tasks completed"],
        "deliverables": ["Performance report"]
    },
    
    # ========================================
    # DEPLOY Tasks
    # ========================================
    WBSTaskType.DEPLOY_PREPARE: {
        "executor": WBSTaskExecutor.JORDAN,
        "can_automate": True,
        "validation": {
            "method": "package_validate",
            "criteria": ["Package created", "All components included"]
        },
        "prerequisites": ["All DEV and TEST tasks completed"],
        "deliverables": ["Deployment package", "Manifest file"]
    },
    WBSTaskType.DEPLOY_EXECUTE: {
        "executor": WBSTaskExecutor.JORDAN,
        "can_automate": True,
        "validation": {
            "method": "deployment_status",
            "criteria": ["Deployment successful", "No errors"]
        },
        "prerequisites": ["DEPLOY_PREPARE completed", "Target org connected"],
        "deliverables": ["Deployment log", "Deployment ID"]
    },
    WBSTaskType.DEPLOY_VALIDATE: {
        "executor": WBSTaskExecutor.JORDAN,
        "can_automate": True,
        "validation": {
            "method": "smoke_test",
            "criteria": ["All smoke tests pass", "No regressions"]
        },
        "prerequisites": ["DEPLOY_EXECUTE completed"],
        "deliverables": ["Smoke test results", "Validation report"]
    },
    
    # ========================================
    # DOC Tasks
    # ========================================
    WBSTaskType.DOC_TECHNICAL: {
        "executor": WBSTaskExecutor.LUCAS,
        "can_automate": True,
        "validation": {
            "method": "document_review",
            "criteria": ["Document complete", "Approved by tech lead"]
        },
        "prerequisites": ["All DEV tasks completed"],
        "deliverables": ["Technical documentation", "API documentation"]
    },
    WBSTaskType.DOC_USER: {
        "executor": WBSTaskExecutor.LUCAS,
        "can_automate": True,
        "validation": {
            "method": "document_review",
            "criteria": ["Document complete", "Screenshots included"]
        },
        "prerequisites": ["CONFIG_LAYOUTS completed"],
        "deliverables": ["User guide", "Quick reference"]
    },
    WBSTaskType.DOC_TRAINING: {
        "executor": WBSTaskExecutor.LUCAS,
        "can_automate": True,
        "validation": {
            "method": "training_review",
            "criteria": ["Materials complete", "Exercises included"]
        },
        "prerequisites": ["DOC_USER completed"],
        "deliverables": ["Training materials", "Exercises", "Videos"]
    },
    
    # ========================================
    # Generic fallback
    # ========================================
    WBSTaskType.GENERIC: {
        "executor": WBSTaskExecutor.MANUAL,
        "can_automate": False,
        "validation": {
            "method": "manual_review",
            "criteria": ["Task completed"]
        },
        "prerequisites": [],
        "deliverables": ["Task output"]
    },
}


def get_task_config(task_type: WBSTaskType) -> Dict[str, Any]:
    """Get configuration for a task type."""
    return TASK_TYPE_CONFIG.get(task_type, TASK_TYPE_CONFIG[WBSTaskType.GENERIC])


def is_automatable(task_type: WBSTaskType) -> bool:
    """Check if a task type can be automated."""
    config = get_task_config(task_type)
    return config.get("can_automate", False)


def get_executor(task_type: WBSTaskType) -> WBSTaskExecutor:
    """Get the executor for a task type."""
    config = get_task_config(task_type)
    return config.get("executor", WBSTaskExecutor.MANUAL)


def get_automatable_task_types() -> List[WBSTaskType]:
    """Get list of task types that can be automated."""
    return [t for t in WBSTaskType if is_automatable(t)]


def get_manual_task_types() -> List[WBSTaskType]:
    """Get list of task types that require manual execution."""
    return [t for t in WBSTaskType if not is_automatable(t)]


# Task type inference from keywords
TASK_TYPE_KEYWORDS = {
    WBSTaskType.SETUP_ENVIRONMENT: ["sandbox", "environment", "sfdx", "org setup"],
    WBSTaskType.SETUP_REPOSITORY: ["git", "repository", "repo", "github", "gitlab"],
    WBSTaskType.SETUP_PERMISSIONS: ["user setup", "permission", "profile setup"],
    WBSTaskType.DEV_DATA_MODEL: ["object", "field", "data model", "schema", "custom object"],
    WBSTaskType.DEV_APEX: ["apex", "trigger", "class", "controller"],
    WBSTaskType.DEV_LWC: ["lwc", "lightning", "component", "aura"],
    WBSTaskType.DEV_FLOW: ["flow", "process builder", "workflow", "automation"],
    WBSTaskType.DEV_VALIDATION: ["validation rule", "validation"],
    WBSTaskType.DEV_FORMULA: ["formula", "rollup"],
    WBSTaskType.CONFIG_PROFILES: ["profile", "permission set", "fls"],
    WBSTaskType.CONFIG_SHARING: ["sharing", "owd", "access"],
    WBSTaskType.CONFIG_LAYOUTS: ["layout", "page layout", "record type", "lightning page"],
    WBSTaskType.CONFIG_APPS: ["app", "lightning app", "tab"],
    WBSTaskType.CONFIG_REPORTS: ["report", "dashboard", "analytics"],
    WBSTaskType.TEST_UNIT: ["unit test", "test class", "apex test"],
    WBSTaskType.TEST_INTEGRATION: ["integration test", "end to end", "e2e"],
    WBSTaskType.TEST_UAT: ["uat", "user acceptance", "client test"],
    WBSTaskType.TEST_PERFORMANCE: ["performance", "load test", "stress test"],
    WBSTaskType.DEPLOY_PREPARE: ["package", "prepare deploy", "deployment prep"],
    WBSTaskType.DEPLOY_EXECUTE: ["deploy", "deployment", "release"],
    WBSTaskType.DEPLOY_VALIDATE: ["smoke test", "post deploy", "validation"],
    WBSTaskType.DOC_TECHNICAL: ["technical doc", "api doc", "architecture doc"],
    WBSTaskType.DOC_USER: ["user guide", "user doc", "help doc"],
    WBSTaskType.DOC_TRAINING: ["training", "formation", "tutorial"],
}


def infer_task_type(task_name: str, task_description: str = "") -> WBSTaskType:
    """
    Infer the task type from task name and description.
    Uses keyword matching.
    """
    text = f"{task_name} {task_description}".lower()
    
    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in text:
                return task_type
    
    return WBSTaskType.GENERIC


# Test
if __name__ == "__main__":
    print("WBS Task Types Configuration")
    print("=" * 50)
    
    automatable = get_automatable_task_types()
    manual = get_manual_task_types()
    
    print(f"\n✅ Automatable tasks ({len(automatable)}):")
    for t in automatable:
        config = get_task_config(t)
        print(f"  - {t.value}: {config['executor'].value}")
    
    print(f"\n🔧 Manual tasks ({len(manual)}):")
    for t in manual:
        print(f"  - {t.value}")
    
    print("\n🔍 Task type inference test:")
    test_cases = [
        "Create Customer custom object",
        "Develop Apex trigger for validation",
        "Build LWC component for dashboard",
        "Configure profiles and permissions",
        "Run unit tests",
        "Deploy to production",
        "Create user documentation"
    ]
    
    for tc in test_cases:
        inferred = infer_task_type(tc)
        print(f"  '{tc}' → {inferred.value}")
