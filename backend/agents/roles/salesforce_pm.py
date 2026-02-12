#!/usr/bin/env python3
"""
Salesforce Project Manager (Sophie) Agent

Two distinct roles:
1. extract_br: Extract atomic Business Requirements from raw input
2. consolidate_sds: Consolidate all artifacts into final SDS document

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (PMAgent.run()) or CLI (python salesforce_pm.py --mode ...).
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

# Prompt Service for externalized prompts
try:
    from prompts.prompt_service import PromptService
    PROMPT_SERVICE = PromptService()
except ImportError:
    PROMPT_SERVICE = None


# ============================================================================
# PROMPT 1: EXTRACT BUSINESS REQUIREMENTS
# ============================================================================
def get_extract_br_prompt(requirements: str) -> str:
    # Try external prompt first
    if PROMPT_SERVICE:
        try:
            return PROMPT_SERVICE.render("sophie_pm", "br_extraction", {
                "requirements": requirements,
            })
        except Exception as e:
            logger.warning(f"PromptService fallback for sophie_pm/br_extraction: {e}")

    # FALLBACK: original f-string prompt
    return f'''# BUSINESS REQUIREMENTS EXTRACTION

You are **Sophie**, a Senior Project Manager specialized in requirements analysis.

## YOUR MISSION
Extract **atomic Business Requirements (BR)** from the raw user input.
Each BR must be:
- **Atomic**: One single, testable requirement
- **Clear**: Unambiguous and precise
- **Independent**: Can be analyzed separately
- **Traceable**: Has a unique ID (BR-001, BR-002, etc.)

## OUTPUT FORMAT (JSON)
Output a JSON object with this structure:
- "project_summary": Brief 2-3 sentence summary of the project
- "business_requirements": Array of BR objects, each with:
  - "id": "BR-001", "BR-002", etc.
  - "title": Short descriptive title (max 10 words)
  - "description": Clear description (1-3 sentences)
  - "category": One of DATA_MODEL, AUTOMATION, INTEGRATION, UI_UX, REPORTING, SECURITY, OTHER
  - "priority": One of MUST_HAVE, SHOULD_HAVE, NICE_TO_HAVE
  - "stakeholder": Who needs this (e.g., "Sales Manager", "System Admin")
  - "metadata": Object containing:
    - "fields": Array of specific field names mentioned (e.g., ["Customer.Phone", "Order.Amount"])
    - "validation_rules": Array of business rules (e.g., ["Amount must be > 0", "Date cannot be in past"])
    - "dependencies": Array of related BR IDs (e.g., ["BR-001", "BR-003"])
    - "acceptance_criteria": Array of testable criteria (e.g., ["User can create record", "System validates input"])
- "constraints": Array of technical or business constraints
- "assumptions": Array of assumptions made

## RULES
1. Extract 10-30 atomic BRs depending on project complexity
2. **EXTRACT SPECIFIC DETAILS**:
   - When user mentions a field (e.g., "track the customer's phone number"), add it to metadata.fields
   - When user mentions a rule (e.g., "discount cannot exceed 30%"), add it to metadata.validation_rules
   - When a BR depends on another (e.g., "products need an order"), note the dependency
3. Do NOT add Salesforce-specific details (that's the BA's job)
4. Do NOT design solutions (that's the Architect's job)
5. Focus on WHAT is needed, not HOW to implement
6. Group related requirements under appropriate categories
7. Preserve the business intent from the original text
8. If something is unclear, list it as an assumption

## EXAMPLE
For input: "We need to track customer phone and email. Discounts cannot exceed 30%."

Output should include:
- metadata.fields: ["Customer.Phone", "Customer.Email", "Order.Discount"]
- metadata.validation_rules: ["Discount <= 30%"]
- metadata.acceptance_criteria: ["User can enter phone", "System rejects discount > 30%"]

---

## RAW REQUIREMENTS TO ANALYZE:

{requirements}

---

**Extract all Business Requirements now. Output ONLY valid JSON, no markdown fences or extra text.**
'''

def get_consolidate_sds_prompt(artifacts: str) -> str:
    # Try external prompt first
    if PROMPT_SERVICE:
        try:
            return PROMPT_SERVICE.render("sophie_pm", "consolidate_sds", {
                "artifacts": artifacts,
            })
        except Exception as e:
            logger.warning(f"PromptService fallback for sophie_pm/consolidate_sds: {e}")

    # FALLBACK: original f-string prompt
    return f'''# SOLUTION DESIGN SPECIFICATION - FINAL DOCUMENT

You are **Sophie**, a Senior Project Manager creating the final SDS document.

## YOUR MISSION
Consolidate all agent artifacts into a **professional, well-formatted** Solution Design Specification.

## CRITICAL FORMATTING RULES

### Mermaid Diagrams
All diagrams MUST use proper Mermaid syntax wrapped in code blocks:

**ERD Diagram Example:**
```mermaid
erDiagram
    Account ||--o{{ Opportunity : has
    Opportunity ||--o{{ OpportunityLineItem : contains
    Product2 ||--o{{ OpportunityLineItem : "product for"
    Opportunity ||--o{{ Trade_In__c : includes
```

**Flow Diagram Example:**
```mermaid
flowchart TD
    A[Start: New Opportunity] --> B{{Multi-Product?}}
    B -->|Yes| C[Add Products]
    B -->|No| D[Standard Flow]
    C --> E[Calculate Total]
    E --> F[End]
```

**Sequence Diagram Example:**
```mermaid
sequenceDiagram
    participant User
    participant Salesforce
    participant ExternalAPI
    User->>Salesforce: Create Trade-In
    Salesforce->>ExternalAPI: Get Valuation
    ExternalAPI-->>Salesforce: Return Value
    Salesforce-->>User: Display Quote
```

### Tables
Use proper Markdown tables with headers:
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |

## DOCUMENT STRUCTURE (15-25 pages max)

### 1. Executive Summary (1 page max)
- **Project Name**: [Name]
- **Date**: [Date]
- **Version**: 1.0
- **Overview**: 3-5 sentences describing the project
- **Key Objectives**: 3-5 bullet points
- **Success Criteria**: Measurable outcomes

### 2. Business Requirements Summary (2-3 pages)
Create a table:
| BR ID | Title | Category | Priority | Status |
|-------|-------|----------|----------|--------|

Then add **BR to UC Traceability Matrix**:
| BR ID | Related Use Cases |
|-------|-------------------|

### 3. Solution Architecture (4-5 pages)

#### 3.1 Data Model
- Include the **ERD diagram** from ARCH-001 using Mermaid erDiagram
- List custom objects with key fields
- Document relationships

#### 3.2 Security Model
| Profile/Permission Set | Description | Key Permissions |
|------------------------|-------------|-----------------|

#### 3.3 Automation Design
- **Flows**: List with purpose
- **Triggers**: Only if necessary
- Include a **Process Flow diagram** using Mermaid flowchart

#### 3.4 Integration Architecture
| System | Direction | Method | Frequency |
|--------|-----------|--------|-----------|

Include a **Sequence Diagram** for key integrations

### 4. Gap Analysis Summary (2-3 pages)
From GAP-001:
| Gap ID | Category | Description | Effort | Assigned To |
|--------|----------|-------------|--------|-------------|

### 5. Implementation Plan (3-4 pages)
From WBS-001:

#### 5.1 Project Phases
| Phase | Duration | Key Deliverables |
|-------|----------|------------------|

#### 5.2 Timeline (Gantt-style using Mermaid)
```mermaid
gantt
    title Project Timeline
    dateFormat  YYYY-MM-DD
    section Foundation
    Security Setup     :a1, 2024-01-01, 2w
    section Build
    Data Model        :a2, after a1, 3w
```

#### 5.3 Resource Allocation
| Agent/Role | Allocation | Primary Responsibilities |
|------------|------------|--------------------------|

### 6. Risks and Mitigations (1 page)
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|

### 7. Appendix
- Reference to detailed artifacts (ARCH-001, ASIS-001, GAP-001, WBS-001)
- Glossary of terms
- Do NOT copy full artifact content

## OUTPUT RULES
1. Output clean Markdown only
2. All Mermaid diagrams must be syntactically correct
3. Use proper heading hierarchy (# ## ### ####)
4. Tables must have header separators (|---|)
5. Keep content concise - reference artifacts instead of copying
6. Include page breaks as: `---` between major sections
7. No JSON output - pure Markdown document

---

## ARTIFACTS TO CONSOLIDATE:

{artifacts}

---

**Generate the complete SDS document now in Markdown format.**
'''


# ============================================================================
# PM AGENT CLASS — Importable + CLI compatible
# ============================================================================
class PMAgent:
    """
    Sophie (PM) Agent - Extract BR + Consolidate SDS.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - extract_br: Extract atomic Business Requirements from raw input
        - consolidate_sds: Consolidate all artifacts into final SDS document

    Usage (import):
        agent = PMAgent()
        result = agent.run({"mode": "extract_br", "input_content": "..."})

    Usage (CLI):
        python salesforce_pm.py --mode extract_br --input input.json --output output.json
    """

    VALID_MODES = ("extract_br", "consolidate_sds")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "extract_br" or "consolidate_sds"
                - input_content: string content for the prompt
                - execution_id: int (optional, default 0)
                - project_id: int (optional, default 0)

        Returns:
            dict with agent output including "success" key.
            On success: full output dict with agent_id, content, metadata, etc.
            On failure: {"success": False, "error": "..."}
        """
        mode = task_data.get("mode", "extract_br")
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
            logger.error(f"PMAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _execute(
        self,
        mode: str,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Core execution logic shared by all modes."""
        start_time = time.time()

        # Select prompt and parameters based on mode
        if mode == "extract_br":
            prompt = get_extract_br_prompt(input_content)
            system_prompt = (
                "You are Sophie, a Senior Project Manager. "
                "Extract atomic business requirements from the input. "
                "Output ONLY valid JSON, no markdown code fences."
            )
            deliverable_type = "business_requirements_extraction"
            agent_role = "PM - BR Extraction"
            max_tokens = 8000
            temperature = 0.3
        else:  # consolidate_sds
            prompt = get_consolidate_sds_prompt(input_content)
            system_prompt = (
                "You are Sophie, a Senior Project Manager. "
                "Create a professional SDS document in clean Markdown format "
                "with properly formatted Mermaid diagrams."
            )
            deliverable_type = "solution_design_specification"
            agent_role = "PM - SDS Consolidation"
            max_tokens = 16000
            temperature = 0.4

        logger.info(f"PMAgent mode={mode}, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, system_prompt, max_tokens, temperature, execution_id=execution_id
        )

        execution_time = time.time() - start_time
        logger.info(
            f"PMAgent generated {len(content)} chars in {execution_time:.1f}s, "
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

        # Parse content based on mode
        parsed_content = self._parse_response(mode, content)

        # Build output
        output_data = {
            "success": True,
            "agent_id": "pm",
            "agent_name": "Sophie (Project Manager)",
            "agent_role": agent_role,
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": deliverable_type,
            "mode": mode,
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": datetime.now().isoformat(),
            },
        }

        # Add mode-specific metadata
        if mode == "extract_br" and isinstance(parsed_content, dict) and "business_requirements" in parsed_content:
            output_data["metadata"]["br_count"] = len(parsed_content["business_requirements"])
            output_data["metadata"]["categories"] = list(set(
                br.get("category", "OTHER")
                for br in parsed_content["business_requirements"]
            ))
        elif mode == "consolidate_sds":
            output_data["metadata"]["mermaid_diagrams_count"] = content.count("```mermaid")
            output_data["metadata"]["tables_count"] = content.count("|---|")

        return output_data

    def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int,
        temperature: float,
        execution_id: int = 0,
    ) -> tuple:
        """
        Call LLM via llm_service or direct Anthropic fallback.

        Returns:
            tuple of (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            logger.debug("Calling LLM via llm_service (PM tier)")
            response = generate_llm_response(
                prompt=prompt,
                agent_type="pm",
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                execution_id=execution_id,
            )
            return (
                response["content"],
                response["tokens_used"],
                response.get("input_tokens", 0),
                response["model"],
                response["provider"],
            )
        else:
            # Fallback to direct Anthropic API
            logger.warning("llm_service unavailable, falling back to direct Anthropic API")
            from anthropic import Anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set and llm_service unavailable")

            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            input_tokens = response.usage.input_tokens
            return (content, tokens_used, input_tokens, "claude-sonnet-4-20250514", "anthropic")

    def _parse_response(self, mode: str, content: str) -> Any:
        """Parse LLM response based on mode."""
        if mode == "extract_br":
            try:
                clean_content = content.strip()
                if clean_content.startswith("```"):
                    clean_content = clean_content.split("\n", 1)[1] if "\n" in clean_content else clean_content[3:]
                if clean_content.endswith("```"):
                    clean_content = clean_content[:-3]
                clean_content = clean_content.strip()

                parsed = json.loads(clean_content)
                br_count = len(parsed.get("business_requirements", []))
                logger.info(f"Extracted {br_count} Business Requirements")
                return parsed
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error in extract_br response: {e}")
                return {"raw": content, "parse_error": str(e)}
        else:
            # For SDS, content is markdown - store as-is
            mermaid_count = content.count("```mermaid")
            logger.info(f"SDS generated with {mermaid_count} Mermaid diagrams")
            return {"markdown": content}

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
                agent_id="sophie",
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
# CLI MODE — Backward compatibility for subprocess invocation
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

    parser = argparse.ArgumentParser(description="Sophie PM Agent")
    parser.add_argument("--mode", required=True, choices=["extract_br", "consolidate_sds"],
                        help="Operation mode")
    parser.add_argument("--input", required=True, help="Input file path")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--execution-id", type=int, default=0, help="Execution ID")
    parser.add_argument("--project-id", type=int, default=0, help="Project ID")

    args = parser.parse_args()

    try:
        # Read input file
        logger.info("Reading input from %s...", args.input)
        with open(args.input, "r", encoding="utf-8") as f:
            input_content = f.read()
        logger.info("Read %d characters", len(input_content))

        # Run agent
        agent = PMAgent()
        result = agent.run({
            "mode": args.mode,
            "input_content": input_content,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
        })

        if result.get("success"):
            # Save output file
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.info("SUCCESS: Output saved to %s", args.output)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            sys.exit(0)
        else:
            logger.error("ERROR: %s", result.get('error'))
            sys.exit(1)

    except Exception as e:
        logger.error("ERROR: %s", str(e), exc_info=True)
        sys.exit(1)
