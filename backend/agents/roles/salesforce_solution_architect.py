#!/usr/bin/env python3
"""
Salesforce Solution Architect (Marcus) Agent - Refactored Version
4 distinct modes:
1. design: UC/UC Digest -> Architecture globale (ARCH-001)
2. as_is: SFDX metadata -> Resume structure (ASIS-001)
3. gap: ARCH + ASIS + UC context -> Deltas (GAP-001)
4. wbs: GAP -> Taches + Planning (WBS-001)

EMMA INTEGRATION (v2.5):
- design mode: Accepts uc_digest from Emma for richer context
- gap mode: Uses UC context from digest or raw UCs
- Fallback: If no uc_digest, uses raw UCs (old behavior)

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (SolutionArchitectAgent.run()) or CLI.

Module-level prompt functions (get_design_prompt, get_as_is_prompt, get_gap_prompt,
get_wbs_prompt, get_fix_gaps_prompt) are preserved for direct import by tests.
"""

import os
import re
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

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

# JSON Cleaner for robust parsing (added 2025-12-22)
try:
    from app.utils.json_cleaner import clean_llm_json_response
    JSON_CLEANER_AVAILABLE = True
except ImportError:
    JSON_CLEANER_AVAILABLE = False
    def clean_llm_json_response(s): return None, "JSON cleaner not available"


# ============================================================================
# PROMPT 1: SOLUTION DESIGN (UC -> Architecture)
# ============================================================================
def get_design_prompt(use_cases: list, project_summary: str, rag_context: str = "", uc_digest: dict = None, coverage_gaps: list = None, uncovered_use_cases: list = None, revision_request: str = None) -> str:
    """
    Generate design prompt with UC Digest (from Emma) or raw UCs as fallback.
    UC Digest provides pre-analyzed, structured information about ALL use cases.

    Revision mode: If coverage_gaps provided, this is a revision request to address gaps.
    """

    # REVISION MODE: Add coverage gaps context if this is a revision request
    revision_context = ""
    if revision_request and coverage_gaps:
        revision_context = f"""
## REVISION REQUEST

{revision_request}

### Coverage Gaps to Address
The following gaps were identified by Emma (Research Analyst) and MUST be addressed in this revision:

"""
        for i, gap in enumerate(coverage_gaps[:10], 1):
            if isinstance(gap, dict):
                revision_context += f"{i}. **{gap.get('category', 'Gap')}**: {gap.get('description', str(gap))}\n"
            else:
                revision_context += f"{i}. {gap}\n"

        if uncovered_use_cases:
            revision_context += f"\n### Uncovered Use Cases ({len(uncovered_use_cases)})\n"
            for uc in uncovered_use_cases[:5]:
                if isinstance(uc, dict):
                    revision_context += f"- {uc.get('id', 'UC')}: {uc.get('title', str(uc))}\n"
                else:
                    revision_context += f"- {uc}\n"
            if len(uncovered_use_cases) > 5:
                revision_context += f"- ... and {len(uncovered_use_cases) - 5} more\n"

        revision_context += "\n**Instructions**: Update your solution design to ensure ALL above gaps are addressed.\n\n"

    # EMMA INTEGRATION: Use UC Digest if available (preferred)
    if uc_digest and uc_digest.get('by_requirement'):
        uc_text = "\n## ANALYZED USE CASE DIGEST (from Emma)\n"
        uc_text += "This digest contains pre-analyzed information from ALL Use Cases, grouped by Business Requirement.\n"

        for br_id, br_data in uc_digest.get('by_requirement', {}).items():
            uc_text += f"\n### {br_id}: {br_data.get('title', 'Untitled')}\n"
            uc_text += f"- **UC Count**: {br_data.get('uc_count', 0)}\n"

            # SF Objects
            sf_objects = br_data.get('sf_objects', [])
            if sf_objects:
                uc_text += f"- **Salesforce Objects**: {', '.join(sf_objects)}\n"

            # SF Fields by Object
            sf_fields = br_data.get('sf_fields', {})
            if sf_fields:
                uc_text += "- **Fields by Object**:\n"
                for obj, fields in sf_fields.items():
                    uc_text += f"  - {obj}: {', '.join(fields[:10])}{'...' if len(fields) > 10 else ''}\n"

            # Automations
            automations = br_data.get('automations', [])
            if automations:
                uc_text += "- **Automations**:\n"
                for auto in automations[:5]:
                    uc_text += f"  - {auto.get('type', 'Unknown')}: {auto.get('purpose', '')}\n"

            # UI Components
            ui_components = br_data.get('ui_components', [])
            if ui_components:
                uc_text += f"- **UI Components**: {', '.join(ui_components[:5])}\n"

            # Key Acceptance Criteria
            criteria = br_data.get('key_acceptance_criteria', [])
            if criteria:
                uc_text += "- **Key Acceptance Criteria**:\n"
                for c in criteria[:3]:
                    uc_text += f"  - {c}\n"

        # Cross-cutting concerns
        cross_cutting = uc_digest.get('cross_cutting_concerns', {})
        if cross_cutting:
            uc_text += "\n### Cross-Cutting Concerns\n"
            shared = cross_cutting.get('shared_objects', [])
            if shared:
                # Handle both string list and dict list formats
                if isinstance(shared[0], dict):
                    shared_names = [s.get('object', str(s)) for s in shared]
                    uc_text += f"- **Shared Objects**: {', '.join(shared_names)}\n"
                    for s in shared[:3]:
                        uc_text += f"  - {s.get('object', 'Unknown')}: {s.get('usage', '')[:100]}\n"
                else:
                    uc_text += f"- **Shared Objects**: {', '.join(shared)}\n"
            integrations = cross_cutting.get('integration_points', [])
            if integrations:
                if isinstance(integrations[0], dict):
                    int_names = [i.get('name', str(i)) for i in integrations]
                    uc_text += f"- **Integration Points**: {', '.join(int_names)}\n"
                else:
                    uc_text += f"- **Integration Points**: {', '.join(integrations)}\n"

        # Recommendations from Emma
        recommendations = uc_digest.get('recommendations', [])
        if recommendations:
            uc_text += "\n### Emma's Recommendations for Architecture\n"
            for rec in recommendations[:5]:
                uc_text += f"- {rec}\n"
    else:
        # FALLBACK: Use raw Use Cases (old behavior, limited to 15)
        uc_text = ""
        for uc in use_cases[:15]:  # Limit to avoid token overflow
            uc_text += f"\n**{uc.get('id', 'UC-XXX')}: {uc.get('title', 'Untitled')}**\n"
            uc_text += f"- Actor: {uc.get('actor', 'User')}\n"
            sf = uc.get('salesforce_components', {})
            if sf:
                uc_text += f"- Objects: {', '.join(sf.get('objects', []))}\n"
                uc_text += f"- Automation: {', '.join(sf.get('automation', []))}\n"

    rag_section = f"\n## SALESFORCE BEST PRACTICES (RAG)\n{rag_context}\n---\n" if rag_context else ""

    return f'''{revision_context}# SOLUTION DESIGN SPECIFICATION

You are **Marcus**, a Salesforce Certified Technical Architect (CTA).

## YOUR MISSION
Create a **High-Level Solution Design** from the Use Cases provided.

## PROJECT CONTEXT
{project_summary}

## USE CASES TO ARCHITECT
{uc_text}
{rag_section}

## OUTPUT FORMAT (JSON)
Generate a solution design with:
- "artifact_id": "ARCH-001"
- "title": "Solution Design Specification"
- "data_model": Object with:
  - "standard_objects": Array of objects, each with: {{"api_name": "Case", "purpose": "...", "customizations": [...]}}
  - "custom_objects": Array of objects, each with: {{"api_name": "Error_Log__c", "purpose": "...", "fields": [...]}}
  - "relationships": Array of object relationships
  - "erd_mermaid": ERD diagram in Mermaid syntax
- "security_model": Object with:
  - "profiles": Array of profiles needed
  - "permission_sets": Array of permission sets
  - "sharing_rules": Summary of sharing approach
  - "field_level_security": Key FLS considerations
- "automation_design": Object with:
  - "flows": Array of Flows with purpose
  - "triggers": Array of Apex triggers if needed
  - "scheduled_jobs": Array of batch/scheduled processes
- "integration_points": Array of external integrations with:
  - "system": External system name
  - "direction": Inbound/Outbound/Bidirectional
  - "method": API type (REST, SOAP, etc.)
  - "frequency": Real-time, Batch, etc.
- "ui_components": Object with:
  - "lightning_pages": Array of custom pages
  - "lwc_components": Array of LWC needed
  - "quick_actions": Array of actions
- "technical_considerations": Array of key technical decisions
- "risks": Array of technical risks identified

## RULES
1. Use Salesforce standard objects before creating custom ones
2. Prefer declarative (Flows) over code (Apex) where possible
3. Follow Salesforce naming conventions
4. Consider governor limits in design
5. ERD must use valid Mermaid erDiagram syntax
6. Be specific about object and field API names

---

**Generate the Solution Design now. Output ONLY valid JSON.**
'''

# ============================================================================
# PROMPT 2: AS-IS ANALYSIS (SFDX -> Summary)
# ============================================================================
def get_as_is_prompt(sfdx_metadata: str) -> str:
    sfdx_metadata_truncated = sfdx_metadata[:15000] if len(sfdx_metadata) > 15000 else sfdx_metadata
    return f'''# AS-IS ANALYSIS

You are **Marcus**, a Salesforce Certified Technical Architect.

## YOUR MISSION
Analyze the existing Salesforce org metadata and create a structured summary.

## SFDX METADATA EXTRACT
{sfdx_metadata_truncated}  <!-- Truncate to avoid token overflow -->

## OUTPUT FORMAT (JSON)
Generate an As-Is analysis with:
- "artifact_id": "ASIS-001"
- "title": "Current State Analysis"
- "data_model_summary": Object with:
  - "custom_objects_count": Number
  - "key_objects": Array of main objects with field counts
  - "relationships_summary": Brief description
- "automation_summary": Object with:
  - "flows_count": Number
  - "triggers_count": Number
  - "key_automations": Array of main automations
- "security_summary": Object with:
  - "profiles_count": Number
  - "permission_sets_count": Number
  - "sharing_model": Brief description
- "integration_summary": Object with:
  - "connected_apps": Array
  - "named_credentials": Array
  - "external_services": Array
- "ui_summary": Object with:
  - "lightning_pages_count": Number
  - "lwc_components": Array
  - "custom_tabs": Array
- "technical_debt": Array of issues identified
- "recommendations": Array of quick wins

## RULES
1. Focus on summarizing, not listing everything
2. Identify patterns and anti-patterns
3. Highlight technical debt
4. Note deprecated features in use

---

**Generate the As-Is Analysis now. Output ONLY valid JSON.**
'''

# ============================================================================
# PROMPT 3: GAP ANALYSIS (SOLUTION DESIGN + ASIS -> Implementation Gaps)
# ============================================================================
def get_gap_prompt(solution_design: str, asis_summary: str, uc_context: str = "") -> str:
    """
    Generate gap analysis comparing Solution Design (target) vs As-Is (current).
    UPDATED: Added agent table, uc_refs requirement, UI component emphasis.
    """
    uc_section = ""
    if uc_context:
        uc_section = f"""
## USE CASE REQUIREMENTS (from Emma's Analysis)
{uc_context}

"""

    # ADDED (19/12/2025): Include Solution Design as the TARGET architecture
    design_section = ""
    if solution_design and solution_design.strip() != "{{}}":
        design_section = f"""
## TARGET ARCHITECTURE (Solution Design - ARCH-001)
This is the validated architecture we need to implement.
Identify gaps between Current State and this Target.
Use the EXACT object and component names from this design.

{solution_design}

"""

    return f'''# GAP ANALYSIS

You are **Marcus**, a Salesforce Certified Technical Architect.

## YOUR MISSION
Compare the **Current State (As-Is)** with the **Target Architecture (Solution Design)** to identify ALL implementation gaps.
Each gap represents work needed to transform the current org into the target architecture.

**CRITICAL RULES**:
1. ONLY create gaps for components defined in the Solution Design
2. Use the EXACT object names from the Solution Design (e.g., Property__c, Lease__c)
3. DO NOT invent objects or components not in the Solution Design
4. Every UI component (LWC, Screen Flow) in the Solution Design MUST have a corresponding gap
{design_section}{uc_section}
## CURRENT STATE (ASIS-001)
{asis_summary}

## AVAILABLE AGENTS (assign gaps to the RIGHT agent)

| Agent | Role | Handles |
|-------|------|---------|
| Diego | Apex Developer | Apex classes, triggers, batch jobs, schedulable, REST/SOAP integrations |
| Zara | LWC Developer | Lightning Web Components, Aura components, custom UI components |
| Raj | SF Admin | Objects, fields, page layouts, flows, validation rules, profiles, permission sets |
| Elena | QA Engineer | Test plans, test cases, UAT scenarios |
| Jordan | DevOps | CI/CD, deployments, environments |
| Aisha | Data Migration | Data mapping, ETL, migration scripts |
| Lucas | Trainer | Training materials, user guides, documentation |
| Marcus | Architect | Architecture reviews only |

## AGENT ASSIGNMENT RULES (STRICT)

- **Lightning Web Components (LWC)** -> **Zara** (NOT Raj, NOT Diego)
- **Aura components** -> **Zara**
- **Custom UI with JavaScript** -> **Zara**
- **Screen Flows** -> **Raj** (declarative, no code)
- **Record-Triggered Flows** -> **Raj**
- **Validation Rules** -> **Raj**
- **Objects, Fields, Layouts** -> **Raj**
- **Apex classes/triggers** -> **Diego**
- **Apex integration code** -> **Diego**

## OUTPUT FORMAT (JSON)

```json
{{{{
  "artifact_id": "GAP-001",
  "title": "Gap Analysis",
  "gaps": [
    {{{{
      "id": "GAP-001-01",
      "category": "DATA_MODEL | AUTOMATION | SECURITY | INTEGRATION | UI | OTHER",
      "uc_refs": ["UC-001-01", "UC-001-02"],
      "current_state": "What exists now (or 'None' if greenfield)",
      "target_state": "What is needed - be specific about component type",
      "gap_description": "Clear description of the delta",
      "complexity": "LOW | MEDIUM | HIGH",
      "effort_days": 2,
      "dependencies": ["GAP-001-XX"],
      "assigned_agent": "Raj | Diego | Zara | Elena | Jordan | Aisha | Lucas | Marcus"
    }}}}
  ],
  "summary": {{{{
    "total_gaps": 50,
    "by_category": {{{{"DATA_MODEL": 15, "AUTOMATION": 20, "UI": 8}}}},
    "by_complexity": {{{{"LOW": 20, "MEDIUM": 25, "HIGH": 5}}}},
    "by_agent": {{{{"Raj": 25, "Diego": 10, "Zara": 8}}}},
    "total_effort_days": 120
  }}}},
  "migration_considerations": ["..."],
  "risk_areas": ["..."]
}}}}
```

## RULES

1. **Match Solution Design exactly** - use the SAME object/field names as in ARCH-001
2. **EVERY component in Solution Design** needs a gap if it doesn't exist in As-Is
3. **uc_refs is MANDATORY** - each gap must reference which UCs it addresses
4. **Be specific** about component types (e.g., "LWC propertyCard" not just "component")
5. **Realistic effort estimates** - include time for testing
6. **No orphan UCs** - every UC must be covered by at least one gap
7. **Correct agent assignment** - LWC/Aura always to Zara, never to Raj or Diego
8. **NO HALLUCINATION** - ONLY include components from Solution Design, never invent new ones

---

**Generate the Gap Analysis now. Output ONLY valid JSON.**
'''

# ============================================================================
# PROMPT 4: WBS (GAP -> Tasks + Planning)
# ============================================================================
def get_wbs_prompt(gap_analysis: str, project_constraints: str = "") -> str:
    return f'''# WORK BREAKDOWN STRUCTURE - ENRICHED

You are **Marcus**, a Salesforce Certified Technical Architect.

## MISSION
Create a detailed Work Breakdown Structure from the Gap Analysis.
Each task MUST have validation criteria and clear agent assignment.

## GAP ANALYSIS
{gap_analysis}

## PROJECT CONSTRAINTS
{project_constraints if project_constraints else "Standard Salesforce implementation timeline"}

## OUTPUT FORMAT (JSON - STRICT)

```json
{{
  "artifact_id": "WBS-001",
  "title": "Work Breakdown Structure",
  "phases": [
    {{
      "id": "PHASE-01",
      "name": "Phase name",
      "duration_weeks": 2,
      "tasks": [
        {{
          "id": "TASK-001",
          "name": "Task name (action verb + object)",
          "description": "Brief description (1-2 sentences max)",
          "task_type": "dev_data_model",
          "gap_refs": ["GAP-001-01"],
          "assigned_agent": "Raj",
          "effort_days": 2,
          "dependencies": [],
          "deliverables": ["Deliverable 1"],
          "validation_criteria": [
            "DONE WHEN: [specific measurable outcome]",
            "VERIFIED BY: [how Elena/reviewer checks it]"
          ],
          "test_approach": "Unit test / Manual test / UAT"
        }}
      ]
    }}
  ],
  "milestones": [...],
  "resource_allocation": {{...}},
  "critical_path": ["TASK-001", "TASK-005", ...],
  "risks_and_mitigations": [...]
}}
```

## AVAILABLE AGENTS (ONLY these 8)

| Agent | Role | Handles |
|-------|------|---------|
| Diego | Apex Developer | Apex classes, triggers, batch, integration code |
| Zara | LWC Developer | LWC, Aura, custom UI components |
| Raj | SF Admin | Objects, fields, flows, validation rules, profiles |
| Elena | QA Engineer | Test plans, test execution, UAT, bugs |
| Jordan | DevOps | CI/CD, deployments, environments, releases |
| Aisha | Data Migration | Data mapping, ETL, migration, data validation |
| Lucas | Trainer | Training docs, user guides, training sessions |
| Marcus | Architect | Architecture reviews, design oversight |

## TASK TYPES (REQUIRED - use exact values)

| Type | Agent | Description |
|------|-------|-------------|
| setup_environment | MANUAL | Sandbox/SFDX setup |
| setup_repository | MANUAL | Git repo setup |
| setup_permissions | Raj | Initial profiles/permissions |
| dev_data_model | Raj | Objects, fields, relationships |
| dev_apex | Diego | Apex classes, triggers |
| dev_lwc | Zara | Lightning Web Components |
| dev_flow | Raj | Flows, automation |
| dev_validation | Raj | Validation rules |
| dev_formula | Raj | Formula fields |
| config_profiles | Raj | Profile configuration |
| config_sharing | Raj | Sharing rules, OWD |
| config_layouts | Raj | Page layouts |
| config_apps | Raj | Lightning apps |
| config_reports | Raj | Reports/dashboards |
| test_unit | Elena | Apex unit tests |
| test_integration | Elena | Integration tests |
| test_uat | MANUAL | User acceptance tests |
| deploy_prepare | Jordan | Package preparation |
| deploy_execute | Jordan | Deployment |
| deploy_validate | Jordan | Post-deploy validation |
| doc_technical | Lucas | Technical docs |
| doc_user | Lucas | User documentation |
| doc_training | Lucas | Training materials |

## TASK ASSIGNMENT RULES (STRICT)

- **Config (no code)** -> Raj: objects, fields, page layouts, flows, validation rules, profiles, permission sets
- **Apex code** -> Diego: classes, triggers, batch, schedulable, REST/SOAP
- **UI code** -> Zara: LWC, Aura, Lightning pages
- **Testing** -> Elena: ALL test tasks (unit, integration, UAT)
- **Deploy** -> Jordan: ALL deployment/pipeline tasks
- **Data** -> Aisha: ALL data migration tasks
- **Docs** -> Lucas: ALL training/documentation tasks
- **Review** -> Marcus: architecture reviews only

## VALIDATION CRITERIA FORMAT (REQUIRED for each task)

Each task MUST have 1-3 validation_criteria using this format:
- "DONE WHEN: [specific outcome that can be verified]"
- "VERIFIED BY: [how the reviewer/Elena checks this is complete]"

**Good examples:**
- "DONE WHEN: Custom object Account_Score__c created with 5 fields"
- "VERIFIED BY: Run SOQL query, check field count in Setup"
- "DONE WHEN: All unit tests pass with >80% coverage"
- "VERIFIED BY: Deploy to scratch org, run apex:test:run"

**Bad examples (avoid):**
- "DONE WHEN: Task is complete" (too vague)
- "VERIFIED BY: Check it works" (not specific)

## GENERAL RULES

1. **Every task has task_type** - MUST be one from the TASK TYPES table above
2. **30-60 tasks** total - fewer means too coarse, more means micromanagement
2. **Max 10 tasks per phase** - split large phases
3. **Every task has validation_criteria** - NO exceptions
4. **Respect dependencies** - no circular refs
5. **Balance workload** - no agent should have >40% of tasks
6. **Include test tasks** - at least 15% of tasks should be Elena's
7. **Include deploy tasks** - at least 5% of tasks should be Jordan's

---

**Generate the WBS now. Output ONLY valid JSON, no markdown fences.**
'''


# ============================================================================
# MODE FIX_GAPS - Revision de solution pour corriger les gaps de couverture
# ============================================================================

def get_fix_gaps_prompt(current_solution: dict, coverage_gaps: list, uncovered_use_cases: list = None, iteration: int = 1) -> str:
    """
    Generate prompt for fix_gaps mode.

    This mode receives the current solution and coverage gaps from Emma validate,
    and produces an improved solution that addresses the gaps.
    """

    # Format current solution
    solution_json = json.dumps(current_solution, indent=2, ensure_ascii=False)

    # Format gaps
    gaps_text = ""
    for i, gap in enumerate(coverage_gaps[:20], 1):
        if isinstance(gap, dict):
            element_type = gap.get('element_type', 'unknown')
            element_value = gap.get('element_value', str(gap))
            severity = gap.get('severity', 'medium')
            gaps_text += f"{i}. [{severity.upper()}] {element_type}: {element_value}\n"
        else:
            gaps_text += f"{i}. {gap}\n"

    if len(coverage_gaps) > 20:
        gaps_text += f"\n... and {len(coverage_gaps) - 20} more gaps\n"

    # Format uncovered UCs
    uncovered_text = ""
    if uncovered_use_cases:
        for uc in uncovered_use_cases[:10]:
            if isinstance(uc, dict):
                uncovered_text += f"- {uc.get('id', 'UC')}: {uc.get('title', str(uc))}\n"
            else:
                uncovered_text += f"- {uc}\n"
        if len(uncovered_use_cases) > 10:
            uncovered_text += f"... and {len(uncovered_use_cases) - 10} more\n"

    return f'''# SOLUTION DESIGN REVISION (Iteration {iteration})

## CONTEXT
Emma (Research Analyst) has analyzed your solution design and found coverage gaps.
Your task is to revise the solution to address ALL identified gaps.

## CURRENT SOLUTION
```json
{solution_json[:15000]}
```

## COVERAGE GAPS TO ADDRESS ({len(coverage_gaps)} gaps)
{gaps_text}

## UNCOVERED USE CASES
{uncovered_text if uncovered_text else "None specified"}

## REVISION INSTRUCTIONS

1. **Preserve existing elements** - Do not remove elements that are working
2. **Add missing elements** - For each gap, add the necessary Salesforce component
3. **Update related elements** - If adding a field, update relevant automations
4. **Maintain consistency** - Ensure naming conventions and relationships are consistent

## OUTPUT FORMAT

Return the COMPLETE revised solution design in the same JSON structure:
{{
    "artifact_id": "ARCH-001-v{iteration + 1}",
    "title": "Revised Solution Design v{iteration + 1}",
    "revision_notes": {{
        "iteration": {iteration + 1},
        "gaps_addressed": [/* list of addressed gaps */],
        "changes_made": [/* list of changes */]
    }},
    "data_model": {{
        "standard_objects": [...],
        "custom_objects": [...],
        "relationships": [...],
        "erd_mermaid": "..."
    }},
    "security_model": {{...}},
    "automation_design": {{
        "flows": [...],
        "triggers": [...],
        "scheduled_jobs": [...]
    }},
    "integration_points": [...],
    "ui_components": {{...}},
    "technical_considerations": [...],
    "risks": [...]
}}

**IMPORTANT**:
- Address ALL gaps listed above
- Output ONLY valid JSON, no markdown fences
- Include revision_notes explaining what was changed
'''


# ============================================================================
# JSON PARSING HELPER
# ============================================================================
def _parse_json_content(content: str) -> dict:
    """Parse JSON from LLM response using robust cleaner with fallback."""
    if JSON_CLEANER_AVAILABLE:
        parsed_content, parse_error = clean_llm_json_response(content)
        if parsed_content is not None:
            logger.info("JSON parsed successfully (via cleaner)")
            return parsed_content
        else:
            logger.warning(f"JSON parse error: {parse_error}")
            logger.debug(f"Content preview: {content[:200]}...")

    # Fallback to basic parsing
    try:
        clean_content = content.strip()
        if clean_content.startswith('```'):
            clean_content = re.sub(r'^```(?:json)?\s*', '', clean_content)
            clean_content = re.sub(r'```\s*$', '', clean_content)
        parsed = json.loads(clean_content.strip())
        logger.info("JSON parsed successfully (basic)")
        return parsed
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error (basic): {e}")
        return {"raw": content, "parse_error": str(e)}


# ============================================================================
# SOLUTION ARCHITECT AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class SolutionArchitectAgent:
    """
    Marcus (Solution Architect) Agent - 5 modes.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - design: UC/UC Digest -> Architecture globale (ARCH-001)
        - as_is: SFDX metadata -> Resume structure (ASIS-001)
        - gap: ARCH + ASIS + UC context -> Deltas (GAP-001)
        - wbs: GAP -> Taches + Planning (WBS-001)
        - fix_gaps: Revise solution to address coverage gaps

    Usage (import):
        agent = SolutionArchitectAgent()
        result = agent.run({"mode": "design", "input_content": '{"use_cases": [...], "project_summary": "..."}'})

    Usage (CLI):
        python salesforce_solution_architect.py --mode design --input input.json --output output.json

    Note: Module-level prompt functions (get_design_prompt, get_as_is_prompt,
    get_gap_prompt, get_wbs_prompt, get_fix_gaps_prompt) are preserved for
    direct import by tests.
    """

    VALID_MODES = ("design", "as_is", "gap", "wbs", "fix_gaps")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: one of VALID_MODES
                - input_content: JSON string with mode-specific data
                - execution_id: int (optional, default 0)
                - project_id: int (optional, default 0)

        Returns:
            dict with agent output including "success" key.
        """
        mode = task_data.get("mode", "design")
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

            return self._execute(mode, input_data, execution_id, project_id)
        except Exception as e:
            logger.error(f"SolutionArchitectAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _execute(
        self,
        mode: str,
        input_data: dict,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Core execution logic for all modes."""
        start_time = time.time()

        # Get RAG context for design mode
        rag_context = ""
        if mode == 'design' and RAG_AVAILABLE:
            rag_context = self._get_rag_context(input_data, project_id=project_id)

        # Build prompt based on mode
        prompt, deliverable_type, artifact_prefix = self._build_prompt(mode, input_data, rag_context)

        system_prompt = f"You are Marcus, a Salesforce CTA. Generate {deliverable_type}. Output ONLY valid JSON."

        logger.info(f"Mode: {mode}, prompt size: {len(prompt)} characters")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, system_prompt, max_tokens=16000, temperature=0.4,
            execution_id=execution_id
        )

        execution_time = time.time() - start_time
        logger.info(f"Generated {len(content)} chars in {execution_time:.1f}s, tokens={tokens_used}")

        # Log LLM interaction
        self._log_interaction(
            mode=mode,
            prompt=prompt,
            content=content,
            execution_id=execution_id,
            input_tokens=input_tokens,
            tokens_used=tokens_used,
            model_used=model_used,
            provider_used=provider_used,
            execution_time=execution_time,
            rag_context=rag_context,
        )

        # Parse JSON output
        parsed_content = _parse_json_content(content)

        return {
            "success": True,
            "agent_id": "architect",
            "agent_name": "Marcus (Solution Architect)",
            "mode": mode,
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": deliverable_type,
            "artifact_id": f"{artifact_prefix}-001",
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "rag_used": bool(rag_context),
                "generated_at": datetime.now().isoformat()
            }
        }

    def _build_prompt(self, mode: str, input_data: dict, rag_context: str) -> tuple:
        """Build the prompt based on mode. Returns (prompt, deliverable_type, artifact_prefix)."""
        if mode == 'design':
            use_cases = input_data.get('use_cases', [])
            project_summary = input_data.get('project_summary', '')
            uc_digest = input_data.get('uc_digest', None)
            coverage_gaps = input_data.get('coverage_gaps', None)
            uncovered_use_cases = input_data.get('uncovered_use_cases', None)
            revision_request = input_data.get('revision_request', None)

            if revision_request:
                logger.info(f"REVISION MODE: Addressing {len(coverage_gaps or [])} coverage gaps")
            elif uc_digest:
                logger.info("Using UC Digest from Emma (structured analysis)")
            else:
                logger.info(f"No UC Digest, using raw UCs ({len(use_cases)} UCs)")

            prompt = get_design_prompt(
                use_cases, project_summary, rag_context, uc_digest,
                coverage_gaps=coverage_gaps,
                uncovered_use_cases=uncovered_use_cases,
                revision_request=revision_request
            )
            return prompt, "solution_design", "ARCH"

        elif mode == 'as_is':
            sfdx_metadata = input_data.get('sfdx_metadata', json.dumps(input_data))
            prompt = get_as_is_prompt(sfdx_metadata)
            return prompt, "as_is_analysis", "ASIS"

        elif mode == 'gap':
            solution_design_data = input_data.get('solution_design', input_data.get('architecture', {}))
            solution_design_str = json.dumps(solution_design_data, indent=2)
            asis_summary = json.dumps(input_data.get('as_is', {}), indent=2)

            uc_context = self._build_uc_context(input_data)
            prompt = get_gap_prompt(solution_design_str, asis_summary, uc_context)
            return prompt, "gap_analysis", "GAP"

        elif mode == 'wbs':
            gap_analysis = json.dumps(input_data.get('gaps', input_data), indent=2)
            constraints = input_data.get('constraints', '')
            prompt = get_wbs_prompt(gap_analysis, constraints)
            return prompt, "work_breakdown_structure", "WBS"

        elif mode == 'fix_gaps':
            current_solution = input_data.get('current_solution', input_data.get('solution_design', {}))
            coverage_gaps = input_data.get('coverage_gaps', [])
            uncovered_use_cases = input_data.get('uncovered_use_cases', [])
            iteration = input_data.get('iteration', 1)
            prompt = get_fix_gaps_prompt(current_solution, coverage_gaps, uncovered_use_cases, iteration)
            return prompt, f"solution_design_v{iteration + 1}", "ARCH"

        raise ValueError(f"Unknown mode: {mode}")

    def _build_uc_context(self, input_data: dict) -> str:
        """Build enriched UC context for gap mode."""
        uc_digest = input_data.get('uc_digest', None)
        if uc_digest and uc_digest.get('by_requirement'):
            logger.info("Using ENRICHED UC Digest for gap context")
            uc_lines = []
            for br_id, br_data in uc_digest.get('by_requirement', {}).items():
                title = br_data.get('title', br_id)
                uc_count = br_data.get('uc_count', 0)
                objects = br_data.get('sf_objects', [])
                ui_components = br_data.get('ui_components', [])
                automations = br_data.get('automations', [])
                auto_details = []
                for a in automations:
                    a_type = a.get('type', '') if isinstance(a, dict) else str(a)
                    a_purpose = a.get('purpose', '')[:80] if isinstance(a, dict) else ''
                    if a_purpose:
                        auto_details.append(f"{a_type}: {a_purpose}")
                    else:
                        auto_details.append(a_type)
                criteria = br_data.get('key_acceptance_criteria', [])
                line = f"\n### {br_id}: {title} ({uc_count} UCs)"
                line += f"\n- **Objects**: {', '.join(objects)}"
                if ui_components:
                    line += f"\n- **UI Components**: {', '.join(ui_components)}"
                if auto_details:
                    line += f"\n- **Automations**:"
                    for ad in auto_details[:4]:
                        line += f"\n  - {ad}"
                if criteria:
                    line += f"\n- **Key Criteria**: {criteria[0][:100]}..."
                uc_lines.append(line)
            logger.info(f"Generated {len(uc_lines)} BR contexts with UI details")
            return "\n".join(uc_lines)
        else:
            # Fallback: Use raw UCs
            use_cases = input_data.get('use_cases', [])
            if use_cases:
                logger.info(f"Using raw UCs for gap context ({len(use_cases)} UCs)")
                uc_lines = []
                for uc in use_cases[:10]:
                    sf = uc.get('salesforce_components', {})
                    objects = sf.get('objects', [])
                    uc_lines.append(f"- {uc.get('id', 'UC')}: {uc.get('title', '')[:50]} (Objects: {', '.join(objects[:3])})")
                return "\n".join(uc_lines)
            return ""

    # ------------------------------------------------------------------
    # LLM / RAG / Logger helpers
    # ------------------------------------------------------------------
    def _call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 16000,
        temperature: float = 0.4,
        execution_id: int = 0,
    ) -> tuple:
        """
        Call LLM service with fallback to direct Anthropic API.

        Returns:
            (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            logger.info("Calling Claude API (Architect tier)...")
            response = generate_llm_response(
                prompt=prompt,
                agent_type="architect",
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                execution_id=execution_id
            )
            content = response["content"]
            tokens_used = response["tokens_used"]
            input_tokens = response.get("input_tokens", 0)
            model_used = response["model"]
            provider_used = response["provider"]
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

    def _get_rag_context(self, input_data: dict, project_id: int = 0) -> str:
        """Fetch RAG context for design mode with dynamic query based on project objects."""
        if not RAG_AVAILABLE:
            return ""
        try:
            use_cases_text = json.dumps(input_data.get('use_cases', []))
            project_summary = input_data.get('project_summary', '')
            combined_text = f"{use_cases_text} {project_summary}".lower()

            standard_objects = [
                'case', 'contact', 'account', 'lead', 'opportunity', 'campaign',
                'task', 'event', 'user', 'product', 'pricebook', 'quote', 'order',
                'contract', 'asset', 'entitlement', 'knowledge', 'solution'
            ]
            detected_objects = [obj for obj in standard_objects if obj in combined_text]

            if detected_objects:
                objects_str = ' '.join([obj.capitalize() for obj in detected_objects[:5]])
                query = f"Salesforce {objects_str} object standard fields relationships best practices"
                logger.info(f"RAG query (detected objects: {detected_objects[:5]}): {query}")
            else:
                query = "Salesforce architecture design patterns data model best practices"
                logger.info(f"RAG query (generic): {query}")

            rag_context = get_salesforce_context(query, n_results=8, agent_type="solution_architect", project_id=project_id or None)
            logger.info(f"RAG context: {len(rag_context)} chars")
            return rag_context
        except Exception as e:
            logger.warning(f"RAG error: {e}")
            return ""

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
        rag_context: str = "",
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="marcus",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=None,
                agent_mode=mode,
                rag_context=rag_context if rag_context else None,
                previous_feedback=None,
                parsed_files=None,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider=provider_used,
                execution_time_seconds=execution_time,
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

    parser = argparse.ArgumentParser(description='Marcus Architect Agent')
    parser.add_argument('--mode', required=False, default='design',
                        choices=['design', 'as_is', 'gap', 'wbs', 'fix_gaps'],
                        help='Operation mode: design, as_is, gap, wbs, or fix_gaps')
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
        agent = SolutionArchitectAgent()
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
