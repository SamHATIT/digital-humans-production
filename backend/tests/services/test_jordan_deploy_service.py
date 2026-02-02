"""
Tests unitaires pour JordanDeployService - BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §6.4
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from app.services.jordan_deploy_service import JordanDeployService, PHASE_CONFIGS


class TestJordanDeployService:
    """Tests pour JordanDeployService selon spec §6.4."""
    
    # ═══════════════════════════════════════════════════════════════
    # Tests PHASE_CONFIGS
    # ═══════════════════════════════════════════════════════════════
    
    def test_phase_configs_exists(self):
        """Spec: PHASE_CONFIGS définit la config par phase"""
        assert PHASE_CONFIGS is not None
        assert isinstance(PHASE_CONFIGS, dict)
    
    def test_phase_configs_has_6_phases(self):
        """6 phases configurées"""
        assert len(PHASE_CONFIGS) >= 6
        
        for phase in range(1, 7):
            assert phase in PHASE_CONFIGS, f"Config manquante pour phase {phase}"
    
    def test_phase_configs_has_required_fields(self):
        """Chaque phase a les champs requis"""
        for phase, config in PHASE_CONFIGS.items():
            # Doit avoir agent et deploy_method (ou équivalent)
            assert hasattr(config, 'agent') or 'agent' in str(config)
    
    def test_phase1_uses_tooling_api(self):
        """Phase 1 utilise Tooling API"""
        config = PHASE_CONFIGS.get(1)
        config_str = str(config).lower()
        assert "tooling" in config_str or "admin" in config_str
    
    def test_phase2_uses_sfdx(self):
        """Phase 2 utilise SFDX deploy"""
        config = PHASE_CONFIGS.get(2)
        config_str = str(config).lower()
        assert "sfdx" in config_str or "source" in config_str
    
    # ═══════════════════════════════════════════════════════════════
    # Tests class JordanDeployService
    # ═══════════════════════════════════════════════════════════════
    
    def test_class_exists(self):
        """La classe JordanDeployService existe"""
        assert JordanDeployService is not None
    
    def test_deploy_phase_method_exists(self):
        """Spec: deploy_phase() point d'entrée unique"""
        service = JordanDeployService.__new__(JordanDeployService)
        assert hasattr(service, 'deploy_phase')
        assert callable(service.deploy_phase)
    
    def test_create_phase_branch_method_exists(self):
        """Spec: create_phase_branch() pour Git"""
        service = JordanDeployService.__new__(JordanDeployService)
        assert hasattr(service, 'create_phase_branch')
        assert callable(service.create_phase_branch)
    
    def test_create_phase_pr_method_exists(self):
        """Spec: create_phase_pr() pour créer PR"""
        service = JordanDeployService.__new__(JordanDeployService)
        assert hasattr(service, 'create_phase_pr')
        assert callable(service.create_phase_pr)
    
    def test_merge_pr_method_exists(self):
        """Spec: merge_pr() pour merger la PR"""
        service = JordanDeployService.__new__(JordanDeployService)
        assert hasattr(service, 'merge_pr')
        assert callable(service.merge_pr)
    
    def test_deploy_admin_config_method_exists(self):
        """Spec: deploy_admin_config() pour Tooling API"""
        service = JordanDeployService.__new__(JordanDeployService)
        assert hasattr(service, 'deploy_admin_config')
        assert callable(service.deploy_admin_config)
    
    def test_deploy_source_code_method_exists(self):
        """Spec: deploy_source_code() pour SFDX"""
        service = JordanDeployService.__new__(JordanDeployService)
        assert hasattr(service, 'deploy_source_code')
        assert callable(service.deploy_source_code)
    
    def test_generate_final_package_xml_method_exists(self):
        """Spec: generate_final_package_xml() en fin de BUILD"""
        service = JordanDeployService.__new__(JordanDeployService)
        assert hasattr(service, 'generate_final_package_xml')
        assert callable(service.generate_final_package_xml)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
