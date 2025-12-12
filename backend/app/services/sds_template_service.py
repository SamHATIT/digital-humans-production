"""
SDS Template Service
Gestion des templates pour la génération de documents SDS.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Path to templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "sds"


class SDSTemplateService:
    """Service for managing SDS document templates."""
    
    def __init__(self):
        self._templates_cache: Dict[str, Dict] = {}
        self._load_templates()
    
    def _load_templates(self):
        """Load all templates from the templates directory."""
        if not TEMPLATES_DIR.exists():
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            return
        
        for template_file in TEMPLATES_DIR.glob("*.json"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    template = json.load(f)
                    template_id = template.get('template_id', template_file.stem)
                    self._templates_cache[template_id] = template
            except Exception as e:
                print(f"⚠️ Error loading template {template_file}: {e}")
    
    def get_template(self, template_id: str = "SDS-TEMPLATE-001") -> Optional[Dict]:
        """Get a template by ID."""
        return self._templates_cache.get(template_id)
    
    def get_default_template(self) -> Dict:
        """Get the default SDS template."""
        return self.get_template("SDS-TEMPLATE-001") or self._create_minimal_template()
    
    def list_templates(self) -> List[Dict]:
        """List all available templates with metadata."""
        return [
            {
                "template_id": t.get("template_id"),
                "template_name": t.get("template_name"),
                "language": t.get("language"),
                "section_count": len(t.get("sections", [])),
                "description": t.get("metadata", {}).get("description", "")
            }
            for t in self._templates_cache.values()
        ]
    
    def get_section(self, template_id: str, section_id: str) -> Optional[Dict]:
        """Get a specific section from a template."""
        template = self.get_template(template_id)
        if not template:
            return None
        
        for section in template.get("sections", []):
            if section.get("id") == section_id:
                return section
        return None
    
    def get_sections_for_sources(self, template_id: str, available_sources: List[str]) -> List[Dict]:
        """Get sections that can be generated with the available data sources."""
        template = self.get_template(template_id)
        if not template:
            return []
        
        applicable_sections = []
        for section in template.get("sections", []):
            section_sources = set()
            for subsection in section.get("subsections", []):
                source = subsection.get("source", "").split(".")[0]
                section_sources.add(source)
            
            # Check if at least one source is available
            if section_sources & set(available_sources):
                applicable_sections.append(section)
        
        return applicable_sections
    
    def extract_data_for_section(self, sources: Dict, source_path: str) -> Any:
        """Extract data from sources using dot notation path."""
        if not source_path or source_path == "auto_generated":
            return None
        
        parts = source_path.split(".")
        data = sources
        
        for part in parts:
            if isinstance(data, dict):
                data = data.get(part)
            elif isinstance(data, list) and part.startswith("[") and part.endswith("]"):
                # Handle array indexing like [0] or [] for all
                if part == "[]":
                    return data  # Return full list
                try:
                    idx = int(part[1:-1])
                    data = data[idx] if idx < len(data) else None
                except ValueError:
                    return None
            else:
                return None
            
            if data is None:
                return None
        
        return data
    
    def _create_minimal_template(self) -> Dict:
        """Create a minimal template if no templates are found."""
        return {
            "template_id": "SDS-MINIMAL",
            "template_name": "Minimal SDS Template",
            "language": "fr",
            "sections": [
                {
                    "id": "1",
                    "title": "Résumé Exécutif",
                    "subsections": [
                        {"id": "1.1", "title": "Contexte", "source": "project_info", "format": "prose"}
                    ]
                },
                {
                    "id": "2",
                    "title": "Exigences Métier",
                    "subsections": [
                        {"id": "2.1", "title": "Business Requirements", "source": "business_requirements", "format": "summary_table"}
                    ]
                },
                {
                    "id": "3",
                    "title": "Architecture Technique",
                    "subsections": [
                        {"id": "3.1", "title": "Solution Design", "source": "solution_design", "format": "prose"}
                    ]
                }
            ]
        }


# Singleton instance
_service_instance = None

def get_sds_template_service() -> SDSTemplateService:
    """Get or create the singleton SDSTemplateService instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SDSTemplateService()
    return _service_instance


# Quick test
if __name__ == "__main__":
    service = get_sds_template_service()
    templates = service.list_templates()
    print(f"📋 Templates disponibles: {len(templates)}")
    for t in templates:
        print(f"   - {t['template_id']}: {t['template_name']} ({t['section_count']} sections)")
    
    default = service.get_default_template()
    print(f"\n📄 Template par défaut: {default.get('template_name')}")
    print(f"   Sections: {[s.get('title') for s in default.get('sections', [])]}")
