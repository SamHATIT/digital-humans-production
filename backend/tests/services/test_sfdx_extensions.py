"""
Tests unitaires pour SFDX Service extensions - BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §6.6
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from app.services.sfdx_service import SFDXService


class TestSFDXExtensions:
    """Tests pour les extensions SFDX selon spec §6.6."""
    
    def test_retrieve_metadata_exists(self):
        """Spec: retrieve_metadata() pour récupérer metadata après Tooling API"""
        service = SFDXService.__new__(SFDXService)
        assert hasattr(service, 'retrieve_metadata')
        assert callable(service.retrieve_metadata)
    
    def test_execute_anonymous_exists(self):
        """Spec: execute_anonymous() pour scripts Aisha"""
        service = SFDXService.__new__(SFDXService)
        assert hasattr(service, 'execute_anonymous')
        assert callable(service.execute_anonymous)
    
    def test_deploy_with_manifest_exists(self):
        """Spec: deploy_with_manifest() avec package.xml explicite"""
        service = SFDXService.__new__(SFDXService)
        assert hasattr(service, 'deploy_with_manifest')
        assert callable(service.deploy_with_manifest)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
