"""
SF Admin Service - BUILD v2
Exécute les plans JSON Raj via l'API Salesforce (Tooling API / Metadata API).
"""
import logging
import httpx
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolingAPIResult:
    """Résultat d'une opération Tooling API."""
    success: bool
    id: Optional[str] = None
    errors: List[str] = None
    operation: str = ""
    api_name: str = ""
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SFAdminService:
    """
    Service d'administration Salesforce pour le BUILD v2.
    Exécute les plans JSON générés par Raj via Tooling API.
    """
    
    API_VERSION = "59.0"
    
    
    # Mapping operation type -> handler method name (spec §6.5)
    OPERATION_HANDLERS = {
        "create_object": "_create_custom_object",
        "create_field": "_create_custom_field",
        "create_record_type": "_create_record_type",
        "create_list_view": "_create_list_view",
        "create_validation_rule": "_create_validation_rule",
        "create_flow": "_create_flow",
        "create_permission_set": "_create_permission_set",
        "create_page_layout": "_create_page_layout",
        "create_sharing_rule": "_create_sharing_rule",
        "create_approval_process": "_create_approval_process",
    }
    # Mapping field_type vers Salesforce FieldType
    FIELD_TYPE_MAPPING = {
        "Text": "Text",
        "TextArea": "TextArea",
        "LongTextArea": "LongTextArea",
        "Number": "Number",
        "Currency": "Currency",
        "Percent": "Percent",
        "Date": "Date",
        "DateTime": "DateTime",
        "Checkbox": "Checkbox",
        "Email": "Email",
        "Phone": "Phone",
        "Url": "Url",
        "Picklist": "Picklist",
        "MultiselectPicklist": "MultiselectPicklist",
        "Lookup": "Lookup",
        "MasterDetail": "MasterDetail",
        "Formula": "Text",  # Formula fields need special handling
        "AutoNumber": "AutoNumber",
    }
    
    # Alias for spec compatibility (spec uses FIELD_TYPE_MAP)
    FIELD_TYPE_MAP = FIELD_TYPE_MAPPING
    
    def __init__(self, instance_url: str, access_token: str):
        """
        Args:
            instance_url: URL de l'instance Salesforce (ex: https://myorg.my.salesforce.com)
            access_token: Token d'accès OAuth ou session ID
        """
        self.instance_url = instance_url.rstrip("/")
        self.access_token = access_token
        self.base_url = f"{self.instance_url}/services/data/v{self.API_VERSION}"
        self.tooling_url = f"{self.base_url}/tooling"
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        
        # Track created components for rollback
        self.created_components: List[Dict[str, str]] = []
    
    async def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Exécute un plan JSON complet.
        
        Args:
            plan: Plan JSON avec liste d'operations
            
        Returns:
            Résultat avec succès/échec par opération
        """
        operations = plan.get("operations", [])
        results = []
        all_success = True
        
        logger.info(f"[SFAdmin] Executing plan with {len(operations)} operations")
        
        # Trier par order si présent
        sorted_ops = sorted(operations, key=lambda x: x.get("order", 0))
        
        for op in sorted_ops:
            op_type = op.get("type", "")
            result = await self._execute_operation(op)
            results.append(result.__dict__)
            
            if not result.success:
                all_success = False
                logger.error(f"[SFAdmin] Operation failed: {op_type} - {result.errors}")
                # Continue avec les autres opérations au lieu d'arrêter
        
        return {
            "success": all_success,
            "results": results,
            "total_operations": len(operations),
            "successful_operations": len([r for r in results if r["success"]]),
            "failed_operations": len([r for r in results if not r["success"]]),
            "created_components": self.created_components,
        }
    
    async def _execute_operation(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Route l'opération vers le handler approprié."""
        op_type = op.get("type", "")
        
        handlers = {
            "create_object": self._create_custom_object,
            "create_field": self._create_custom_field,
            "create_record_type": self._create_record_type,
            "create_list_view": self._create_list_view,
            "create_validation_rule": self._create_validation_rule,
            "create_flow": self._create_flow,
            "create_permission_set": self._create_permission_set,
            "create_page_layout": self._create_page_layout,
            "create_sharing_rule": self._create_sharing_rule,
        }
        
        handler = handlers.get(op_type)
        if not handler:
            return ToolingAPIResult(
                success=False,
                errors=[f"Unknown operation type: {op_type}"],
                operation=op_type,
                api_name=op.get("api_name", "")
            )
        
        try:
            return await handler(op)
        except Exception as e:
            logger.exception(f"[SFAdmin] Error executing {op_type}")
            return ToolingAPIResult(
                success=False,
                errors=[str(e)],
                operation=op_type,
                api_name=op.get("api_name", "")
            )
    
    async def _create_custom_object(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Crée un Custom Object via Tooling API."""
        api_name = op.get("api_name", "")
        
        # Ensure __c suffix
        if not api_name.endswith("__c"):
            api_name = f"{api_name}__c"
        
        # Build metadata
        metadata = {
            "fullName": api_name,
            "label": op.get("label", api_name.replace("__c", "")),
            "pluralLabel": op.get("plural_label", op.get("label", api_name.replace("__c", "")) + "s"),
            "deploymentStatus": "Deployed",
            "sharingModel": op.get("sharing_model", "ReadWrite"),
            "enableActivities": True,
            "enableReports": True,
        }
        
        # Name field configuration
        name_field_type = op.get("name_field_type", "Text")
        if name_field_type == "AutoNumber":
            metadata["nameField"] = {
                "type": "AutoNumber",
                "label": "Name",
                "displayFormat": op.get("auto_number_format", f"{api_name[:3].upper()}-{{0000}}")
            }
        else:
            metadata["nameField"] = {
                "type": "Text",
                "label": "Name"
            }
        
        if op.get("description"):
            metadata["description"] = op["description"]
        
        payload = {"Metadata": metadata, "FullName": api_name}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.tooling_url}/sobjects/CustomObject/",
                headers=self.headers,
                json=payload
            )
        
        if response.status_code in (200, 201):
            result_data = response.json()
            self.created_components.append({"type": "CustomObject", "id": result_data.get("id"), "name": api_name})
            logger.info(f"[SFAdmin] Created object: {api_name}")
            return ToolingAPIResult(success=True, id=result_data.get("id"), operation="create_object", api_name=api_name)
        else:
            error_msg = self._parse_error(response)
            return ToolingAPIResult(success=False, errors=[error_msg], operation="create_object", api_name=api_name)
    
    async def _create_custom_field(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Crée un Custom Field via Tooling API."""
        obj = op.get("object", "")
        api_name = op.get("api_name", "")
        field_type = op.get("field_type", "Text")
        
        # Ensure __c suffix
        if not api_name.endswith("__c"):
            api_name = f"{api_name}__c"
        
        full_name = f"{obj}.{api_name}"
        
        # Build metadata based on field type
        metadata = {
            "fullName": full_name,
            "label": op.get("label", api_name.replace("__c", "")),
            "type": self.FIELD_TYPE_MAPPING.get(field_type, "Text"),
        }
        
        # Type-specific properties
        if field_type == "Text":
            metadata["length"] = op.get("length", 255)
        
        elif field_type == "LongTextArea":
            metadata["length"] = op.get("length", 32768)
            metadata["visibleLines"] = op.get("visible_lines", 5)
        
        elif field_type in ("Number", "Currency", "Percent"):
            metadata["precision"] = op.get("precision", 18)
            metadata["scale"] = op.get("scale", 2)
        
        elif field_type == "Checkbox":
            metadata["defaultValue"] = op.get("default_value", False)
        
        elif field_type == "Picklist":
            values = op.get("values", [])
            if values:
                metadata["valueSet"] = {
                    "restricted": op.get("restricted", True),
                    "valueSetDefinition": {
                        "sorted": False,
                        "value": [
                            {
                                "fullName": v.get("api_name", v.get("label", "")),
                                "label": v.get("label", v.get("api_name", "")),
                                "default": v.get("default", False)
                            }
                            for v in values
                        ]
                    }
                }
        
        elif field_type == "MultiselectPicklist":
            values = op.get("values", [])
            metadata["visibleLines"] = op.get("visible_lines", 4)
            if values:
                metadata["valueSet"] = {
                    "restricted": op.get("restricted", True),
                    "valueSetDefinition": {
                        "sorted": False,
                        "value": [
                            {
                                "fullName": v.get("api_name", v.get("label", "")),
                                "label": v.get("label", v.get("api_name", "")),
                                "default": v.get("default", False)
                            }
                            for v in values
                        ]
                    }
                }
        
        elif field_type == "Lookup":
            metadata["referenceTo"] = op.get("reference_to", "")
            metadata["relationshipName"] = op.get("relationship_name", api_name.replace("__c", ""))
            metadata["relationshipLabel"] = op.get("relationship_label", op.get("label", ""))
        
        elif field_type == "MasterDetail":
            metadata["referenceTo"] = op.get("reference_to", "")
            metadata["relationshipName"] = op.get("relationship_name", api_name.replace("__c", ""))
            metadata["relationshipLabel"] = op.get("relationship_label", op.get("label", ""))
            metadata["writeRequiresMasterRead"] = False
        
        elif field_type == "Formula":
            metadata["formula"] = op.get("formula", "")
            return_type = op.get("return_type", "Text")
            if return_type == "Text":
                metadata["type"] = "Text"
                metadata["length"] = 1300
            elif return_type == "Number":
                metadata["type"] = "Number"
                metadata["precision"] = 18
                metadata["scale"] = 2
            elif return_type == "Currency":
                metadata["type"] = "Currency"
                metadata["precision"] = 18
                metadata["scale"] = 2
            elif return_type == "Date":
                metadata["type"] = "Date"
            elif return_type == "Checkbox":
                metadata["type"] = "Checkbox"
                metadata["formula"] = op.get("formula", "false")
        
        elif field_type == "AutoNumber":
            metadata["displayFormat"] = op.get("format", f"NUM-{{0000}}")
            metadata["startingNumber"] = op.get("start_number", 1)
        
        # Required field
        if op.get("required", False) and field_type not in ("Checkbox", "Formula", "AutoNumber"):
            metadata["required"] = True
        
        if op.get("description"):
            metadata["description"] = op["description"]
        
        payload = {"Metadata": metadata, "FullName": full_name}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.tooling_url}/sobjects/CustomField/",
                headers=self.headers,
                json=payload
            )
        
        if response.status_code in (200, 201):
            result_data = response.json()
            self.created_components.append({"type": "CustomField", "id": result_data.get("id"), "name": full_name})
            logger.info(f"[SFAdmin] Created field: {full_name}")
            return ToolingAPIResult(success=True, id=result_data.get("id"), operation="create_field", api_name=full_name)
        else:
            error_msg = self._parse_error(response)
            return ToolingAPIResult(success=False, errors=[error_msg], operation="create_field", api_name=full_name)
    
    async def _create_record_type(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Crée un Record Type via Tooling API."""
        obj = op.get("object", "")
        api_name = op.get("api_name", "")
        full_name = f"{obj}.{api_name}"
        
        metadata = {
            "fullName": full_name,
            "label": op.get("label", api_name),
            "active": True,
        }
        
        if op.get("description"):
            metadata["description"] = op["description"]
        
        payload = {"Metadata": metadata, "FullName": full_name}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.tooling_url}/sobjects/RecordType/",
                headers=self.headers,
                json=payload
            )
        
        if response.status_code in (200, 201):
            result_data = response.json()
            self.created_components.append({"type": "RecordType", "id": result_data.get("id"), "name": full_name})
            logger.info(f"[SFAdmin] Created record type: {full_name}")
            return ToolingAPIResult(success=True, id=result_data.get("id"), operation="create_record_type", api_name=full_name)
        else:
            error_msg = self._parse_error(response)
            return ToolingAPIResult(success=False, errors=[error_msg], operation="create_record_type", api_name=full_name)
    
    async def _create_list_view(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Crée une List View via Tooling API."""
        obj = op.get("object", "")
        api_name = op.get("api_name", "")
        full_name = f"{obj}.{api_name}"
        
        metadata = {
            "fullName": full_name,
            "label": op.get("label", api_name),
            "columns": op.get("columns", ["Name"]),
            "filterScope": op.get("filter_scope", "Everything"),
        }
        
        payload = {"Metadata": metadata, "FullName": full_name}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.tooling_url}/sobjects/ListView/",
                headers=self.headers,
                json=payload
            )
        
        if response.status_code in (200, 201):
            result_data = response.json()
            self.created_components.append({"type": "ListView", "id": result_data.get("id"), "name": full_name})
            logger.info(f"[SFAdmin] Created list view: {full_name}")
            return ToolingAPIResult(success=True, id=result_data.get("id"), operation="create_list_view", api_name=full_name)
        else:
            error_msg = self._parse_error(response)
            return ToolingAPIResult(success=False, errors=[error_msg], operation="create_list_view", api_name=full_name)
    
    async def _create_validation_rule(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Crée une Validation Rule via Tooling API."""
        obj = op.get("object", "")
        api_name = op.get("api_name", "")
        full_name = f"{obj}.{api_name}"
        
        metadata = {
            "fullName": full_name,
            "active": op.get("active", True),
            "errorConditionFormula": op.get("formula", "false"),
            "errorMessage": op.get("error_message", "Validation error"),
        }
        
        if op.get("error_field"):
            metadata["errorDisplayField"] = op["error_field"]
        
        if op.get("description"):
            metadata["description"] = op["description"]
        
        payload = {"Metadata": metadata, "FullName": full_name}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.tooling_url}/sobjects/ValidationRule/",
                headers=self.headers,
                json=payload
            )
        
        if response.status_code in (200, 201):
            result_data = response.json()
            self.created_components.append({"type": "ValidationRule", "id": result_data.get("id"), "name": full_name})
            logger.info(f"[SFAdmin] Created validation rule: {full_name}")
    
    async def _create_flow(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """
        Note: Les Flows sont trop complexes pour Tooling API en JSON.
        On génère un placeholder qui devra être déployé via SFDX.
        """
        api_name = op.get("api_name", "")
        logger.warning(f"[SFAdmin] Flow {api_name} must be deployed via SFDX, not Tooling API")
        return ToolingAPIResult(
            success=True,
            operation="create_flow",
            api_name=api_name,
            message="Flow requires SFDX deployment"
        )
    
    async def _create_permission_set(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Crée un Permission Set via Tooling API."""
        api_name = op.get("api_name", "")
        label = op.get("label", api_name)
        description = op.get("description", "")
        
        payload = {
            "Name": api_name,
            "Label": label,
            "Description": description
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.tooling_url}/sobjects/PermissionSet/",
                headers=self.headers,
                json=payload
            )
        
        if response.status_code in (200, 201):
            result_data = response.json()
            self.created_components.append({"type": "PermissionSet", "id": result_data.get("id"), "name": api_name})
            logger.info(f"[SFAdmin] Created permission set: {api_name}")
            return ToolingAPIResult(success=True, id=result_data.get("id"), operation="create_permission_set", api_name=api_name)
        else:
            error_msg = self._parse_error(response)
            return ToolingAPIResult(success=False, errors=[error_msg], operation="create_permission_set", api_name=api_name)
    
    async def _create_page_layout(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Page Layouts doivent être déployés via SFDX."""
        api_name = op.get("api_name", "")
        logger.warning(f"[SFAdmin] Page Layout {api_name} must be deployed via SFDX")
        return ToolingAPIResult(
            success=True,
            operation="create_page_layout",
            api_name=api_name,
            message="Page Layout requires SFDX deployment"
        )
    
    async def _create_sharing_rule(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Sharing Rules doivent être déployés via SFDX."""
        api_name = op.get("api_name", "")
        logger.warning(f"[SFAdmin] Sharing Rule {api_name} must be deployed via SFDX")
        return ToolingAPIResult(
            success=True,
            operation="create_sharing_rule",
            api_name=api_name,
            message="Sharing Rule requires SFDX deployment"
        )
    
    async def _create_approval_process(self, op: Dict[str, Any]) -> ToolingAPIResult:
        """Approval Processes doivent être déployés via SFDX."""
        api_name = op.get("api_name", "")
        logger.warning(f"[SFAdmin] Approval Process {api_name} must be deployed via SFDX")
        return ToolingAPIResult(
            success=True,
            operation="create_approval_process",
            api_name=api_name,
            message="Approval Process requires SFDX deployment"
        )
    
    
    # ═══════════════════════════════════════════════════════════════
    # TOOLING API HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    async def _tooling_api_create(self, sobject_type: str, payload: Dict[str, Any]) -> ToolingAPIResult:
        """
        Appel Tooling API générique pour création.
        
        Args:
            sobject_type: Type d'objet Salesforce (CustomObject, CustomField, etc.)
            payload: Données à créer
            
        Returns:
            ToolingAPIResult avec id ou erreurs
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.tooling_url}/sobjects/{sobject_type}/",
                headers=self.headers,
                json=payload
            )
        
        if response.status_code in (200, 201):
            result_data = response.json()
            return ToolingAPIResult(
                success=True,
                id=result_data.get("id"),
                operation="tooling_api_create",
                api_name=sobject_type
            )
        else:
            error_msg = self._parse_error(response)
            return ToolingAPIResult(
                success=False,
                errors=[error_msg],
                operation="tooling_api_create",
                api_name=sobject_type
            )
    
    async def _tooling_api_delete(self, sobject_type: str, record_id: str) -> ToolingAPIResult:
        """
        Supprime un enregistrement via Tooling API (pour rollback).
        
        Args:
            sobject_type: Type d'objet Salesforce
            record_id: ID de l'enregistrement à supprimer
            
        Returns:
            ToolingAPIResult
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{self.tooling_url}/sobjects/{sobject_type}/{record_id}",
                headers=self.headers
            )
        
        if response.status_code in (200, 204):
            logger.info(f"[SFAdmin] Deleted {sobject_type} {record_id}")
            return ToolingAPIResult(
                success=True,
                id=record_id,
                operation="tooling_api_delete",
                api_name=sobject_type
            )
        else:
            error_msg = self._parse_error(response)
            logger.warning(f"[SFAdmin] Failed to delete {sobject_type} {record_id}: {error_msg}")
            return ToolingAPIResult(
                success=False,
                errors=[error_msg],
                operation="tooling_api_delete",
                api_name=sobject_type
            )
    
    def _parse_error(self, response) -> str:
        """Parse erreur depuis réponse HTTP."""
        try:
            data = response.json()
            if isinstance(data, list) and data:
                return data[0].get("message", str(data))
            elif isinstance(data, dict):
                return data.get("message", data.get("errorCode", str(data)))
            return str(data)
        except:
            return f"HTTP {response.status_code}: {response.text[:200]}"

    # ═══════════════════════════════════════════════════════════════
    # ROLLBACK
    # ═══════════════════════════════════════════════════════════════
    
    async def rollback(self) -> Dict[str, Any]:
        """Supprime tous les composants créés (rollback)."""
        logger.info(f"[SFAdmin] Rolling back {len(self.created_components)} components")
        
        results = []
        for component in reversed(self.created_components):
            comp_type = component.get("type")
            comp_id = component.get("id")
            
            if comp_id:
                result = await self._tooling_api_delete(comp_type, comp_id)
                results.append(result)
        
        self.created_components = []
        return {"rolled_back": len(results), "results": results}


# ═══════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ═══════════════════════════════════════════════════════════════

async def create_sf_admin_service(project_id: int, db) -> SFAdminService:
    """
    Crée et initialise un SFAdminService avec l'auth du projet.
    
    Args:
        project_id: ID du projet
        db: Session SQLAlchemy
        
    Returns:
        SFAdminService configuré
    """
    from app.services.sfdx_auth_service import SFDXAuthService
    
    auth_service = SFDXAuthService(project_id, db)
    access_token = await auth_service.get_access_token()
    instance_url = await auth_service.get_instance_url()
    
    return SFAdminService(instance_url, access_token)
