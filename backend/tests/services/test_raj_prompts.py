"""
Tests unitaires pour Raj Prompts BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §5.3
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from agents.roles.salesforce_admin import (
    BUILD_V2_PHASE1_PROMPT,
    BUILD_V2_PHASE4_PROMPT,
    BUILD_V2_PHASE5_PROMPT,
    generate_build_v2
)


class TestRajBuildV2Prompts:
    """Tests pour les prompts BUILD v2 de Raj selon spec §5.3."""
    
    # ═══════════════════════════════════════════════════════════════
    # Tests Phase 1 - Data Model
    # ═══════════════════════════════════════════════════════════════
    
    def test_phase1_prompt_exists(self):
        """Spec: Prompt Phase 1 pour Data Model"""
        assert BUILD_V2_PHASE1_PROMPT is not None
        assert len(BUILD_V2_PHASE1_PROMPT) > 100
    
    def test_phase1_prompt_mentions_json_format(self):
        """Spec: Sortie JSON au lieu de XML"""
        assert "JSON" in BUILD_V2_PHASE1_PROMPT or "json" in BUILD_V2_PHASE1_PROMPT
    
    def test_phase1_prompt_mentions_operations(self):
        """Spec: Format operations[] avec type, order, api_name"""
        prompt = BUILD_V2_PHASE1_PROMPT.lower()
        assert "operation" in prompt
    
    def test_phase1_prompt_mentions_create_object(self):
        """Spec: create_object operation"""
        assert "create_object" in BUILD_V2_PHASE1_PROMPT
    
    def test_phase1_prompt_mentions_create_field(self):
        """Spec: create_field operation"""
        assert "create_field" in BUILD_V2_PHASE1_PROMPT
    
    def test_phase1_prompt_mentions_field_types(self):
        """Spec: field_type (Text, Picklist, Lookup, etc.)"""
        prompt = BUILD_V2_PHASE1_PROMPT
        # Au moins quelques types de champs doivent être mentionnés
        field_types_mentioned = sum(1 for ft in ['Text', 'Picklist', 'Lookup', 'Number', 'Date']
                                    if ft in prompt)
        assert field_types_mentioned >= 3
    
    # ═══════════════════════════════════════════════════════════════
    # Tests Phase 4 - Automation
    # ═══════════════════════════════════════════════════════════════
    
    def test_phase4_prompt_exists(self):
        """Spec: Prompt Phase 4 pour Automation"""
        assert BUILD_V2_PHASE4_PROMPT is not None
        assert len(BUILD_V2_PHASE4_PROMPT) > 100
    
    def test_phase4_prompt_mentions_flow_or_validation(self):
        """Spec: Phase 4 = Flows + Validation Rules complexes"""
        prompt = BUILD_V2_PHASE4_PROMPT.lower()
        assert "flow" in prompt or "validation" in prompt
    
    # ═══════════════════════════════════════════════════════════════
    # Tests Phase 5 - Security
    # ═══════════════════════════════════════════════════════════════
    
    def test_phase5_prompt_exists(self):
        """Spec: Prompt Phase 5 pour Security"""
        assert BUILD_V2_PHASE5_PROMPT is not None
        assert len(BUILD_V2_PHASE5_PROMPT) > 100
    
    def test_phase5_prompt_mentions_permission_set(self):
        """Spec: Phase 5 = Permission Sets"""
        prompt = BUILD_V2_PHASE5_PROMPT.lower()
        assert "permission" in prompt or "profile" in prompt
    
    # ═══════════════════════════════════════════════════════════════
    # Tests generate_build_v2 function
    # ═══════════════════════════════════════════════════════════════
    
    def test_generate_build_v2_exists(self):
        """Spec: Fonction generate_build_v2() pour générer les plans"""
        assert callable(generate_build_v2)
    
    def test_generate_build_v2_signature(self):
        """Spec: generate_build_v2(phase, target, task_description, context, execution_id)"""
        import inspect
        sig = inspect.signature(generate_build_v2)
        params = list(sig.parameters.keys())
        
        assert 'phase' in params
        assert 'target' in params
        assert 'task_description' in params or 'description' in str(params)
        assert 'context' in params
        assert 'execution_id' in params


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
