#!/usr/bin/env python3
"""
Tests d'intégration pour Phase 4 - Emma Write_SDS

Scénarios testés:
1. Template service fonctionne
2. Prompts write_sds sont définis
3. Fonction run_write_sds_mode existe
4. Markdown to DOCX converter fonctionne
5. Orchestrator Phase 5 appelle Emma write_sds
"""

import sys
import os

# Add backend to path
sys.path.insert(0, '/root/workspace/digital-humans-production/backend')


def test_template_service():
    """Test 1: Template service loads and returns template."""
    try:
        from app.services.sds_template_service import get_sds_template_service
        service = get_sds_template_service()
        template = service.get_default_template()
        
        assert template is not None, "Template should not be None"
        assert "sections" in template, "Template should have sections"
        assert len(template["sections"]) >= 5, "Template should have at least 5 sections"
        
        print("✅ Test 1: Template service works")
        return True
    except Exception as e:
        print(f"❌ Test 1: Template service error: {e}")
        return False


def test_write_sds_prompts():
    """Test 2: Write_SDS prompts are defined."""
    try:
        from agents.roles.salesforce_research_analyst import (
            WRITE_SDS_SYSTEM,
            WRITE_FULL_SDS_PROMPT,
            WRITE_SECTION_PROMPT,
            SECTION_GUIDANCE
        )
        
        assert "Emma" in WRITE_SDS_SYSTEM, "System prompt should mention Emma"
        assert "GÉNÉRATION" in WRITE_FULL_SDS_PROMPT or "document" in WRITE_FULL_SDS_PROMPT.lower()
        assert "{section_id}" in WRITE_SECTION_PROMPT, "Section prompt should have placeholders"
        assert isinstance(SECTION_GUIDANCE, dict), "SECTION_GUIDANCE should be a dict"
        assert len(SECTION_GUIDANCE) >= 5, "Should have guidance for at least 5 sections"
        
        print("✅ Test 2: Write_SDS prompts defined correctly")
        return True
    except ImportError as e:
        print(f"❌ Test 2: Import error: {e}")
        return False
    except AssertionError as e:
        print(f"❌ Test 2: Assertion error: {e}")
        return False


def test_run_write_sds_mode_exists():
    """Test 3: run_write_sds_mode function exists."""
    try:
        from agents.roles.salesforce_research_analyst import run_write_sds_mode
        import inspect
        
        assert callable(run_write_sds_mode), "Should be callable"
        assert inspect.iscoroutinefunction(run_write_sds_mode), "Should be async function"
        
        sig = inspect.signature(run_write_sds_mode)
        params = list(sig.parameters.keys())
        assert "input_data" in params, "Should have input_data parameter"
        assert "execution_id" in params, "Should have execution_id parameter"
        
        print("✅ Test 3: run_write_sds_mode exists and is async")
        return True
    except Exception as e:
        print(f"❌ Test 3: Error: {e}")
        return False


def test_markdown_to_docx():
    """Test 4: Markdown to DOCX converter works."""
    try:
        from app.services.markdown_to_docx import convert_markdown_to_docx, DOCX_AVAILABLE
        
        if not DOCX_AVAILABLE:
            print("⚠️ Test 4: python-docx not available (expected in some envs)")
            return True
        
        test_md = """# Test SDS
## Section 1
This is a **bold** and *italic* test.

| Col1 | Col2 |
|------|------|
| A    | B    |

```mermaid
erDiagram
    Account {
        Id PK
        Name string
    }
```
"""
        
        output_path = "/tmp/test_p4_sds.docx"
        result = convert_markdown_to_docx(test_md, output_path, "Test Project")
        
        assert os.path.exists(result), "Output file should exist"
        assert os.path.getsize(result) > 10000, "File should have reasonable size"
        
        # Cleanup
        os.unlink(result)
        
        print("✅ Test 4: Markdown to DOCX converter works")
        return True
    except Exception as e:
        print(f"❌ Test 4: Error: {e}")
        return False


def test_orchestrator_phase5():
    """Test 5: Orchestrator Phase 5 calls Emma write_sds."""
    try:
        with open('/root/workspace/digital-humans-production/backend/app/services/pm_orchestrator_service_v2.py', 'r') as f:
            content = f.read()
        
        # Check for Emma write_sds integration
        assert 'Emma Research Analyst - Writing SDS' in content or 'emma_write_input' in content, \
            "Phase 5 should call Emma write_sds"
        assert 'mode="write_sds"' in content, "Should have write_sds mode call"
        assert 'sds_markdown' in content, "Should handle sds_markdown"
        
        print("✅ Test 5: Orchestrator Phase 5 integrates Emma write_sds")
        return True
    except Exception as e:
        print(f"❌ Test 5: Error: {e}")
        return False


def test_mermaid_formatting():
    """Test 6: Mermaid diagrams are converted to tables."""
    try:
        from app.services.markdown_to_docx import _format_mermaid_as_tables, DOCX_AVAILABLE
        
        if not DOCX_AVAILABLE:
            print("⚠️ Test 6: Skipped (python-docx not available)")
            return True
        
        from docx import Document
        doc = Document()
        
        mermaid_code = """erDiagram
    Account {
        Id PK
        Name string
    }
    Contact {
        Id PK
        AccountId FK
    }
    Account ||--o{ Contact : "has many"
"""
        
        # This should not raise an error
        _format_mermaid_as_tables(doc, mermaid_code)
        
        # Check that paragraphs were added (tables create paragraphs)
        assert len(doc.paragraphs) > 0, "Should have created content"
        
        print("✅ Test 6: Mermaid diagrams format correctly")
        return True
    except Exception as e:
        print(f"❌ Test 6: Error: {e}")
        return False


# Run all tests
if __name__ == "__main__":
    print("=" * 60)
    print("Phase 4 Integration Tests - Emma Write_SDS")
    print("=" * 60)
    
    results = []
    results.append(test_template_service())
    results.append(test_write_sds_prompts())
    results.append(test_run_write_sds_mode_exists())
    results.append(test_markdown_to_docx())
    results.append(test_orchestrator_phase5())
    results.append(test_mermaid_formatting())
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All Phase 4 tests PASSED!")
    else:
        print("⚠️ Some tests failed")
    print("=" * 60)
