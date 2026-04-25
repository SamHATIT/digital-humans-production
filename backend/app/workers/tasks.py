"""ARQ task definitions for long-running executions."""
import logging
from app.database import SessionLocal
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

logger = logging.getLogger("arq.worker")


async def execute_sds_task(ctx, execution_id: int, project_id: int,
                           selected_agents: list = None,
                           include_as_is: bool = False,
                           sfdx_metadata: dict = None,
                           resume_from: str = None):
    """ARQ task: Execute SDS workflow in isolated worker process."""
    db = SessionLocal()
    try:
        # BUG-008: Ghost job guard — skip if execution already completed/failed
        from app.models.execution import Execution, ExecutionStatus
        execution = db.query(Execution).get(execution_id)
        if execution and execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            logger.warning(f"[ARQ] Ghost job detected for exec {execution_id} (status={execution.status.value}), skipping")
            return {"skipped": True, "reason": "ghost_job", "execution_id": execution_id}

        service = PMOrchestratorServiceV2(db)
        result = await service.execute_workflow(
            execution_id=execution_id,
            project_id=project_id,
            selected_agents=selected_agents,
            include_as_is=include_as_is,
            sfdx_metadata=sfdx_metadata,
            resume_from=resume_from,
        )
        logger.info(f"[ARQ] Execution {execution_id} completed successfully")
        return result
    except Exception as e:
        logger.error(f"[ARQ] Execution {execution_id} failed: {e}")
        # Ensure execution is marked FAILED in DB
        try:
            from app.models.execution import Execution, ExecutionStatus
            execution = db.query(Execution).get(execution_id)
            if execution and execution.status not in (
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED
            ):
                execution.status = ExecutionStatus.FAILED
                execution.logs = str(e)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


async def resume_architecture_task(ctx, execution_id: int, project_id: int, action: str):
    """ARQ task: Resume from architecture validation pause."""
    db = SessionLocal()
    try:
        # BUG-008: Ghost job guard
        from app.models.execution import Execution, ExecutionStatus
        execution = db.query(Execution).get(execution_id)
        if execution and execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            logger.warning(f"[ARQ] Ghost resume detected for exec {execution_id} (status={execution.status.value}), skipping")
            return {"skipped": True, "reason": "ghost_job", "execution_id": execution_id}

        service = PMOrchestratorServiceV2(db)
        result = await service.resume_from_architecture_validation(
            execution_id=execution_id,
            project_id=project_id,
            action=action,
        )
        logger.info(f"[ARQ] Architecture resume {execution_id} completed: action={action}")
        return result
    except Exception as e:
        logger.error(f"[ARQ] Architecture resume {execution_id} failed: {e}")
        try:
            from app.models.execution import Execution, ExecutionStatus
            execution = db.query(Execution).get(execution_id)
            if execution and execution.status not in (
                ExecutionStatus.COMPLETED, ExecutionStatus.FAILED
            ):
                execution.status = ExecutionStatus.FAILED
                execution.logs = str(e)
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


async def execute_build_task(ctx, project_id: int, execution_id: int):
    """ARQ task: Execute BUILD v2 with PhasedBuildExecutor."""
    from app.services.phased_build_executor import PhasedBuildExecutor
    from app.services.execution_state import ExecutionStateMachine, InvalidTransitionError
    from app.models.task_execution import TaskExecution

    db = SessionLocal()
    try:
        logger.info(f"[ARQ] BUILD v2 starting for project {project_id}, execution {execution_id}")

        # Transition to build_running
        sm = ExecutionStateMachine(db, execution_id)
        try:
            sm.transition_to("build_running")
            db.commit()
        except InvalidTransitionError as e:
            logger.warning(f"[ARQ] BUILD state transition skipped: {e}")

        tasks = db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution_id
        ).all()

        wbs_tasks = []
        for task in tasks:
            wbs_tasks.append({
                "task_id": task.task_id,
                "task_name": task.task_name,
                "name": task.task_name,
                "target_object": task.task_name,
                "task_type": task.task_type,
                "assigned_agent": task.assigned_agent,
                "description": task.description or task.task_name,
                "phase_name": task.phase_name,
            })

        logger.info(f"[ARQ] BUILD v2 found {len(wbs_tasks)} tasks")

        executor = PhasedBuildExecutor(project_id, execution_id, db)
        result = await executor.execute_build(wbs_tasks)

        # Transition to build_complete or failed
        try:
            if result.get("success"):
                sm.transition_to("build_complete")
            else:
                sm.transition_to("failed")
            db.commit()
        except InvalidTransitionError as e:
            logger.warning(f"[ARQ] BUILD final state transition skipped: {e}")

        logger.info(f"[ARQ] BUILD v2 completed: {result}")
        return result
    except Exception as e:
        logger.error(f"[ARQ] BUILD v2 error: {e}")
        # Mark as failed in state machine
        try:
            sm = ExecutionStateMachine(db, execution_id)
            sm.transition_to("failed")
            db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


async def generate_uc_batch_task(
    ctx,
    execution_id: int,
    batch_idx: int,
    total_batches: int,
    ucs_batch: list,
    project_name: str = "",
    project_context: dict = None,
    system_prompt: str = "",
):
    """ARQ task: generate ONE UC Section 3 batch in isolation.

    Replaces the inline per-batch LLM call that used to happen inside
    ``generate_uc_section_batched``. With this refactor each batch becomes an
    independent ARQ job, so the global 1 h ``job_timeout`` on
    ``execute_sds_task`` is no longer hit when a project has many UCs
    (2+ batches of Sonnet-4.5 ~10 min each).

    Idempotent: if a successful ``DeliverableItem`` already exists for this
    (execution_id, item_id) tuple, returns cached result without calling the
    LLM. This means a worker retry simply picks up where the previous run
    stopped.

    Result is persisted in ``deliverable_items`` with:
      - agent_id = "research_analyst"
      - item_type = "uc_sds_batch"
      - item_id = "batch-{idx:03d}" (0-padded)
      - parent_ref = "exec-{execution_id}"

    The orchestrator polls this table to assemble Section 3.
    """
    import json
    from app.services.llm_service import generate_llm_response_async
    from app.models.deliverable_item import DeliverableItem

    batch_num = batch_idx + 1
    item_id = f"batch-{batch_idx:03d}"

    db = SessionLocal()
    try:
        # 1. Idempotency check — skip if already in DB (handles ARQ retries)
        existing = db.query(DeliverableItem).filter(
            DeliverableItem.execution_id == execution_id,
            DeliverableItem.agent_id == "research_analyst",
            DeliverableItem.item_type == "uc_sds_batch",
            DeliverableItem.item_id == item_id,
            DeliverableItem.parse_success == True,  # noqa: E712
        ).first()
        if existing:
            logger.info(
                f"[UC-BATCH] Batch {batch_num}/{total_batches} — "
                f"already in DB (id={existing.id}), skipping LLM call"
            )
            return {
                "batch_idx": batch_idx,
                "success": True,
                "cached": True,
                "content_length": len(existing.content_raw or ""),
                "tokens_used": existing.tokens_used or 0,
            }

        # 2. Build prompt (mirrors the logic that used to live in
        #    generate_uc_section_batched)
        context_block = ""
        if project_context:
            proj = project_context.get("project", project_context) or {}
            brs = project_context.get("business_requirements", [])
            context_lines = []
            for key, label in (
                ("name", "Project"),
                ("description", "Description"),
                ("salesforce_product", "Salesforce Product"),
                ("organization_type", "Organization Type"),
            ):
                if proj.get(key):
                    context_lines.append(f"- {label}: {proj[key]}")
            if brs:
                br_summary = ", ".join(
                    br.get("category", br.get("requirement", "")[:40])
                    for br in brs[:15]
                )
                context_lines.append(
                    f"- Business Requirements ({len(brs)} total): {br_summary}"
                )
            if context_lines:
                context_block = "PROJECT CONTEXT:\n" + "\n".join(context_lines) + "\n\n"

        header_instruction = (
            "Include section header and introduction only in batch 1."
            if batch_num == 1
            else (
                "Continue directly with use case specifications, no section "
                "header. Maintain consistent formatting and numbering with "
                "previous batches."
            )
        )
        batch_start_uc = batch_idx * 50 + 1  # UC_BATCH_SIZE=50
        batch_end_uc = batch_start_uc + len(ucs_batch) - 1

        batch_prompt = (
            f"{context_block}"
            f"Generate Use Case Specifications for batch "
            f"{batch_num}/{total_batches}.\n"
            f"{f'Project: {project_name}' if project_name else ''}\n\n"
            f"This batch covers Use Cases {batch_start_uc} to {batch_end_uc}.\n"
            f"{header_instruction}\n\n"
            "For each Use Case, provide:\n"
            "- UC ID and title\n"
            "- Description and business context\n"
            "- Actors involved\n"
            "- Preconditions and postconditions\n"
            "- Main flow (numbered steps)\n"
            "- Alternative flows (if any)\n"
            "- Business rules applied\n"
            "- Salesforce objects involved\n"
            "- Assigned agent (from the authorized list only)\n\n"
            f"Use Cases for this batch:\n"
            f"{json.dumps(ucs_batch, indent=2, ensure_ascii=False)}\n"
        )

        # 3. LLM call (can raise — ARQ will retry the whole task)
        response = await generate_llm_response_async(
            prompt=batch_prompt,
            agent_type="research",
            system_prompt=system_prompt,
            max_tokens=16384,
        )

        # 4. Parse + persist
        if response.get("success") is False or not response.get("content"):
            error_msg = response.get("error", "Unknown error")
            logger.warning(
                f"[UC-BATCH] Batch {batch_num}/{total_batches}: failed — {error_msg}"
            )
            item = DeliverableItem(
                execution_id=execution_id,
                agent_id="research_analyst",
                item_type="uc_sds_batch",
                item_id=item_id,
                parent_ref=f"exec-{execution_id}",
                content_raw="",
                parse_success=False,
                parse_error=error_msg[:500],
                tokens_used=0,
            )
            db.add(item)
            db.commit()
            return {
                "batch_idx": batch_idx,
                "success": False,
                "error": error_msg,
            }

        content = response.get("content", "")
        if isinstance(content, dict):
            content = content.get("text", content.get("document", str(content)))
        content = str(content)
        tokens = int(response.get("tokens_used", 0) or 0)
        model = response.get("model", "claude-sonnet-4-5-20250929")

        item = DeliverableItem(
            execution_id=execution_id,
            agent_id="research_analyst",
            item_type="uc_sds_batch",
            item_id=item_id,
            parent_ref=f"exec-{execution_id}",
            content_raw=content,
            parse_success=True,
            tokens_used=tokens,
            model_used=str(model)[:100],
        )
        db.add(item)
        db.commit()

        logger.info(
            f"[UC-BATCH] Batch {batch_num}/{total_batches}: OK "
            f"({tokens} tokens, {len(content)} chars, db_id={item.id})"
        )
        return {
            "batch_idx": batch_idx,
            "success": True,
            "cached": False,
            "content_length": len(content),
            "tokens_used": tokens,
            "db_id": item.id,
        }
    except Exception as e:
        logger.error(
            f"[UC-BATCH] Batch {batch_num}/{total_batches}: exception — {e}"
        )
        # Don't swallow — let ARQ retry this single batch
        raise
    finally:
        db.close()
