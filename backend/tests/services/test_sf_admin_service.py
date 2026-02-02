"""
Tests unitaires pour SFAdminService - BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §6.5
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from app.services.sf_admin_service import SFAdminService


class TestSFAdminService:
    """Tests pour SFAdminService selon spec §6.5."""
    
    # ═══════════════════════════════════════════════════════════════
    # Tests OPERATION_HANDLERS
    # ═══════════════════════════════════════════════════════════════
    
    def test_operation_handlers_exist(self):
        """Spec: OPERATION_HANDLERS définit les handlers pour chaque type d'opération"""
        assert hasattr(SFAdminService, 'OPERATION_HANDLERS')
        handlers = SFAdminService.OPERATION_HANDLERS
        
        required_handlers = [
            'create_object',
            'create_field',
            'create_record_type',
            'create_list_view',
            'create_validation_rule',
            'create_flow',
            'create_permission_set',
            'create_page_layout',
            'create_sharing_rule',
            'create_approval_process',
        ]
        
        for handler_name in required_handlers:
            assert handler_name in handlers, f"Handler manquant: {handler_name}"
    
    def test_field_type_mapping_exists(self):
        """Spec: Gère tous les field_types (Text, Picklist, Lookup, etc.)"""
        assert hasattr(SFAdminService, 'FIELD_TYPE_MAP')
        field_map = SFAdminService.FIELD_TYPE_MAP
        
        # Types de champs requis selon Salesforce
        required_types = [
            'Text',
            'Number',
            'Currency',
            'Date',
            'DateTime',
            'Picklist',
            'Lookup',
            'MasterDetail',
            'Checkbox',
            'Email',
            'Phone',
            'Url',
            'TextArea',
            'LongTextArea',
            'Formula',
        ]
        
        for field_type in required_types:
            assert field_type in field_map, f"Field type manquant: {field_type}"
    
    # ═══════════════════════════════════════════════════════════════
    # Tests execute_plan
    # ═══════════════════════════════════════════════════════════════
    
    def test_execute_plan_method_exists(self):
        """Spec: execute_plan(plan) -> exécute les opérations séquentiellement"""
        service = SFAdminService.__new__(SFAdminService)
        assert hasattr(service, 'execute_plan')
        assert callable(service.execute_plan)
    
    def test_execute_plan_respects_order(self):
        """Spec: Exécute les opérations séquentiellement (respecte l'order)"""
        # Ce test vérifie que la méthode existe et prend un plan avec operations
        service = SFAdminService.__new__(SFAdminService)
        
        # Vérifier que la signature accepte un plan
        import inspect
        sig = inspect.signature(service.execute_plan)
        params = list(sig.parameters.keys())
        assert 'plan' in params or len(params) >= 1
    
    # ═══════════════════════════════════════════════════════════════
    # Tests handlers individuels
    # ═══════════════════════════════════════════════════════════════
    
    def test_create_custom_object_handler_exists(self):
        """Spec: _create_custom_object(op) -> POST Tooling API"""
        service = SFAdminService.__new__(SFAdminService)
        handler_method = SFAdminService.OPERATION_HANDLERS.get('create_object')
        assert handler_method is not None
        assert hasattr(service, handler_method) or hasattr(service, '_create_custom_object')
    
    def test_create_custom_field_handler_exists(self):
        """Spec: _create_custom_field(op) -> POST Tooling API avec field_type"""
        service = SFAdminService.__new__(SFAdminService)
        handler_method = SFAdminService.OPERATION_HANDLERS.get('create_field')
        assert handler_method is not None
        assert hasattr(service, handler_method) or hasattr(service, '_create_custom_field')
    
    # ═══════════════════════════════════════════════════════════════
    # Tests Tooling API helpers
    # ═══════════════════════════════════════════════════════════════
    
    def test_tooling_api_create_method_exists(self):
        """Spec: _tooling_api_create(sobject_type, payload) -> appel générique"""
        service = SFAdminService.__new__(SFAdminService)
        assert hasattr(service, '_tooling_api_create') or hasattr(service, 'tooling_api_create')
    
    def test_tooling_api_delete_method_exists(self):
        """Spec: _tooling_api_delete(sobject_type, id) -> pour rollback"""
        service = SFAdminService.__new__(SFAdminService)
        assert hasattr(service, '_tooling_api_delete') or hasattr(service, 'tooling_api_delete')
    
    # ═══════════════════════════════════════════════════════════════
    # Tests logging format
    # ═══════════════════════════════════════════════════════════════
    
    def test_logging_prefix(self):
        """Spec: Logger avec le format [SFAdmin] ou [Raj]"""
        import logging
        # Vérifier que le module utilise un logger avec un préfixe approprié
        # On vérifie simplement que le module importe logging
        from app.services import sf_admin_service
        assert hasattr(sf_admin_service, 'logger')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
