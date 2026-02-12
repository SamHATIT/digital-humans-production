"""
SDS Section Writer - Sectioned SDS generation with agent list enforcement.

Provides the DIGITAL_HUMANS_AGENTS constant and UC sub-batching for Phase 5.
Used by pm_orchestrator_service_v2.py for SDS generation.
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# AGENT LIST CONSTANT — Source of truth for all SDS generation prompts
# ============================================================================

DIGITAL_HUMANS_AGENTS = """
The Digital Humans platform has exactly 11 specialized agents:
- Sophie (PM/Project Manager) — orchestration, project management
- Olivia (BA/Business Analyst) — use cases, requirements analysis
- Emma (Research Analyst) — coverage validation, research
- Marcus (Architect/Solution Architect) — architecture, data model, WBS
- Diego (Apex Developer) — Apex code, triggers, batch jobs
- Zara (LWC Developer) — Lightning Web Components, UI
- Jordan (DevOps Engineer) — CI/CD, deployment, environments
- Elena (QA Specialist) — test strategy, test cases, quality
- Raj (Admin/Salesforce Admin) — configuration, permissions, security
- Aisha (Data Specialist) — data migration, data model, ETL
- Lucas (Trainer) — training, documentation, change management

IMPORTANT: Only reference these 11 agents by their exact names. Never invent other agent names.
"""

# Sub-batch size for Section 3 (Use Case Specifications)
UC_BATCH_SIZE = 50  # TRUNC-002: 50 UCs/batch to avoid truncation (was 100, caused 16K overflow + continuations)


def get_section_system_prompt(section_name: str = "") -> str:
    """Build a system prompt that includes the agent list for any SDS section."""
    return f"""You are a senior Salesforce consultant writing a professional SDS (Solution Design Specification).

{DIGITAL_HUMANS_AGENTS}

Write in a clear, professional tone. Be specific and actionable.
Only reference the 11 agents listed above — never invent agent names.
{"Section: " + section_name if section_name else ""}"""


async def generate_uc_section_batched(
    all_ucs: List[Dict[str, Any]],
    project_name: str = "",
    project_context: dict = None,
    progress_callback=None,
) -> Dict[str, Any]:
    """
    Generate SDS Section 3 (Use Case Specifications) in sub-batches.

    When UCs exceed UC_BATCH_SIZE, splits into batches and makes separate
    LLM calls per batch, then concatenates the results.

    Args:
        all_ucs: List of use case dicts to include in section.
        project_name: Project name for prompt context.
        project_context: Optional dict with project metadata and BRs.
            Expected keys: project (dict with name, description,
            salesforce_product, organization_type), business_requirements (list).

    Returns:
        Dict with keys: content (str), tokens_used (int), batch_count (int)
    """
    from app.services.llm_service import generate_llm_response_async

    total_ucs = len(all_ucs)
    total_batches = (total_ucs + UC_BATCH_SIZE - 1) // UC_BATCH_SIZE
    section_parts = []
    total_tokens = 0

    # Build project context block for prompt enrichment
    context_block = ""
    if project_context:
        proj = project_context.get("project", {})
        brs = project_context.get("business_requirements", [])
        context_lines = []
        if proj.get("name"):
            context_lines.append(f"- Project: {proj['name']}")
        if proj.get("description"):
            context_lines.append(f"- Description: {proj['description']}")
        if proj.get("salesforce_product"):
            context_lines.append(f"- Salesforce Product: {proj['salesforce_product']}")
        if proj.get("organization_type"):
            context_lines.append(f"- Organization Type: {proj['organization_type']}")
        if brs:
            br_summary = ", ".join(
                br.get("category", br.get("requirement", "")[:40])
                for br in brs[:15]
            )
            context_lines.append(f"- Business Requirements ({len(brs)} total): {br_summary}")
        if context_lines:
            context_block = "PROJECT CONTEXT:\n" + "\n".join(context_lines) + "\n\n"

    section_system_prompt = get_section_system_prompt("Use Case Specifications")

    for batch_idx in range(0, total_ucs, UC_BATCH_SIZE):
        batch = all_ucs[batch_idx:batch_idx + UC_BATCH_SIZE]
        batch_num = batch_idx // UC_BATCH_SIZE + 1

        logger.info(
            f"[P9] Section 3 batch {batch_num}/{total_batches}: "
            f"UCs {batch_idx + 1}-{batch_idx + len(batch)}"
        )

        if batch_num == 1:
            header_instruction = "Include section header and introduction only in batch 1."
        else:
            header_instruction = (
                "Continue directly with use case specifications, no section header. "
                "Maintain consistent formatting and numbering with previous batches."
            )

        batch_prompt = f"""{context_block}Generate Use Case Specifications for batch {batch_num}/{total_batches}.
{f"Project: {project_name}" if project_name else ""}

This batch covers Use Cases {batch_idx + 1} to {batch_idx + len(batch)} out of {total_ucs} total.
{header_instruction}

For each Use Case, provide:
- UC ID and title
- Description and business context
- Actors involved
- Preconditions and postconditions
- Main flow (numbered steps)
- Alternative flows (if any)
- Business rules applied
- Salesforce objects involved
- Assigned agent (from the authorized list only)

Use Cases for this batch:
{json.dumps(batch, indent=2, ensure_ascii=False)}
"""
        try:
            response = await generate_llm_response_async(
                prompt=batch_prompt,
                agent_type="research",
                system_prompt=section_system_prompt,
                max_tokens=16384,
            )

            if response.get("success") is not False and response.get("content"):
                content = response.get("content", "")
                if isinstance(content, dict):
                    content = content.get("text", content.get("document", str(content)))
                section_parts.append(str(content))
                batch_tokens = response.get("tokens_used", 0)
                total_tokens += batch_tokens
                logger.info(
                    f"[P9] Section 3 batch {batch_num}/{total_batches}: "
                    f"OK ({batch_tokens} tokens)"
                )
                # BUG-014: Report progress per batch
                if progress_callback:
                    try:
                        progress_callback(batch_num, total_batches)
                    except Exception:
                        pass
            else:
                error_msg = response.get("error", "Unknown error")
                logger.warning(
                    f"[P9] Section 3 batch {batch_num}/{total_batches}: "
                    f"FAILED — {error_msg}, skipping batch"
                )
        except Exception as e:
            logger.warning(
                f"[P9] Section 3 batch {batch_num}/{total_batches}: "
                f"EXCEPTION — {e}, skipping batch"
            )

    section_content = "\n\n".join(section_parts)

    return {
        "content": section_content,
        "tokens_used": total_tokens,
        "batch_count": total_batches,
    }
