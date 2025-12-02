#!/usr/bin/env python3
"""
Salesforce Metadata Fetcher
Récupère les métadonnées d'une org via Tooling API / REST API
ZERO LLM - Pure Python data fetching
"""

import os
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SalesforceCredentials:
    """Credentials from SFDX"""
    access_token: str
    instance_url: str
    org_id: str
    api_version: str = "65.0"

@dataclass 
class FetchResult:
    """Result of metadata fetch operation"""
    success: bool
    data: Optional[Dict] = None
    error: Optional[str] = None
    records_count: int = 0

class MetadataFetcher:
    """
    Fetches Salesforce metadata via REST/Tooling APIs
    Uses existing SFDX authentication
    """
    
    def __init__(self, org_alias: str = "digital-humans-dev"):
        self.org_alias = org_alias
        self.credentials: Optional[SalesforceCredentials] = None
        self.base_url: Optional[str] = None
        self.headers: Optional[Dict] = None
        
    def authenticate(self) -> bool:
        """Get credentials from SFDX CLI"""
        try:
            result = subprocess.run(
                ["sf", "org", "display", "--target-org", self.org_alias, "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"SFDX auth failed: {result.stderr}")
                return False
                
            data = json.loads(result.stdout)
            org_info = data.get("result", {})
            
            self.credentials = SalesforceCredentials(
                access_token=org_info.get("accessToken"),
                instance_url=org_info.get("instanceUrl"),
                org_id=org_info.get("id"),
                api_version="65.0"
            )
            
            self.base_url = f"{self.credentials.instance_url}/services/data/v{self.credentials.api_version}"
            self.headers = {
                "Authorization": f"Bearer {self.credentials.access_token}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"✅ Authenticated to org: {self.credentials.org_id}")
            return True
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def _query_tooling(self, soql: str) -> FetchResult:
        """Execute SOQL query via Tooling API"""
        if not self.credentials:
            return FetchResult(success=False, error="Not authenticated")
            
        try:
            url = f"{self.base_url}/tooling/query"
            params = {"q": soql}
            response = requests.get(url, headers=self.headers, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])
                return FetchResult(success=True, data=records, records_count=len(records))
            else:
                return FetchResult(
                    success=False, 
                    error=f"API Error {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return FetchResult(success=False, error=str(e))
    
    def _query_rest(self, soql: str) -> FetchResult:
        """Execute SOQL query via REST API"""
        if not self.credentials:
            return FetchResult(success=False, error="Not authenticated")
            
        try:
            url = f"{self.base_url}/query"
            params = {"q": soql}
            response = requests.get(url, headers=self.headers, params=params, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                records = data.get("records", [])
                return FetchResult(success=True, data=records, records_count=len(records))
            else:
                return FetchResult(
                    success=False,
                    error=f"API Error {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return FetchResult(success=False, error=str(e))
    
    def _describe_object(self, object_name: str) -> FetchResult:
        """Get object describe metadata"""
        if not self.credentials:
            return FetchResult(success=False, error="Not authenticated")
            
        try:
            url = f"{self.base_url}/sobjects/{object_name}/describe"
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                return FetchResult(success=True, data=response.json(), records_count=1)
            else:
                return FetchResult(
                    success=False,
                    error=f"Describe failed for {object_name}: {response.status_code}"
                )
                
        except Exception as e:
            return FetchResult(success=False, error=str(e))

    # =========================================================================
    # METADATA FETCH METHODS
    # =========================================================================
    
    def fetch_custom_objects(self) -> FetchResult:
        """Fetch all custom objects with field counts"""
        soql = """
            SELECT Id, DeveloperName, NamespacePrefix, Description
            FROM CustomObject
            WHERE NamespacePrefix = null
        """
        return self._query_tooling(soql)
    
    def fetch_custom_fields(self) -> FetchResult:
        """Fetch custom fields grouped by object"""
        soql = """
            SELECT Id, DeveloperName, TableEnumOrId, NamespacePrefix, Description, Length
            FROM CustomField
            WHERE ManageableState = 'unmanaged'
        """
        return self._query_tooling(soql)
    
    def fetch_flows(self) -> FetchResult:
        """Fetch all Flow definitions with details"""
        soql = """
            SELECT Id, DeveloperName, MasterLabel, Description,
                   ActiveVersionId, LatestVersionId
            FROM FlowDefinition
        """
        return self._query_tooling(soql)
    
    def fetch_flow_versions(self, flow_ids: List[str] = None) -> FetchResult:
        """Fetch Flow version details (element counts, etc.)"""
        soql = """
            SELECT Id, DefinitionId, MasterLabel, VersionNumber, Status,
                   ProcessType, Description
            FROM Flow
            WHERE Status = 'Active'
        """
        return self._query_tooling(soql)
    
    def fetch_apex_classes(self) -> FetchResult:
        """Fetch all Apex classes"""
        soql = """
            SELECT Id, Name, ApiVersion, Status, IsValid, 
                   LengthWithoutComments, NamespacePrefix, Body
            FROM ApexClass
            WHERE NamespacePrefix = null
        """
        result = self._query_tooling(soql)
        
        # Truncate Body for large classes (keep first 500 chars for analysis)
        if result.success and result.data:
            for cls in result.data:
                if cls.get('Body') and len(cls['Body']) > 500:
                    cls['BodyPreview'] = cls['Body'][:500] + "..."
                    cls['BodyLength'] = len(cls['Body'])
                    del cls['Body']  # Remove full body to save space
                    
        return result
    
    def fetch_apex_triggers(self) -> FetchResult:
        """Fetch all Apex triggers"""
        soql = """
            SELECT Id, Name, TableEnumOrId, ApiVersion, Status, 
                   IsValid, LengthWithoutComments, Body, 
                   UsageBeforeInsert, UsageBeforeUpdate, UsageBeforeDelete,
                   UsageAfterInsert, UsageAfterUpdate, UsageAfterDelete,
                   UsageAfterUndelete
            FROM ApexTrigger
            WHERE NamespacePrefix = null
        """
        result = self._query_tooling(soql)
        
        # Truncate Body
        if result.success and result.data:
            for trigger in result.data:
                if trigger.get('Body') and len(trigger['Body']) > 500:
                    trigger['BodyPreview'] = trigger['Body'][:500] + "..."
                    trigger['BodyLength'] = len(trigger['Body'])
                    del trigger['Body']
                    
        return result
    
    def fetch_validation_rules(self) -> FetchResult:
        """Fetch validation rules"""
        soql = """
            SELECT Id, ValidationName, EntityDefinitionId, Active,
                   Description, ErrorMessage, ErrorDisplayField
            FROM ValidationRule
            WHERE ManageableState = 'unmanaged'
        """
        return self._query_tooling(soql)
    
    def fetch_profiles(self) -> FetchResult:
        """Fetch profiles"""
        soql = "SELECT Id, Name, UserType FROM Profile"
        return self._query_rest(soql)
    
    def fetch_permission_sets(self) -> FetchResult:
        """Fetch permission sets"""
        soql = """
            SELECT Id, Name, Label, Description, IsCustom, NamespacePrefix
            FROM PermissionSet
            WHERE IsOwnedByProfile = false
        """
        return self._query_rest(soql)
    
    def fetch_connected_apps(self) -> FetchResult:
        """Fetch connected apps (integrations)"""
        soql = """
            SELECT Id, Name, ContactEmail, Description
            FROM ConnectedApplication
        """
        return self._query_tooling(soql)
    
    def fetch_named_credentials(self) -> FetchResult:
        """Fetch named credentials"""
        soql = """
            SELECT Id, DeveloperName, Endpoint, PrincipalType
            FROM NamedCredential
        """
        return self._query_tooling(soql)
    
    def fetch_lightning_pages(self) -> FetchResult:
        """Fetch Lightning pages"""
        soql = """
            SELECT Id, DeveloperName, MasterLabel, Type, EntityDefinitionId
            FROM FlexiPage
            WHERE NamespacePrefix = null
        """
        return self._query_tooling(soql)
    
    def fetch_lwc_components(self) -> FetchResult:
        """Fetch LWC components"""
        soql = """
            SELECT Id, DeveloperName, MasterLabel, Description
            FROM LightningComponentBundle
            WHERE NamespacePrefix = null
        """
        return self._query_tooling(soql)
    
    def fetch_aura_components(self) -> FetchResult:
        """Fetch Aura components"""
        soql = """
            SELECT Id, DeveloperName, MasterLabel, Description
            FROM AuraDefinitionBundle
            WHERE NamespacePrefix = null
        """
        return self._query_tooling(soql)
    
    def fetch_custom_metadata_types(self) -> FetchResult:
        """Fetch custom metadata types"""
        soql = """
            SELECT Id, DeveloperName, MasterLabel, QualifiedApiName
            FROM EntityDefinition
            WHERE QualifiedApiName LIKE '%__mdt'
            LIMIT 100
        """
        return self._query_tooling(soql)

    # =========================================================================
    # MAIN FETCH ALL METHOD
    # =========================================================================
    
    def fetch_all_metadata(self, output_dir: str) -> Dict[str, Any]:
        """
        Fetch all metadata and save to files
        Returns summary of what was fetched
        """
        if not self.authenticate():
            return {"success": False, "error": "Authentication failed"}
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        raw_path = output_path / "raw"
        raw_path.mkdir(exist_ok=True)
        
        results = {}
        fetch_methods = {
            "custom_objects": self.fetch_custom_objects,
            "custom_fields": self.fetch_custom_fields,
            "flows": self.fetch_flows,
            "flow_versions": self.fetch_flow_versions,
            "apex_classes": self.fetch_apex_classes,
            "apex_triggers": self.fetch_apex_triggers,
            "validation_rules": self.fetch_validation_rules,
            "profiles": self.fetch_profiles,
            "permission_sets": self.fetch_permission_sets,
            "connected_apps": self.fetch_connected_apps,
            "named_credentials": self.fetch_named_credentials,
            "lightning_pages": self.fetch_lightning_pages,
            "lwc_components": self.fetch_lwc_components,
            "aura_components": self.fetch_aura_components,
            "custom_metadata_types": self.fetch_custom_metadata_types,
        }
        
        summary = {
            "org_id": self.credentials.org_id,
            "instance_url": self.credentials.instance_url,
            "fetch_timestamp": datetime.now().isoformat(),
            "metadata_counts": {},
            "errors": []
        }
        
        for name, method in fetch_methods.items():
            logger.info(f"Fetching {name}...")
            result = method()
            
            if result.success:
                # Save raw data
                file_path = raw_path / f"{name}.json"
                with open(file_path, 'w') as f:
                    json.dump(result.data, f, indent=2, default=str)
                
                summary["metadata_counts"][name] = result.records_count
                results[name] = result.data
                logger.info(f"  ✅ {name}: {result.records_count} records")
            else:
                summary["errors"].append({
                    "component": name,
                    "error": result.error
                })
                logger.warning(f"  ⚠️ {name}: {result.error}")
        
        # Save summary
        summary_path = output_path / "extraction_log.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        summary["success"] = True
        summary["raw_data_path"] = str(raw_path)
        
        return summary


# =========================================================================
# CLI INTERFACE
# =========================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch Salesforce metadata")
    parser.add_argument("--org", default="digital-humans-dev", help="SFDX org alias")
    parser.add_argument("--output", default="/tmp/metadata", help="Output directory")
    parser.add_argument("--project-id", help="Project ID for path")
    
    args = parser.parse_args()
    
    output_dir = args.output
    if args.project_id:
        output_dir = f"/app/metadata/{args.project_id}"
    
    fetcher = MetadataFetcher(org_alias=args.org)
    result = fetcher.fetch_all_metadata(output_dir)
    
    print("\n" + "="*60)
    print("METADATA FETCH COMPLETE")
    print("="*60)
    print(json.dumps(result, indent=2))
