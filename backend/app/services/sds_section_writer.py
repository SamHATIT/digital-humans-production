"""
SDS Section Writer — P9 Sectioned Generation

Replaces the monolithic Emma write_sds call with 11 sequential LLM calls.
Each call generates one SDS section loading full deliverables from the
agent_deliverables table — zero truncation.

Architecture:
  - Uses generate_llm_response() from llm_service (P6-compatible: routes through
    LLM Router V3 when available, falls back to V1).
  - Loads deliverables from PostgreSQL (agent_deliverables table) for each section.
  - Section #11 (consolidation) receives summaries of sections 1-10 and produces
    intro, conclusion, cross-references, and table of contents.

Usage:
    from app.services.sds_section_writer import SDSSectionWriter

    writer = SDSSectionWriter(db=db_session)
    result = writer.generate_sds(
        execution_id=42,
        project=project,
        artifacts=results["artifacts"],
        agent_outputs=results["agent_outputs"],
        on_progress=my_callback,
    )
    markdown = result["markdown"]
    metrics = result["metrics"]
"""

import json
import time
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Callable

from sqlalchemy.orm import Session

from app.models.agent_deliverable import AgentDeliverable
from app.models.project import Project
from app.services.llm_service import generate_llm_response
from app.services.sds_section_template import (
    SDS_SECTIONS,
    SECTION_SYSTEM_PROMPT,
    CONSOLIDATION_SYSTEM_PROMPT,
    build_section_prompt,
    build_consolidation_prompt,
)

logger = logging.getLogger(__name__)

# Maximum characters for a section summary sent to consolidation call
_SUMMARY_MAX_CHARS = 800


class SDSSectionWriter:
    """
    Generates a complete SDS document via 11 sequential LLM calls.

    Each section receives the full, untruncated deliverables relevant to it.
    The final consolidation call (#11) produces intro, ToC, cross-references,
    and conclusion from section summaries.
    """

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def generate_sds(
        self,
        execution_id: int,
        project: Project,
        artifacts: Dict[str, Any],
        agent_outputs: Dict[str, Any],
        on_progress: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Generate the full SDS document section by section.

        Args:
            execution_id: Current execution ID (for loading deliverables from DB)
            project: Project SQLAlchemy model
            artifacts: results["artifacts"] from the orchestrator
            agent_outputs: results["agent_outputs"] from the orchestrator
            on_progress: Optional callback(section_id, section_num, total, status)

        Returns:
            {
                "markdown": str,          # Full SDS markdown document
                "metrics": {
                    "total_sections": int,
                    "successful_sections": int,
                    "failed_sections": int,
                    "total_tokens": int,
                    "total_time_seconds": float,
                    "document_length_chars": int,
                    "sections": [{ id, title, tokens, time_seconds, chars, status }]
                }
            }
        """
        start_time = time.time()
        total_sections = len(SDS_SECTIONS)

        project_info = {
            "name": project.name,
            "description": project.description or "",
            "client_name": getattr(project, "client_name", "") or "",
            "objectives": project.architecture_notes or "",
        }

        # Prepare deliverable data accessible to all sections
        deliverable_pool = self._build_deliverable_pool(
            execution_id, project_info, artifacts, agent_outputs
        )

        section_results: List[Dict[str, Any]] = []
        section_markdowns: List[str] = []
        total_tokens = 0

        # --- Sections 1-10: content sections ---
        for section_def in SDS_SECTIONS:
            section_id = section_def["id"]
            section_num = section_def["number"]
            is_consolidation = section_def.get("is_consolidation", False)

            if is_consolidation:
                # Section 11 handled after loop
                continue

            if on_progress:
                on_progress(section_id, section_num, total_sections, "generating")

            logger.info(
                f"[P9] Section {section_num}/{total_sections}: {section_def['title']}"
            )

            section_start = time.time()
            try:
                # Gather data for this section
                section_data = self._gather_section_data(section_def, deliverable_pool)

                prompt = build_section_prompt(section_def, project_info, section_data)

                response = generate_llm_response(
                    prompt=prompt,
                    agent_type="research",
                    system_prompt=SECTION_SYSTEM_PROMPT,
                    max_tokens=16000,
                    temperature=0.3,
                )

                content = response.get("content", "")
                tokens_used = response.get("tokens_used", 0)
                total_tokens += tokens_used

                # Wrap in section header
                section_md = f"## {section_num}. {section_def['title']}\n\n{content}\n\n"
                section_markdowns.append(section_md)

                elapsed = time.time() - section_start
                section_results.append({
                    "id": section_id,
                    "number": section_num,
                    "title": section_def["title"],
                    "tokens": tokens_used,
                    "time_seconds": round(elapsed, 2),
                    "chars": len(content),
                    "status": "success",
                })

                logger.info(
                    f"[P9] Section {section_num} done — "
                    f"{len(content):,} chars, {tokens_used} tokens, {elapsed:.1f}s"
                )

                if on_progress:
                    on_progress(section_id, section_num, total_sections, "done")

            except Exception as exc:
                elapsed = time.time() - section_start
                logger.error(f"[P9] Section {section_num} failed: {exc}")
                section_markdowns.append(
                    f"## {section_num}. {section_def['title']}\n\n"
                    f"*[Section generation failed: {str(exc)[:200]}]*\n\n"
                )
                section_results.append({
                    "id": section_id,
                    "number": section_num,
                    "title": section_def["title"],
                    "tokens": 0,
                    "time_seconds": round(elapsed, 2),
                    "chars": 0,
                    "status": "failed",
                })
                if on_progress:
                    on_progress(section_id, section_num, total_sections, "failed")

        # --- Section 11: Consolidation ---
        consol_def = SDS_SECTIONS[-1]  # Last entry is consolidation
        consol_num = consol_def["number"]
        if on_progress:
            on_progress("consolidation", consol_num, total_sections, "generating")

        logger.info(f"[P9] Section {consol_num}/{total_sections}: Consolidation")
        consol_start = time.time()

        try:
            # Build summaries from sections 1-10
            section_summaries = []
            for sr in section_results:
                # Use first N chars of the section markdown as summary
                idx = sr["number"] - 1
                if idx < len(section_markdowns):
                    raw_md = section_markdowns[idx]
                    summary = raw_md[:_SUMMARY_MAX_CHARS].strip()
                    if len(raw_md) > _SUMMARY_MAX_CHARS:
                        summary += "..."
                else:
                    summary = f"[Section {sr['number']} not available]"
                section_summaries.append({
                    "number": sr["number"],
                    "title": sr["title"],
                    "summary": summary,
                })

            prompt = build_consolidation_prompt(project_info, section_summaries)

            response = generate_llm_response(
                prompt=prompt,
                agent_type="research",
                system_prompt=CONSOLIDATION_SYSTEM_PROMPT,
                max_tokens=8000,
                temperature=0.3,
            )

            consol_content = response.get("content", "")
            consol_tokens = response.get("tokens_used", 0)
            total_tokens += consol_tokens

            consol_elapsed = time.time() - consol_start
            section_results.append({
                "id": "consolidation",
                "number": consol_num,
                "title": consol_def["title"],
                "tokens": consol_tokens,
                "time_seconds": round(consol_elapsed, 2),
                "chars": len(consol_content),
                "status": "success",
            })

            if on_progress:
                on_progress("consolidation", consol_num, total_sections, "done")

            logger.info(
                f"[P9] Consolidation done — "
                f"{len(consol_content):,} chars, {consol_tokens} tokens"
            )

        except Exception as exc:
            consol_elapsed = time.time() - consol_start
            logger.error(f"[P9] Consolidation failed: {exc}")
            consol_content = ""
            section_results.append({
                "id": "consolidation",
                "number": consol_num,
                "title": consol_def["title"],
                "tokens": 0,
                "time_seconds": round(consol_elapsed, 2),
                "chars": 0,
                "status": "failed",
            })
            if on_progress:
                on_progress("consolidation", consol_num, total_sections, "failed")

        # --- Assemble final document ---
        final_markdown = self._assemble_document(
            project_info, consol_content, section_markdowns
        )

        total_time = time.time() - start_time
        successful = sum(1 for s in section_results if s["status"] == "success")
        failed = sum(1 for s in section_results if s["status"] == "failed")

        metrics = {
            "total_sections": total_sections,
            "successful_sections": successful,
            "failed_sections": failed,
            "total_tokens": total_tokens,
            "total_time_seconds": round(total_time, 2),
            "document_length_chars": len(final_markdown),
            "sections": section_results,
        }

        logger.info(
            f"[P9] SDS complete — {len(final_markdown):,} chars, "
            f"{successful}/{total_sections} sections, "
            f"{total_tokens} tokens, {total_time:.1f}s"
        )

        return {"markdown": final_markdown, "metrics": metrics}

    # ========================================================================
    # PRIVATE — DATA GATHERING
    # ========================================================================

    def _build_deliverable_pool(
        self,
        execution_id: int,
        project_info: Dict,
        artifacts: Dict[str, Any],
        agent_outputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Build a flat pool of all deliverable data keyed by logical name.
        Sources: in-memory artifacts, agent_outputs, and DB deliverables.
        """
        pool: Dict[str, Any] = {}

        # Project info
        pool["project_info"] = project_info

        # Business requirements (from DB for completeness)
        pool["business_requirements"] = self._load_brs_from_db(execution_id)

        # Use cases (from DB)
        pool["use_cases"] = self._load_use_cases_from_db(execution_id)

        # Artifacts from orchestrator memory
        artifact_mappings = {
            "UC_DIGEST": "uc_digest",
            "AS_IS": "as_is",
            "GAP": "gap_analysis",
            "COVERAGE": "coverage_report",
            "ARCHITECTURE": "solution_design",
            "WBS": "wbs",
            "BR": "br_extraction",
        }
        for artifact_key, pool_key in artifact_mappings.items():
            data = artifacts.get(artifact_key, {})
            if isinstance(data, dict):
                pool[pool_key] = data.get("content", data)
            else:
                pool[pool_key] = data

        # Agent outputs (Phase 4 experts)
        for agent_id in ["qa", "devops", "trainer", "data"]:
            agent_data = agent_outputs.get(agent_id)
            if agent_data and isinstance(agent_data, dict):
                pool[agent_id] = agent_data.get("content", agent_data)
            elif agent_data:
                pool[agent_id] = agent_data

        # Also load Phase 4 deliverables from DB (full, untruncated)
        db_experts = self._load_expert_deliverables_from_db(execution_id)
        for agent_id, content in db_experts.items():
            # DB version takes priority (guaranteed untruncated)
            if content:
                pool[agent_id] = content

        return pool

    def _gather_section_data(
        self, section_def: Dict, pool: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract the relevant deliverable data for a specific section.
        """
        data: Dict[str, Any] = {}

        # Deliverable keys (project_info, business_requirements, use_cases, uc_digest)
        for key in section_def.get("deliverable_keys", []):
            if key in pool and pool[key]:
                data[key] = pool[key]

        # Artifact keys (BR, USE_CASES, UC_DIGEST, AS_IS, GAP, COVERAGE, ARCHITECTURE, WBS)
        artifact_to_pool = {
            "BR": "br_extraction",
            "USE_CASES": "use_cases",
            "UC_DIGEST": "uc_digest",
            "AS_IS": "as_is",
            "GAP": "gap_analysis",
            "COVERAGE": "coverage_report",
            "ARCHITECTURE": "solution_design",
            "WBS": "wbs",
        }
        for ak in section_def.get("artifact_keys", []):
            pool_key = artifact_to_pool.get(ak, ak.lower())
            if pool_key in pool and pool[pool_key]:
                data[ak] = pool[pool_key]

        # Agent output keys (qa, devops, trainer, data)
        for agent_id in section_def.get("agent_output_keys", []):
            if agent_id in pool and pool[agent_id]:
                data[agent_id] = pool[agent_id]

        return data

    # ========================================================================
    # PRIVATE — DB LOADERS
    # ========================================================================

    def _load_brs_from_db(self, execution_id: int) -> List[Dict]:
        """Load business requirements from the business_requirements table."""
        try:
            from app.models.business_requirement import BusinessRequirement

            brs = (
                self.db.query(BusinessRequirement)
                .filter(BusinessRequirement.execution_id == execution_id)
                .all()
            )
            if brs:
                return [
                    {
                        "id": br.br_id,
                        "title": br.requirement[:100] if br.requirement else br.br_id,
                        "description": br.requirement or "",
                        "priority": br.priority.value if br.priority else "SHOULD",
                    }
                    for br in brs
                ]

            # Fallback: agent_deliverables
            return self._load_brs_from_deliverables(execution_id)
        except Exception as e:
            logger.warning(f"[P9] Failed to load BRs from DB: {e}")
            return []

    def _load_brs_from_deliverables(self, execution_id: int) -> List[Dict]:
        """Fallback: load BRs from agent_deliverables table."""
        try:
            deliverable = (
                self.db.query(AgentDeliverable)
                .filter(
                    AgentDeliverable.execution_id == execution_id,
                    AgentDeliverable.deliverable_type.in_(
                        ["br_extraction", "pm_br_extraction",
                         "business_requirements_extraction"]
                    ),
                )
                .first()
            )
            if deliverable and deliverable.content:
                content_data = deliverable.content
                if isinstance(content_data, str):
                    content_data = json.loads(content_data)
                brs = content_data.get("content", {}).get("business_requirements", [])
                if not brs:
                    brs = content_data.get("business_requirements", [])
                return brs
        except Exception as e:
            logger.warning(f"[P9] Failed to load BRs from deliverables: {e}")
        return []

    def _load_use_cases_from_db(self, execution_id: int) -> List[Dict]:
        """Load use cases from deliverable_items table."""
        try:
            from app.models.deliverable_item import DeliverableItem

            items = (
                self.db.query(DeliverableItem)
                .filter(
                    DeliverableItem.execution_id == execution_id,
                    DeliverableItem.agent_id == "ba",
                    DeliverableItem.item_type == "use_case",
                    DeliverableItem.parse_success == True,
                )
                .order_by(DeliverableItem.id)
                .all()
            )
            return [item.content_parsed for item in items if item.content_parsed]
        except Exception as e:
            logger.warning(f"[P9] Failed to load UCs from DB: {e}")
            return []

    def _load_expert_deliverables_from_db(
        self, execution_id: int
    ) -> Dict[str, Any]:
        """
        Load Phase 4 expert deliverables from agent_deliverables table.
        Returns full content (untruncated) keyed by agent_id.
        """
        expert_data: Dict[str, Any] = {}
        expert_types = {
            "qa": ["qa_qa_specifications", "qa_specifications"],
            "devops": ["devops_devops_specifications", "devops_specifications"],
            "trainer": ["trainer_trainer_specifications", "trainer_specifications"],
            "data": ["data_data_specifications", "data_specifications"],
        }

        try:
            for agent_id, type_candidates in expert_types.items():
                deliverable = (
                    self.db.query(AgentDeliverable)
                    .filter(
                        AgentDeliverable.execution_id == execution_id,
                        AgentDeliverable.deliverable_type.in_(type_candidates),
                    )
                    .order_by(AgentDeliverable.created_at.desc())
                    .first()
                )
                if deliverable and deliverable.content:
                    content = deliverable.content
                    if isinstance(content, str):
                        try:
                            content = json.loads(content)
                        except json.JSONDecodeError:
                            pass
                    if isinstance(content, dict):
                        expert_data[agent_id] = content.get("content", content)
                    else:
                        expert_data[agent_id] = content
        except Exception as e:
            logger.warning(f"[P9] Failed to load expert deliverables: {e}")

        return expert_data

    # ========================================================================
    # PRIVATE — DOCUMENT ASSEMBLY
    # ========================================================================

    def _assemble_document(
        self,
        project_info: Dict,
        consolidation_content: str,
        section_markdowns: List[str],
    ) -> str:
        """
        Assemble the final SDS Markdown document.

        Structure:
          - Title & metadata
          - Consolidation (intro, ToC, cross-refs) from section #11
          - Sections 1-10 content
          - Conclusion (extracted from consolidation if present)
        """
        parts = []

        # Title page
        parts.append(f"# Solution Design Specification (SDS)")
        parts.append(f"## {project_info.get('name', 'Untitled Project')}\n")
        parts.append(f"**Generated by:** Digital Humans — P9 Sectioned Generation")
        parts.append(
            f"**Date:** {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M UTC')}"
        )
        parts.append(f"**Client:** {project_info.get('client_name', 'N/A')}")
        parts.append("\n---\n")

        # Consolidation output (intro, ToC, cross-refs)
        if consolidation_content:
            parts.append(consolidation_content)
            parts.append("\n---\n")

        # Sections 1-10
        for md in section_markdowns:
            parts.append(md)

        # Footer
        parts.append("\n---\n")
        parts.append(
            "*Document generated by Digital Humans platform — "
            "P9 Sectioned Generation (11 LLM calls, 0% truncation)*"
        )

        return "\n".join(parts)
