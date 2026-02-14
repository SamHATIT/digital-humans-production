#!/usr/bin/env python3
"""
Salesforce Business Analyst (Olivia) Agent - Refactored Version
Generates Use Cases (UC) from a single Business Requirement (BR)
Uses RAG for Salesforce best practices enrichment

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (BusinessAnalystAgent.run()) or CLI.
"""

import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# LLM imports - clean imports for direct import mode
try:
    from app.services.llm_service import generate_llm_response, LLMProvider
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

# LLM Logger for debugging (INFRA-002)
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
except ImportError:
    LLM_LOGGER_AVAILABLE = False
    def log_llm_interaction(*args, **kwargs): pass

# JSON Cleaner for robust parsing (F-081)
try:
    from app.utils.json_cleaner import clean_llm_json_response
    JSON_CLEANER_AVAILABLE = True
except ImportError:
    JSON_CLEANER_AVAILABLE = False
    def clean_llm_json_response(s): return None, "JSON cleaner not available"

# RAG Service
try:
    from app.services.rag_service import get_salesforce_context
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Prompt Service for externalized prompts
from prompts.prompt_service import PromptService
PROMPT_SERVICE = PromptService()

# ============================================================================
# PROMPT: BR -> USE CASES (~100 lines)
def get_uc_generation_prompt(br: dict, rag_context: str = "") -> str:
    br_id = br.get('id', 'BR-XXX')
    br_title = br.get('title', br.get('requirement', '')[:50])
    br_description = br.get('description', br.get('requirement', ''))
    br_category = br.get('category', 'OTHER')
    br_stakeholder = br.get('stakeholder', br.get('metadata', {}).get('stakeholder', 'Business User'))

    # PRPT-01 metadata if available
    br_metadata = br.get('metadata', br.get('br_metadata', {}))
    br_fields = br_metadata.get('fields', [])
    br_rules = br_metadata.get('validation_rules', [])

    metadata_section = ""
    if br_fields or br_rules:
        metadata_section = f"""
## EXTRACTED DETAILS FROM BR
- **Fields mentioned**: {', '.join(br_fields) if br_fields else 'None specified'}
- **Validation rules**: {', '.join(br_rules) if br_rules else 'None specified'}
"""

    rag_section = ""
    if rag_context:
        # Truncate RAG context to avoid verbosity
        rag_section = f"""
## SALESFORCE CONTEXT (use for field names and patterns)
{rag_context[:1500]}
"""

    # Try external prompt first
    return PROMPT_SERVICE.render("olivia_ba", "generate", {
        "br_id": br_id,
        "br_title": br_title,
        "br_category": br_category,
        "br_stakeholder": br_stakeholder,
        "br_description": br_description,
        "metadata_section": metadata_section,
        "rag_section": rag_section,
        "br_id_suffix": br_id[3:] if len(br_id) > 3 else "XXX",
    })

    # FALLBACK: original f-string prompt
    return f'''# USE CASE GENERATION - COMPACT FORMAT

You are **Olivia**, Senior Salesforce Business Analyst.

## MISSION
Generate 3-5 **concise** Use Cases for this BR. Each UC must be:
- **Atomic**: One user goal per UC
- **Testable**: Clear pass/fail criteria
- **Compact**: No filler text, only essential info

## INPUT BR

**{br_id}: {br_title}**
- Category: {br_category}
- Stakeholder: {br_stakeholder}
- Description: {br_description}
{metadata_section}
{rag_section}

## OUTPUT FORMAT (JSON - STRICT)

```json
{{
  "parent_br": "{br_id}",
  "use_cases": [
    {{
      "id": "UC-{br_id[3:]}-01",
      "title": "Action-oriented title (max 8 words)",
      "actor": "Role (e.g., Sales Rep, System Admin)",
      "trigger": "What starts this UC (e.g., User clicks button)",
      "main_flow": [
        "1. User does X",
        "2. System validates Y",
        "3. System saves Z"
      ],
      "alt_flows": [
        "1a. If validation fails: show error"
      ],
      "acceptance_criteria": [
        "GIVEN [context] WHEN [action] THEN [result]"
      ],
      "sf_objects": ["Account", "Custom_Object__c"],
      "sf_fields": ["Account.Name", "Custom_Object__c.Status__c"],
      "sf_automation": "Record-Triggered Flow / Apex Trigger / None"
    }}
  ]
}}
```

## RULES (CRITICAL)

1. **3-5 UCs only** - More is waste, less is incomplete
2. **Max 6 steps** in main_flow - If more needed, split into separate UC
3. **Max 3 alt_flows** - Focus on critical paths only
4. **Max 4 acceptance criteria** - Use GIVEN/WHEN/THEN format
5. **Specific Salesforce objects** - No generic "data object", use real SF names
6. **Real field names** - Use API names (MyField__c), not labels
7. **One automation type** per UC - Flow OR Trigger, not both
8. **No redundancy** - If UC-01 covers "create record", UC-02 should NOT repeat it

## ANTI-PATTERNS TO AVOID

- "User performs action" -> "User clicks Save button"
- "System processes data" -> "System runs validation rule"
- "Record is updated" -> "Account.Status__c = 'Qualified'"
- Long paragraphs -> Short numbered steps
- 10+ acceptance criteria -> 3-4 key testable criteria

---

**Generate Use Cases for {br_id}. Output ONLY valid JSON, no markdown fences or explanations.**
'''



# F-081: Batch mode prompt for processing 2 BRs at once
def get_uc_generation_prompt_batch(brs: list, rag_context: str = "") -> str:
    """Generate UC prompt for 1 or 2 BRs at once (F-081 optimization)"""
    br_sections = []
    br_ids = []

    for br in brs:
        br_id = br.get('id', 'BR-XXX')
        br_ids.append(br_id)
        br_title = br.get('title', br.get('requirement', '')[:50])
        br_description = br.get('description', br.get('requirement', ''))
        br_category = br.get('category', 'OTHER')
        br_stakeholder = br.get('stakeholder', br.get('metadata', {}).get('stakeholder', 'Business User'))

        br_metadata = br.get('metadata', br.get('br_metadata', {}))
        br_fields = br_metadata.get('fields', [])

        fields_text = f"Fields: {', '.join(br_fields)}" if br_fields else ""

        br_sections.append(f"""### {br_id}: {br_title}
- Category: {br_category} | Stakeholder: {br_stakeholder}
- {br_description[:500]}
{fields_text}""")

    brs_text = "\n\n".join(br_sections)
    br_count = len(brs)

    rag_section = f"\n## SALESFORCE CONTEXT\n{rag_context[:1200]}\n" if rag_context else ""

    # Try external prompt first
    return PROMPT_SERVICE.render("olivia_ba", "generate_batch", {
        "br_count": str(br_count),
        "brs_text": brs_text,
        "rag_section": rag_section,
    })

    # FALLBACK: original f-string prompt
    return f"""# USE CASE GENERATION - {br_count} BR{"s" if br_count > 1 else ""}

You are **Olivia**, Senior Salesforce Business Analyst.

## INPUT BRs

{brs_text}
{rag_section}

## OUTPUT FORMAT

Return a JSON object with "results" array. Each result has "parent_br" and "use_cases" array.
Generate 3-5 Use Cases per BR with: id, title, actor, trigger, main_flow (max 6 steps),
alt_flows (max 3), acceptance_criteria (GIVEN/WHEN/THEN), sf_objects, sf_fields, sf_automation.

## RULES
- UC IDs: UC-XXX-01, UC-XXX-02 (XXX = BR number)
- Real Salesforce object/field names with __c suffix
- One automation type per UC (Flow/Apex/None)
- Max 6 main_flow steps, max 4 acceptance criteria

Output ONLY valid JSON, no markdown fences."""


# ============================================================================
# BUSINESS ANALYST AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class BusinessAnalystAgent:
    """
    Olivia (Business Analyst) Agent - Use Case Generation from BRs.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - generate_uc: Generate Use Cases from Business Requirements
          (supports single BR and batch BR input via F-081)

    Usage (import):
        agent = BusinessAnalystAgent()
        result = agent.run({"mode": "generate_uc", "input_content": '{"business_requirement": {...}}'})

    Usage (CLI):
        python salesforce_business_analyst.py --input input.json --output output.json
    """

    VALID_MODES = ("generate_uc",)

    SYSTEM_PROMPT = (
        "You are Olivia, a Senior Salesforce Business Analyst. "
        "Generate detailed Use Cases from the Business Requirement. "
        "Output ONLY valid JSON."
    )

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._total_cost = 0.0

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "generate_uc" (default)
                - input_content: JSON string with BR data
                - execution_id: int (optional, default 0)
                - project_id: int (optional, default 0)

        Returns:
            dict with agent output including "success" key.
            On success: full output dict with agent_id, content, metadata, etc.
            On failure: {"success": False, "error": "..."}
        """
        mode = task_data.get("mode", "generate_uc")
        input_content = task_data.get("input_content", "")
        execution_id = task_data.get("execution_id", 0)
        project_id = task_data.get("project_id", 0)

        if mode not in self.VALID_MODES:
            return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

        if not input_content:
            return {"success": False, "error": "No input_content provided"}

        try:
            return self._execute(mode, input_content, execution_id, project_id)
        except Exception as e:
            logger.error(f"BusinessAnalystAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _execute(
        self,
        mode: str,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Core execution logic for UC generation."""
        start_time = time.time()

        # Parse input content
        input_data = self._parse_input(input_content)

        # Extract BR(s) from input
        brs = self._extract_brs(input_data)
        batch_mode = len(brs) > 1
        br_ids = [br.get('id', 'BR-XXX') for br in brs]
        br = brs[0]
        br_id = br_ids[0]

        logger.info(f"BusinessAnalystAgent processing {len(brs)} BR(s): {', '.join(br_ids)}")

        # Get RAG context
        rag_context = self._get_rag_context(br, project_id=project_id)

        # Build prompt (single or batch)
        if batch_mode:
            prompt = get_uc_generation_prompt_batch(brs, rag_context)
        logger.info(f"BusinessAnalystAgent prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, self.SYSTEM_PROMPT, execution_id=execution_id
        )

        execution_time = time.time() - start_time
        logger.info(
            f"BusinessAnalystAgent generated {len(content)} chars in {execution_time:.1f}s, "
            f"tokens={tokens_used}, model={model_used}"
        )

        # Log LLM interaction (INFRA-002)
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
        )

        # Parse JSON response (with json_cleaner and batch support)
        parsed_content, uc_count = self._parse_response(content, br_id, br_ids, batch_mode)

        # Build output
        output_data = {
            "success": True,
            "agent_id": "ba",
            "agent_name": "Olivia (Business Analyst)",
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": "use_case_specification",
            "parent_br": br_id,
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "cost_usd": getattr(self, '_total_cost', 0.0),
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "uc_count": uc_count,
                "rag_used": bool(rag_context),
                "rag_context_length": len(rag_context),
                "generated_at": datetime.now().isoformat(),
            },
        }

        return output_data

    def _parse_input(self, input_content: str) -> Dict:
        """Parse input content string to dict."""
        try:
            return json.loads(input_content) if isinstance(input_content, str) else input_content
        except (json.JSONDecodeError, TypeError):
            # Wrap raw text as a minimal BR for tester compatibility
            return {
                "business_requirement": {
                    "id": "BR-001",
                    "title": "Auto-generated from raw input",
                    "description": input_content if isinstance(input_content, str) else str(input_content),
                    "category": "OTHER",
                    "stakeholder": "Business User",
                }
            }

    def _extract_brs(self, input_data: Dict) -> list:
        """Extract list of BR dicts from input data (single or batch)."""
        if 'business_requirements' in input_data:
            # Batch mode: list of BRs
            return input_data['business_requirements']
        elif 'business_requirement' in input_data:
            return [input_data['business_requirement']]
        elif 'id' in input_data and str(input_data.get('id', '')).startswith('BR-'):
            return [input_data]
        else:
            raise ValueError("Input must contain business_requirement(s) with 'id' starting with 'BR-'")

    def _get_rag_context(self, br: Dict, project_id: int = 0) -> str:
        """Fetch RAG context based on BR content."""
        if not RAG_AVAILABLE:
            return ""
        try:
            query = f"Salesforce {br.get('category', '')} {br.get('title', '')} {br.get('description', '')}"
            logger.debug(f"Querying RAG: {query[:80]}...")
            rag_context = get_salesforce_context(query[:500], n_results=5, agent_type="business_analyst", project_id=project_id or None)
            logger.info(f"RAG context: {len(rag_context)} chars")
            return rag_context
        except Exception as e:
            logger.warning(f"RAG error: {e}")
            return ""

    def _call_llm(self, prompt: str, system_prompt: str, execution_id: int = 0) -> tuple:
        """
        Call LLM via llm_service or direct Anthropic fallback.

        Returns:
            tuple of (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            logger.debug("Calling LLM via llm_service (BA tier)")
            response = generate_llm_response(
                prompt=prompt,
                agent_type="ba",
                system_prompt=system_prompt,
                max_tokens=8000,
                temperature=0.4,
                execution_id=execution_id,
            )
            self._total_cost += response.get("cost_usd", 0.0)
            return (
                response["content"],
                response["tokens_used"],
                response.get("input_tokens", 0),
                response["model"],
                response["provider"],
            )
    def _parse_response(self, content: str, br_id: str, br_ids: list, batch_mode: bool) -> tuple:
        """
        Parse JSON from LLM response with json_cleaner and batch support (F-081).

        Returns:
            tuple of (parsed_content dict, uc_count int)
        """
        try:
            # Use robust json_cleaner if available
            if JSON_CLEANER_AVAILABLE:
                parsed_content, parse_error = clean_llm_json_response(content)
                if parsed_content is None:
                    raise json.JSONDecodeError(parse_error or "Parse error", content, 0)
            # F-081: Handle batch response format {"results": [...]}
            if 'results' in parsed_content and isinstance(parsed_content['results'], list):
                # Batch response - flatten all use_cases with their parent_br
                all_use_cases = []
                for result in parsed_content['results']:
                    parent_br = result.get('parent_br', br_id)
                    for uc in result.get('use_cases', []):
                        uc['parent_br'] = parent_br
                        all_use_cases.append(uc)
                parsed_content = {"use_cases": all_use_cases, "batch_mode": True, "parent_brs": br_ids}
                uc_count = len(all_use_cases)
                logger.info(f"Batch mode: Generated {uc_count} Use Cases for {len(br_ids)} BRs")
            return parsed_content, uc_count

        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return {"raw": content, "parse_error": str(e)}, 0

    def _log_interaction(
        self,
        mode: str,
        prompt: str,
        content: str,
        execution_id: int,
        input_tokens: int,
        tokens_used: int,
        model_used: str,
        provider_used: str,
        execution_time: float,
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="olivia",
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
                execution_time_seconds=execution_time,
                success=True,
                error_message=None,
            )
            logger.debug("LLM interaction logged (INFRA-002)")
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")


# ============================================================================
# CLI MODE -- Backward compatibility for subprocess invocation
# ============================================================================
if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path

    # Ensure backend is on sys.path for CLI mode
    _backend_dir = str(Path(__file__).resolve().parent.parent.parent)
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)

    # Re-import after sys.path fix (module-level imports may have failed in CLI mode)
    if not LLM_SERVICE_AVAILABLE:
        try:
            from app.services.llm_service import generate_llm_response, LLMProvider
            LLM_SERVICE_AVAILABLE = True
        except ImportError:
            pass

    if not RAG_AVAILABLE:
        try:
            from app.services.rag_service import get_salesforce_context
            RAG_AVAILABLE = True
        except ImportError:
            pass

    parser = argparse.ArgumentParser(description='Olivia BA Agent - UC Generation')
    parser.add_argument('--input', required=True, help='Input JSON file with BR')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--execution-id', type=int, default=0, help='Execution ID')
    parser.add_argument('--project-id', type=int, default=0, help='Project ID')
    parser.add_argument('--use-rag', action='store_true', default=True, help='Use RAG for context')
    parser.add_argument('--mode', default='generate_uc', help='Agent mode')

    args = parser.parse_args()

    try:
        logger.info("Reading BR from %s...", args.input)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()
        logger.info("Read %d characters", len(input_content))

        agent = BusinessAnalystAgent()
        result = agent.run({
            "mode": args.mode,
            "input_content": input_content,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
        })

        if result.get("success"):
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
