"""
Tests unitaires pour Zara corrections BUILD v2
Basé sur la spec BUILD_V2_SPEC.md §5.2
"""
import pytest
import sys
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')

from agents.roles.salesforce_developer_lwc import (
    validate_lwc_naming,
    validate_lwc_structure,
    parse_lwc_files_robust
)


class TestZaraCorrections:
    """Tests pour les corrections Zara selon spec §5.2."""
    
    # ═══════════════════════════════════════════════════════════════
    # Tests validate_lwc_naming
    # ═══════════════════════════════════════════════════════════════
    
    def test_validate_lwc_naming_exists(self):
        """Spec: validate_lwc_naming force camelCase"""
        assert callable(validate_lwc_naming)
    
    def test_validate_lwc_naming_snake_case(self):
        """Convertit snake_case en camelCase"""
        assert validate_lwc_naming("formation_list") == "formationList"
    
    def test_validate_lwc_naming_kebab_case(self):
        """Convertit kebab-case en camelCase"""
        assert validate_lwc_naming("formation-list") == "formationList"
    
    def test_validate_lwc_naming_pascal_case(self):
        """Convertit PascalCase en camelCase (première lettre minuscule)"""
        result = validate_lwc_naming("FormationList")
        assert result[0].islower(), "Première lettre doit être minuscule"
        assert result == "formationList"
    
    def test_validate_lwc_naming_already_camel_case(self):
        """Préserve camelCase valide"""
        assert validate_lwc_naming("formationList") == "formationList"
    
    # ═══════════════════════════════════════════════════════════════
    # Tests validate_lwc_structure
    # ═══════════════════════════════════════════════════════════════
    
    def test_validate_lwc_structure_exists(self):
        """Spec: validate_lwc_structure vérifie la structure LWC"""
        assert callable(validate_lwc_structure)
    
    def test_validate_lwc_structure_returns_dict(self):
        """Retourne un dict avec valid et issues"""
        files = {
            "force-app/main/default/lwc/testComponent/testComponent.js": "export default class TestComponent extends LightningElement {}"
        }
        result = validate_lwc_structure(files)
        
        assert isinstance(result, dict)
        assert "valid" in result
        assert "issues" in result
    
    def test_validate_lwc_structure_detects_missing_export(self):
        """Détecte l'absence de export default class"""
        files = {
            "force-app/main/default/lwc/bad/bad.js": "class BadComponent {}"
        }
        result = validate_lwc_structure(files)
        
        # Doit signaler un problème
        assert len(result.get("issues", [])) > 0 or not result.get("valid", True)
    
    def test_validate_lwc_structure_detects_bad_naming(self):
        """Détecte le nommage non-camelCase"""
        files = {
            "force-app/main/default/lwc/bad_naming/bad_naming.js": "export default class BadNaming extends LightningElement {}"
        }
        result = validate_lwc_structure(files)
        
        # Doit signaler un problème de nommage
        has_naming_issue = any("nom" in str(i).lower() or "camel" in str(i).lower() 
                               for i in result.get("issues", []))
        assert has_naming_issue or len(result.get("issues", [])) > 0
    
    # ═══════════════════════════════════════════════════════════════
    # Tests parse_lwc_files_robust
    # ═══════════════════════════════════════════════════════════════
    
    def test_parse_lwc_files_robust_exists(self):
        """Spec: parse_lwc_files_robust parse avec fallback progressif"""
        assert callable(parse_lwc_files_robust)
    
    def test_parse_lwc_files_with_backticks(self):
        """Parse format standard avec backticks"""
        content = '''
```html
<!-- FILE: force-app/main/default/lwc/test/test.html -->
<template>
    <div>Test</div>
</template>
```

```javascript
// FILE: force-app/main/default/lwc/test/test.js
import { LightningElement } from 'lwc';
export default class Test extends LightningElement {}
```
'''
        files = parse_lwc_files_robust(content)
        
        assert len(files) >= 1
        # Au moins un fichier doit contenir "test"
        assert any("test" in path.lower() for path in files.keys())
    
    def test_parse_lwc_files_returns_dict(self):
        """Retourne toujours un dict"""
        content = "No valid files here"
        files = parse_lwc_files_robust(content)
        
        assert isinstance(files, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
