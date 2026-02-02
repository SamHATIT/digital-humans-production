"""
Phase Aggregator - BUILD v2
Fusionne les outputs des sous-lots en un output de phase unifié.
"""
import logging
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)


class PhaseAggregator:
    """
    Agrégateur de lots pour le BUILD v2.
    Fusionne les outputs de plusieurs lots en un output de phase unifié.
    """
    
    def aggregate(self, phase: int, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Agrège les résultats de lots selon la phase.
        
        Args:
            phase: Numéro de phase (1-6)
            batch_results: Liste des outputs de lots
            
        Returns:
            Output agrégé pour la phase
        """
        logger.info(f"[PhaseAggregator] Aggregating {len(batch_results)} batches for phase {phase}")
        
        if not batch_results:
            return {"phase": phase, "operations": [], "files": {}}
        
        if phase == 1:
            return self.aggregate_data_model(batch_results)
        elif phase == 2:
            return self.aggregate_source_code(batch_results, "apex")
        elif phase == 3:
            return self.aggregate_source_code(batch_results, "lwc")
        elif phase == 4:
            return self.aggregate_automation(batch_results)
        elif phase == 5:
            return self.aggregate_security(batch_results)
        elif phase == 6:
            return self.aggregate_data_migration(batch_results)
        else:
            logger.warning(f"[PhaseAggregator] Unknown phase {phase}")
            return {"phase": phase, "operations": [], "files": {}}
    
    def aggregate_data_model(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 1: Fusionne les plans JSON Raj en un plan unifié.
        Vérifie les collisions d'API names.
        """
        aggregated = {
            "phase": 1,
            "phase_name": "data_model",
            "operations": [],
            "metadata": {
                "total_batches": len(batch_results),
                "objects_count": 0,
                "fields_count": 0,
            }
        }
        
        seen_objects = set()
        seen_fields = {}  # {object: set(fields)}
        operation_order = 1
        
        for batch in batch_results:
            operations = batch.get("operations", [])
            
            for op in operations:
                op_type = op.get("type", "")
                api_name = op.get("api_name", "")
                obj = op.get("object", "")
                
                # Vérification collision objets
                if op_type == "create_object":
                    if api_name in seen_objects:
                        logger.warning(f"[Aggregator] Duplicate object ignored: {api_name}")
                        continue
                    seen_objects.add(api_name)
                    seen_fields[api_name] = set()
                    aggregated["metadata"]["objects_count"] += 1
                
                # Vérification collision champs
                elif op_type == "create_field":
                    if obj not in seen_fields:
                        seen_fields[obj] = set()
                    
                    if api_name in seen_fields[obj]:
                        logger.warning(f"[Aggregator] Duplicate field ignored: {obj}.{api_name}")
                        continue
                    seen_fields[obj].add(api_name)
                    aggregated["metadata"]["fields_count"] += 1
                
                # Ajouter l'opération avec un order global
                op_copy = op.copy()
                op_copy["order"] = operation_order
                aggregated["operations"].append(op_copy)
                operation_order += 1
        
        logger.info(f"[Aggregator] Data model aggregated: {aggregated['metadata']}")
        return aggregated
    
    def aggregate_source_code(self, batch_results: List[Dict[str, Any]], code_type: str) -> Dict[str, Any]:
        """
        Phase 2 (Apex) et Phase 3 (LWC): Fusionne les fichiers source.
        """
        phase = 2 if code_type == "apex" else 3
        phase_name = "business_logic" if code_type == "apex" else "ui_components"
        
        aggregated = {
            "phase": phase,
            "phase_name": phase_name,
            "files": {},
            "metadata": {
                "total_batches": len(batch_results),
                "files_count": 0,
            }
        }
        
        seen_files = set()
        
        for batch in batch_results:
            files = batch.get("files", {})
            
            for path, content in files.items():
                # Normaliser le path
                normalized_path = self._normalize_path(path)
                
                if normalized_path in seen_files:
                    logger.warning(f"[Aggregator] Duplicate file ignored: {normalized_path}")
                    continue
                
                seen_files.add(normalized_path)
                aggregated["files"][normalized_path] = content
                aggregated["metadata"]["files_count"] += 1
        
        logger.info(f"[Aggregator] {code_type} code aggregated: {aggregated['metadata']['files_count']} files")
        return aggregated
    
    def aggregate_automation(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 4: Fusionne flows + validation rules complexes.
        Mix de JSON (VRs) et XML (Flows).
        """
        aggregated = {
            "phase": 4,
            "phase_name": "automation",
            "operations": [],  # VRs, Approval Processes
            "files": {},       # Flows (XML)
            "metadata": {
                "total_batches": len(batch_results),
                "flows_count": 0,
                "vrs_count": 0,
            }
        }
        
        seen_flows = set()
        seen_vrs = set()
        operation_order = 1
        
        for batch in batch_results:
            # Operations (VRs, Approvals)
            for op in batch.get("operations", []):
                op_type = op.get("type", "")
                api_name = op.get("api_name", "")
                obj = op.get("object", "")
                
                full_name = f"{obj}.{api_name}" if obj else api_name
                
                if op_type in ("complex_validation_rule", "create_validation_rule"):
                    if full_name in seen_vrs:
                        continue
                    seen_vrs.add(full_name)
                    aggregated["metadata"]["vrs_count"] += 1
                
                elif op_type == "create_flow":
                    if api_name in seen_flows:
                        continue
                    seen_flows.add(api_name)
                    aggregated["metadata"]["flows_count"] += 1
                
                op_copy = op.copy()
                op_copy["order"] = operation_order
                aggregated["operations"].append(op_copy)
                operation_order += 1
            
            # Files (Flow XML)
            for path, content in batch.get("files", {}).items():
                normalized_path = self._normalize_path(path)
                if normalized_path not in aggregated["files"]:
                    aggregated["files"][normalized_path] = content
        
        logger.info(f"[Aggregator] Automation aggregated: {aggregated['metadata']}")
        return aggregated
    
    def aggregate_security(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 5: Fusionne permission sets, profiles, sharing rules, layouts.
        """
        aggregated = {
            "phase": 5,
            "phase_name": "security",
            "operations": [],
            "files": {},
            "metadata": {
                "total_batches": len(batch_results),
                "permission_sets_count": 0,
                "profiles_count": 0,
                "layouts_count": 0,
            }
        }
        
        seen_ps = set()
        seen_profiles = set()
        seen_layouts = set()
        operation_order = 1
        
        for batch in batch_results:
            for op in batch.get("operations", []):
                op_type = op.get("type", "")
                api_name = op.get("api_name", "")
                
                if op_type == "create_permission_set":
                    if api_name in seen_ps:
                        continue
                    seen_ps.add(api_name)
                    aggregated["metadata"]["permission_sets_count"] += 1
                
                elif op_type in ("profile", "create_profile"):
                    if api_name in seen_profiles:
                        continue
                    seen_profiles.add(api_name)
                    aggregated["metadata"]["profiles_count"] += 1
                
                elif op_type in ("page_layout", "create_page_layout"):
                    if api_name in seen_layouts:
                        continue
                    seen_layouts.add(api_name)
                    aggregated["metadata"]["layouts_count"] += 1
                
                op_copy = op.copy()
                op_copy["order"] = operation_order
                aggregated["operations"].append(op_copy)
                operation_order += 1
            
            # Files (Profiles, Layouts XML)
            for path, content in batch.get("files", {}).items():
                normalized_path = self._normalize_path(path)
                if normalized_path not in aggregated["files"]:
                    aggregated["files"][normalized_path] = content
        
        logger.info(f"[Aggregator] Security aggregated: {aggregated['metadata']}")
        return aggregated
    
    def aggregate_data_migration(self, batch_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phase 6: Fusionne scripts migration (SDL, Apex anonymous, SOQL).
        """
        aggregated = {
            "phase": 6,
            "phase_name": "data_migration",
            "files": {},
            "scripts": [],  # Scripts Apex anonymous à exécuter
            "metadata": {
                "total_batches": len(batch_results),
                "files_count": 0,
                "scripts_count": 0,
            }
        }
        
        for batch in batch_results:
            # Files (SDL, CSV templates, SOQL)
            for path, content in batch.get("files", {}).items():
                normalized_path = self._normalize_path(path)
                if normalized_path not in aggregated["files"]:
                    aggregated["files"][normalized_path] = content
                    aggregated["metadata"]["files_count"] += 1
            
            # Scripts Apex anonymous
            for script in batch.get("scripts", []):
                aggregated["scripts"].append(script)
                aggregated["metadata"]["scripts_count"] += 1
        
        logger.info(f"[Aggregator] Data migration aggregated: {aggregated['metadata']}")
        return aggregated
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalise un chemin de fichier.
        Assure que le path commence par force-app/main/default/.
        """
        # Supprimer les marqueurs de fichier
        path = path.replace("// FILE:", "").replace("<!-- FILE:", "").replace("-->", "").strip()
        
        # Supprimer un éventuel leading slash
        if path.startswith("/"):
            path = path[1:]
        
        # S'assurer que le path commence correctement
        if not path.startswith("force-app/"):
            if "classes/" in path or "triggers/" in path:
                path = f"force-app/main/default/{path}"
            elif "lwc/" in path:
                path = f"force-app/main/default/{path}"
        
        return path
    
    def validate_aggregated_output(self, phase: int, aggregated: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valide l'output agrégé et retourne un rapport de validation.
        """
        issues = []
        
        if phase == 1:
            # Vérifier que chaque champ référence un objet existant
            objects = {op["api_name"] for op in aggregated.get("operations", []) if op.get("type") == "create_object"}
            for op in aggregated.get("operations", []):
                if op.get("type") == "create_field":
                    if op.get("object") not in objects:
                        issues.append({
                            "severity": "critical",
                            "issue": f"Field {op.get('api_name')} references non-existent object {op.get('object')}"
                        })
        
        elif phase in (2, 3):
            # Vérifier que les fichiers ne sont pas vides
            for path, content in aggregated.get("files", {}).items():
                if not content or len(content.strip()) < 10:
                    issues.append({
                        "severity": "warning",
                        "issue": f"File {path} appears to be empty or very short"
                    })
        
        return {
            "valid": len([i for i in issues if i["severity"] == "critical"]) == 0,
            "issues": issues,
            "files_count": len(aggregated.get("files", {})),
            "operations_count": len(aggregated.get("operations", [])),
        }
