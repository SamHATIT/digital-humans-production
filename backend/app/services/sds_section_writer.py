"""
SDS Section Writer - Sectioned SDS generation with agent list enforcement.

Provides the DIGITAL_HUMANS_AGENTS constant and UC sub-batching for Phase 5.
Used by pm_orchestrator_service_v2.py for SDS generation.
"""

import json
import logging
from typing import Dict, List, Any

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
    execution_id: int = None,
) -> Dict[str, Any]:
    """
    Generate SDS Section 3 (Use Case Specifications) in sub-batches.

    Two modes (chosen automatically):

    - **ARQ parallel** (when ``execution_id`` is provided): enqueues one
      ``generate_uc_batch_task`` job per batch. Each batch runs as an
      independent ARQ job with its own timeout, so the global 1 h
      ``execute_sds_task`` timeout is no longer hit on large projects.
      Results are polled from ``deliverable_items`` (``item_type='uc_sds_batch'``).
      Idempotent: already-persisted batches are reused on retry.

    - **In-process sequential** (when ``execution_id`` is None): original
      behaviour. Used by standalone callers (tests, scripts) that do not have
      a worker / Redis available.

    Args:
        all_ucs: List of use case dicts to include in section.
        project_name: Project name for prompt context.
        project_context: Optional dict with project metadata and BRs.
        progress_callback: Called with ``(current, total)`` as batches complete.
        execution_id: When present, enables ARQ parallel mode.

    Returns:
        Dict with keys: content (str), tokens_used (int), batch_count (int),
        plus (parallel mode only) completed_batches / failed_batches.
    """
    total_ucs = len(all_ucs)
    total_batches = (total_ucs + UC_BATCH_SIZE - 1) // UC_BATCH_SIZE
    section_system_prompt = get_section_system_prompt("Use Case Specifications")

    if execution_id is None:
        return await _generate_uc_section_inprocess(
            all_ucs=all_ucs,
            total_batches=total_batches,
            project_name=project_name,
            project_context=project_context,
            progress_callback=progress_callback,
            section_system_prompt=section_system_prompt,
        )

    return await _generate_uc_section_parallel_arq(
        all_ucs=all_ucs,
        total_batches=total_batches,
        project_name=project_name,
        project_context=project_context,
        progress_callback=progress_callback,
        section_system_prompt=section_system_prompt,
        execution_id=execution_id,
    )


def _build_context_block(project_context: dict, brs_seen: int = 15) -> str:
    """Shared prompt-context helper for both modes."""
    if not project_context:
        return ""
    proj = project_context.get("project", project_context) or {}
    brs = project_context.get("business_requirements", []) or []
    lines = []
    for key, label in (
        ("name", "Project"),
        ("description", "Description"),
        ("salesforce_product", "Salesforce Product"),
        ("organization_type", "Organization Type"),
    ):
        if proj.get(key):
            lines.append(f"- {label}: {proj[key]}")
    if brs:
        br_summary = ", ".join(
            br.get("category", br.get("requirement", "")[:40])
            for br in brs[:brs_seen]
        )
        lines.append(f"- Business Requirements ({len(brs)} total): {br_summary}")
    if not lines:
        return ""
    return "PROJECT CONTEXT:\n" + "\n".join(lines) + "\n\n"


async def _generate_uc_section_inprocess(
    all_ucs, total_batches, project_name, project_context, progress_callback,
    section_system_prompt,
):
    """Sequential in-process fallback — original behaviour."""
    from app.services.llm_service import generate_llm_response_async

    context_block = _build_context_block(project_context)
    section_parts = []
    total_tokens = 0
    total_ucs = len(all_ucs)

    for batch_idx in range(0, total_ucs, UC_BATCH_SIZE):
        batch = all_ucs[batch_idx:batch_idx + UC_BATCH_SIZE]
        batch_num = batch_idx // UC_BATCH_SIZE + 1
        logger.info(
            f"[P9] Section 3 batch {batch_num}/{total_batches}: "
            f"UCs {batch_idx + 1}-{batch_idx + len(batch)} (in-process mode)"
        )
        header_instruction = (
            "Include section header and introduction only in batch 1."
            if batch_num == 1
            else (
                "Continue directly with use case specifications, no section "
                "header. Maintain consistent formatting and numbering with "
                "previous batches."
            )
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
                batch_tokens = response.get("tokens_used", 0) or 0
                total_tokens += batch_tokens
                logger.info(
                    f"[P9] Section 3 batch {batch_num}/{total_batches}: "
                    f"OK ({batch_tokens} tokens)"
                )
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

    return {
        "content": "\n\n".join(section_parts),
        "tokens_used": total_tokens,
        "batch_count": total_batches,
    }


async def _generate_uc_section_parallel_arq(
    all_ucs, total_batches, project_name, project_context, progress_callback,
    section_system_prompt, execution_id,
):
    """Parallel mode: one ARQ job per batch, results polled from DB."""
    import asyncio
    from app.workers.arq_config import get_redis_pool
    from app.database import SessionLocal
    from app.models.deliverable_item import DeliverableItem

    total_ucs = len(all_ucs)
    logger.info(
        f"[P9-ARQ] Enqueuing {total_batches} UC batch jobs "
        f"(exec_id={execution_id}, total_ucs={total_ucs})"
    )

    # 1. Enqueue all batch jobs
    pool = await get_redis_pool()
    enqueued = 0
    for batch_idx in range(0, total_ucs, UC_BATCH_SIZE):
        batch = all_ucs[batch_idx:batch_idx + UC_BATCH_SIZE]
        batch_num = batch_idx // UC_BATCH_SIZE + 1
        job = await pool.enqueue_job(
            "generate_uc_batch_task",
            execution_id=execution_id,
            batch_idx=batch_num - 1,
            total_batches=total_batches,
            ucs_batch=batch,
            project_name=project_name,
            project_context=project_context or {},
            system_prompt=section_system_prompt,
            _queue_name="digital-humans",
        )
        enqueued += 1
        logger.info(
            f"[P9-ARQ] Batch {batch_num}/{total_batches}: job {job.job_id} enqueued"
        )

    # 2. Poll DB for completion
    poll_interval = 5  # seconds
    max_wait = 7200    # 2 h safety cap
    elapsed = 0
    last_reported = -1

    db = SessionLocal()
    try:
        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            items = db.query(DeliverableItem).filter(
                DeliverableItem.execution_id == execution_id,
                DeliverableItem.agent_id == "research_analyst",
                DeliverableItem.item_type == "uc_sds_batch",
            ).all()
            completed = [i for i in items if i.parse_success]
            failed = [i for i in items if i.parse_success is False]
            done_count = len(completed) + len(failed)

            if progress_callback and done_count != last_reported and done_count > 0:
                try:
                    progress_callback(done_count, total_batches)
                except Exception:
                    pass
                last_reported = done_count

            if elapsed % 60 == 0:
                logger.info(
                    f"[P9-ARQ] Polling... {len(completed)}/{total_batches} done, "
                    f"{len(failed)} failed, {elapsed}s elapsed"
                )

            if done_count >= total_batches:
                break

        # 3. Assemble in order
        all_items = db.query(DeliverableItem).filter(
            DeliverableItem.execution_id == execution_id,
            DeliverableItem.agent_id == "research_analyst",
            DeliverableItem.item_type == "uc_sds_batch",
            DeliverableItem.parse_success == True,  # noqa: E712
        ).order_by(DeliverableItem.item_id).all()

        section_parts = [i.content_raw for i in all_items if i.content_raw]
        total_tokens = sum(i.tokens_used or 0 for i in all_items)
        completed_count = len(all_items)
        failed_count = db.query(DeliverableItem).filter(
            DeliverableItem.execution_id == execution_id,
            DeliverableItem.agent_id == "research_analyst",
            DeliverableItem.item_type == "uc_sds_batch",
            DeliverableItem.parse_success == False,  # noqa: E712
        ).count()

        if completed_count < total_batches:
            logger.warning(
                f"[P9-ARQ] Partial completion: {completed_count}/{total_batches} "
                f"({failed_count} failed, {elapsed}s elapsed)"
            )
        else:
            logger.info(
                f"[P9-ARQ] All {total_batches} batches complete "
                f"({total_tokens} tokens, {elapsed}s elapsed)"
            )

        return {
            "content": "\n\n".join(section_parts),
            "tokens_used": total_tokens,
            "batch_count": total_batches,
            "completed_batches": completed_count,
            "failed_batches": failed_count,
        }
    finally:
        db.close()
