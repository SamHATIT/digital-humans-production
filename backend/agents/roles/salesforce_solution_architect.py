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

# Prompt Service — MANDATORY, no fallback
from prompts.prompt_service import PromptService
PROMPT_SERVICE = PromptService()


# ============================================================================
# PROMPT 1: SOLUTION DESIGN (UC -> Architecture)
# ============================================================================
def get_design_prompt(use_cases: list, project_summary: str, rag_context: str = "", uc_digest: dict = None, coverage_gaps: list = None, uncovered_use_cases: list = None, revision_request: str = None, previous_design: dict = None, design_focus: str = None, data_model_context: dict = None) -> str:
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
                category = gap.get('category', 'Gap')
                description = gap.get('description', str(gap))
                fix_instruction = gap.get('fix_instruction', '')
                severity = gap.get('severity', '')
                uc_refs = gap.get('uc_refs', [])

                revision_context += f"{i}. **[{severity.upper()}] {category}**: {description}\n"
                if uc_refs:
                    revision_context += f"   - UCs affected: {', '.join(str(r) for r in uc_refs)}\n"
                if fix_instruction:
                    revision_context += f"   - **FIX**: {fix_instruction}\n"
                revision_context += "\n"
            else:
                revision_context += f"{i}. {gap}\n"

        if uncovered_use_cases:
            revision_context += f"\n### Uncovered Use Cases ({len(uncovered_use_cases)})\n"
            for uc in uncovered_use_cases[:5]:
                if isinstance(uc, dict):
                    uc_id = uc.get('id', 'UC')
                    uc_title = uc.get('title', str(uc))
                    uc_reason = uc.get('reason', '')
                    uc_fix = uc.get('fix_instruction', '')
                    revision_context += f"- **{uc_id}**: {uc_title}\n"
                    if uc_reason:
                        revision_context += f"  Reason: {uc_reason}\n"
                    if uc_fix:
                        revision_context += f"  **FIX**: {uc_fix}\n"
                else:
                    revision_context += f"- {uc}\n"
            if len(uncovered_use_cases) > 5:
                revision_context += f"- ... and {len(uncovered_use_cases) - 5} more\n"

        revision_context += "\n**CRITICAL**: For each gap above with a FIX instruction, apply it EXACTLY as specified. Add the described component to the correct section of your JSON.\n\n"

        # ARCH-001: Inject previous design so Marcus revises instead of regenerating
        if previous_design:
            import json
            prev_json = json.dumps(previous_design, indent=2, ensure_ascii=False)
            # Truncate if very large (keep first 40K chars ~ 10K tokens)
            if len(prev_json) > 40000:
                prev_json = prev_json[:40000] + "\n... [truncated]"
            revision_context += f"""## YOUR PREVIOUS DESIGN (REVISE, do NOT regenerate from scratch)

```json
{prev_json}
```

CRITICAL: The JSON above is your previous output. UPDATE it by adding/fixing the elements listed in Coverage Gaps.
Do NOT discard existing content — KEEP everything that was correct and ADD what is missing.

"""

    # TRUNC-001: Design focus — split large designs into 2 calls
    focus_instruction = ""
    if design_focus == "core":
        focus_instruction = """
## DESIGN FOCUS: CORE ARCHITECTURE ONLY

Generate ONLY the following sections with full detail:
- data_model (standard_objects, custom_objects, relationships, erd_mermaid)
- security_model (profiles, permission_sets, sharing_rules, owd)
- queues
- reporting (reports, dashboards)

Set these sections to EMPTY objects/arrays (they will be generated in a second pass):
- automation_design: {}
- integration_points: []
- ui_components: {}
- uc_traceability: {}
- technical_considerations: []
- risks: []

This lets you use your FULL token budget for data model and security detail.

"""
    elif design_focus == "technical":
        import json as _json
        dm_json = _json.dumps(data_model_context, indent=2, ensure_ascii=False)[:30000] if data_model_context else "{}"
        focus_instruction = f"""
## DESIGN FOCUS: TECHNICAL ARCHITECTURE ONLY

The DATA MODEL and SECURITY MODEL are already designed (see below). Reference them for consistency.

### EXISTING DATA MODEL (DO NOT REGENERATE)
```json
{dm_json}
```

Generate ONLY the following sections with full detail:
- automation_design (flows with elements array, apex_triggers, scheduled_jobs, platform_events)
- integration_points (with auth, endpoint_spec, error_handling)
- ui_components (lightning_apps, lightning_pages, lwc_components with api_properties/wire_adapters, quick_actions)
- uc_traceability (map EVERY UC to implementing components)
- technical_considerations
- risks

Set these sections to EMPTY (they are already generated):
- data_model: {{}}
- security_model: {{}}
- queues: []
- reporting: {{}}

"""
    if focus_instruction:
        revision_context = focus_instruction + revision_context

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

    # Try external prompt first
    return PROMPT_SERVICE.render("marcus_architect", "design", {
        "revision_context": revision_context,
        "project_summary": project_summary,
        "uc_text": uc_text,
        "rag_section": rag_section,
    })


# ============================================================================
# PROMPT 2: AS-IS ANALYSIS (SFDX -> Summary)
# ============================================================================
def get_as_is_prompt(sfdx_metadata: str) -> str:
    sfdx_metadata_truncated = sfdx_metadata[:15000] if len(sfdx_metadata) > 15000 else sfdx_metadata

    # Try external prompt first
    return PROMPT_SERVICE.render("marcus_architect", "as_is", {
        "sfdx_metadata": sfdx_metadata_truncated,
    })


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

    return PROMPT_SERVICE.render("marcus_architect", "gap", {
        "design_section": design_section,
        "uc_section": uc_section,
        "asis_summary": asis_summary,
    })


# ============================================================================
# PROMPT 4: WBS (GAP -> Tasks + Planning)
# ============================================================================
def get_wbs_prompt(gap_analysis: str, project_constraints: str = "", architecture_context: str = "") -> str:
    return PROMPT_SERVICE.render("marcus_architect", "wbs", {
        "gap_analysis": gap_analysis,
        "project_constraints": project_constraints if project_constraints else "Standard Salesforce implementation timeline",
        "architecture_context": architecture_context if architecture_context else "No architecture provided — use gap descriptions for implementation details.",
    })


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

    return PROMPT_SERVICE.render("marcus_architect", "fix_gaps", {
        "iteration": str(iteration),
        "solution_json": solution_json[:15000],
        "gap_count": str(len(coverage_gaps)),
        "gaps_text": gaps_text,
        "uncovered_text": uncovered_text if uncovered_text else "None specified",
        "next_iteration": str(iteration + 1),
    })


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
# MODE: PATCH — Apply targeted fixes to one architecture section
# ============================================================================
def get_patch_prompt(section_key: str, current_section: dict, fix_instructions: list) -> str:
    """Build patch prompt for a single architecture section. YAML only, no fallback."""
    current_json = json.dumps(current_section, indent=2, ensure_ascii=False)

    # Format fix instructions
    fix_text = ""
    for i, gap in enumerate(fix_instructions, 1):
        fix_text += f"\n### Fix {i}: {gap.get('what_is_missing', 'Gap')}\n"
        fi = gap.get('fix_instruction', {})
        if isinstance(fi, dict):
            action = fi.get('action', 'ADD')
            fi_content = fi.get('content', {})
            fix_text += f"- **Action**: {action}\n"
            fix_text += f"- **Content to add**:\n```json\n{json.dumps(fi_content, indent=2, ensure_ascii=False)}\n```\n"
            uc_refs = fi.get('uc_refs', [])
            if uc_refs:
                fix_text += f"- **Required by**: {', '.join(uc_refs)}\n"
        else:
            fix_text += f"- {fi}\n"

    return PROMPT_SERVICE.render("marcus_architect", "patch", {
        "section_key": section_key,
        "current_section_json": current_json,
        "fix_instructions_text": fix_text,
    })


# ============================================================================
# SOLUTION ARCHITECT AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class SolutionArchitectAgent:
    """
    Marcus (Solution Architect) Agent - 6 modes (design, as_is, gap, wbs, fix_gaps, patch).

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

    VALID_MODES = ("design", "as_is", "gap", "wbs", "fix_gaps", "patch")

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
        # V4: design/wbs/fix_gaps need more tokens for enriched output
        max_out = 64000 if mode in ('design', 'wbs', 'fix_gaps', 'gap') else 16000
        content, tokens_used, input_tokens, model_used, provider_used, cost_usd = self._call_llm(
            prompt, system_prompt, max_tokens=max_out, temperature=0.4,
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
                "cost_usd": cost_usd,
                "input_tokens": input_tokens,
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

            previous_design = input_data.get('previous_design', None)
            design_focus = input_data.get('design_focus', None)
            data_model_context = input_data.get('data_model_context', None)
            prompt = get_design_prompt(
                use_cases, project_summary, rag_context, uc_digest,
                coverage_gaps=coverage_gaps,
                uncovered_use_cases=uncovered_use_cases,
                revision_request=revision_request,
                previous_design=previous_design,
                design_focus=design_focus,
                data_model_context=data_model_context
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
            # PROMPTS-005: Pass architecture to WBS so implementation_specs can reference real components
            architecture = input_data.get('architecture', {})
            architecture_str = json.dumps(architecture, indent=2) if architecture else ""
            prompt = get_wbs_prompt(gap_analysis, constraints, architecture_context=architecture_str)
            return prompt, "work_breakdown_structure", "WBS"

        elif mode == 'fix_gaps':
            current_solution = input_data.get('current_solution', input_data.get('solution_design', {}))
            coverage_gaps = input_data.get('coverage_gaps', [])
            uncovered_use_cases = input_data.get('uncovered_use_cases', [])
            iteration = input_data.get('iteration', 1)
            prompt = get_fix_gaps_prompt(current_solution, coverage_gaps, uncovered_use_cases, iteration)
            return prompt, f"solution_design_v{iteration + 1}", "ARCH"

        elif mode == 'patch':
            section_key = input_data.get('section_key', 'unknown')
            current_section = input_data.get('current_section', {})
            fix_instructions = input_data.get('fix_instructions', [])
            prompt = get_patch_prompt(section_key, current_section, fix_instructions)
            return prompt, f"solution_design_patch_{section_key}", "ARCH"

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
            cost_usd = response.get("cost_usd", 0.0)
            logger.info(f"Using {provider_used} / {model_used} (cost: ${cost_usd:.4f})")
            return content, tokens_used, input_tokens, model_used, provider_used, cost_usd

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
        return content, tokens_used, input_tokens, "claude-sonnet-4-20250514", "anthropic", 0.0

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
