#!/usr/bin/env python3
"""
Salesforce Research Analyst Agent - Emma
3 distinct modes:
1. analyze (Phase 2.5): UCs -> UC Digest (for Marcus)
2. validate (Phase 3.3): Solution Design + UCs -> Coverage Analysis (for Marcus revision)
3. write_sds (Phase 5): All deliverables -> Final SDS Document

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (ResearchAnalystAgent.run()) or CLI.

Module-level utility functions (parse_json_response, calculate_coverage_score,
generate_coverage_report_programmatic) are preserved for direct import by tests.
"""

import os
import re
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# LLM imports
try:
    from app.services.llm_service import generate_llm_response, LLMProvider
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

# RAG Service
try:
    from app.services.rag_service import get_salesforce_context
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# LLM Logger for debugging (INFRA-002)
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
except ImportError:
    LLM_LOGGER_AVAILABLE = False
    def log_llm_interaction(*args, **kwargs): pass

# JSON Cleaner for robust parsing
try:
    from app.utils.json_cleaner import clean_llm_json_response
    JSON_CLEANER_AVAILABLE = True
except ImportError:
    JSON_CLEANER_AVAILABLE = False
    def clean_llm_json_response(s): return None, "JSON cleaner not available"

# Prompt Service for externalized prompts
try:
    from prompts.prompt_service import PromptService
    PROMPT_SERVICE = PromptService()
except ImportError:
    PROMPT_SERVICE = None


# ============================================================================
# JSON PARSING UTILITIES
# ============================================================================

def parse_json_response(content: str) -> dict:
    """
    Parse JSON from LLM response using json_cleaner with fallback.
    Exported for direct import by tests and other services.
    """
    if JSON_CLEANER_AVAILABLE:
        parsed_content, parse_error = clean_llm_json_response(content)
        if parsed_content is not None:
            return parsed_content
        else:
            logger.warning(f"JSON parse error (cleaner): {parse_error}")

    # Fallback to basic parsing
    try:
        clean_content = content.strip()
        if clean_content.startswith('```'):
            clean_content = re.sub(r'^```(?:json)?\s*', '', clean_content)
            clean_content = re.sub(r'```\s*$', '', clean_content)
        return json.loads(clean_content.strip())
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error (basic): {e}")
        return {"raw": content, "parse_error": str(e)}


# ============================================================================
# MODE 1: ANALYZE (Phase 2.5) - UC Digest Generation
# ============================================================================

ANALYZE_PROMPT = """# UC DIGEST GENERATION

You are **Emma**, a Research Analyst specializing in Salesforce project analysis.

## YOUR MISSION
Analyze ALL the Use Cases and create a structured UC Digest that will help Marcus (Solution Architect) design the best architecture.

## USE CASES TO ANALYZE

{use_cases_text}

## OUTPUT FORMAT (JSON)
Generate a UC Digest with this EXACT structure:

```json
{{
  "artifact_id": "UCD-001",
  "title": "Use Case Digest",
  "generated_at": "{timestamp}",
  "total_use_cases_analyzed": {uc_count},
  "by_requirement": {{
    "BR-001": {{
      "title": "Business Requirement title",
      "uc_count": 5,
      "sf_objects": ["Account", "Contact", "CustomObj__c"],
      "sf_fields": {{
        "Account": ["Name", "Industry", "Custom_Field__c"],
        "Contact": ["Email", "Phone"]
      }},
      "automations": [
        {{"type": "Flow", "purpose": "Auto-create contact on account creation"}},
        {{"type": "Trigger", "purpose": "Validate email format before save"}}
      ],
      "ui_components": ["accountDashboard", "contactList"],
      "key_acceptance_criteria": [
        "User can create a new account with all required fields",
        "Contact is auto-created with default values"
      ]
    }}
  }},
  "cross_cutting_concerns": {{
    "shared_objects": [
      {{"object": "Account", "usage": "Used in BR-001, BR-002, BR-003"}}
    ],
    "integration_points": [
      {{"name": "ERP Sync", "systems": ["SAP"], "direction": "Bidirectional"}}
    ],
    "security_requirements": [
      "Role-based access to sensitive fields",
      "Record-level sharing for regional data"
    ]
  }},
  "recommendations": [
    "Consider Master-Detail relationship between X and Y",
    "Use Platform Events for real-time notifications"
  ],
  "data_volume_estimates": {{
    "Account": "10K-50K records",
    "Contact": "50K-100K records"
  }}
}}
```

## ANALYSIS RULES
1. Group analysis BY BUSINESS REQUIREMENT (BR)
2. Extract ALL Salesforce objects mentioned (standard + custom)
3. Identify ALL fields per object
4. List ALL automations (Flows, Triggers, Scheduled Jobs)
5. Extract UI component needs (LWC, Lightning Pages)
6. Note cross-cutting concerns (shared objects, integrations)
7. Provide actionable recommendations for Marcus
8. Estimate data volumes where possible

---

**Analyze ALL Use Cases now. Output ONLY valid JSON.**
"""


# ============================================================================
# MODE 2: VALIDATE (Phase 3.3) - Coverage Analysis
# ============================================================================

VALIDATE_PROMPT = """# SOLUTION DESIGN COVERAGE VALIDATION

You are **Emma**, a Research Analyst validating Marcus's Solution Design.

## YOUR MISSION
Compare the Solution Design against ALL Use Cases to ensure complete coverage.
Identify gaps, missing elements, and areas needing improvement.

## SOLUTION DESIGN TO VALIDATE
{solution_design_text}

## USE CASES TO CHECK AGAINST
{use_cases_text}

## UC DIGEST (Summary)
{uc_digest_text}

## OUTPUT FORMAT (JSON)

```json
{{
  "artifact_id": "COV-001",
  "title": "Coverage Analysis Report",
  "generated_at": "{timestamp}",
  "overall_coverage_score": 85,
  "coverage_by_requirement": {{
    "BR-001": {{
      "title": "Requirement title",
      "coverage_score": 90,
      "covered_elements": ["Object X created", "Flow Y defined"],
      "missing_elements": ["Field Z not in data model"],
      "partial_elements": ["Integration defined but missing error handling"]
    }}
  }},
  "coverage_by_category": {{
    "data_model": {{
      "score": 90,
      "covered": ["All custom objects defined"],
      "gaps": ["Missing picklist values for Status__c"]
    }},
    "automation": {{
      "score": 80,
      "covered": ["Main flows defined"],
      "gaps": ["No scheduled job for data cleanup"]
    }},
    "security": {{
      "score": 75,
      "covered": ["Permission sets defined"],
      "gaps": ["Missing FLS for sensitive fields"]
    }},
    "ui_components": {{
      "score": 70,
      "covered": ["Dashboard LWC defined"],
      "gaps": ["Missing detail view component"]
    }},
    "integration": {{
      "score": 85,
      "covered": ["REST API defined"],
      "gaps": ["Missing retry mechanism"]
    }}
  }},
  "critical_gaps": [
    {{
      "element_type": "custom_object",
      "element_value": "Audit_Log__c",
      "severity": "high",
      "uc_refs": ["UC-003-01"],
      "recommendation": "Add Audit_Log__c to data model for compliance tracking"
    }}
  ],
  "uncovered_use_cases": [
    {{
      "id": "UC-005-03",
      "title": "Bulk data import",
      "reason": "No data migration strategy defined"
    }}
  ],
  "recommendations": [
    "Add missing objects to data model",
    "Define error handling for all integrations"
  ],
  "verdict": "NEEDS_REVISION"
}}
```

## SCORING RULES
- 95-100%: APPROVED - No changes needed
- 80-94%: NEEDS_MINOR_REVISION - Small gaps to address
- 60-79%: NEEDS_REVISION - Significant gaps found
- <60%: REJECTED - Major redesign needed

## VALIDATION RULES
1. Every UC must be traceable to at least one Solution Design element
2. Every custom object in UCs must exist in the data model
3. Every automation mentioned in UCs must be designed
4. Every UI component needed by UCs must be specified
5. Security model must cover all roles mentioned in UCs
6. Integration points must match UC requirements

---

**Validate the Solution Design now. Output ONLY valid JSON.**
"""


# ============================================================================
# MODE 3: WRITE_SDS (Phase 5) - Final SDS Document Assembly
# ============================================================================

WRITE_SDS_PROMPT = """# SDS DOCUMENT GENERATION

You are **Emma**, a Research Analyst writing the final Solution Design Specification (SDS) document.

## YOUR MISSION
Assemble ALL deliverables from all agents into a cohesive, professional SDS document in Markdown.

## PROJECT INFORMATION
**Project Name:** {project_name}
**Generated:** {timestamp}

## DELIVERABLES TO ASSEMBLE

### Business Requirements (Sophie - PM)
{br_content}

### Use Cases (Olivia - BA)
{uc_content}

### UC Digest (Emma - Research Analyst)
{uc_digest_content}

### Solution Design (Marcus - Solution Architect)
{solution_design_content}

### Gap Analysis (Marcus)
{gap_analysis_content}

### WBS (Marcus)
{wbs_content}

### QA Test Plan (Elena - QA)
{qa_content}

### DevOps Plan (Jordan - DevOps)
{devops_content}

### Training Plan (Lucas - Trainer)
{training_content}

### Data Migration Plan (Aisha - Data Migration)
{data_migration_content}

## SDS DOCUMENT STRUCTURE

Generate a complete SDS with these sections:

1. **Executive Summary** - Project overview, scope, objectives
2. **Business Requirements** - Validated BRs from Sophie
3. **Use Case Analysis** - Key UCs from Olivia, organized by BR
4. **Solution Architecture**
   - 4.1 Data Model (objects, fields, relationships, ERD)
   - 4.2 Security Model (profiles, permissions, sharing)
   - 4.3 Automation Design (flows, triggers, scheduled jobs)
   - 4.4 Integration Architecture (APIs, external systems)
   - 4.5 UI/UX Design (Lightning pages, LWC components)
5. **Gap Analysis Summary** - Key gaps and resolution approach
6. **Implementation Plan** (WBS summary)
   - 6.1 Phases and Milestones
   - 6.2 Resource Allocation
   - 6.3 Critical Path
7. **Quality Assurance**
   - 7.1 Test Strategy
   - 7.2 Test Scenarios
8. **DevOps & Deployment**
   - 8.1 Environment Strategy
   - 8.2 CI/CD Pipeline
   - 8.3 Release Plan
9. **Training & Adoption**
   - 9.1 Training Plan
   - 9.2 User Documentation
10. **Data Migration**
    - 10.1 Data Mapping
    - 10.2 Migration Strategy
    - 10.3 Validation Plan
11. **Risks & Mitigations**
12. **Appendices**
    - A. Glossary
    - B. Reference Documents
    - C. Change Log

## WRITING RULES
1. Use professional, clear language
2. Include specific Salesforce terminology
3. Reference deliverables by artifact ID (ARCH-001, GAP-001, etc.)
4. Include tables for structured data
5. Use Mermaid diagrams where available
6. Cross-reference between sections
7. Highlight risks and dependencies
8. Keep each section concise but complete
9. Use consistent formatting throughout

---

**Write the complete SDS document now. Output ONLY Markdown.**
"""


# ============================================================================
# COVERAGE CALCULATION UTILITIES
# ============================================================================

def calculate_coverage_score(solution_design: dict, use_cases: list) -> dict:
    """
    Programmatic coverage calculation (no LLM needed).
    Exported for direct import by tests and other services.

    Checks:
    - Object coverage: Are all UC-referenced objects in the data model?
    - Automation coverage: Are all UC automations designed?
    - UC traceability: Can every UC be traced to a solution element?
    """
    if not solution_design or not use_cases:
        return {
            "overall_score": 0,
            "details": "Missing solution_design or use_cases",
            "by_category": {}
        }

    # Extract elements from solution design
    data_model = solution_design.get('data_model', {})
    sd_objects = set()
    for obj in data_model.get('standard_objects', []):
        if isinstance(obj, dict):
            sd_objects.add(obj.get('api_name', '').lower())
        elif isinstance(obj, str):
            sd_objects.add(obj.lower())
    for obj in data_model.get('custom_objects', []):
        if isinstance(obj, dict):
            sd_objects.add(obj.get('api_name', '').lower())
        elif isinstance(obj, str):
            sd_objects.add(obj.lower())

    automation = solution_design.get('automation_design', {})
    sd_automations = set()
    for flow in automation.get('flows', []):
        if isinstance(flow, dict):
            sd_automations.add(flow.get('name', '').lower())
        elif isinstance(flow, str):
            sd_automations.add(flow.lower())
    for trigger in automation.get('apex_triggers', automation.get('triggers', [])):
        if isinstance(trigger, dict):
            sd_automations.add(trigger.get('name', '').lower())
        elif isinstance(trigger, str):
            sd_automations.add(trigger.lower())
    for job in automation.get('scheduled_jobs', []):
        if isinstance(job, dict):
            sd_automations.add(job.get('name', '').lower())

    ui = solution_design.get('ui_components', {})
    sd_ui = set()
    for lwc in ui.get('lwc_components', []):
        if isinstance(lwc, dict):
            sd_ui.add(lwc.get('name', '').lower())
        elif isinstance(lwc, str):
            sd_ui.add(lwc.lower())

    # Extract requirements from UCs
    uc_objects = set()
    uc_automations = set()
    uc_ui = set()
    covered_ucs = 0
    total_ucs = len(use_cases)

    for uc in use_cases:
        # Support BOTH formats: nested salesforce_components{} AND flat sf_objects/sf_automation
        sf = uc.get('salesforce_components', {})
        uc_objs = set()
        
        # Objects: salesforce_components.objects OR sf_objects (Olivia format)
        obj_list = sf.get('objects', []) or []
        if not obj_list:
            obj_list = uc.get('sf_objects', []) or []
        for obj in obj_list:
            obj_lower = obj.lower().strip() if isinstance(obj, str) else ''
            if obj_lower:
                uc_objects.add(obj_lower)
                uc_objs.add(obj_lower)
        
        # Automations: salesforce_components.automation OR sf_automation
        auto_list = sf.get('automation', []) or []
        if not auto_list:
            sf_auto = uc.get('sf_automation', [])
            if isinstance(sf_auto, list):
                auto_list = sf_auto
            elif isinstance(sf_auto, str) and sf_auto.lower() not in ('none', '', 'n/a'):
                auto_list = [sf_auto]
        for auto in auto_list:
            auto_lower = auto.lower().strip() if isinstance(auto, str) else ''
            if auto_lower:
                uc_automations.add(auto_lower)
        
        # UI: salesforce_components.ui_components OR sf_ui_components
        ui_list = sf.get('ui_components', sf.get('components', [])) or []
        if not ui_list:
            ui_list = uc.get('sf_ui_components', uc.get('ui_components', [])) or []
        for comp in ui_list:
            comp_lower = comp.lower().strip() if isinstance(comp, str) else ''
            if comp_lower:
                uc_ui.add(comp_lower)

        # Check if this UC is covered by solution design
        # Method 1: object overlap
        obj_covered = bool(uc_objs & sd_objects)
        # Method 2: UC ID in traceability map
        uc_id = uc.get('id', '')
        trace_covered = uc_id in solution_design.get('uc_traceability', {})
        if obj_covered or trace_covered:
            covered_ucs += 1

    # Calculate scores
    # Filter out standard SF infra objects that don't belong in data_model
    SF_INFRA_OBJECTS = {
        'user', 'group', 'queue', 'queuesobject', 'report', 'dashboard',
        'emailtemplate', 'listview', 'attachment', 'businesshours',
        'namedcredential', 'processinstance', 'processinstanceworkitem',
        'pendingservicerouting', 'agentwork', 'servicechannel',
        'externalserviceregistration', 'datacategoryselection',
        'personaccount', 'individual', 'campaign', 'campaignmember',
        'contract', 'order', 'slaprocess', 'milestone', 'milestonetype',
    }
    uc_objects_filtered = uc_objects - SF_INFRA_OBJECTS
    obj_coverage = len(uc_objects_filtered & sd_objects) / max(len(uc_objects_filtered), 1) * 100
    # If UCs don't specify automation requirements (empty set), default to 100%
    # Also ignore empty strings and generic type names (flow, apex, etc.)
    uc_automations.discard('')
    sd_automations.discard('')
    GENERIC_AUTO_TYPES = {'flow', 'apex', 'validation rule', 'process builder', 'workflow', 'trigger', 'batch', 'scheduled'}
    uc_automations_specific = uc_automations - GENERIC_AUTO_TYPES
    # If UCs only list generic types, check that SD has SOME automations of those types
    if not uc_automations_specific and uc_automations:
        # UCs say "needs Flow/Apex" — check if SD has any flows/triggers
        has_flows = bool(solution_design.get('automation_design', {}).get('flows', []))
        has_triggers = bool(solution_design.get('automation_design', {}).get('apex_triggers', []))
        auto_coverage = 100.0 if (has_flows or has_triggers) else 0.0
    else:
        auto_coverage = len(uc_automations_specific & sd_automations) / max(len(uc_automations_specific), 1) * 100 if uc_automations_specific else 100
    ui_coverage = len(uc_ui & sd_ui) / max(len(uc_ui), 1) * 100 if uc_ui else 100
    uc_coverage = covered_ucs / max(total_ucs, 1) * 100

    # Rebalanced weights: traceability is the most meaningful metric
    # Old: obj=0.35, auto=0.25, ui=0.20, trace=0.20
    # New: obj=0.20, auto=0.15, ui=0.10, trace=0.55
    overall = (obj_coverage * 0.20 + auto_coverage * 0.15 + ui_coverage * 0.10 + uc_coverage * 0.55)

    return {
        "overall_score": round(overall, 1),
        "by_category": {
            "data_model": {
                "score": round(obj_coverage, 1),
                "sd_objects": list(sd_objects),
                "uc_objects": list(uc_objects),
                "missing": list(uc_objects - sd_objects)
            },
            "automation": {
                "score": round(auto_coverage, 1),
                "sd_automations": list(sd_automations),
                "uc_automations": list(uc_automations),
                "missing": list(uc_automations - sd_automations)
            },
            "ui_components": {
                "score": round(ui_coverage, 1),
                "sd_ui": list(sd_ui),
                "uc_ui": list(uc_ui),
                "missing": list(uc_ui - sd_ui)
            },
            "uc_traceability": {
                "score": round(uc_coverage, 1),
                "covered": covered_ucs,
                "total": total_ucs,
                "coverage_pct": round(uc_coverage, 1)
            }
        },
        "verdict": (
            "APPROVED" if overall >= 95 else
            "NEEDS_MINOR_REVISION" if overall >= 80 else
            "NEEDS_REVISION" if overall >= 60 else
            "REJECTED"
        )
    }


def generate_coverage_report_programmatic(solution_design: dict, use_cases: list) -> dict:
    """
    Generate a full coverage report combining programmatic + LLM analysis.
    Exported for direct import by tests and other services.

    The programmatic part checks object/automation coverage.
    If LLM is available, it also generates qualitative analysis.
    """
    prog_report = calculate_coverage_score(solution_design, use_cases)

    # Build critical gaps list from missing elements
    critical_gaps = []
    dm = prog_report.get('by_category', {}).get('data_model', {})
    for missing_obj in dm.get('missing', []):
        critical_gaps.append({
            "element_type": "object",
            "element_value": missing_obj,
            "severity": "high",
            "category": "DATA_MODEL"
        })

    auto = prog_report.get('by_category', {}).get('automation', {})
    for missing_auto in auto.get('missing', []):
        critical_gaps.append({
            "element_type": "automation",
            "element_value": missing_auto,
            "severity": "medium",
            "category": "AUTOMATION"
        })

    ui = prog_report.get('by_category', {}).get('ui_components', {})
    for missing_ui in ui.get('missing', []):
        critical_gaps.append({
            "element_type": "ui_component",
            "element_value": missing_ui,
            "severity": "medium",
            "category": "UI"
        })

    prog_report['critical_gaps'] = critical_gaps
    prog_report['total_gaps'] = len(critical_gaps)

    return prog_report


# ============================================================================
# RESEARCH ANALYST AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class ResearchAnalystAgent:
    """
    Emma (Research Analyst) Agent - 3 modes.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - analyze (Phase 2.5): UCs -> UC Digest
        - validate (Phase 3.3): Solution Design + UCs -> Coverage Analysis
        - write_sds (Phase 5): All deliverables -> Final SDS Document

    Usage (import):
        agent = ResearchAnalystAgent()
        result = agent.run({"mode": "analyze", "input_content": '{"use_cases": [...]}'})

    Usage (CLI):
        python salesforce_research_analyst.py --mode analyze --input input.json --output output.json

    Note: Module-level utility functions (parse_json_response, calculate_coverage_score,
    generate_coverage_report_programmatic) are preserved for direct import.
    """

    VALID_MODES = ("analyze", "validate", "write_sds")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "analyze", "validate", or "write_sds"
                - input_content: JSON string with mode-specific data
                - execution_id: int (optional, default 0)
                - project_id: int (optional, default 0)

        Returns:
            dict with agent output including "success" key.
        """
        mode = task_data.get("mode", "analyze")
        input_content = task_data.get("input_content", "")
        execution_id = task_data.get("execution_id", 0)
        project_id = task_data.get("project_id", 0)

        if mode not in self.VALID_MODES:
            return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

        if not input_content:
            return {"success": False, "error": "No input_content provided"}

        try:
            # Parse input JSON
            try:
                input_data = json.loads(input_content) if isinstance(input_content, str) else input_content
            except (json.JSONDecodeError, TypeError):
                input_data = {"raw_input": str(input_content)}

            if mode == "analyze":
                return self._execute_analyze(input_data, execution_id, project_id)
            elif mode == "validate":
                return self._execute_validate(input_data, execution_id, project_id)
            else:  # write_sds
                return self._execute_write_sds(input_data, execution_id, project_id)
        except Exception as e:
            logger.error(f"ResearchAnalystAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # MODE 1: ANALYZE (Phase 2.5) - UC Digest
    # ------------------------------------------------------------------
    def _execute_analyze(
        self,
        input_data: dict,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Generate UC Digest from Use Cases for Marcus."""
        start_time = time.time()

        use_cases = input_data.get('use_cases', [])
        if not use_cases:
            return {"success": False, "error": "No use_cases provided for analyze mode"}

        # Build UC text for prompt
        uc_text = ""
        for i, uc in enumerate(use_cases):
            uc_id = uc.get('id', f'UC-{i+1:03d}')
            uc_title = uc.get('title', 'Untitled')
            uc_actor = uc.get('actor', 'User')
            uc_description = uc.get('description', '')

            uc_text += f"\n### {uc_id}: {uc_title}\n"
            uc_text += f"- **Actor**: {uc_actor}\n"
            if uc_description:
                uc_text += f"- **Description**: {uc_description[:500]}\n"

            sf = uc.get('salesforce_components', {})
            if sf:
                objects = sf.get('objects', [])
                if objects:
                    uc_text += f"- **Objects**: {', '.join(objects)}\n"
                automation = sf.get('automation', [])
                if automation:
                    uc_text += f"- **Automation**: {', '.join(automation)}\n"

            # BR reference
            br_ref = uc.get('br_ref', uc.get('requirement_id', ''))
            if br_ref:
                uc_text += f"- **Business Requirement**: {br_ref}\n"

            criteria = uc.get('acceptance_criteria', [])
            if criteria:
                uc_text += "- **Acceptance Criteria**:\n"
                for c in criteria[:3]:
                    if isinstance(c, dict):
                        uc_text += f"  - {c.get('description', str(c))}\n"
                    else:
                        uc_text += f"  - {c}\n"

        timestamp = datetime.now().isoformat()

        # Try external prompt
        if PROMPT_SERVICE:
            try:
                prompt = PROMPT_SERVICE.render("emma_research", "uc_digest", {
                    "use_cases_text": uc_text,
                    "timestamp": timestamp,
                    "uc_count": str(len(use_cases)),
                })
            except Exception as e:
                logger.warning(f"PromptService fallback for emma_research/uc_digest: {e}")
                prompt = ANALYZE_PROMPT.format(
                    use_cases_text=uc_text,
                    timestamp=timestamp,
                    uc_count=len(use_cases)
                )
        else:
            prompt = ANALYZE_PROMPT.format(
                use_cases_text=uc_text,
                timestamp=timestamp,
                uc_count=len(use_cases)
            )

        system_prompt = "You are Emma, a Research Analyst. Generate a UC Digest. Output ONLY valid JSON."

        logger.info(f"ANALYZE mode: {len(use_cases)} UCs, prompt size: {len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, system_prompt, max_tokens=16000, temperature=0.3,
            execution_id=execution_id
        )

        execution_time = time.time() - start_time

        # Log interaction
        self._log_interaction(
            mode="analyze", prompt=prompt, content=content,
            execution_id=execution_id, input_tokens=input_tokens,
            tokens_used=tokens_used, model_used=model_used,
            provider_used=provider_used, execution_time=execution_time,
        )

        # Parse JSON
        parsed_content = parse_json_response(content)

        return {
            "success": True,
            "agent_id": "research_analyst",
            "agent_name": "Emma (Research Analyst)",
            "mode": "analyze",
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": "uc_digest",
            "artifact_id": "UCD-001",
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "use_cases_count": len(use_cases),
                "generated_at": timestamp
            }
        }

    # ------------------------------------------------------------------
    # MODE 2: VALIDATE (Phase 3.3) - Coverage Analysis
    # ------------------------------------------------------------------
    def _execute_validate(
        self,
        input_data: dict,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Validate Solution Design coverage against Use Cases."""
        start_time = time.time()

        solution_design = input_data.get('solution_design', input_data.get('architecture', {}))
        use_cases = input_data.get('use_cases', [])
        uc_digest = input_data.get('uc_digest', {})

        if not solution_design:
            return {"success": False, "error": "No solution_design provided for validate mode"}

        # Step 1: Programmatic coverage analysis
        prog_report = generate_coverage_report_programmatic(solution_design, use_cases)
        prog_score = prog_report.get('overall_score', 0)

        logger.info(f"Programmatic coverage score: {prog_score}%")

        # Step 2: LLM-based qualitative analysis
        solution_text = json.dumps(solution_design, indent=2, ensure_ascii=False)[:12000]

        uc_text = ""
        for uc in use_cases[:20]:
            uc_text += f"- {uc.get('id', 'UC')}: {uc.get('title', '')}\n"
            sf = uc.get('salesforce_components', {})
            if sf:
                objects = sf.get('objects', [])
                if objects:
                    uc_text += f"  Objects: {', '.join(objects[:5])}\n"

        uc_digest_text = json.dumps(uc_digest, indent=2, ensure_ascii=False)[:5000] if uc_digest else "Not available"

        timestamp = datetime.now().isoformat()

        # Try external prompt
        if PROMPT_SERVICE:
            try:
                prompt = PROMPT_SERVICE.render("emma_research", "coverage_review", {
                    "solution_design_text": solution_text,
                    "use_cases_text": uc_text,
                    "uc_digest_text": uc_digest_text,
                    "timestamp": timestamp,
                })
            except Exception as e:
                logger.warning(f"PromptService fallback for emma_research/coverage_review: {e}")
                prompt = VALIDATE_PROMPT.format(
                    solution_design_text=solution_text,
                    use_cases_text=uc_text,
                    uc_digest_text=uc_digest_text,
                    timestamp=timestamp
                )
        else:
            prompt = VALIDATE_PROMPT.format(
                solution_design_text=solution_text,
                use_cases_text=uc_text,
                uc_digest_text=uc_digest_text,
                timestamp=timestamp
            )

        system_prompt = "You are Emma, a Research Analyst. Validate coverage. Output ONLY valid JSON."

        logger.info(f"VALIDATE mode: {len(use_cases)} UCs, prompt size: {len(prompt)} chars")

        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, system_prompt, max_tokens=16000, temperature=0.3,
            execution_id=execution_id
        )

        execution_time = time.time() - start_time

        # Log interaction
        self._log_interaction(
            mode="validate", prompt=prompt, content=content,
            execution_id=execution_id, input_tokens=input_tokens,
            tokens_used=tokens_used, model_used=model_used,
            provider_used=provider_used, execution_time=execution_time,
        )

        # Parse LLM response
        llm_report = parse_json_response(content)

        # Merge programmatic + LLM results
        # Use LLM score if available, otherwise use programmatic
        llm_score = llm_report.get('overall_coverage_score', prog_score)
        final_score = (llm_score * 0.6 + prog_score * 0.4)  # Weighted average

        # Determine verdict
        if final_score >= 95:
            verdict = "APPROVED"
        elif final_score >= 80:
            verdict = "NEEDS_MINOR_REVISION"
        elif final_score >= 60:
            verdict = "NEEDS_REVISION"
        else:
            verdict = "REJECTED"

        # Combine critical gaps from both sources
        all_gaps = prog_report.get('critical_gaps', [])
        llm_gaps = llm_report.get('critical_gaps', [])
        if isinstance(llm_gaps, list):
            all_gaps.extend(llm_gaps)

        # Combine uncovered UCs
        uncovered_ucs = llm_report.get('uncovered_use_cases', [])

        return {
            "success": True,
            "agent_id": "research_analyst",
            "agent_name": "Emma (Research Analyst)",
            "mode": "validate",
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": "coverage_analysis",
            "artifact_id": "COV-001",
            "content": {
                "overall_coverage_score": round(final_score, 1),
                "programmatic_score": prog_score,
                "llm_score": llm_score,
                "verdict": verdict,
                "coverage_by_category": {
                    **prog_report.get('by_category', {}),
                    **(llm_report.get('coverage_by_category', {}))
                },
                "coverage_by_requirement": llm_report.get('coverage_by_requirement', {}),
                "critical_gaps": all_gaps,
                "uncovered_use_cases": uncovered_ucs,
                "recommendations": llm_report.get('recommendations', [])
            },
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "use_cases_count": len(use_cases),
                "generated_at": timestamp
            }
        }

    # ------------------------------------------------------------------
    # MODE 3: WRITE_SDS (Phase 5) - Final SDS Document
    # ------------------------------------------------------------------
    def _execute_write_sds(
        self,
        input_data: dict,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Assemble all deliverables into final SDS document."""
        start_time = time.time()

        project_name = input_data.get('project_name', 'Salesforce Project')
        timestamp = datetime.now().isoformat()

        # Extract all deliverables (truncate each to avoid token overflow)
        def safe_content(key: str, max_len: int = 8000) -> str:
            val = input_data.get(key, '')
            if isinstance(val, dict):
                val = json.dumps(val, indent=2, ensure_ascii=False)
            elif isinstance(val, list):
                val = json.dumps(val, indent=2, ensure_ascii=False)
            return str(val)[:max_len] if val else "Not provided"

        # Try external prompt
        if PROMPT_SERVICE:
            try:
                prompt = PROMPT_SERVICE.render("emma_research", "write_sds", {
                    "project_name": project_name,
                    "timestamp": timestamp,
                    "br_content": safe_content('business_requirements', 6000),
                    "uc_content": safe_content('use_cases', 8000),
                    "uc_digest_content": safe_content('uc_digest', 5000),
                    "solution_design_content": safe_content('solution_design', 10000),
                    "gap_analysis_content": safe_content('gap_analysis', 6000),
                    "wbs_content": safe_content('wbs', 6000),
                    "qa_content": safe_content('qa_plan', 4000),
                    "devops_content": safe_content('devops_plan', 3000),
                    "training_content": safe_content('training_plan', 3000),
                    "data_migration_content": safe_content('data_migration_plan', 3000),
                })
            except Exception as e:
                logger.warning(f"PromptService fallback for emma_research/write_sds: {e}")
                prompt = WRITE_SDS_PROMPT.format(
                    project_name=project_name,
                    timestamp=timestamp,
                    br_content=safe_content('business_requirements', 6000),
                    uc_content=safe_content('use_cases', 8000),
                    uc_digest_content=safe_content('uc_digest', 5000),
                    solution_design_content=safe_content('solution_design', 10000),
                    gap_analysis_content=safe_content('gap_analysis', 6000),
                    wbs_content=safe_content('wbs', 6000),
                    qa_content=safe_content('qa_plan', 4000),
                    devops_content=safe_content('devops_plan', 3000),
                    training_content=safe_content('training_plan', 3000),
                    data_migration_content=safe_content('data_migration_plan', 3000),
                )
        else:
            prompt = WRITE_SDS_PROMPT.format(
                project_name=project_name,
                timestamp=timestamp,
                br_content=safe_content('business_requirements', 6000),
                uc_content=safe_content('use_cases', 8000),
                uc_digest_content=safe_content('uc_digest', 5000),
                solution_design_content=safe_content('solution_design', 10000),
                gap_analysis_content=safe_content('gap_analysis', 6000),
                wbs_content=safe_content('wbs', 6000),
                qa_content=safe_content('qa_plan', 4000),
                devops_content=safe_content('devops_plan', 3000),
                training_content=safe_content('training_plan', 3000),
                data_migration_content=safe_content('data_migration_plan', 3000),
            )

        system_prompt = "You are Emma, a Research Analyst. Write the complete SDS document. Output ONLY Markdown."

        logger.info(f"WRITE_SDS mode: prompt size: {len(prompt)} chars")

        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, system_prompt, max_tokens=16000, temperature=0.4,
            execution_id=execution_id
        )

        execution_time = time.time() - start_time

        # Log interaction
        self._log_interaction(
            mode="write_sds", prompt=prompt, content=content,
            execution_id=execution_id, input_tokens=input_tokens,
            tokens_used=tokens_used, model_used=model_used,
            provider_used=provider_used, execution_time=execution_time,
        )

        # For write_sds, content is Markdown, not JSON
        return {
            "success": True,
            "agent_id": "research_analyst",
            "agent_name": "Emma (Research Analyst)",
            "mode": "write_sds",
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": "sds_document",
            "artifact_id": "SDS-001",
            "content": {
                "raw_markdown": content,
                "word_count": len(content.split()),
                "sections_count": content.count('\n# ') + content.count('\n## ')
            },
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": timestamp
            }
        }

    # ------------------------------------------------------------------
    # LLM / RAG / Logger helpers
    # ------------------------------------------------------------------
    def _call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 16000,
        temperature: float = 0.3,
        execution_id: int = 0,
    ) -> tuple:
        """
        Call LLM service with fallback to direct Anthropic API.

        Returns:
            (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            response = generate_llm_response(
                prompt=prompt,
                agent_type="research_analyst",
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                execution_id=execution_id
            )
            content = response.get("content", "")
            tokens_used = response.get("tokens_used", 0)
            input_tokens = response.get("input_tokens", 0)
            model_used = response.get("model", "")
            provider_used = response.get("provider", "")
            logger.info(f"Using {provider_used} / {model_used}")
            return content, tokens_used, input_tokens, model_used, provider_used

        # Fallback to direct Anthropic
        logger.info("Calling Anthropic API directly...")
        from anthropic import Anthropic
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        input_tokens = response.usage.input_tokens
        return content, tokens_used, input_tokens, "claude-sonnet-4-20250514", "anthropic"

    def _log_interaction(
        self,
        mode: str,
        prompt: str,
        content: str,
        execution_id: int,
        input_tokens: int = 0,
        tokens_used: int = 0,
        model_used: str = "",
        provider_used: str = "",
        execution_time: float = 0.0,
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="emma",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=None,
                agent_mode=mode,
                rag_context=None,
                previous_feedback=None,
                parsed_files=None,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider=provider_used,
                execution_time_seconds=round(execution_time, 2),
                success=True,
                error_message=None
            )
            logger.info("LLM interaction logged")
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")


# ============================================================================
# CLI MODE - Backward compatible subprocess entry point
# ============================================================================

if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path

    # Add backend root to sys.path for CLI mode
    _backend_root = str(Path(__file__).resolve().parent.parent.parent)
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

    parser = argparse.ArgumentParser(description='Emma - Research Analyst Agent')
    parser.add_argument('--mode', required=True,
                        choices=['analyze', 'validate', 'write_sds'],
                        help='Operation mode')
    parser.add_argument('--input', required=True, help='Input JSON file')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--execution-id', type=int, default=0)
    parser.add_argument('--project-id', type=int, default=0)
    parser.add_argument('--use-rag', action='store_true', default=True)

    args = parser.parse_args()

    try:
        # Read input
        logger.info("Reading input from %s...", args.input)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()

        # Use agent class
        agent = ResearchAnalystAgent()
        task_data = {
            "mode": args.mode,
            "input_content": input_content,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
        }
        result = agent.run(task_data)

        # Save output
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        logger.info("SUCCESS: Output saved to %s", args.output)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        sys.exit(0)

    except Exception as e:
        logger.error("ERROR: %s", str(e), exc_info=True)
        sys.exit(1)
