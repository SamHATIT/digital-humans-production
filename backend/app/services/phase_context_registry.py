"""
Phase Context Registry - BUILD v2
Maintient le contexte progressif entre les lots et les phases.
"""
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, field
import re

logger = logging.getLogger(__name__)


@dataclass
class PhaseContextRegistry:
    """
    Registre de contexte progressif pour le BUILD v2.
    Chaque lot enrichit ce registre. Les lots suivants reçoivent ce contexte dans leur prompt.
    """
    
    # Phase 1: Data Model
    generated_objects: List[str] = field(default_factory=list)
    generated_fields: Dict[str, List[str]] = field(default_factory=dict)
    generated_record_types: Dict[str, List[str]] = field(default_factory=dict)
    generated_validation_rules: List[str] = field(default_factory=list)
    
    # Phase 2: Business Logic
    generated_classes: Dict[str, List[str]] = field(default_factory=dict)
    generated_triggers: List[str] = field(default_factory=list)
    
    # Phase 3: UI Components
    generated_components: Dict[str, List[str]] = field(default_factory=dict)
    
    # Phase 4: Automation
    generated_flows: List[str] = field(default_factory=list)
    generated_complex_vrs: List[str] = field(default_factory=list)
    
    # Phase 5: Security
    generated_permission_sets: List[str] = field(default_factory=list)
    generated_profiles: List[str] = field(default_factory=list)
    
    # Phase 6: Data Migration
    generated_migration_scripts: List[str] = field(default_factory=list)
    
    # Deployed components (après validation Jordan)
    deployed_components: Dict[int, List[str]] = field(default_factory=dict)
    
    # ═══════════════════════════════════════════════════════════════
    # REGISTRATION METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def register_batch_output(self, phase: int, output: Dict[str, Any]) -> None:
        """Met à jour le registre après un lot."""
        logger.info(f"[PhaseContextRegistry] Registering batch output for phase {phase}")
        
        if phase == 1:
            self._register_data_model(output)
        elif phase == 2:
            self._register_business_logic(output)
        elif phase == 3:
            self._register_ui_components(output)
        elif phase == 4:
            self._register_automation(output)
        elif phase == 5:
            self._register_security(output)
        elif phase == 6:
            self._register_data_migration(output)
    
    def _register_data_model(self, output: Dict[str, Any]) -> None:
        """Enregistre les outputs Phase 1 (Raj Data Model)."""
        operations = output.get("operations", [])
        
        for op in operations:
            op_type = op.get("type", "")
            
            if op_type == "create_object":
                api_name = op.get("api_name", "")
                if api_name and api_name not in self.generated_objects:
                    self.generated_objects.append(api_name)
                    self.generated_fields[api_name] = []
                    logger.debug(f"[Registry] Object registered: {api_name}")
                    
            elif op_type == "create_field":
                obj = op.get("object", "")
                field_name = op.get("api_name", "")
                if obj and field_name:
                    if obj not in self.generated_fields:
                        self.generated_fields[obj] = []
                    if field_name not in self.generated_fields[obj]:
                        self.generated_fields[obj].append(field_name)
                        
            elif op_type == "create_record_type":
                obj = op.get("object", "")
                rt_name = op.get("api_name", "")
                if obj and rt_name:
                    if obj not in self.generated_record_types:
                        self.generated_record_types[obj] = []
                    if rt_name not in self.generated_record_types[obj]:
                        self.generated_record_types[obj].append(rt_name)
                        
            elif op_type in ("create_validation_rule", "simple_validation_rule"):
                obj = op.get("object", "")
                vr_name = op.get("api_name", "")
                full_name = f"{obj}.{vr_name}" if obj else vr_name
                if full_name not in self.generated_validation_rules:
                    self.generated_validation_rules.append(full_name)
    
    def _register_business_logic(self, output: Dict[str, Any]) -> None:
        """Enregistre les outputs Phase 2 (Diego Apex)."""
        files = output.get("files", {})
        
        for path, content in files.items():
            if path.endswith(".cls") and not path.endswith("Test.cls"):
                class_name = self._extract_class_name(path, content)
                methods = self._extract_public_methods(content)
                if class_name:
                    self.generated_classes[class_name] = methods
                    logger.debug(f"[Registry] Class registered: {class_name}")
                    
            elif path.endswith(".trigger"):
                trigger_name = self._extract_trigger_name(path)
                if trigger_name and trigger_name not in self.generated_triggers:
                    self.generated_triggers.append(trigger_name)
    
    def _register_ui_components(self, output: Dict[str, Any]) -> None:
        """Enregistre les outputs Phase 3 (Zara LWC)."""
        files = output.get("files", {})
        
        for path, content in files.items():
            if "/lwc/" in path and path.endswith(".js"):
                component_name = self._extract_lwc_name(path)
                props = self._extract_public_props(content)
                if component_name:
                    self.generated_components[component_name] = props
                    logger.debug(f"[Registry] LWC registered: {component_name}")
    
    def _register_automation(self, output: Dict[str, Any]) -> None:
        """Enregistre les outputs Phase 4 (Raj Automation)."""
        operations = output.get("operations", [])
        
        for op in operations:
            op_type = op.get("type", "")
            
            if op_type == "create_flow":
                flow_name = op.get("api_name", "")
                if flow_name and flow_name not in self.generated_flows:
                    self.generated_flows.append(flow_name)
                    
            elif op_type == "complex_validation_rule":
                obj = op.get("object", "")
                vr_name = op.get("api_name", "")
                full_name = f"{obj}.{vr_name}" if obj else vr_name
                if full_name not in self.generated_complex_vrs:
                    self.generated_complex_vrs.append(full_name)
    
    def _register_security(self, output: Dict[str, Any]) -> None:
        """Enregistre les outputs Phase 5 (Raj Security)."""
        operations = output.get("operations", [])
        
        for op in operations:
            op_type = op.get("type", "")
            
            if op_type == "create_permission_set":
                ps_name = op.get("api_name", "")
                if ps_name and ps_name not in self.generated_permission_sets:
                    self.generated_permission_sets.append(ps_name)
                    
            elif op_type in ("profile", "create_profile"):
                profile_name = op.get("api_name", "")
                if profile_name and profile_name not in self.generated_profiles:
                    self.generated_profiles.append(profile_name)
    
    def _register_data_migration(self, output: Dict[str, Any]) -> None:
        """Enregistre les outputs Phase 6 (Aisha Data Migration)."""
        files = output.get("files", {})
        
        for path in files.keys():
            if path not in self.generated_migration_scripts:
                self.generated_migration_scripts.append(path)
    
    def mark_phase_deployed(self, phase: int, components: List[str]) -> None:
        """Marque les composants d'une phase comme déployés."""
        self.deployed_components[phase] = components
        logger.info(f"[Registry] Phase {phase} marked as deployed: {len(components)} components")
    
    # ═══════════════════════════════════════════════════════════════
    # CONTEXT RETRIEVAL METHODS
    # ═══════════════════════════════════════════════════════════════
    
    def get_context_for_batch(self, phase: int, include_previous_batches: bool = True) -> str:
        """
        Retourne le contexte à injecter dans le prompt du lot.
        
        Args:
            phase: Numéro de phase (1-6)
            include_previous_batches: Inclure les lots précédents de la même phase
            
        Returns:
            Contexte formaté pour injection dans le prompt
        """
        context_parts = []
        
        if phase == 1 and include_previous_batches:
            if self.generated_objects:
                context_parts.append(self._format_phase1_partial())
        
        elif phase == 2:
            context_parts.append(self.get_full_data_model())
            if include_previous_batches and self.generated_classes:
                context_parts.append(self.get_class_signatures())
        
        elif phase == 3:
            context_parts.append(self.get_full_data_model())
            context_parts.append(self.get_class_signatures())
            if include_previous_batches and self.generated_components:
                context_parts.append(self.get_component_signatures())
        
        elif phase == 4:
            context_parts.append(self.get_full_data_model())
            context_parts.append(self.get_class_signatures())
            if include_previous_batches and self.generated_flows:
                context_parts.append(self._format_phase4_context())
        
        elif phase == 5:
            context_parts.append(self.get_full_data_model())
            context_parts.append(self.get_class_signatures())
            context_parts.append(self.get_component_signatures())
            context_parts.append(self._format_phase4_context())
        
        elif phase == 6:
            context_parts.append(self.get_full_data_model())
            context_parts.append(self.get_class_signatures())
            context_parts.append(self.get_component_signatures())
            context_parts.append(self._format_phase4_context())
            context_parts.append(self._format_phase5_context())
        
        return "\n\n".join(filter(None, context_parts))
    
    def get_full_data_model(self) -> str:
        """Retourne le modèle de données complet (Phase 1)."""
        if not self.generated_objects:
            return ""
        
        lines = ["## MODÈLE DE DONNÉES DISPONIBLE (Phase 1 déployée)", ""]
        
        for obj in self.generated_objects:
            lines.append(f"### {obj}")
            
            fields = self.generated_fields.get(obj, [])
            if fields:
                lines.append("**Champs:** " + ", ".join(fields))
            
            rts = self.generated_record_types.get(obj, [])
            if rts:
                lines.append("**Record Types:** " + ", ".join(rts))
            
            lines.append("")
        
        if self.generated_validation_rules:
            lines.append("### Validation Rules")
            for vr in self.generated_validation_rules:
                lines.append(f"  - {vr}")
            lines.append("")
        
        lines.append("⚠️ UTILISEZ UNIQUEMENT ces objets et champs dans vos requêtes SOQL/SOSL.")
        
        return "\n".join(lines)
    
    def get_class_signatures(self) -> str:
        """Retourne les signatures des classes Apex (Phase 2)."""
        if not self.generated_classes and not self.generated_triggers:
            return ""
        
        lines = ["## CLASSES APEX DISPONIBLES (Phase 2 déployée)", ""]
        
        for class_name, methods in self.generated_classes.items():
            lines.append(f"### {class_name}")
            if methods:
                lines.append("**Méthodes:** " + ", ".join(methods))
            lines.append("")
        
        if self.generated_triggers:
            lines.append("### Triggers: " + ", ".join(self.generated_triggers))
            lines.append("")
        
        lines.append("⚠️ Vous pouvez appeler ces classes. NE LES REDÉFINISSEZ PAS.")
        
        return "\n".join(lines)
    
    def get_component_signatures(self) -> str:
        """Retourne les signatures des composants LWC (Phase 3)."""
        if not self.generated_components:
            return ""
        
        lines = ["## COMPOSANTS LWC DISPONIBLES (Phase 3 déployée)", ""]
        
        for comp_name, props in self.generated_components.items():
            lines.append(f"### {comp_name}")
            if props:
                lines.append("**Props @api:** " + ", ".join(props))
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_phase1_partial(self) -> str:
        """Contexte partiel Phase 1 (pour lots suivants de Phase 1)."""
        if not self.generated_objects:
            return ""
        
        lines = ["## OBJETS DÉJÀ CRÉÉS (lots précédents)", ""]
        lines.append("**Objets:** " + ", ".join(self.generated_objects))
        lines.append("")
        lines.append("⚠️ Ne recréez pas ces objets.")
        
        return "\n".join(lines)
    
    def _format_phase4_context(self) -> str:
        """Contexte Phase 4 (Flows et VRs complexes)."""
        if not self.generated_flows and not self.generated_complex_vrs:
            return ""
        
        lines = ["## AUTOMATISATIONS DISPONIBLES (Phase 4 déployée)", ""]
        
        if self.generated_flows:
            lines.append("**Flows:** " + ", ".join(self.generated_flows))
        if self.generated_complex_vrs:
            lines.append("**Validation Rules complexes:** " + ", ".join(self.generated_complex_vrs))
        
        return "\n".join(lines)
    
    def _format_phase5_context(self) -> str:
        """Contexte Phase 5 (Security)."""
        if not self.generated_permission_sets and not self.generated_profiles:
            return ""
        
        lines = ["## SÉCURITÉ CONFIGURÉE (Phase 5 déployée)", ""]
        
        if self.generated_permission_sets:
            lines.append("**Permission Sets:** " + ", ".join(self.generated_permission_sets))
        if self.generated_profiles:
            lines.append("**Profiles modifiés:** " + ", ".join(self.generated_profiles))
        
        return "\n".join(lines)
    
    # ═══════════════════════════════════════════════════════════════
    # EXTRACTION HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _extract_class_name(self, path: str, content: str) -> str:
        """Extrait le nom de classe depuis le path ou le contenu."""
        # Essayer depuis le path
        match = re.search(r'/([^/]+)\.cls$', path)
        if match:
            return match.group(1)
        
        # Fallback: depuis le contenu
        match = re.search(r'(?:public|private|global)\s+(?:with\s+sharing\s+)?class\s+(\w+)', content)
        if match:
            return match.group(1)
        
        return ""
    
    def _extract_trigger_name(self, path: str) -> str:
        """Extrait le nom du trigger depuis le path."""
        match = re.search(r'/([^/]+)\.trigger$', path)
        return match.group(1) if match else ""
    
    def _extract_public_methods(self, content: str) -> List[str]:
        """Extrait les signatures des méthodes publiques."""
        methods = []
        pattern = r'(?:public|global)\s+(?:static\s+)?(\w+)\s+(\w+)\s*\([^)]*\)'
        
        for match in re.finditer(pattern, content):
            return_type = match.group(1)
            method_name = match.group(2)
            if method_name not in ('class', 'interface'):
                methods.append(f"{method_name}()")
        
        return methods[:10]  # Limiter à 10 méthodes
    
    def _extract_lwc_name(self, path: str) -> str:
        """Extrait le nom du composant LWC depuis le path."""
        match = re.search(r'/lwc/([^/]+)/', path)
        return match.group(1) if match else ""
    
    def _extract_public_props(self, content: str) -> List[str]:
        """Extrait les propriétés @api d'un composant LWC."""
        props = []
        pattern = r'@api\s+(\w+)'
        
        for match in re.finditer(pattern, content):
            props.append(match.group(1))
        
        return props
    
    # ═══════════════════════════════════════════════════════════════
    # SERIALIZATION
    # ═══════════════════════════════════════════════════════════════
    
    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le registre en dictionnaire."""
        return {
            "generated_objects": self.generated_objects,
            "generated_fields": self.generated_fields,
            "generated_record_types": self.generated_record_types,
            "generated_validation_rules": self.generated_validation_rules,
            "generated_classes": self.generated_classes,
            "generated_triggers": self.generated_triggers,
            "generated_components": self.generated_components,
            "generated_flows": self.generated_flows,
            "generated_complex_vrs": self.generated_complex_vrs,
            "generated_permission_sets": self.generated_permission_sets,
            "generated_profiles": self.generated_profiles,
            "generated_migration_scripts": self.generated_migration_scripts,
            "deployed_components": self.deployed_components,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PhaseContextRegistry":
        """Désérialise un dictionnaire en registre."""
        registry = cls()
        registry.generated_objects = data.get("generated_objects", [])
        registry.generated_fields = data.get("generated_fields", {})
        registry.generated_record_types = data.get("generated_record_types", {})
        registry.generated_validation_rules = data.get("generated_validation_rules", [])
        registry.generated_classes = data.get("generated_classes", {})
        registry.generated_triggers = data.get("generated_triggers", [])
        registry.generated_components = data.get("generated_components", {})
        registry.generated_flows = data.get("generated_flows", [])
        registry.generated_complex_vrs = data.get("generated_complex_vrs", [])
        registry.generated_permission_sets = data.get("generated_permission_sets", [])
        registry.generated_profiles = data.get("generated_profiles", [])
        registry.generated_migration_scripts = data.get("generated_migration_scripts", [])
        registry.deployed_components = {int(k): v for k, v in data.get("deployed_components", {}).items()}
        return registry
