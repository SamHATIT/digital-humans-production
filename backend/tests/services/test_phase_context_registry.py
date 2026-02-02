"""
Tests unitaires pour PhaseContextRegistry - BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §4.3
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from app.services.phase_context_registry import PhaseContextRegistry


class TestPhaseContextRegistry:
    """Tests pour PhaseContextRegistry selon spec §4.3."""
    
    def setup_method(self):
        self.registry = PhaseContextRegistry()
    
    # ═══════════════════════════════════════════════════════════════
    # Tests d'initialisation (selon spec §4.3)
    # ═══════════════════════════════════════════════════════════════
    
    def test_init_phase1_attributes(self):
        """Spec: Phase 1 alimente generated_objects, generated_fields, generated_record_types, generated_validation_rules"""
        assert hasattr(self.registry, 'generated_objects')
        assert hasattr(self.registry, 'generated_fields')
        assert hasattr(self.registry, 'generated_record_types')
        assert hasattr(self.registry, 'generated_validation_rules')
        assert self.registry.generated_objects == []
        assert self.registry.generated_fields == {}
    
    def test_init_phase2_attributes(self):
        """Spec: Phase 2 alimente generated_classes, generated_triggers"""
        assert hasattr(self.registry, 'generated_classes')
        assert hasattr(self.registry, 'generated_triggers')
        assert self.registry.generated_classes == {}
        assert self.registry.generated_triggers == []
    
    def test_init_phase3_attributes(self):
        """Spec: Phase 3 alimente generated_components"""
        assert hasattr(self.registry, 'generated_components')
        assert self.registry.generated_components == {}
    
    def test_init_phase4_attributes(self):
        """Spec: Phase 4 alimente generated_flows, generated_complex_vrs"""
        assert hasattr(self.registry, 'generated_flows')
        assert hasattr(self.registry, 'generated_complex_vrs')
        assert self.registry.generated_flows == []
        assert self.registry.generated_complex_vrs == []
    
    # ═══════════════════════════════════════════════════════════════
    # Tests register_batch_output (selon spec)
    # ═══════════════════════════════════════════════════════════════
    
    def test_register_phase1_create_object(self):
        """Spec: Phase 1 - create_object → generated_objects"""
        output = {
            "operations": [
                {"type": "create_object", "api_name": "Formation__c", "label": "Formation"}
            ]
        }
        
        self.registry.register_batch_output(1, output)
        
        assert "Formation__c" in self.registry.generated_objects
        assert "Formation__c" in self.registry.generated_fields  # Dict initialized
    
    def test_register_phase1_create_field(self):
        """Spec: Phase 1 - create_field → generated_fields"""
        output = {
            "operations": [
                {"type": "create_object", "api_name": "Formation__c"},
                {"type": "create_field", "object": "Formation__c", "api_name": "Titre__c", "field_type": "Text"},
                {"type": "create_field", "object": "Formation__c", "api_name": "Statut__c", "field_type": "Picklist"}
            ]
        }
        
        self.registry.register_batch_output(1, output)
        
        assert "Titre__c" in self.registry.generated_fields["Formation__c"]
        assert "Statut__c" in self.registry.generated_fields["Formation__c"]
    
    def test_register_phase1_record_type(self):
        """Spec: Phase 1 - record_type → generated_record_types"""
        output = {
            "operations": [
                {"type": "create_object", "api_name": "Formation__c"},
                {"type": "create_record_type", "object": "Formation__c", "api_name": "Presentiel"},
                {"type": "create_record_type", "object": "Formation__c", "api_name": "Distanciel"}
            ]
        }
        
        self.registry.register_batch_output(1, output)
        
        assert "Presentiel" in self.registry.generated_record_types["Formation__c"]
        assert "Distanciel" in self.registry.generated_record_types["Formation__c"]
    
    def test_register_phase1_validation_rule(self):
        """Spec: Phase 1 - simple_validation_rule → generated_validation_rules"""
        output = {
            "operations": [
                {"type": "create_validation_rule", "object": "Formation__c", "api_name": "Titre_Required"}
            ]
        }
        
        self.registry.register_batch_output(1, output)
        
        assert "Formation__c.Titre_Required" in self.registry.generated_validation_rules
    
    def test_register_phase2_apex_class(self):
        """Spec: Phase 2 - classes Apex → generated_classes avec méthodes"""
        output = {
            "files": {
                "force-app/main/default/classes/FormationService.cls": """
public class FormationService {
    public Formation__c getFormation(Id formationId) {
        return [SELECT Id FROM Formation__c WHERE Id = :formationId];
    }
    public void createFormation(Formation__c formation) {
        insert formation;
    }
}
"""
            }
        }
        
        self.registry.register_batch_output(2, output)
        
        assert "FormationService" in self.registry.generated_classes
        # Vérifie que les méthodes sont extraites
        methods = self.registry.generated_classes["FormationService"]
        assert any("getFormation" in m for m in methods)
    
    def test_register_phase2_trigger(self):
        """Spec: Phase 2 - triggers → generated_triggers"""
        output = {
            "files": {
                "force-app/main/default/triggers/FormationTrigger.trigger": "trigger FormationTrigger on Formation__c (before insert) {}"
            }
        }
        
        self.registry.register_batch_output(2, output)
        
        assert "FormationTrigger" in self.registry.generated_triggers
    
    def test_register_phase3_lwc(self):
        """Spec: Phase 3 - LWC → generated_components avec @api props"""
        output = {
            "files": {
                "force-app/main/default/lwc/formationList/formationList.js": """
import { LightningElement, api } from 'lwc';
export default class FormationList extends LightningElement {
    @api recordId;
    @api filters;
}
"""
            }
        }
        
        self.registry.register_batch_output(3, output)
        
        assert "formationList" in self.registry.generated_components
        props = self.registry.generated_components["formationList"]
        assert "recordId" in props
        assert "filters" in props
    
    def test_register_phase4_flow(self):
        """Spec: Phase 4 - flows → generated_flows"""
        output = {
            "operations": [
                {"type": "create_flow", "api_name": "FormationAutoNotification"}
            ]
        }
        
        self.registry.register_batch_output(4, output)
        
        assert "FormationAutoNotification" in self.registry.generated_flows
    
    def test_register_phase4_complex_vr(self):
        """Spec: Phase 4 - complex_validation_rule → generated_complex_vrs"""
        output = {
            "operations": [
                {"type": "complex_validation_rule", "object": "Session__c", "api_name": "DateCoherente"}
            ]
        }
        
        self.registry.register_batch_output(4, output)
        
        assert "Session__c.DateCoherente" in self.registry.generated_complex_vrs
    
    # ═══════════════════════════════════════════════════════════════
    # Tests get_context_for_batch (selon spec table)
    # ═══════════════════════════════════════════════════════════════
    
    def test_context_phase1_lot_n_receives_previous_lots(self):
        """Spec: Phase 1 (lot N) reçoit objets+champs des lots 1..N-1"""
        # Simuler lot 1
        self.registry.register_batch_output(1, {
            "operations": [{"type": "create_object", "api_name": "Formation__c"}]
        })
        
        # Contexte pour lot 2 de Phase 1
        context = self.registry.get_context_for_batch(1)
        
        assert "Formation__c" in context
        assert "DÉJÀ CRÉÉS" in context or "déjà" in context.lower()
    
    def test_context_phase2_receives_full_phase1(self):
        """Spec: Phase 2 reçoit TOUT Phase 1"""
        self.registry.register_batch_output(1, {
            "operations": [
                {"type": "create_object", "api_name": "Formation__c"},
                {"type": "create_field", "object": "Formation__c", "api_name": "Titre__c"}
            ]
        })
        
        context = self.registry.get_context_for_batch(2)
        
        assert "Formation__c" in context
        assert "Titre__c" in context
    
    def test_context_phase3_receives_phase1_and_class_signatures(self):
        """Spec: Phase 3 reçoit Phase 1 + signatures classes Phase 2"""
        self.registry.register_batch_output(1, {
            "operations": [{"type": "create_object", "api_name": "Formation__c"}]
        })
        self.registry.register_batch_output(2, {
            "files": {
                "classes/FormationService.cls": "public class FormationService { public void test() {} }"
            }
        })
        
        context = self.registry.get_context_for_batch(3)
        
        assert "Formation__c" in context
        assert "FormationService" in context
    
    # ═══════════════════════════════════════════════════════════════
    # Tests get_full_data_model
    # ═══════════════════════════════════════════════════════════════
    
    def test_get_full_data_model_format(self):
        """Spec: get_full_data_model() retourne le modèle de données complet"""
        self.registry.register_batch_output(1, {
            "operations": [
                {"type": "create_object", "api_name": "Formation__c"},
                {"type": "create_field", "object": "Formation__c", "api_name": "Titre__c"}
            ]
        })
        
        data_model = self.registry.get_full_data_model()
        
        assert "Formation__c" in data_model
        assert "Titre__c" in data_model
        assert "MODÈLE DE DONNÉES" in data_model or "Champs" in data_model
    
    # ═══════════════════════════════════════════════════════════════
    # Tests get_class_signatures
    # ═══════════════════════════════════════════════════════════════
    
    def test_get_class_signatures_format(self):
        """Spec: get_class_signatures() retourne les signatures (pas le code complet)"""
        self.registry.register_batch_output(2, {
            "files": {
                "classes/FormationService.cls": """
public class FormationService {
    public Formation__c getFormation(Id formationId) {
        return [SELECT Id FROM Formation__c WHERE Id = :formationId];
    }
}
"""
            }
        })
        
        signatures = self.registry.get_class_signatures()
        
        assert "FormationService" in signatures
        # Doit contenir les noms de méthodes, pas le code complet
        assert "getFormation" in signatures
        assert "SELECT" not in signatures  # Le code SOQL ne doit pas être là
    
    # ═══════════════════════════════════════════════════════════════
    # Tests sérialisation (pour persistence entre sessions)
    # ═══════════════════════════════════════════════════════════════
    
    def test_to_dict_and_from_dict(self):
        """Test round-trip sérialisation"""
        self.registry.register_batch_output(1, {
            "operations": [{"type": "create_object", "api_name": "Test__c"}]
        })
        self.registry.register_batch_output(2, {
            "files": {"classes/TestService.cls": "public class TestService {}"}
        })
        
        data = self.registry.to_dict()
        restored = PhaseContextRegistry.from_dict(data)
        
        assert restored.generated_objects == self.registry.generated_objects
        assert restored.generated_classes.keys() == self.registry.generated_classes.keys()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
