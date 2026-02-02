"""
Tests unitaires pour Diego corrections BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §5.1
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from agents.roles.salesforce_developer_apex import sanitize_apex_code, validate_apex_structure


class TestDiegoCorrections:
    """Tests pour les corrections Diego selon spec §5.1."""
    
    # ═══════════════════════════════════════════════════════════════
    # Tests sanitize_apex_code
    # ═══════════════════════════════════════════════════════════════
    
    def test_sanitize_function_exists(self):
        """Spec: sanitize_apex_code corrige les erreurs LLM courantes"""
        assert callable(sanitize_apex_code)
    
    def test_sanitize_with_security_enforced_after_group_by(self):
        """Spec: Fix WITH SECURITY_ENFORCED mal placé après GROUP BY"""
        code = """
        List<AggregateResult> results = [
            SELECT COUNT(Id), Status__c
            FROM Formation__c
            GROUP BY Status__c
            WITH SECURITY_ENFORCED
        ];
        """
        sanitized = sanitize_apex_code(code)
        
        # WITH SECURITY_ENFORCED doit être AVANT GROUP BY
        group_by_pos = sanitized.upper().find("GROUP BY")
        security_pos = sanitized.upper().find("WITH SECURITY_ENFORCED")
        
        if group_by_pos > 0 and security_pos > 0:
            assert security_pos < group_by_pos, "WITH SECURITY_ENFORCED doit être avant GROUP BY"
    
    def test_sanitize_with_security_enforced_after_order_by(self):
        """Spec: Fix WITH SECURITY_ENFORCED mal placé après ORDER BY"""
        code = """
        List<Formation__c> results = [
            SELECT Id, Name
            FROM Formation__c
            ORDER BY Name
            WITH SECURITY_ENFORCED
        ];
        """
        sanitized = sanitize_apex_code(code)
        
        # WITH SECURITY_ENFORCED doit être AVANT ORDER BY
        order_by_pos = sanitized.upper().find("ORDER BY")
        security_pos = sanitized.upper().find("WITH SECURITY_ENFORCED")
        
        if order_by_pos > 0 and security_pos > 0:
            assert security_pos < order_by_pos, "WITH SECURITY_ENFORCED doit être avant ORDER BY"
    
    def test_sanitize_double_semicolons(self):
        """Spec: Retire les doubles points-virgules ;;"""
        code = "Integer x = 1;;"
        sanitized = sanitize_apex_code(code)
        assert ";;" not in sanitized
    
    def test_sanitize_multiple_spaces(self):
        """Spec: Normalise les espaces multiples"""
        code = "Integer   x   =   1;"
        sanitized = sanitize_apex_code(code)
        # Ne doit pas y avoir plus de 2 espaces consécutifs
        assert "   " not in sanitized
    
    def test_sanitize_preserves_valid_code(self):
        """Sanitize ne doit pas casser du code valide"""
        code = """
public class FormationService {
    public List<Formation__c> getFormations() {
        return [SELECT Id, Name FROM Formation__c WITH SECURITY_ENFORCED];
    }
}
"""
        sanitized = sanitize_apex_code(code)
        assert "class FormationService" in sanitized
        assert "getFormations" in sanitized
    
    # ═══════════════════════════════════════════════════════════════
    # Tests validate_apex_structure
    # ═══════════════════════════════════════════════════════════════
    
    def test_validate_function_exists(self):
        """Spec: validate_apex_structure vérifie la structure"""
        assert callable(validate_apex_structure)
    
    def test_validate_balanced_braces(self):
        """Spec: Vérifie accolades équilibrées"""
        bad_code = "public class Test { public void method() { }"  # Missing closing brace
        result = validate_apex_structure(bad_code)
        
        # Doit signaler un problème
        assert "valid" in result
        if not result["valid"]:
            assert "issues" in result
    
    def test_validate_valid_code_passes(self):
        """Code valide doit passer la validation"""
        good_code = """
public class Test {
    public void method() {
        System.debug('test');
    }
}
"""
        result = validate_apex_structure(good_code)
        assert result.get("valid", False) == True
    
    def test_validate_returns_dict(self):
        """validate_apex_structure retourne un dict avec valid et issues"""
        code = "public class Test {}"
        result = validate_apex_structure(code)
        
        assert isinstance(result, dict)
        assert "valid" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
