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

# Prompt Service — MANDATORY, no fallback
from prompts.prompt_service import PromptService
PROMPT_SERVICE = PromptService()


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
# Prompt loaded from YAML: emma_research.yaml -> uc_digest


# ============================================================================
# MODE 2: VALIDATE (Phase 3.3) - Coverage Analysis
# ============================================================================

# Prompt loaded from YAML: emma_research.yaml -> coverage_review (now fix_instructions)


# ============================================================================
# MODE 3: WRITE_SDS (Phase 5) - Final SDS Document Assembly
# ============================================================================

# Prompt loaded from YAML: emma_research.yaml -> write_sds


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
        self._total_cost = 0.0

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

        # Build UC text for prompt — reads Olivia's actual output format
        uc_text = ""
        for i, uc in enumerate(use_cases):
            uc_id = uc.get('id', f'UC-{i+1:03d}')
            uc_title = uc.get('title', 'Untitled')
            uc_actor = uc.get('actor', 'User')
            parent_br = uc.get('parent_br', uc.get('br_ref', uc.get('requirement_id', '')))

            uc_text += f"\n### {uc_id}: {uc_title}\n"
            uc_text += f"- **Actor**: {uc_actor}\n"
            if parent_br:
                uc_text += f"- **Business Requirement**: {parent_br}\n"

            # Trigger
            trigger = uc.get('trigger', '')
            if trigger:
                uc_text += f"- **Trigger**: {trigger}\n"

            # SF Objects (Olivia format: flat list)
            sf_objects = uc.get('sf_objects', [])
            if sf_objects:
                uc_text += f"- **SF Objects**: {', '.join(sf_objects)}\n"

            # SF Fields (Olivia format: ["Object.Field", ...])
            sf_fields = uc.get('sf_fields', [])
            if sf_fields:
                uc_text += f"- **SF Fields**: {', '.join(sf_fields[:10])}\n"

            # SF Automation (Olivia format: string, not list)
            sf_auto = uc.get('sf_automation', '')
            if sf_auto and str(sf_auto).lower() not in ('none', 'n/a', ''):
                uc_text += f"- **Automation**: {sf_auto}\n"

            # Main flow (summary)
            main_flow = uc.get('main_flow', [])
            if main_flow:
                uc_text += f"- **Main Flow**: {' → '.join(str(s)[:60] for s in main_flow[:4])}\n"

            # Acceptance criteria (max 3)
            criteria = uc.get('acceptance_criteria', [])
            if criteria:
                uc_text += "- **Acceptance Criteria**:\n"
                for c in criteria[:3]:
                    c_text = c.get('description', str(c)) if isinstance(c, dict) else str(c)
                    uc_text += f"  - {c_text[:150]}\n"

        timestamp = datetime.now().isoformat()

        # Render prompt from YAML — no fallback
        prompt = PROMPT_SERVICE.render("emma_research", "uc_digest", {
            "use_cases_text": uc_text,
            "timestamp": timestamp,
            "uc_count": str(len(use_cases)),
        })

        system_prompt = "You are Emma, a Research Analyst. Generate a UC Digest. Output ONLY valid JSON."

        logger.info(f"ANALYZE mode: {len(use_cases)} UCs, prompt size: {len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, system_prompt, max_tokens=32000, temperature=0.3,
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
                "cost_usd": getattr(self, '_total_cost', 0.0),
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
        """
        Validate Solution Design coverage against Use Cases.
        
        OPTION C Architecture:
        - Score = 100% programmatic (deterministic, no LLM)
        - If score < 95%: LLM generates fix_instructions for Marcus (no LLM scoring)
        """
        start_time = time.time()

        solution_design = input_data.get('solution_design', input_data.get('architecture', {}))
        use_cases = input_data.get('use_cases', [])

        if not solution_design:
            return {"success": False, "error": "No solution_design provided for validate mode"}

        # ── STEP 1: 100% programmatic score (SOLE decision maker) ──
        prog_report = generate_coverage_report_programmatic(solution_design, use_cases)
        score = prog_report.get('overall_score', 0)
        verdict = prog_report.get('verdict', 'UNKNOWN')

        logger.info(f"[Coverage] Programmatic score: {score}% — {verdict}")

        # ── STEP 2: If < 95%, call LLM for fix_instructions only ──
        llm_gaps = []
        llm_tokens = 0
        llm_model = None
        llm_provider = None
        llm_called = False

        if score < 95:
            llm_called = True
            llm_input = self._build_fix_instructions_input(prog_report, solution_design, use_cases)

            prompt = PROMPT_SERVICE.render("emma_research", "fix_instructions", llm_input)
            system_prompt = (
                "You are Emma, a Research Analyst. Generate actionable fix instructions "
                "for each gap. Output ONLY valid JSON."
            )

            logger.info(f"[Coverage] Score {score}% < 95% — calling LLM for fix_instructions")

            content, llm_tokens, input_tokens, llm_model, llm_provider = self._call_llm(
                prompt, system_prompt, max_tokens=32000, temperature=0.3,
                execution_id=execution_id
            )

            self._log_interaction(
                mode="fix_instructions", prompt=prompt, content=content,
                execution_id=execution_id, input_tokens=input_tokens,
                tokens_used=llm_tokens, model_used=llm_model,
                provider_used=llm_provider, execution_time=time.time() - start_time,
            )

            llm_result = parse_json_response(content)
            llm_gaps = llm_result.get('gaps', [])
            logger.info(f"[Coverage] LLM produced {len(llm_gaps)} fix_instructions")

        # ── STEP 3: Build uncovered UCs list ──
        covered_uc_ids = set(solution_design.get('uc_traceability', {}).keys())
        uncovered_ucs = []
        for uc in use_cases:
            uc_id = uc.get('id', '')
            # Check both traceability and object overlap
            sf_objs = set(o.lower() for o in uc.get('sf_objects', []))
            sd_objs = set()
            dm = solution_design.get('data_model', {})
            for o in dm.get('standard_objects', []):
                sd_objs.add((o.get('api_name', '') if isinstance(o, dict) else str(o)).lower())
            for o in dm.get('custom_objects', []):
                sd_objs.add((o.get('api_name', '') if isinstance(o, dict) else str(o)).lower())
            obj_covered = bool(sf_objs & sd_objs)
            trace_covered = uc_id in covered_uc_ids

            if not (obj_covered or trace_covered):
                uncovered_ucs.append({
                    "id": uc_id,
                    "title": uc.get('title', ''),
                    "parent_br": uc.get('parent_br', ''),
                })

        # ── STEP 4: Assemble final report ──
        execution_time = time.time() - start_time
        timestamp = datetime.now().isoformat()

        # Use LLM gaps if available, otherwise programmatic gaps
        final_gaps = llm_gaps if llm_gaps else prog_report.get('critical_gaps', [])

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
                "overall_coverage_score": score,       # 100% programmatic
                "verdict": verdict,                     # 100% programmatic
                "scoring_method": "programmatic_only",  # Traceability
                "by_category": prog_report.get('by_category', {}),
                "critical_gaps": final_gaps,
                "uncovered_use_cases": uncovered_ucs,
            },
            "metadata": {
                "tokens_used": llm_tokens,
                "cost_usd": getattr(self, '_total_cost', 0.0),
                "model": llm_model,
                "provider": llm_provider,
                "execution_time_seconds": round(execution_time, 2),
                "use_cases_count": len(use_cases),
                "llm_called": llm_called,
                "generated_at": timestamp
            }
        }

    def _build_fix_instructions_input(self, prog_report: dict, solution_design: dict, use_cases: list) -> dict:
        """Build targeted input for LLM fix_instructions prompt."""
        by_cat = prog_report.get('by_category', {})

        missing_objects = by_cat.get('data_model', {}).get('missing', [])
        missing_autos = by_cat.get('automation', {}).get('missing', [])
        missing_ui = by_cat.get('ui_components', {}).get('missing', [])

        # Identify uncovered UCs
        covered_uc_ids = set(solution_design.get('uc_traceability', {}).keys())
        uncovered_ucs = []
        for uc in use_cases:
            uc_id = uc.get('id', '')
            if uc_id and uc_id not in covered_uc_ids:
                uncovered_ucs.append({
                    "id": uc_id,
                    "title": uc.get('title', ''),
                    "parent_br": uc.get('parent_br', ''),
                    "sf_objects": uc.get('sf_objects', []),
                    "sf_automation": uc.get('sf_automation', ''),
                    "main_flow_summary": ' → '.join(
                        str(s)[:40] for s in uc.get('main_flow', [])[:3]
                    )
                })

        # Existing architecture elements for context
        arch_context = {}
        dm = solution_design.get('data_model', {})
        existing_std = [o.get('api_name', str(o)) for o in dm.get('standard_objects', []) if isinstance(o, dict)]
        existing_cust = [o.get('api_name', str(o)) for o in dm.get('custom_objects', []) if isinstance(o, dict)]
        arch_context['existing_objects'] = existing_std + existing_cust

        auto = solution_design.get('automation_design', {})
        existing_flows = [f.get('api_name', f.get('name', '')) for f in auto.get('flows', []) if isinstance(f, dict)]
        existing_triggers = [t.get('name', '') for t in auto.get('apex_triggers', []) if isinstance(t, dict)]
        arch_context['existing_automations'] = existing_flows + existing_triggers

        # Format texts for prompt template
        missing_objects_text = '\n'.join(f"- {obj}" for obj in missing_objects) if missing_objects else "None"
        missing_autos_text = '\n'.join(f"- {a}" for a in missing_autos) if missing_autos else "None"
        missing_ui_text = '\n'.join(f"- {u}" for u in missing_ui) if missing_ui else "None"

        uncovered_text = ""
        for uc in uncovered_ucs[:15]:
            uncovered_text += f"- **{uc['id']}**: {uc['title']} (BR: {uc['parent_br']})"
            uncovered_text += f"\n  Objects: {', '.join(uc['sf_objects'][:5])}"
            uncovered_text += f"\n  Automation: {uc['sf_automation']}"
            uncovered_text += f"\n  Flow: {uc['main_flow_summary']}\n"
        if not uncovered_text:
            uncovered_text = "None"

        return {
            "score": str(prog_report.get('overall_score', 0)),
            "verdict": prog_report.get('verdict', 'UNKNOWN'),
            "missing_objects_text": missing_objects_text,
            "missing_object_count": str(len(missing_objects)),
            "missing_automations_text": missing_autos_text,
            "missing_automation_count": str(len(missing_autos)),
            "missing_ui_text": missing_ui_text,
            "missing_ui_count": str(len(missing_ui)),
            "uncovered_ucs_text": uncovered_text,
            "uncovered_count": str(len(uncovered_ucs)),
            "arch_context": json.dumps(arch_context, ensure_ascii=False),
            "timestamp": datetime.now().isoformat(),
        }


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

        # Extract deliverables — generous limits to preserve expert content
        # Sonnet 4.5 context = 200K tokens (~800K chars), so total ~200K chars is safe
        def safe_content(key: str, max_len: int = 30000) -> str:
            val = input_data.get(key, '')
            if isinstance(val, dict):
                val = json.dumps(val, indent=2, ensure_ascii=False)
            elif isinstance(val, list):
                val = json.dumps(val, indent=2, ensure_ascii=False)
            return str(val)[:max_len] if val else "Not provided"

        # Render prompt from YAML — no fallback
        prompt = PROMPT_SERVICE.render("emma_research", "write_sds", {
            "project_name": project_name,
            "timestamp": timestamp,
            "br_content": safe_content('business_requirements', 20000),
            "uc_content": safe_content('use_cases', 15000),
            "uc_digest_content": safe_content('uc_digest', 15000),
            "solution_design_content": safe_content('solution_design', 60000),
            "gap_analysis_content": safe_content('gap_analysis', 20000),
            "wbs_content": safe_content('wbs', 30000),
            "qa_content": safe_content('qa_plan', 15000),
            "devops_content": safe_content('devops_plan', 10000),
            "training_content": safe_content('training_plan', 10000),
            "data_migration_content": safe_content('data_migration_plan', 10000),
        })

        system_prompt = "You are Emma, a Research Analyst. Write the complete SDS document. Output ONLY Markdown."

        logger.info(f"WRITE_SDS mode: prompt size: {len(prompt)} chars")

        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, system_prompt, max_tokens=32000, temperature=0.4,
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
                "cost_usd": getattr(self, '_total_cost', 0.0),
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
            self._total_cost += response.get("cost_usd", 0.0)
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
            model=os.environ.get("ANTHROPIC_FALLBACK_MODEL", "claude-sonnet-4-5-20250929"),
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        input_tokens = response.usage.input_tokens
        fallback_model = os.environ.get("ANTHROPIC_FALLBACK_MODEL", "claude-sonnet-4-5-20250929")
        return content, tokens_used, input_tokens, fallback_model, "anthropic"

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
