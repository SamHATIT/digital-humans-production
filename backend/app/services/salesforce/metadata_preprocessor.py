#!/usr/bin/env python3
"""
Salesforce Metadata Preprocessor
Analyse les raw metadata et génère un summary intelligent pour Marcus
ZERO LLM - Pure Python analysis with RED FLAG detection
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class RedFlagType(str, Enum):
    # Code Quality
    SOQL_IN_LOOP = "SOQL_IN_LOOP"
    DML_IN_LOOP = "DML_IN_LOOP"
    HARDCODED_ID = "HARDCODED_ID"
    NO_TEST_CLASS = "NO_TEST_CLASS"
    LOW_API_VERSION = "LOW_API_VERSION"
    
    # Architecture
    TRIGGER_NO_HANDLER = "TRIGGER_NO_HANDLER"
    DEPRECATED_FEATURE = "DEPRECATED_FEATURE"
    PROCESS_BUILDER = "PROCESS_BUILDER"  # Should be Flow
    WORKFLOW_RULE = "WORKFLOW_RULE"  # Should be Flow
    
    # Complexity
    HIGH_COMPLEXITY_FLOW = "HIGH_COMPLEXITY_FLOW"
    HIGH_COMPLEXITY_CLASS = "HIGH_COMPLEXITY_CLASS"
    TOO_MANY_TRIGGERS = "TOO_MANY_TRIGGERS"
    
    # Security
    SHARING_VIOLATION = "SHARING_VIOLATION"
    CRUD_VIOLATION = "CRUD_VIOLATION"
    
    # Technical Debt
    UNUSED_CODE = "UNUSED_CODE"
    DUPLICATE_LOGIC = "DUPLICATE_LOGIC"
    MISSING_DESCRIPTION = "MISSING_DESCRIPTION"


@dataclass
class RedFlag:
    """A detected issue in the org"""
    type: RedFlagType
    severity: Severity
    component: str
    component_type: str
    description: str
    recommendation: str
    details: Dict = field(default_factory=dict)


@dataclass
class ComponentSummary:
    """Summary of a component type"""
    count: int
    items: List[Dict]
    by_category: Dict[str, int] = field(default_factory=dict)


class MetadataPreprocessor:
    """
    Analyzes raw Salesforce metadata and produces an intelligent summary
    with RED FLAGS for Marcus to consume
    """
    
    # Patterns for code analysis
    SOQL_IN_LOOP_PATTERN = re.compile(r'for\s*\([^)]+\)[^}]*\[SELECT', re.IGNORECASE | re.DOTALL)
    DML_IN_LOOP_PATTERN = re.compile(r'for\s*\([^)]+\)[^}]*(insert|update|delete|upsert)\s+', re.IGNORECASE | re.DOTALL)
    HARDCODED_ID_PATTERN = re.compile(r"['\"]([a-zA-Z0-9]{15}|[a-zA-Z0-9]{18})['\"]")
    
    # API Version thresholds
    CURRENT_API_VERSION = 65.0
    DEPRECATED_API_THRESHOLD = 50.0
    WARNING_API_THRESHOLD = 58.0
    
    def __init__(self, raw_data_path: str):
        self.raw_path = Path(raw_data_path)
        self.red_flags: List[RedFlag] = []
        self.raw_data: Dict[str, Any] = {}
        
    def load_raw_data(self) -> bool:
        """Load all raw JSON files"""
        try:
            for json_file in self.raw_path.glob("*.json"):
                component_name = json_file.stem
                with open(json_file, 'r') as f:
                    self.raw_data[component_name] = json.load(f)
            logger.info(f"Loaded {len(self.raw_data)} raw data files")
            return True
        except Exception as e:
            logger.error(f"Failed to load raw data: {e}")
            return False
    
    def _add_flag(self, flag_type: RedFlagType, severity: Severity, 
                  component: str, component_type: str, 
                  description: str, recommendation: str, **details):
        """Add a red flag"""
        self.red_flags.append(RedFlag(
            type=flag_type,
            severity=severity,
            component=component,
            component_type=component_type,
            description=description,
            recommendation=recommendation,
            details=details
        ))
    
    # =========================================================================
    # ANALYSIS METHODS
    # =========================================================================
    
    def analyze_apex_classes(self) -> Dict:
        """Analyze Apex classes for issues and patterns"""
        classes = self.raw_data.get("apex_classes", [])
        if not classes:
            return {"count": 0, "items": [], "test_coverage": "unknown"}
        
        summary = {
            "count": len(classes),
            "test_classes": [],
            "regular_classes": [],
            "by_api_version": defaultdict(int),
            "complex_classes": [],
            "issues": []
        }
        
        for cls in classes:
            name = cls.get("Name", "Unknown")
            api_version = cls.get("ApiVersion", 0)
            body_preview = cls.get("BodyPreview", cls.get("Body", ""))
            body_length = cls.get("BodyLength", len(body_preview))
            
            # Categorize
            is_test = name.lower().endswith("test") or "@istest" in body_preview.lower()
            if is_test:
                summary["test_classes"].append(name)
            else:
                summary["regular_classes"].append({
                    "name": name,
                    "api_version": api_version,
                    "lines": body_length // 50  # Rough line estimate
                })
            
            # API Version analysis
            summary["by_api_version"][str(int(api_version))] += 1
            
            if api_version and api_version < self.DEPRECATED_API_THRESHOLD:
                self._add_flag(
                    RedFlagType.LOW_API_VERSION, Severity.HIGH,
                    name, "ApexClass",
                    f"Class uses deprecated API version {api_version}",
                    f"Update to API version {self.CURRENT_API_VERSION}",
                    current_version=api_version
                )
            elif api_version and api_version < self.WARNING_API_THRESHOLD:
                self._add_flag(
                    RedFlagType.LOW_API_VERSION, Severity.MEDIUM,
                    name, "ApexClass",
                    f"Class uses old API version {api_version}",
                    f"Consider updating to API version {self.CURRENT_API_VERSION}",
                    current_version=api_version
                )
            
            # Code pattern analysis
            if body_preview:
                # SOQL in loop
                if self.SOQL_IN_LOOP_PATTERN.search(body_preview):
                    self._add_flag(
                        RedFlagType.SOQL_IN_LOOP, Severity.CRITICAL,
                        name, "ApexClass",
                        "Potential SOQL query inside loop detected",
                        "Move SOQL outside loop or use collections"
                    )
                
                # DML in loop
                if self.DML_IN_LOOP_PATTERN.search(body_preview):
                    self._add_flag(
                        RedFlagType.DML_IN_LOOP, Severity.CRITICAL,
                        name, "ApexClass",
                        "Potential DML operation inside loop detected",
                        "Collect records and perform single DML outside loop"
                    )
                
                # Hardcoded IDs
                hardcoded_ids = self.HARDCODED_ID_PATTERN.findall(body_preview)
                if hardcoded_ids:
                    self._add_flag(
                        RedFlagType.HARDCODED_ID, Severity.HIGH,
                        name, "ApexClass",
                        f"Found {len(hardcoded_ids)} potential hardcoded IDs",
                        "Use Custom Metadata Types or Custom Labels instead",
                        id_count=len(hardcoded_ids)
                    )
            
            # Complexity check
            if body_length > 5000:
                summary["complex_classes"].append({
                    "name": name,
                    "length": body_length,
                    "reason": "Large class > 5000 chars"
                })
                self._add_flag(
                    RedFlagType.HIGH_COMPLEXITY_CLASS, Severity.MEDIUM,
                    name, "ApexClass",
                    f"Large class with {body_length} characters",
                    "Consider refactoring into smaller classes",
                    length=body_length
                )
        
        # Check for missing test classes
        for regular_class in summary["regular_classes"]:
            class_name = regular_class["name"]
            expected_test = f"{class_name}Test"
            if expected_test not in summary["test_classes"]:
                # Check variations
                variations = [f"{class_name}_Test", f"Test{class_name}"]
                if not any(v in summary["test_classes"] for v in variations):
                    self._add_flag(
                        RedFlagType.NO_TEST_CLASS, Severity.HIGH,
                        class_name, "ApexClass",
                        f"No test class found for {class_name}",
                        f"Create test class {expected_test}"
                    )
        
        return summary
    
    def analyze_apex_triggers(self) -> Dict:
        """Analyze Apex triggers"""
        triggers = self.raw_data.get("apex_triggers", [])
        if not triggers:
            return {"count": 0, "items": [], "by_object": {}}
        
        summary = {
            "count": len(triggers),
            "items": [],
            "by_object": defaultdict(list),
            "events_used": defaultdict(int)
        }
        
        for trigger in triggers:
            name = trigger.get("Name", "Unknown")
            sobject = trigger.get("TableEnumOrId", "Unknown")
            body_preview = trigger.get("BodyPreview", trigger.get("Body", ""))
            
            # Collect events
            events = []
            for event in ["BeforeInsert", "BeforeUpdate", "BeforeDelete",
                          "AfterInsert", "AfterUpdate", "AfterDelete", "AfterUndelete"]:
                if trigger.get(f"Usage{event}"):
                    events.append(event)
                    summary["events_used"][event] += 1
            
            trigger_info = {
                "name": name,
                "object": sobject,
                "events": events,
                "api_version": trigger.get("ApiVersion", 0)
            }
            summary["items"].append(trigger_info)
            summary["by_object"][sobject].append(name)
            
            # Check for trigger handler pattern
            if body_preview and "handler" not in body_preview.lower():
                self._add_flag(
                    RedFlagType.TRIGGER_NO_HANDLER, Severity.MEDIUM,
                    name, "ApexTrigger",
                    "Trigger may not use handler pattern",
                    "Implement trigger handler pattern for better maintainability",
                    object=sobject
                )
        
        # Check for multiple triggers on same object
        for sobject, trigger_list in summary["by_object"].items():
            if len(trigger_list) > 1:
                self._add_flag(
                    RedFlagType.TOO_MANY_TRIGGERS, Severity.HIGH,
                    sobject, "Object",
                    f"Multiple triggers ({len(trigger_list)}) on {sobject}",
                    "Consolidate into single trigger with handler",
                    triggers=trigger_list
                )
        
        summary["by_object"] = dict(summary["by_object"])
        summary["events_used"] = dict(summary["events_used"])
        return summary
    
    def analyze_flows(self) -> Dict:
        """Analyze Flows and detect deprecated automation"""
        flows = self.raw_data.get("flows", [])
        flow_versions = self.raw_data.get("flow_versions", [])
        
        if not flows:
            return {"count": 0, "items": [], "by_type": {}}
        
        summary = {
            "count": len(flows),
            "items": [],
            "by_type": defaultdict(int),
            "by_status": defaultdict(int),
            "deprecated_types": [],
            "complex_flows": []
        }
        
        for flow in flows:
            api_name = flow.get("ApiName", "Unknown")
            process_type = flow.get("ProcessType", "Unknown")
            status = flow.get("Status", "Unknown")
            
            summary["by_type"][process_type] += 1
            summary["by_status"][status] += 1
            
            flow_info = {
                "name": api_name,
                "type": process_type,
                "status": status,
                "description": flow.get("Description", "")[:100] if flow.get("Description") else None
            }
            summary["items"].append(flow_info)
            
            # Detect deprecated automation types
            if process_type in ["Workflow", "InvocableProcess"]:
                self._add_flag(
                    RedFlagType.PROCESS_BUILDER if process_type == "InvocableProcess" else RedFlagType.WORKFLOW_RULE,
                    Severity.MEDIUM,
                    api_name, "Flow",
                    f"Deprecated automation type: {process_type}",
                    "Migrate to Record-Triggered Flow",
                    process_type=process_type
                )
                summary["deprecated_types"].append(api_name)
        
        summary["by_type"] = dict(summary["by_type"])
        summary["by_status"] = dict(summary["by_status"])
        return summary
    
    def analyze_custom_objects(self) -> Dict:
        """Analyze custom objects"""
        objects = self.raw_data.get("custom_objects", [])
        fields = self.raw_data.get("custom_fields", [])
        
        # Group fields by object
        fields_by_object = defaultdict(list)
        if fields:
            for field in fields:
                obj_id = field.get("TableEnumOrId", "")
                fields_by_object[obj_id].append(field)
        
        summary = {
            "count": len(objects) if objects else 0,
            "items": [],
            "total_custom_fields": len(fields) if fields else 0,
            "objects_with_many_fields": []
        }
        
        if objects:
            for obj in objects:
                dev_name = obj.get("DeveloperName", "Unknown")
                obj_id = obj.get("Id", "")
                obj_fields = fields_by_object.get(obj_id, [])
                
                obj_info = {
                    "name": dev_name,
                    "field_count": len(obj_fields),
                    "has_description": bool(obj.get("Description"))
                }
                summary["items"].append(obj_info)
                
                # Check for missing description
                if not obj.get("Description"):
                    self._add_flag(
                        RedFlagType.MISSING_DESCRIPTION, Severity.LOW,
                        f"{dev_name}__c", "CustomObject",
                        "Custom object has no description",
                        "Add description for documentation"
                    )
                
                # Flag objects with many fields
                if len(obj_fields) > 50:
                    summary["objects_with_many_fields"].append({
                        "name": dev_name,
                        "field_count": len(obj_fields)
                    })
        
        return summary
    
    def analyze_validation_rules(self) -> Dict:
        """Analyze validation rules"""
        rules = self.raw_data.get("validation_rules", [])
        
        summary = {
            "count": len(rules) if rules else 0,
            "by_object": defaultdict(int),
            "active_count": 0,
            "items": []
        }
        
        if rules:
            for rule in rules:
                name = rule.get("ValidationName", "Unknown")
                entity = rule.get("EntityDefinitionId", "Unknown")
                is_active = rule.get("Active", False)
                
                summary["by_object"][entity] += 1
                if is_active:
                    summary["active_count"] += 1
                
                summary["items"].append({
                    "name": name,
                    "object": entity,
                    "active": is_active,
                    "has_description": bool(rule.get("Description"))
                })
        
        summary["by_object"] = dict(summary["by_object"])
        return summary
    
    def analyze_security(self) -> Dict:
        """Analyze security configuration"""
        profiles = self.raw_data.get("profiles", [])
        perm_sets = self.raw_data.get("permission_sets", [])
        
        summary = {
            "profiles_count": len(profiles) if profiles else 0,
            "permission_sets_count": len(perm_sets) if perm_sets else 0,
            "profiles": [],
            "permission_sets": []
        }
        
        if profiles:
            for profile in profiles:
                summary["profiles"].append({
                    "name": profile.get("Name", "Unknown"),
                    "user_type": profile.get("UserType", "Unknown")
                })
        
        if perm_sets:
            for ps in perm_sets:
                if ps.get("IsCustom"):
                    summary["permission_sets"].append({
                        "name": ps.get("Name", "Unknown"),
                        "label": ps.get("Label", ""),
                        "has_description": bool(ps.get("Description"))
                    })
        
        return summary
    
    def analyze_integrations(self) -> Dict:
        """Analyze integration components"""
        connected_apps = self.raw_data.get("connected_apps", [])
        named_creds = self.raw_data.get("named_credentials", [])
        
        summary = {
            "connected_apps": [],
            "named_credentials": [],
            "integration_count": 0
        }
        
        if connected_apps:
            for app in connected_apps:
                summary["connected_apps"].append({
                    "name": app.get("Name", "Unknown"),
                    "description": app.get("Description", "")[:100] if app.get("Description") else None
                })
        
        if named_creds:
            for cred in named_creds:
                summary["named_credentials"].append({
                    "name": cred.get("DeveloperName", "Unknown"),
                    "endpoint": cred.get("Endpoint", "")
                })
        
        summary["integration_count"] = len(summary["connected_apps"]) + len(summary["named_credentials"])
        return summary
    
    def analyze_ui_components(self) -> Dict:
        """Analyze UI components"""
        lightning_pages = self.raw_data.get("lightning_pages", [])
        lwc = self.raw_data.get("lwc_components", [])
        aura = self.raw_data.get("aura_components", [])
        
        summary = {
            "lightning_pages_count": len(lightning_pages) if lightning_pages else 0,
            "lwc_count": len(lwc) if lwc else 0,
            "aura_count": len(aura) if aura else 0,
            "lightning_pages": [],
            "lwc_components": [],
            "aura_components": []
        }
        
        if lightning_pages:
            for page in lightning_pages[:20]:  # Limit to first 20
                summary["lightning_pages"].append({
                    "name": page.get("DeveloperName", "Unknown"),
                    "type": page.get("Type", "Unknown")
                })
        
        if lwc:
            for component in lwc:
                summary["lwc_components"].append({
                    "name": component.get("DeveloperName", "Unknown"),
                    "has_description": bool(component.get("Description"))
                })
        
        if aura:
            for component in aura:
                summary["aura_components"].append({
                    "name": component.get("DeveloperName", "Unknown")
                })
            # Flag Aura components as potential modernization candidates
            if len(aura) > 0:
                self._add_flag(
                    RedFlagType.DEPRECATED_FEATURE, Severity.LOW,
                    f"{len(aura)} Aura Components", "AuraComponent",
                    "Aura components found - consider LWC migration",
                    "Evaluate migration to Lightning Web Components",
                    count=len(aura)
                )
        
        return summary
    
    # =========================================================================
    # MAIN PROCESSING METHOD
    # =========================================================================
    
    def generate_summary(self, output_path: str = None) -> Dict:
        """
        Generate complete metadata summary for Marcus
        Returns dict suitable for LLM consumption (~10-15k tokens)
        """
        if not self.load_raw_data():
            return {"success": False, "error": "Failed to load raw data"}
        
        logger.info("Analyzing metadata...")
        
        summary = {
            "metadata_analysis": {
                "generated_at": datetime.now().isoformat(),
                "analysis_version": "2.0",
                "purpose": "Structured org analysis for Solution Architect"
            },
            
            # Component Analyses
            "data_model": {
                "custom_objects": self.analyze_custom_objects(),
            },
            
            "automation": {
                "flows": self.analyze_flows(),
                "apex_triggers": self.analyze_apex_triggers(),
                "validation_rules": self.analyze_validation_rules(),
            },
            
            "code": {
                "apex_classes": self.analyze_apex_classes(),
            },
            
            "security": self.analyze_security(),
            
            "integrations": self.analyze_integrations(),
            
            "ui_components": self.analyze_ui_components(),
            
            # Red Flags - CRITICAL SECTION
            "red_flags": {
                "total_count": len(self.red_flags),
                "by_severity": {},
                "items": []
            },
            
            # Technical Debt Score
            "technical_debt_score": 0,
            
            # Executive Summary for Marcus
            "executive_summary": {}
        }
        
        # Process red flags
        severity_counts = defaultdict(int)
        for flag in self.red_flags:
            severity_counts[flag.severity.value] += 1
            summary["red_flags"]["items"].append({
                "type": flag.type.value,
                "severity": flag.severity.value,
                "component": flag.component,
                "component_type": flag.component_type,
                "description": flag.description,
                "recommendation": flag.recommendation,
                "details": flag.details
            })
        
        summary["red_flags"]["by_severity"] = dict(severity_counts)
        
        # Calculate technical debt score (0-100, higher = more debt)
        debt_score = 0
        debt_score += severity_counts.get("CRITICAL", 0) * 15
        debt_score += severity_counts.get("HIGH", 0) * 8
        debt_score += severity_counts.get("MEDIUM", 0) * 3
        debt_score += severity_counts.get("LOW", 0) * 1
        summary["technical_debt_score"] = min(100, debt_score)
        
        # Generate executive summary
        summary["executive_summary"] = {
            "org_complexity": self._calculate_complexity(summary),
            "key_stats": {
                "custom_objects": summary["data_model"]["custom_objects"]["count"],
                "apex_classes": summary["code"]["apex_classes"]["count"],
                "apex_triggers": summary["automation"]["apex_triggers"]["count"],
                "flows": summary["automation"]["flows"]["count"],
                "lwc_components": summary["ui_components"]["lwc_count"],
                "integrations": summary["integrations"]["integration_count"],
            },
            "critical_issues": [
                f for f in summary["red_flags"]["items"] 
                if f["severity"] in ["CRITICAL", "HIGH"]
            ][:10],  # Top 10 critical issues
            "modernization_opportunities": self._identify_modernization(summary),
            "recommended_focus_areas": self._recommend_focus_areas(summary)
        }
        
        # Save summary
        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            logger.info(f"Summary saved to {output_file}")
        
        return summary
    
    def _calculate_complexity(self, summary: Dict) -> str:
        """Calculate overall org complexity"""
        score = 0
        score += summary["data_model"]["custom_objects"]["count"] * 2
        score += summary["code"]["apex_classes"]["count"] * 1
        score += summary["automation"]["flows"]["count"] * 1
        score += summary["automation"]["apex_triggers"]["count"] * 3
        score += summary["integrations"]["integration_count"] * 5
        
        if score < 50:
            return "LOW"
        elif score < 150:
            return "MEDIUM"
        elif score < 300:
            return "HIGH"
        else:
            return "VERY_HIGH"
    
    def _identify_modernization(self, summary: Dict) -> List[str]:
        """Identify modernization opportunities"""
        opportunities = []
        
        if summary["automation"]["flows"].get("deprecated_types"):
            opportunities.append(
                f"Migrate {len(summary['automation']['flows']['deprecated_types'])} "
                f"Process Builder/Workflow to Flows"
            )
        
        if summary["ui_components"]["aura_count"] > 0:
            opportunities.append(
                f"Consider migrating {summary['ui_components']['aura_count']} "
                f"Aura components to LWC"
            )
        
        old_api_flags = [f for f in self.red_flags if f.type == RedFlagType.LOW_API_VERSION]
        if old_api_flags:
            opportunities.append(
                f"Update {len(old_api_flags)} classes to current API version"
            )
        
        return opportunities
    
    def _recommend_focus_areas(self, summary: Dict) -> List[str]:
        """Recommend areas to focus on"""
        focus = []
        
        critical_flags = [f for f in self.red_flags if f.severity == Severity.CRITICAL]
        if critical_flags:
            focus.append(f"Address {len(critical_flags)} CRITICAL issues immediately")
        
        no_tests = [f for f in self.red_flags if f.type == RedFlagType.NO_TEST_CLASS]
        if len(no_tests) > 3:
            focus.append(f"Improve test coverage: {len(no_tests)} classes lack tests")
        
        multi_triggers = [f for f in self.red_flags if f.type == RedFlagType.TOO_MANY_TRIGGERS]
        if multi_triggers:
            focus.append("Consolidate triggers - multiple triggers on same object")
        
        if summary["technical_debt_score"] > 50:
            focus.append("High technical debt - plan remediation sprint")
        
        return focus[:5]  # Top 5 focus areas


# =========================================================================
# CLI INTERFACE
# =========================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Preprocess Salesforce metadata")
    parser.add_argument("--input", required=True, help="Path to raw metadata directory")
    parser.add_argument("--output", help="Output file path for summary JSON")
    
    args = parser.parse_args()
    
    preprocessor = MetadataPreprocessor(args.input)
    
    output_path = args.output or f"{args.input}/../metadata_summary.json"
    summary = preprocessor.generate_summary(output_path)
    
    print("\n" + "="*60)
    print("METADATA ANALYSIS COMPLETE")
    print("="*60)
    print(f"Technical Debt Score: {summary['technical_debt_score']}/100")
    print(f"Red Flags Found: {summary['red_flags']['total_count']}")
    print(f"  - CRITICAL: {summary['red_flags']['by_severity'].get('CRITICAL', 0)}")
    print(f"  - HIGH: {summary['red_flags']['by_severity'].get('HIGH', 0)}")
    print(f"  - MEDIUM: {summary['red_flags']['by_severity'].get('MEDIUM', 0)}")
    print(f"  - LOW: {summary['red_flags']['by_severity'].get('LOW', 0)}")
