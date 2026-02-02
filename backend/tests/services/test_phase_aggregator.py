"""
Tests unitaires pour PhaseAggregator - BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §6.2
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from app.services.phase_aggregator import PhaseAggregator


class TestPhaseAggregator:
    """Tests pour PhaseAggregator selon spec §6.2."""
    
    def setup_method(self):
        self.aggregator = PhaseAggregator()
    
    # ═══════════════════════════════════════════════════════════════
    # Tests aggregate_data_model (Phase 1)
    # ═══════════════════════════════════════════════════════════════
    
    def test_aggregate_data_model_merges_operations(self):
        """Spec: Fusionne les plans JSON Raj en un plan unifié"""
        batch_results = [
            {
                "operations": [
                    {"type": "create_object", "api_name": "Formation__c", "order": 1},
                    {"type": "create_field", "object": "Formation__c", "api_name": "Titre__c", "order": 2}
                ]
            },
            {
                "operations": [
                    {"type": "create_object", "api_name": "Session__c", "order": 1},
                    {"type": "create_field", "object": "Session__c", "api_name": "Date__c", "order": 2}
                ]
            }
        ]
        
        result = self.aggregator.aggregate_data_model(batch_results)
        
        assert "operations" in result
        assert len(result["operations"]) == 4
    
    def test_aggregate_data_model_detects_duplicate_objects(self):
        """Spec: vérifie pas de collision d'API names"""
        batch_results = [
            {"operations": [{"type": "create_object", "api_name": "Formation__c"}]},
            {"operations": [{"type": "create_object", "api_name": "Formation__c"}]}  # Duplicate!
        ]
        
        result = self.aggregator.aggregate_data_model(batch_results)
        
        # Doit soit lever une erreur, soit avoir un flag duplicates
        assert "duplicates" in result or "errors" in result or len([
            op for op in result.get("operations", [])
            if op.get("type") == "create_object" and op.get("api_name") == "Formation__c"
        ]) == 1  # Ou déduplique
    
    def test_aggregate_data_model_assigns_global_order(self):
        """Spec: L'ordre global des opérations doit être cohérent"""
        batch_results = [
            {"operations": [{"type": "create_object", "api_name": "A__c", "order": 1}]},
            {"operations": [{"type": "create_object", "api_name": "B__c", "order": 1}]}
        ]
        
        result = self.aggregator.aggregate_data_model(batch_results)
        
        # Les ordres doivent être réassignés de manière globale
        orders = [op.get("order", 0) for op in result.get("operations", [])]
        assert orders == sorted(orders)  # Ordres croissants
    
    # ═══════════════════════════════════════════════════════════════
    # Tests aggregate_source_code (Phase 2 & 3)
    # ═══════════════════════════════════════════════════════════════
    
    def test_aggregate_source_code_merges_files(self):
        """Spec: Fusionne les fichiers en un dict unique"""
        batch_results = [
            {"files": {"classes/ServiceA.cls": "public class ServiceA {}"}},
            {"files": {"classes/ServiceB.cls": "public class ServiceB {}"}}
        ]
        
        result = self.aggregator.aggregate_source_code(batch_results)
        
        assert "files" in result
        assert len(result["files"]) == 2
        assert "ServiceA.cls" in str(result["files"].keys())
        assert "ServiceB.cls" in str(result["files"].keys())
    
    def test_aggregate_source_code_detects_duplicate_files(self):
        """Spec: Détecte les fichiers en double"""
        batch_results = [
            {"files": {"classes/Service.cls": "public class Service { // v1 }"}},
            {"files": {"classes/Service.cls": "public class Service { // v2 }"}}  # Duplicate!
        ]
        
        result = self.aggregator.aggregate_source_code(batch_results)
        
        # Doit signaler le conflit
        assert "duplicates" in result or "conflicts" in result or len(result.get("files", {})) == 1
    
    # ═══════════════════════════════════════════════════════════════
    # Tests aggregate_automation (Phase 4)
    # ═══════════════════════════════════════════════════════════════
    
    def test_aggregate_automation_merges_flows_and_vrs(self):
        """Spec: Fusionne flows + validation rules"""
        batch_results = [
            {"operations": [{"type": "create_flow", "api_name": "Flow1"}]},
            {"operations": [{"type": "complex_validation_rule", "api_name": "VR1"}]}
        ]
        
        result = self.aggregator.aggregate_automation(batch_results)
        
        operations = result.get("operations", [])
        types = [op.get("type") for op in operations]
        assert "create_flow" in types or len([o for o in operations if "flow" in str(o).lower()]) > 0
    
    # ═══════════════════════════════════════════════════════════════
    # Tests aggregate_security (Phase 5)
    # ═══════════════════════════════════════════════════════════════
    
    def test_aggregate_security_merges_permission_sets(self):
        """Spec: Fusionne permission sets + profiles"""
        batch_results = [
            {"operations": [{"type": "create_permission_set", "api_name": "PS1"}]},
            {"files": {"layouts/Formation__c-Layout.layout": "<Layout/>"}}
        ]
        
        result = self.aggregator.aggregate_security(batch_results)
        
        # Doit avoir soit operations soit files
        assert "operations" in result or "files" in result
    
    # ═══════════════════════════════════════════════════════════════
    # Tests aggregate_data_migration (Phase 6)
    # ═══════════════════════════════════════════════════════════════
    
    def test_aggregate_data_migration_merges_scripts(self):
        """Spec: Fusionne scripts migration"""
        batch_results = [
            {"files": {"data/Formation_mapping.sdl": "Field1=Col1"}},
            {"files": {"data/Session_mapping.sdl": "Field2=Col2"}},
            {"scripts": [{"name": "init", "code": "System.debug('init');"}]}
        ]
        
        result = self.aggregator.aggregate_data_migration(batch_results)
        
        assert "files" in result or "scripts" in result
    
    # ═══════════════════════════════════════════════════════════════
    # Tests méthode principale aggregate()
    # ═══════════════════════════════════════════════════════════════
    
    def test_aggregate_routes_to_correct_method(self):
        """Test que aggregate() route vers la bonne méthode selon la phase"""
        batch_results = [{"operations": [{"type": "create_object", "api_name": "Test__c"}]}]
        
        result = self.aggregator.aggregate(1, batch_results)
        
        assert "operations" in result  # Phase 1 → aggregate_data_model
    
    def test_aggregate_phase2_routes_to_source_code(self):
        """Test routage Phase 2"""
        batch_results = [{"files": {"classes/Test.cls": "public class Test {}"}}]
        
        result = self.aggregator.aggregate(2, batch_results)
        
        assert "files" in result
    
    # ═══════════════════════════════════════════════════════════════
    # Tests validation
    # ═══════════════════════════════════════════════════════════════
    
    def test_validate_aggregated_output_phase1(self):
        """Test validation Phase 1 - références champs vers objets"""
        aggregated = {
            "operations": [
                {"type": "create_field", "object": "Unknown__c", "api_name": "Field__c"}
                # Pas de create_object pour Unknown__c !
            ]
        }
        
        # Doit détecter le problème
        if hasattr(self.aggregator, 'validate_aggregated_output'):
            validation = self.aggregator.validate_aggregated_output(1, aggregated)
            assert not validation.get("valid", True) or validation.get("warnings")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
