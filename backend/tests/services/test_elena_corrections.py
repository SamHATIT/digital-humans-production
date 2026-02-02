"""
Tests unitaires pour Elena corrections BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §5.4
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from agents.roles.salesforce_qa_tester import (
    structural_validation,
    PHASE_REVIEW_PROMPTS,
    get_phase_review_prompt
)


class TestElenaCorrections:
    """Tests pour les corrections Elena selon spec §5.4."""
    
    # ═══════════════════════════════════════════════════════════════
    # Tests structural_validation
    # ═══════════════════════════════════════════════════════════════
    
    def test_structural_validation_exists(self):
        """Spec: structural_validation pré-valide avant LLM"""
        assert callable(structural_validation)
    
    def test_structural_validation_returns_dict(self):
        """Retourne un dict avec valid et issues"""
        files = {}
        result = structural_validation(files, 1)
        
        assert isinstance(result, dict)
        assert "valid" in result
        assert "issues" in result
    
    def test_structural_validation_phase1_valid_json(self):
        """Phase 1: Valide JSON plan"""
        files = {
            "plan.json": '{"operations": [{"type": "create_object", "api_name": "Test__c"}]}'
        }
        result = structural_validation(files, 1)
        
        assert result.get("valid", False) == True
    
    def test_structural_validation_phase2_balanced_braces(self):
        """Phase 2: Détecte accolades déséquilibrées"""
        files = {
            "force-app/main/default/classes/Bad.cls": "public class Bad { public void test() {"
        }
        result = structural_validation(files, 2)
        
        # Doit signaler un problème
        has_brace_issue = any("accolade" in str(i).lower() or "brace" in str(i).lower() 
                              for i in result.get("issues", []))
        assert not result.get("valid", True) or has_brace_issue
    
    def test_structural_validation_phase3_missing_export(self):
        """Phase 3: Détecte export default class manquant"""
        files = {
            "force-app/main/default/lwc/test/test.js": "class Test {}"
        }
        result = structural_validation(files, 3)
        
        # Doit signaler un problème
        has_export_issue = any("export" in str(i).lower() for i in result.get("issues", []))
        assert not result.get("valid", True) or has_export_issue or len(result.get("issues", [])) > 0
    
    # ═══════════════════════════════════════════════════════════════
    # Tests PHASE_REVIEW_PROMPTS
    # ═══════════════════════════════════════════════════════════════
    
    def test_phase_review_prompts_exists(self):
        """Spec: 6 prompts de review par phase"""
        assert PHASE_REVIEW_PROMPTS is not None
        assert isinstance(PHASE_REVIEW_PROMPTS, dict)
    
    def test_phase_review_prompts_has_6_phases(self):
        """6 prompts pour les 6 phases"""
        assert len(PHASE_REVIEW_PROMPTS) >= 6
        
        for phase in range(1, 7):
            assert phase in PHASE_REVIEW_PROMPTS, f"Prompt manquant pour phase {phase}"
    
    def test_phase_review_prompts_not_empty(self):
        """Chaque prompt n'est pas vide"""
        for phase, prompt in PHASE_REVIEW_PROMPTS.items():
            assert len(prompt) > 50, f"Prompt phase {phase} trop court"
    
    def test_phase1_prompt_mentions_data_model(self):
        """Prompt Phase 1 mentionne data model"""
        prompt = PHASE_REVIEW_PROMPTS[1].lower()
        assert "data" in prompt or "model" in prompt or "object" in prompt
    
    def test_phase2_prompt_mentions_apex(self):
        """Prompt Phase 2 mentionne Apex/Business Logic"""
        prompt = PHASE_REVIEW_PROMPTS[2].lower()
        assert "apex" in prompt or "class" in prompt or "business" in prompt
    
    def test_phase3_prompt_mentions_lwc(self):
        """Prompt Phase 3 mentionne LWC/UI"""
        prompt = PHASE_REVIEW_PROMPTS[3].lower()
        assert "lwc" in prompt or "component" in prompt or "ui" in prompt
    
    # ═══════════════════════════════════════════════════════════════
    # Tests get_phase_review_prompt
    # ═══════════════════════════════════════════════════════════════
    
    def test_get_phase_review_prompt_exists(self):
        """Fonction pour obtenir le prompt formaté"""
        assert callable(get_phase_review_prompt)
    
    def test_get_phase_review_prompt_returns_string(self):
        """Retourne une string"""
        result = get_phase_review_prompt(1, "test code content")
        assert isinstance(result, str)
        assert len(result) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
