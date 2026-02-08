"""
PM Orchestrator Service V2 - Complete SDS Workflow

Workflow:
1. Sophie PM → extract_br (atomic BRs from raw requirements)
2. Olivia BA → called N times (1 per BR) → generates UCs
2.5. Emma Research Analyst → analyze mode → generates UC Digest for Marcus
3. Marcus Architect → 4 sequential calls (as_is, gap, design, wbs)
   - Now receives UC Digest instead of raw UCs (context optimization)
4. SDS Experts (systematic):
   - Aisha (Data) → Data Migration Strategy
   - Lucas (Trainer) → Training & Change Management Plan
   - Elena (QA) → Test Strategy & QA Approach
   - Jordan (DevOps) → CI/CD & Deployment Strategy
5. Sophie PM → consolidate_sds (final DOCX document)

Note: Diego (Apex), Zara (LWC), Raj (Admin) are BUILD phase agents,
not included in SDS generation but available for implementation tasks.

Features:
- Token tracking per agent
- Real-time SSE progress updates
- Salesforce metadata retrieval for Marcus
- Professional DOCX generation
- Error recovery with fallback
- Artifact persistence in PostgreSQL
- UC Digest via Emma (context compression for large projects)
"""

import os
import json
import asyncio
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

# PERF-001: Notification service for real-time updates
try:
    from app.services.notification_service import get_notification_service
    NOTIFICATIONS_ENABLED = True
except ImportError:
    NOTIFICATIONS_ENABLED = False

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.database import SessionLocal
from app.services.audit_service import audit_service, ActorType, ActionCategory
from app.models.project import Project
from app.models.execution import Execution, ExecutionStatus
from app.models.agent_deliverable import AgentDeliverable
from app.models.deliverable_item import DeliverableItem
from app.models.business_requirement import BusinessRequirement, BRStatus, BRPriority, BRSource
try:
    from app.models.validation_gate import ValidationGate
    HAS_VALIDATION_GATE = True
except ImportError:
    HAS_VALIDATION_GATE = False
# ValidationGate peut ne pas exister, on le gère dynamiquement
import logging
from app.config import settings
from app.salesforce_config import salesforce_config
from app.services.document_generator import generate_professional_sds, ProfessionalDocumentGenerator

logger = logging.getLogger(__name__)

# C1.1: Direct import registry for migrated agents (P3 fix)
try:
    from app.services.agent_executor import MIGRATED_AGENTS
    DIRECT_IMPORT_AVAILABLE = True
except ImportError:
    MIGRATED_AGENTS = {}
    DIRECT_IMPORT_AVAILABLE = False

# Agent script paths (centralized via config.py)
AGENTS_PATH = settings.BACKEND_ROOT / "agents" / "roles"

# Agent configurations
AGENT_CONFIG = {
    "pm": {"script": "salesforce_pm.py", "tier": "pm", "display_name": "Sophie (PM)"},
    "ba": {"script": "salesforce_business_analyst.py", "tier": "ba", "display_name": "Olivia (BA)"},
    "architect": {"script": "salesforce_solution_architect.py", "tier": "architect", "display_name": "Marcus (Architect)"},
    "apex": {"script": "salesforce_developer_apex.py", "tier": "worker", "display_name": "Diego (Apex Dev)"},
    "lwc": {"script": "salesforce_developer_lwc.py", "tier": "worker", "display_name": "Zara (LWC Dev)"},
    "admin": {"script": "salesforce_admin.py", "tier": "worker", "display_name": "Raj (Admin)"},
    "qa": {"script": "salesforce_qa_tester.py", "tier": "worker", "display_name": "Elena (QA)"},
    "devops": {"script": "salesforce_devops.py", "tier": "worker", "display_name": "Jordan (DevOps)"},
    "data": {"script": "salesforce_data_migration.py", "tier": "worker", "display_name": "Aisha (Data)"},
    "trainer": {"script": "salesforce_trainer.py", "tier": "worker", "display_name": "Lucas (Trainer)"},
    "research_analyst": {"script": "salesforce_research_analyst.py", "tier": "research", "display_name": "Emma (Research Analyst)"},
}

# Validation gates configuration
VALIDATION_GATES = [
    {"gate_number": 1, "name": "Requirements Analysis", "required_artifacts": ["BR", "UC"], "agents": ["pm", "ba"]},
    {"gate_number": 2, "name": "Solution Design", "required_artifacts": ["ARCH", "GAP", "WBS"], "agents": ["architect"]},
    {"gate_number": 3, "name": "Technical Specifications", "required_artifacts": ["APEX", "LWC", "CONFIG"], "agents": ["apex", "lwc", "admin"]},
]

# ORCH-02: Parallel execution configuration
# Set to True to run agents in parallel, False for sequential
PARALLEL_MODE = {
    "sds_experts": True,    # Phase 4: Elena, Jordan, Lucas, Aisha (no dependencies)
    "build_agents": False,  # Phase BUILD: Sequential for now (sandbox 2-user limit)
}

# Note: Resume capability is limited to Phase 1 (BR validation pause/resume)
# Full phase-by-phase resume was attempted but removed due to complexity


class PMOrchestratorServiceV2:
    """
    Refactored orchestrator with atomic BR workflow
    Maintains all essential features from V1
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.temp_dir = Path(tempfile.mkdtemp(prefix="dh_exec_"))
        self.token_tracking = {}  # Per-agent token tracking
        
    async def execute_workflow(
        self,
        execution_id: int,
        project_id: int,
        selected_agents: List[str] = None,
        include_as_is: bool = False,
        sfdx_metadata: Optional[Dict] = None,
        resume_from: Optional[str] = None  # "phase2" to skip Phase 1
    ) -> Dict[str, Any]:
        """
        Main execution method - new atomic workflow
        
        Args:
            execution_id: Execution record ID
            project_id: Project ID
            selected_agents: List of worker agents to include (apex, lwc, admin, etc.)
            include_as_is: Whether to include As-Is analysis (requires SFDX)
            sfdx_metadata: Optional SFDX metadata for As-Is analysis
        """
        try:
            # Get project and execution
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"Project {project_id} not found")
                
            execution = self.db.query(Execution).filter(Execution.id == execution_id).first()
            if not execution:
                raise ValueError(f"Execution {execution_id} not found")
            
            # Initialize
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.now(timezone.utc)
            execution.agent_execution_status = self._init_agent_status(selected_agents or [])
            self.db.commit()
            
            
            # CORE-001: Audit log - execution started
            audit_service.log(
                actor_type=ActorType.SYSTEM,
                actor_id="orchestrator",
                action=ActionCategory.EXECUTION_START,
                entity_type="execution",
                entity_id=str(execution_id),
                project_id=project_id,
                execution_id=execution_id,
                extra_data={"selected_agents": selected_agents or [], "resume_from": resume_from}
            )
            # Initialize validation gates
            # self._initialize_validation_gates(execution_id)  # Disabled - model not available
            
            # Results container
            results = {
                "execution_id": execution_id,
                "project_id": project_id,
                "artifacts": {},
                "agent_outputs": {},
                "metrics": {
                    "total_tokens": 0,
                    "tokens_by_agent": {},
                    "execution_times": {}
                }
            }
            
            # Resume is only supported for Phase 1 (BR validation)
            # If resume_from is set, we skip Phase 1 and use validated BRs

            # ========================================
            # PHASE 1: Sophie PM - Extract BRs (skip if resuming)
            # ========================================
            if resume_from and resume_from not in (None, "phase1", "phase1_pm"):
                # Resuming after BR validation - load validated BRs from database
                logger.info(f"[Phase 1] SKIPPED - Resuming from Phase 2 with validated BRs")
                business_requirements = self._get_validated_brs(project_id)
                self._update_progress(execution, "pm", "completed", 15, f"Using {len(business_requirements)} validated BRs")
                self._save_checkpoint(execution, "phase1_pm")
                logger.info(f"[Phase 1] ✅ Loaded {len(business_requirements)} validated BRs from database")
                
                # Create br_result structure for compatibility with later phases
                br_result = {
                    "success": True,
                    "output": {
                        "content": {
                            "business_requirements": business_requirements,
                            "project_summary": project.description or project.name or ""
                        },
                        "metadata": {"tokens_used": 0}
                    }
                }
                results["artifacts"]["BR_EXTRACTION"] = br_result["output"]
                results["agent_outputs"]["pm_extract"] = br_result["output"]
            else:
                # Normal flow - extract BRs with Sophie
                logger.info(f"[Phase 1] Sophie PM - Extracting Business Requirements")
                self._update_progress(execution, "pm", "running", 5, "Extracting Business Requirements...")
            
                br_result = await self._run_agent(
                    agent_id="pm",
                    mode="extract_br",
                    input_data={"requirements": project.business_requirements or project.requirements_text or ""},
                    execution_id=execution_id,
                    project_id=project_id
                )
                
                if not br_result.get("success"):
                    raise Exception(f"BR extraction failed: {br_result.get('error')}")
                
                results["artifacts"]["BR_EXTRACTION"] = br_result["output"]
                results["agent_outputs"]["pm_extract"] = br_result["output"]
                business_requirements = br_result["output"]["content"].get("business_requirements", [])
                
                self._track_tokens("pm_extract", br_result["output"], results)
                self._save_deliverable(execution_id, "pm", "br_extraction", br_result["output"])
                
                logger.info(f"[Phase 1] ✅ Extracted {len(business_requirements)} Business Requirements")
                self._update_progress(execution, "pm", "completed", 15, f"Extracted {len(business_requirements)} BRs")
                self._save_checkpoint(execution, "phase1_pm")
                
                # ========================================
                # PAUSE FOR BR VALIDATION (if full workflow)
                # ========================================
                # Save extracted BRs to database for client validation
                self._save_extracted_brs(execution_id, project_id, business_requirements)
                
                # Check if we should pause for BR validation
                # Pause only if other agents (ba) are selected, meaning full workflow requested
                if 'ba' in (selected_agents or []):
                    logger.info(f"[BR Validation] Pausing for client validation - {len(business_requirements)} BRs to review")
                    execution.status = ExecutionStatus.WAITING_BR_VALIDATION
                    self.db.commit()
                    
                    return {
                        "execution_id": execution_id,
                        "project_id": project_id,
                        "status": "waiting_br_validation",
                        "brs_extracted": len(business_requirements),
                        "message": f"Extracted {len(business_requirements)} Business Requirements. Waiting for client validation.",
                        "artifacts": results["artifacts"],
                        "metrics": results["metrics"]
                    }
            # ========================================
            # GATE: Validate BRs before Phase 2
            # ========================================
            if not business_requirements:
                logger.error("[GATE] No Business Requirements available - cannot proceed to Phase 2")
                execution.status = ExecutionStatus.FAILED
                self.db.commit()
                raise Exception("No Business Requirements available. Please ensure Sophie extracts BRs first.")
            logger.info(f"[GATE] ✅ {len(business_requirements)} BRs available - proceeding to Phase 2")
            

            
            
            # ========================================
            # ========================================
            # PHASE 2: Olivia BA - Generate UCs per BR (DATABASE-FIRST)
            # ========================================
            logger.info(f"[Phase 2] Olivia BA - Generating Use Cases (database-first)")
            self._update_progress(execution, "ba", "running", 18, "Starting Use Case generation...")
            
            ba_tokens_total = 0
            ba_ucs_saved = 0
            
            # F-081: Process BRs in batches of 2 to reduce API calls
            BATCH_SIZE = 2
            total_batches = (len(business_requirements) + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(f"[Phase 2] Processing {len(business_requirements)} BRs in {total_batches} batches of {BATCH_SIZE}")
            
            batch_idx = 0
            for i in range(0, len(business_requirements), BATCH_SIZE):
                batch_brs = business_requirements[i:i + BATCH_SIZE]
                br_ids = [br.get("id", f"BR-{i+j+1:03d}") for j, br in enumerate(batch_brs)]
                progress = 18 + ((batch_idx + 1) / total_batches) * 27  # 18-45%
                
                self._update_progress(execution, "ba", "running", int(progress), 
                                      f"Processing {', '.join(br_ids)} (batch {batch_idx+1}/{total_batches})...")
                
                # Send batch or single BR based on count
                if len(batch_brs) > 1:
                    input_data = {"business_requirements": batch_brs}
                else:
                    input_data = {"business_requirement": batch_brs[0]}
                
                uc_result = await self._run_agent(
                    agent_id="ba",
                    input_data=input_data,
                    execution_id=execution_id,
                    project_id=project_id
                )
                
                # For compatibility with existing code, use first BR's id
                br = batch_brs[0]
                br_id = br_ids[0]
                batch_idx += 1
                
                if uc_result.get("success"):
                    # Extract metadata
                    metadata = uc_result["output"].get("metadata", {})
                    tokens_used = metadata.get("tokens_used", 0)
                    model_used = metadata.get("model", "unknown")
                    exec_time = metadata.get("execution_time_seconds", 0)
                    
                    # F-081: Handle batch results - tokens are for the whole batch
                    batch_tokens = tokens_used // len(batch_brs) if len(batch_brs) > 1 else tokens_used
                    
                    # SAVE IMMEDIATELY TO DATABASE (database-first)
                    saved = self._save_use_cases_from_result(
                        execution_id=execution_id,
                        br_id=br_id,
                        ba_result=uc_result,
                        tokens_used=tokens_used,
                        model_used=model_used,
                        execution_time=exec_time
                    )
                    
                    ba_ucs_saved += saved
                    ba_tokens_total += tokens_used
                    logger.info(f"[Phase 2] {br_id}: {saved} UCs saved to DB")
                else:
                    logger.warning(f"[Phase 2] {br_id}: Failed - {uc_result.get("error")}")
            
            # Get final stats from database
            uc_stats = self._get_use_case_count(execution_id)
            
            # Store summary in artifacts (for compatibility)
            results["artifacts"]["USE_CASES"] = {
                "artifact_id": "UC-001",
                "total_ucs": uc_stats["parsed"],
                "raw_saved": uc_stats["raw_saved"],
                "metadata": {"tokens_used": ba_tokens_total},
                "storage": "database-first",
                "table": "deliverable_items"
            }
            results["agent_outputs"]["ba"] = results["artifacts"]["USE_CASES"]
            results["metrics"]["tokens_by_agent"]["ba"] = ba_tokens_total
            results["metrics"]["total_tokens"] += ba_tokens_total
            
            # Save summary to deliverables (for backward compatibility)
            self._save_deliverable(execution_id, "ba", "use_cases", results["artifacts"]["USE_CASES"])
            
            logger.info(f"[Phase 2] Saved {uc_stats["parsed"]} UCs + {uc_stats["raw_saved"]} raw to database")
            self._update_progress(execution, "ba", "completed", 42, f"Generated {uc_stats["parsed"]} UCs")
            self._save_checkpoint(execution, "phase2_ba")

            # ========================================
            # GATE: Validate UCs before Phase 2.5
            # ========================================
            all_ucs_count = uc_stats.get("parsed", 0) + uc_stats.get("raw_saved", 0)
            if all_ucs_count == 0:
                logger.error("[GATE] No Use Cases generated - cannot proceed")
                execution.status = ExecutionStatus.FAILED
                self.db.commit()
                raise Exception("No Use Cases generated. Business Analyst failed to produce outputs.")
            logger.info(f"[GATE] ✅ {all_ucs_count} UCs available - proceeding to Phase 2.5")
            
            
            # ========================================
            # PHASE 2.5: Emma Research Analyst - UC Digest Generation
            # ========================================
            # Emma analyzes ALL UCs and creates a structured digest for Marcus
            # This replaces the old approach of passing raw UCs (limited to 15)
            logger.info(f"[Phase 2.5] Emma Research Analyst - Generating UC Digest")
            self._update_progress(execution, "research_analyst", "running", 43, "Analyzing Use Cases...")
            
            # Get ALL use cases (no limit) and business requirements
            all_use_cases = self._get_use_cases(execution_id, limit=None)
            
            emma_result = await self._run_agent(
                agent_id="research_analyst",
                mode="analyze",
                input_data={
                    "use_cases": all_use_cases,
                    "business_requirements": business_requirements
                },
                execution_id=execution_id,
                project_id=project_id
            )
            
            uc_digest = {}
            emma_tokens = 0
            
            if emma_result.get("success"):
                uc_digest = emma_result["output"].get("content", {}).get("digest", {})
                emma_tokens = emma_result["output"].get("metadata", {}).get("tokens_used", 0)
                
                # Save Emma's deliverable
                self._save_deliverable(execution_id, "research_analyst", "uc_digest", emma_result["output"])
                results["artifacts"]["UC_DIGEST"] = emma_result["output"]
                results["agent_outputs"]["research_analyst"] = emma_result["output"]
                results["metrics"]["tokens_by_agent"]["research_analyst"] = emma_tokens
                results["metrics"]["total_tokens"] += emma_tokens
                
                logger.info(f"[Phase 2.5] ✅ UC Digest generated ({len(all_use_cases)} UCs analyzed, {emma_tokens} tokens)")
                self._update_progress(execution, "research_analyst", "completed", 45, f"Analyzed {len(all_use_cases)} UCs")
                self._save_checkpoint(execution, "phase2_5_emma")
            else:
                logger.warning(f"[Phase 2.5] ⚠️ Emma failed: {emma_result.get('error', 'Unknown error')} - Marcus will use raw UCs")
                self._update_progress(execution, "research_analyst", "failed", 45, "Analysis failed - using fallback")
                # Fallback: Marcus will receive raw UCs (old behavior)
            
            # PHASE 3: Marcus Architect - 4 Sequential Calls
            # ========================================
            logger.info(f"[Phase 3] Marcus Architect - Solution Design")
            self._update_progress(execution, "architect", "running", 46, "Retrieving Salesforce metadata...")
            
            # 3.0: Get Salesforce org metadata FIRST
            sf_metadata_result = await self._get_salesforce_metadata(execution_id)
            if sf_metadata_result["success"]:
                org_metadata = sf_metadata_result["full_metadata"]
                org_summary = sf_metadata_result["summary"]
                logger.info(f"[Phase 3.0] ✅ Salesforce metadata retrieved: {org_summary.get('org_edition', 'Unknown')} edition")
            else:
                org_metadata = {}
                org_summary = {"note": "Metadata retrieval failed - proceeding with empty state"}
                logger.warning(f"[Phase 3.0] ⚠️ Metadata retrieval failed: {sf_metadata_result.get('error', 'Unknown')}")
            
            self._update_progress(execution, "architect", "running", 48, "Starting architecture analysis...")
            architect_tokens = 0
            
            # HELPER: Validate UC Digest is properly parsed (ADDED 19/12/2025)
            def is_digest_valid(digest: dict) -> bool:
                """Check if UC Digest was properly parsed (not just raw data)"""
                if not digest:
                    return False
                # Check for parse error indicators
                if digest.get('parse_error') or digest.get('raw'):
                    return False
                # Check for required structure
                if digest.get('by_requirement'):
                    return True
                return False
            
            # Validate UC Digest before using it
            uc_digest_valid = is_digest_valid(uc_digest)
            if uc_digest and not uc_digest_valid:
                logger.warning(f"[Phase 3] ⚠️ UC Digest is corrupted (parse_error or missing by_requirement), falling back to raw UCs")
                logger.warning(f"[Phase 3]    Digest keys: {list(uc_digest.keys())}")
            
            # 3.1: As-Is Analysis (Analyze current Salesforce org - ALWAYS RUN)
            self._update_progress(execution, "architect", "running", 50, "Analyzing Salesforce org...")
            
            asis_result = await self._run_agent(
                agent_id="architect",
                mode="as_is",
                input_data={
                    "sfdx_metadata": json.dumps(org_metadata),
                    "org_summary": org_summary,
                    "org_info": org_summary
                },
                execution_id=execution_id,
                project_id=project_id
            )
            
            if asis_result.get("success"):
                results["artifacts"]["AS_IS"] = asis_result["output"]
                architect_tokens += asis_result["output"]["metadata"].get("tokens_used", 0)
                self._save_deliverable(execution_id, "architect", "as_is", asis_result["output"])
                logger.info(f"[Phase 3.1] ✅ As-Is Analysis (ASIS-001)")
            else:
                results["artifacts"]["AS_IS"] = {"artifact_id": "ASIS-001", "content": {}, "note": "Org analysis pending"}
                logger.warning(f"[Phase 3.1] ⚠️ As-Is Analysis failed, using placeholder")
            
            # Gap Analysis moved to Phase 3.4 (after Emma Validate)
            
            # Gap success handling moved to Phase 3.4
            
            # ========================================
            # 3.2: Solution Design (Design target architecture) - REORDERED
            # ========================================
            # Marcus designs the solution BEFORE gap analysis
            # This way Gap Analysis compares As-Is vs a defined target
            self._update_progress(execution, "architect", "running", 56, "Designing solution architecture...")
            
            # Use valid digest or fallback to raw UCs
            design_uc_digest = uc_digest if uc_digest_valid else None
            design_use_cases = [] if uc_digest_valid else self._get_use_cases(execution_id, limit=50)
            
            if design_uc_digest:
                logger.info(f"[Phase 3.2] Using UC Digest ({len(design_uc_digest.get('by_requirement', {}))} BRs)")
            else:
                logger.info(f"[Phase 3.2] Using raw UCs ({len(design_use_cases)} UCs)")
            
            design_result = await self._run_agent(
                agent_id="architect",
                mode="design",
                input_data={
                    "project_summary": br_result["output"]["content"].get("project_summary", ""),
                    "uc_digest": design_uc_digest,
                    "use_cases": design_use_cases,
                    "as_is": results["artifacts"].get("AS_IS", {}).get("content", {})
                },
                execution_id=execution_id,
                project_id=project_id
            )
            
            if design_result.get("success"):
                results["artifacts"]["ARCHITECTURE"] = design_result["output"]
                architect_tokens += design_result["output"]["metadata"].get("tokens_used", 0)
                self._save_deliverable(execution_id, "architect", "solution_design", design_result["output"])
                logger.info(f"[Phase 3.2] ✅ Solution Design (ARCH-001)")
                
                # ========================================
                # PHASE 3.3: Emma Validate (REORDERED) (Coverage Check)
                # ========================================
                # Emma validates that the solution design covers all UCs
                # If coverage < 95%, Marcus will revise with gaps
                
                self._update_progress(execution, "research_analyst", "running", 68, "Validating UC coverage...")
                
                # Prepare validation input
                all_use_cases = self._get_use_cases(execution_id, limit=None)
                solution_design = results["artifacts"]["ARCHITECTURE"].get("content", {})
                
                validate_result = await self._run_agent(
                    agent_id="research_analyst",
                    mode="validate",
                    input_data={
                        "solution_design": solution_design,
                        "use_cases": all_use_cases,
                        "uc_digest": uc_digest
                    },
                    execution_id=execution_id,
                    project_id=project_id
                )
                
                emma_validate_tokens = 0
                if validate_result.get("success"):
                    coverage_report = validate_result["output"].get("content", {})
                    coverage_pct = coverage_report.get("coverage_percentage", 0)
                    emma_validate_tokens = validate_result["output"].get("metadata", {}).get("tokens_used", 0)
                    
                    self._save_deliverable(execution_id, "research_analyst", "coverage_report", validate_result["output"])
                    results["artifacts"]["COVERAGE"] = validate_result["output"]
                    
                    logger.info(f"[Phase 3.3] ✅ Emma Validate - Coverage: {coverage_pct}%")
                    
                    # Coverage loop: if < 95%, ask Marcus to revise
                    if coverage_pct < 95:
                        gaps = coverage_report.get("gaps", [])
                        uncovered_ucs = coverage_report.get("uncovered_use_cases", [])
                        
                        logger.info(f"[Phase 3.3] ⚠️ Coverage insufficient ({coverage_pct}%), requesting revision...")
                        self._update_progress(execution, "architect", "running", 70, f"Revising design (coverage: {coverage_pct}%)...")
                        
                        # Marcus revision with gaps
                        revision_result = await self._run_agent(
                            agent_id="architect",
                            mode="design",
                            input_data={
                                "project_summary": br_result["output"]["content"].get("project_summary", ""),
                                "uc_digest": uc_digest,
                                "use_cases": [],
                                "gaps": results["artifacts"].get("GAP", {}).get("content", {}).get("gaps", []),
                                "as_is": results["artifacts"].get("AS_IS", {}).get("content", {}),
                                # Add coverage gaps for revision
                                "coverage_gaps": gaps,
                                "uncovered_use_cases": uncovered_ucs,
                                "revision_request": f"Please revise the solution design to address {len(gaps)} coverage gaps affecting {len(uncovered_ucs)} use cases."
                            },
                            execution_id=execution_id,
                            project_id=project_id
                        )
                        
                        if revision_result.get("success"):
                            results["artifacts"]["ARCHITECTURE"] = revision_result["output"]
                            architect_tokens += revision_result["output"]["metadata"].get("tokens_used", 0)
                            self._save_deliverable(execution_id, "architect", "solution_design_revised", revision_result["output"])
                            logger.info(f"[Phase 3.3] ✅ Solution Design Revised (after validation)")
                        else:
                            logger.warning(f"[Phase 3.3] ⚠️ Revision failed, keeping original design")
                    
                    results["metrics"]["tokens_by_agent"]["research_analyst"] = results["metrics"]["tokens_by_agent"].get("research_analyst", 0) + emma_validate_tokens
                    results["metrics"]["total_tokens"] += emma_validate_tokens

                    self._update_progress(execution, "research_analyst", "completed", 72, "Coverage validated")

                else:
                    logger.warning(f"[Phase 3.3] ⚠️ Emma Validate failed: {validate_result.get('error', 'Unknown')}")
                    self._update_progress(execution, "research_analyst", "completed", 72, "Coverage check skipped")
                    
                # ========================================
                # 3.4: Gap Analysis (Compare As-Is vs Final Design) - REORDERED
                # ========================================
                # NOW we do Gap Analysis with the FINAL validated design
                self._update_progress(execution, "architect", "running", 70, "Analyzing implementation gaps...")
                
                # Get the final solution design (original or revised)
                final_solution_design = results["artifacts"]["ARCHITECTURE"].get("content", {})
                
                gap_result = await self._run_agent(
                    agent_id="architect",
                    mode="gap",
                    input_data={
                        "requirements": br_result["output"]["content"].get("business_requirements", []),
                        "uc_digest": design_uc_digest,
                        "use_cases": design_use_cases,
                        "as_is": results["artifacts"].get("AS_IS", {}).get("content", {}),
                        # FIXED: Pass the solution design for proper gap analysis
                        "solution_design": final_solution_design
                    },
                    execution_id=execution_id,
                    project_id=project_id
                )
                
                if gap_result.get("success"):
                    results["artifacts"]["GAP"] = gap_result["output"]
                    architect_tokens += gap_result["output"]["metadata"].get("tokens_used", 0)
                    self._save_deliverable(execution_id, "architect", "gap_analysis", gap_result["output"])
                    logger.info(f"[Phase 3.4] ✅ Gap Analysis (GAP-001)")
                else:
                    results["artifacts"]["GAP"] = {"artifact_id": "GAP-001", "content": {"gaps": []}}
                    logger.warning(f"[Phase 3.4] ⚠️ Gap Analysis failed")
                
                # ========================================
                # 3.5: WBS (Break down gaps into tasks)
                # ========================================
                self._update_progress(execution, "architect", "running", 74, "Creating work breakdown...")
                
                wbs_result = await self._run_agent(
                    agent_id="architect",
                    mode="wbs",
                    input_data={
                        "gaps": results["artifacts"].get("GAP", {}).get("content", {}),
                        "architecture": results["artifacts"].get("ARCHITECTURE", {}).get("content", {}),
                        "constraints": project.compliance_requirements or project.architecture_notes or ""
                    },
                    execution_id=execution_id,
                    project_id=project_id
                )
                
                if wbs_result.get("success"):
                    results["artifacts"]["WBS"] = wbs_result["output"]
                    architect_tokens += wbs_result["output"]["metadata"].get("tokens_used", 0)
                    self._save_deliverable(execution_id, "architect", "wbs", wbs_result["output"])
                    logger.info(f"[Phase 3.5] ✅ WBS (WBS-001)")
                else:
                    logger.warning(f"[Phase 3.5] ⚠️ WBS generation failed: {wbs_result.get('error', 'Unknown')}")


            else:
                results["artifacts"]["ARCHITECTURE"] = {"artifact_id": "ARCH-001", "content": {}}
                logger.warning(f"[Phase 3.2] ⚠️ Solution Design failed: {design_result.get('error', 'Unknown error')}")
            
            
            results["agent_outputs"]["architect"] = {
                "design": results["artifacts"].get("ARCHITECTURE"),
                "as_is": results["artifacts"].get("AS_IS"),
                "gap": results["artifacts"].get("GAP"),
                "wbs": results["artifacts"].get("WBS")
            }
            results["metrics"]["tokens_by_agent"]["architect"] = architect_tokens
            results["metrics"]["total_tokens"] += architect_tokens
            
            self._update_progress(execution, "architect", "completed", 75, "Architecture complete")
            self._save_checkpoint(execution, "phase3_wbs")
            
            # ========================================
            # PHASE 4: SDS Expert Agents (Conditional)
            # ========================================
            # These experts enrich the SDS with specialized sections:
            # - Aisha (Data): Data Migration Strategy
            # - Lucas (Trainer): Training & Change Management Plan  
            # - Elena (QA): Test Strategy & QA Approach
            # - Jordan (DevOps): CI/CD & Deployment Strategy
            # ORCH-01: Only execute agents that were selected by the user
            
            ALL_SDS_EXPERTS = ["data", "trainer", "qa", "devops"]
            
            # Filter to only include experts selected by user (if selection provided)
            if selected_agents:
                SDS_EXPERTS = [agent for agent in ALL_SDS_EXPERTS if agent in selected_agents]
                skipped = [agent for agent in ALL_SDS_EXPERTS if agent not in selected_agents]
                if skipped:
                    logger.info(f"[Phase 4] ⏭️ Skipping non-selected agents: {skipped}")
            else:
                # No selection = run all (backward compatibility)
                SDS_EXPERTS = ALL_SDS_EXPERTS
            
            if SDS_EXPERTS:
                logger.info(f"[Phase 4] SDS Expert Agents to execute: {SDS_EXPERTS}")
            else:
                logger.info(f"[Phase 4] No SDS Expert Agents selected - skipping Phase 4")
            
            expert_progress_start = 75
            expert_progress_end = 90
            
            # Common context for all experts
            common_context = {
                "project": {
                    "name": project.name,
                    "description": project.description or "",
                    "requirements": project.business_requirements or project.requirements_text or "",
                    "product": project.salesforce_product,
                    "compliance": project.compliance_requirements or ""
                },
                "architecture": results["artifacts"].get("ARCHITECTURE", {}).get("content", {}),
                "use_cases": self._get_use_cases(execution_id, 15),
                "gaps": results["artifacts"].get("GAP", {}).get("content", {}).get("gaps", []),
                "wbs": results["artifacts"].get("WBS", {}).get("content", {})
            }
            
            # ORCH-02: Parallel execution for SDS experts
            async def run_sds_expert(agent_id: str) -> dict:
                """Run a single SDS expert agent"""
                agent_name = AGENT_CONFIG[agent_id]["display_name"]
                self._update_progress(execution, agent_id, "running", 80, f"{agent_name} creating specifications...")
                
                # Build expert-specific input
                expert_input = dict(common_context)
                focus_map = {
                    "data": "data_migration",
                    "trainer": "training_adoption",
                    "qa": "quality_assurance",
                    "devops": "deployment_cicd"
                }
                expert_input["focus"] = focus_map.get(agent_id, agent_id)
                
                try:
                    # PRPT-07: Pass mode to trainer (sds_strategy)
                    # PRPT-07: Mode for each SDS expert
                    mode_map = {
                        "trainer": "sds_strategy",
                        "qa": "spec",
                        "devops": "spec",
                        "data": "spec"
                    }
                    agent_mode = mode_map.get(agent_id, "spec")
                    expert_result = await self._run_agent(
                        agent_id=agent_id,
                        input_data=expert_input,
                        execution_id=execution_id,
                        project_id=project_id,
                        mode=agent_mode
                    )
                    return {"agent_id": agent_id, "result": expert_result}
                except Exception as e:
                    return {"agent_id": agent_id, "result": {"success": False, "error": str(e)}}
            
            if SDS_EXPERTS:
                if PARALLEL_MODE.get("sds_experts", False):
                    # Parallel execution
                    logger.info(f"[Phase 4] 🚀 Running {len(SDS_EXPERTS)} SDS experts in PARALLEL")
                    tasks = [run_sds_expert(agent_id) for agent_id in SDS_EXPERTS]
                    expert_results = await asyncio.gather(*tasks)
                else:
                    # Sequential execution (fallback)
                    logger.info(f"[Phase 4] Running {len(SDS_EXPERTS)} SDS experts sequentially")
                    expert_results = []
                    for agent_id in SDS_EXPERTS:
                        result = await run_sds_expert(agent_id)
                        expert_results.append(result)
                
                # Process results
                for item in expert_results:
                    agent_id = item["agent_id"]
                    expert_result = item["result"]
                    agent_name = AGENT_CONFIG[agent_id]["display_name"]
                    
                    if expert_result.get("success"):
                        results["agent_outputs"][agent_id] = expert_result["output"]
                        results["artifacts"][f"{agent_id.upper()}_SPECS"] = expert_result["output"]
                        self._track_tokens(agent_id, expert_result["output"], results)
                        self._save_deliverable(execution_id, agent_id, f"{agent_id}_specifications", expert_result["output"])
                        logger.info(f"[Phase 4] ✅ {agent_name} completed")
                        self._update_progress(execution, agent_id, "completed", 88, f"{agent_name} done")
                    else:
                        logger.warning(f"[Phase 4] ⚠️ {agent_name} failed: {expert_result.get('error')}")
                        self._update_progress(execution, agent_id, "failed", 88, f"Failed: {expert_result.get('error', 'Unknown')[:50]}")
            
            # ========================================
            # PHASE 5: Emma Write_SDS - Generate Professional SDS Document
            # ========================================
            sds_markdown = ""
            logger.info(f"[Phase 5] Emma Research Analyst - Writing SDS Document")
            self._update_progress(execution, "research_analyst", "running", 88, "Writing SDS Document...")
            # DEBUG: Log WBS data availability
            wbs_artifact = results["artifacts"].get("WBS", {})
            logger.info(f"[Phase 5 DEBUG] WBS artifact keys: {list(wbs_artifact.keys())}")
            wbs_content = wbs_artifact.get("content", {})
            logger.info(f"[Phase 5 DEBUG] WBS content keys: {list(wbs_content.keys())}")
            if wbs_content:
                phases_count = len(wbs_content.get('phases', []))
                logger.info(f"[Phase 5 DEBUG] WBS has {phases_count} phases")
            else:
                logger.warning("[Phase 5 DEBUG] ⚠️ WBS content is EMPTY!")
            

            
            # Prepare all sources for Emma write_sds
            emma_write_input = {
                "project_info": {
                    "name": project.name,
                    "description": project.description or "",
                    "client_name": getattr(project, 'client_name', '') or "",
                    "objectives": project.architecture_notes or ""
                },
                "business_requirements": self._get_business_requirements_for_sds(execution_id),
                "use_cases": self._get_use_cases(execution_id, limit=None),
                "uc_digest": results["artifacts"].get("UC_DIGEST", {}).get("content", {}),
                "solution_design": results["artifacts"].get("ARCHITECTURE", {}).get("content", {}),
                "coverage_report": results["artifacts"].get("COVERAGE", {}).get("content", {}),
                "wbs": results["artifacts"].get("WBS", {}).get("content", {}),
                "qa_specs": results["agent_outputs"].get("qa", {}).get("content", {}) if results["agent_outputs"].get("qa") else {},
                "devops_specs": results["agent_outputs"].get("devops", {}).get("content", {}) if results["agent_outputs"].get("devops") else {},
                "training_specs": results["agent_outputs"].get("trainer", {}).get("content", {}) if results["agent_outputs"].get("trainer") else {},
                "data_specs": results["agent_outputs"].get("data", {}).get("content", {}) if results["agent_outputs"].get("data") else {}
            }
            
            emma_write_result = await self._run_agent(
                agent_id="research_analyst",
                mode="write_sds",
                input_data=emma_write_input,
                execution_id=execution_id,
                project_id=project_id
            )
            
            emma_write_tokens = 0
            
            if emma_write_result.get("success"):
                emma_output = emma_write_result["output"]
                emma_write_tokens = emma_output.get("metadata", {}).get("tokens_used", 0)
                sds_markdown = emma_output.get("content", {}).get("document", "")
                
                self._save_deliverable(execution_id, "research_analyst", "sds_document", emma_output)
                results["artifacts"]["SDS"] = emma_output
                results["metrics"]["tokens_by_agent"]["research_analyst"] = results["metrics"]["tokens_by_agent"].get("research_analyst", 0) + emma_write_tokens
                results["metrics"]["total_tokens"] += emma_write_tokens
                
                logger.info(f"[Phase 5] ✅ Emma SDS Document generated ({len(sds_markdown)} chars)")
            else:
                error_msg = emma_write_result.get('error', 'Unknown error')
                logger.error(f"[Phase 5] ❌ Emma write_sds failed: {error_msg}")
                self._update_progress(execution, "research_analyst", "failed", 92, f"Write SDS failed: {error_msg[:50]}")
                raise Exception(f"SDS Document generation failed: {error_msg}")
            
            self._update_progress(execution, "research_analyst", "completed", 92, "SDS Document written")
            self._save_checkpoint(execution, "phase5_write_sds")
            
            # ========================================
            # PHASE 6: Export SDS to DOCX/PDF
            # ========================================
            logger.info(f"[Phase 6] Exporting SDS Document")
            self._update_progress(execution, "pm", "running", 94, "Exporting SDS Document...")
            
            # Generate SDS file (DOCX/PDF) from Emma's markdown
            # Note: sds_markdown is guaranteed to exist (Emma failure raises exception above)
            
            # Save markdown first
            md_path = f"/tmp/sds_{execution_id}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(sds_markdown)
            results["sds_markdown_path"] = md_path
            
            # Convert to DOCX using document generator
            try:
                sds_path = await self._generate_sds_document(
                    project=project,
                    agent_outputs=results["agent_outputs"],
                    artifacts=results["artifacts"],
                    execution_id=execution_id,
                    sds_markdown=sds_markdown
                )
                results["sds_path"] = sds_path
                execution.sds_document_path = sds_path
                logger.info(f"[Phase 6] ✅ SDS Document: {sds_path}")
            except Exception as e:
                logger.error(f"[Phase 6] DOCX export failed: {e}")
                # Keep markdown as the output (no fallback to old generator)
                results["sds_path"] = md_path
                execution.sds_document_path = md_path
                logger.info(f"[Phase 6] ⚠️ Using Markdown instead: {md_path}")
            
            self._update_progress(execution, "pm", "completed", 98, "SDS Document exported")
            self._save_checkpoint(execution, "phase6_export")
            
            # ========================================
            # FINALIZE
            # ========================================
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            execution.total_tokens_used = results["metrics"]["total_tokens"]
            
            # P7: Atomic finalization — status + SDS version + project update in one commit
            self._create_sds_version(project, execution, results.get("sds_path"))
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            
            logger.info(f"[Complete] Execution {execution_id} finished")
            logger.info(f"[Metrics] Total tokens: {results['metrics']['total_tokens']}")
            logger.info(f"[Metrics] By agent: {results['metrics']['tokens_by_agent']}")
            
            
            # CORE-001: Audit log - execution completed
            audit_service.log(
                actor_type=ActorType.SYSTEM,
                actor_id="orchestrator",
                action=ActionCategory.EXECUTION_COMPLETE,
                entity_type="execution",
                entity_id=str(execution_id),
                project_id=project_id,
                execution_id=execution_id,
                extra_data={"total_tokens": results["metrics"]["total_tokens"], "artifacts_count": len(results["artifacts"])}
            )
            return {
                "success": True,
                "execution_id": execution_id,
                "artifacts_count": len(results["artifacts"]),
                "total_tokens": results["metrics"]["total_tokens"],
                "tokens_by_agent": results["metrics"]["tokens_by_agent"],
                "sds_path": results.get("sds_path")
            }
            
        except Exception as e:
            logger.error(f"Execution {execution_id} failed: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # CORE-001: Audit log - execution failed
            audit_service.log(
                actor_type=ActorType.SYSTEM,
                actor_id="orchestrator",
                action=ActionCategory.EXECUTION_FAIL,
                entity_type="execution",
                entity_id=str(execution_id),
                project_id=project_id,
                execution_id=execution_id,
                success="false",
                error_message=str(e)
            )
            
            # P7: Error state commit — must not fail silently or leave dirty session
            try:
                execution.status = ExecutionStatus.FAILED
                # error_message not in model, using logs instead
                if execution.logs:
                    import json as json_module
                    try:
                        log_list = json_module.loads(execution.logs)
                    except Exception:
                        log_list = []
                else:
                    log_list = []
                    import json as json_module
                log_list.append({"type": "error", "message": str(e), "timestamp": datetime.now(timezone.utc).isoformat()})
                execution.logs = json_module.dumps(log_list)
                execution.completed_at = datetime.now(timezone.utc)
                self.db.commit()
            except Exception as commit_err:
                logger.error(f"Failed to commit FAILED status: {commit_err}")
                self.db.rollback()
            
            return {
                "success": False,
                "execution_id": execution_id,
                "error": str(e)
            }
        finally:
            # Cleanup temp files
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir, ignore_errors=True)


    async def _get_salesforce_metadata(self, execution_id: int) -> Dict[str, Any]:
        """
        Retrieve Salesforce org metadata for Marcus as_is analysis.
        
        Returns:
            Dict with:
            - summary: Condensed info for Marcus prompt
            - full_metadata: Complete data stored in DB
            - success: bool
        """
        logger.info(f"[Metadata] Retrieving Salesforce org metadata...")
        
        metadata = {
            "org_info": {},
            "metadata_types": [],
            "objects": [],
            "installed_packages": [],
            "limits": {},
            "retrieved_at": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # 1. Get org info (edition, version, features)
            org_cmd = f"sf org display --target-org {salesforce_config.org_alias} --json"
            org_result = subprocess.run(org_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if org_result.returncode == 0:
                org_data = json.loads(org_result.stdout)
                metadata["org_info"] = org_data.get("result", {})
                logger.info(f"[Metadata] ✅ Org info retrieved: {metadata['org_info'].get('edition', 'Unknown')} edition")
            
            # 2. List available metadata types
            types_cmd = f"sf org list metadata-types --api-version {salesforce_config.api_version} --target-org {salesforce_config.org_alias} --json"
            types_result = subprocess.run(types_cmd, shell=True, capture_output=True, text=True, timeout=60)
            if types_result.returncode == 0:
                types_data = json.loads(types_result.stdout)
                metadata["metadata_types"] = types_data.get("result", {}).get("metadataObjects", [])
                logger.info(f"[Metadata] ✅ {len(metadata['metadata_types'])} metadata types available")
            
            # 3. List all objects (standard + custom)
            objects_cmd = f"sf sobject list --sobject-type all --target-org {salesforce_config.org_alias} --json"
            objects_result = subprocess.run(objects_cmd, shell=True, capture_output=True, text=True, timeout=60)
            if objects_result.returncode == 0:
                objects_data = json.loads(objects_result.stdout)
                metadata["objects"] = objects_data.get("result", [])
                custom_count = len([o for o in metadata["objects"] if o.endswith("__c")])
                logger.info(f"[Metadata] ✅ {len(metadata['objects'])} objects ({custom_count} custom)")
            
            # 4. List installed packages (ISV)
            pkg_cmd = f"sf package installed list --target-org {salesforce_config.org_alias} --json"
            pkg_result = subprocess.run(pkg_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if pkg_result.returncode == 0:
                pkg_data = json.loads(pkg_result.stdout)
                metadata["installed_packages"] = pkg_data.get("result", [])
                logger.info(f"[Metadata] ✅ {len(metadata['installed_packages'])} installed packages")
            
            # 5. Get org limits
            limits_cmd = f"sf limits api display --target-org {salesforce_config.org_alias} --json"
            limits_result = subprocess.run(limits_cmd, shell=True, capture_output=True, text=True, timeout=30)
            if limits_result.returncode == 0:
                limits_data = json.loads(limits_result.stdout)
                # Only keep key limits
                all_limits = limits_data.get("result", [])
                key_limits = ["DailyApiRequests", "DataStorageMB", "FileStorageMB", "DailyAsyncApexExecutions"]
                metadata["limits"] = {l["name"]: l for l in all_limits if l.get("name") in key_limits}
                logger.info(f"[Metadata] ✅ Org limits retrieved")
            
            # 6. BUG-047: Describe key standard objects (Case, Contact, Account, Lead, Opportunity)
            # This gives Marcus the actual fields available, preventing redundant custom fields
            key_objects = ["Case", "Contact", "Account", "Lead", "Opportunity"]
            metadata["object_fields"] = {}
            for obj_name in key_objects:
                try:
                    describe_cmd = f"sf sobject describe --sobject {obj_name} --target-org {salesforce_config.org_alias} --json"
                    describe_result = subprocess.run(describe_cmd, shell=True, capture_output=True, text=True, timeout=30)
                    if describe_result.returncode == 0:
                        describe_data = json.loads(describe_result.stdout)
                        fields = describe_data.get("result", {}).get("fields", [])
                        # Extract key field info (name, type, label, nillable, createable)
                        metadata["object_fields"][obj_name] = [
                            {
                                "name": f.get("name"),
                                "type": f.get("type"),
                                "label": f.get("label"),
                                "nillable": f.get("nillable"),
                                "createable": f.get("createable"),
                                "referenceTo": f.get("referenceTo", [])
                            }
                            for f in fields
                            if f.get("createable") or f.get("name") in ["Id", "Name", "CreatedDate", "LastModifiedDate"]
                        ]
                        logger.info(f"[Metadata] ✅ {obj_name}: {len(metadata['object_fields'][obj_name])} fields")
                except Exception as e:
                    logger.warning(f"[Metadata] ⚠️ Could not describe {obj_name}: {e}")
            
            # Create summary for Marcus
            summary = self._create_metadata_summary(metadata)
            
            # Store full metadata in DB as a deliverable
            self._save_deliverable(
                execution_id=execution_id,
                agent_id="system",
                deliverable_type="salesforce_metadata",
                content={
                    "full_metadata": metadata,
                    "summary": summary
                }
            )
            logger.info(f"[Metadata] ✅ Full metadata stored in DB")
            
            return {
                "success": True,
                "summary": summary,
                "full_metadata": metadata
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"[Metadata] ❌ Timeout retrieving metadata")
            return {"success": False, "summary": {}, "full_metadata": {}, "error": "Timeout"}
        except Exception as e:
            logger.error(f"[Metadata] ❌ Error: {str(e)}")
            return {"success": False, "summary": {}, "full_metadata": {}, "error": str(e)}
    
    def _create_metadata_summary(self, metadata: Dict) -> Dict:
        """Create a condensed summary of metadata for Marcus prompt"""
        org_info = metadata.get("org_info", {})
        
        summary = {
            "org_edition": org_info.get("edition", "Unknown"),
            "org_type": org_info.get("instanceName", "Unknown"),
            "api_version": org_info.get("apiVersion", salesforce_config.api_version),
            "username": org_info.get("username", ""),
            "instance_url": org_info.get("instanceUrl", ""),
            
            # Object counts
            "total_objects": len(metadata.get("objects", [])),
            "custom_objects": [o for o in metadata.get("objects", []) if o.endswith("__c")],
            "custom_object_count": len([o for o in metadata.get("objects", []) if o.endswith("__c")]),
            
            # Installed packages
            "installed_packages": [
                {"name": p.get("SubscriberPackageName", ""), "namespace": p.get("SubscriberPackageNamespace", "")}
                for p in metadata.get("installed_packages", [])
            ],
            
            # Key limits
            "limits": {
                name: {"max": info.get("max", 0), "remaining": info.get("remaining", 0)}
                for name, info in metadata.get("limits", {}).items()
            },
            
            # Metadata capabilities
            "available_metadata_types": len(metadata.get("metadata_types", [])),
            
            # BUG-047: Include standard object fields for Marcus
            "standard_object_fields": {
                obj_name: [
                    {"name": f["name"], "type": f["type"], "label": f["label"]}
                    for f in fields[:50]  # Top 50 fields per object
                ]
                for obj_name, fields in metadata.get("object_fields", {}).items()
            },
            
            # Note for Marcus
            "note": "Standard object fields (Case, Contact, Account, Lead, Opportunity) included above. Use these before creating custom fields."
        }
        
        return summary


    async def _run_agent_direct(
        self,
        agent_id: str,
        input_data: Dict,
        execution_id: int,
        project_id: int,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """C1.1: Run a migrated agent via direct import (no subprocess).
        
        Replaces the subprocess flow with direct class instantiation.
        The agent receives input_data as a JSON string (matching the subprocess
        contract where the agent reads the input file as raw text).
        """
        try:
            agent_class = MIGRATED_AGENTS[agent_id]
            agent_instance = agent_class()
            
            # Build task_data matching agent class interface
            # input_content = JSON string of input_data (same as subprocess reads from file)
            task_data = {
                "mode": mode or "spec",
                "input_content": json.dumps(input_data, ensure_ascii=False),
                "execution_id": execution_id,
                "project_id": project_id,
            }
            
            # Dynamic timeout (same as subprocess version)
            timeout_seconds = 300  # Default 5 min
            if agent_id == "research_analyst":
                timeout_seconds = 3600  # 60 min for Emma (large projects)
            elif agent_id == "architect":
                timeout_seconds = 900  # 15 min for Marcus
            
            config = AGENT_CONFIG.get(agent_id, {})
            display_name = config.get("display_name", agent_id)
            logger.info(f"[C1.1] Running {display_name} via direct import (mode={mode})")
            
            # Run in thread pool with timeout (agents do blocking LLM calls)
            result = await asyncio.wait_for(
                asyncio.to_thread(agent_instance.run, task_data),
                timeout=timeout_seconds
            )
            
            if result.get("success"):
                return {"success": True, "output": result}
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"[C1.1] Agent {agent_id} failed: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except asyncio.TimeoutError:
            logger.error(f"[C1.1] Agent {agent_id} timed out ({timeout_seconds}s)")
            return {"success": False, "error": f"Timeout ({timeout_seconds // 60} min)"}
        except Exception as e:
            logger.error(f"[C1.1] Agent {agent_id} direct import error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _run_agent(
        self,
        agent_id: str,
        input_data: Dict,
        execution_id: int,
        project_id: int,
        mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run an agent script and return the result"""
        try:
            # C1.1: Adapter Pattern — route to direct import for migrated agents
            if DIRECT_IMPORT_AVAILABLE and agent_id in MIGRATED_AGENTS:
                return await self._run_agent_direct(
                    agent_id, input_data, execution_id, project_id, mode
                )
            
            # Legacy subprocess fallback (for non-migrated agents)
            config = AGENT_CONFIG.get(agent_id)
            if not config:
                return {"success": False, "error": f"Unknown agent: {agent_id}"}
            
            # Write input to temp file
            input_file = self.temp_dir / f"input_{agent_id}_{mode or 'default'}_{execution_id}.json"
            output_file = self.temp_dir / f"output_{agent_id}_{mode or 'default'}_{execution_id}.json"
            
            with open(input_file, "w") as f:
                json.dump(input_data, f, indent=2, ensure_ascii=False)
            
            # Build command
            cmd = [
                "python3",
                str(AGENTS_PATH / config["script"]),
                "--input", str(input_file),
                "--output", str(output_file),
                "--execution-id", str(execution_id),
                "--project-id", str(project_id)
            ]
            
            if mode:
                cmd.extend(["--mode", mode])
            
            # Enable RAG for all agents except PM (PM only extracts BRs from raw text)
            if agent_id != "pm":
                cmd.append("--use-rag")
            
            logger.debug(f"Running: {' '.join(cmd)}")
            
            # Run agent with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ}
            )
            
            # Dynamic timeout based on agent/mode
            timeout_seconds = 300  # Default 5 min
            if agent_id == "research_analyst":
                timeout_seconds = 3600  # 60 min for all Emma modes (large projects)
            elif agent_id == "architect":
                timeout_seconds = 900  # 15 min for architecture
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds
            )
            
            if process.returncode != 0:
                error_msg = stderr.decode()[:500] if stderr else "Unknown error"
                logger.error(f"Agent {agent_id} failed: {error_msg}")
                return {"success": False, "error": error_msg}
            
            # Read output
            if output_file.exists():
                with open(output_file) as f:
                    output = json.load(f)
                return {"success": True, "output": output}
            else:
                return {"success": False, "error": "No output file"}
                
        except asyncio.TimeoutError:
            return {"success": False, "error": f"Timeout ({timeout_seconds // 60} min)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _init_agent_status(self, selected_agents: List[str]) -> Dict:
        """Initialize agent execution status - ORCH-01: respects selected_agents"""
        # Core agents always included (mandatory for SDS)
        agents = ["pm", "ba", "research_analyst", "architect"]
        
        # SDS Expert agents - only include if selected (or if no selection for backward compat)
        ALL_SDS_EXPERTS = ["data", "trainer", "qa", "devops"]
        if selected_agents:
            # Only add SDS experts that were selected
            sds_selected = [a for a in ALL_SDS_EXPERTS if a in selected_agents]
            agents.extend(sds_selected)
            # Add any BUILD agents that were selected
            agents.extend([a for a in selected_agents if a not in agents])
        else:
            # No selection = include all for backward compatibility
            agents.extend(ALL_SDS_EXPERTS)
        
        return {
            agent_id: {
                "state": "waiting",
                "progress": 0,
                "message": "Waiting...",
                "started_at": None,
                "completed_at": None,
                "tokens_used": 0
            }
            for agent_id in agents
        }

    # ============================================================================
    # CHECKPOINT/RESUME METHODS
    # ============================================================================
    
    def _save_checkpoint(self, execution: Execution, phase: str):
        """Save checkpoint after successful phase completion for resume capability"""
        try:
            execution.last_completed_phase = phase
            self.db.commit()
            logger.info(f"✅ Checkpoint saved: {phase}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
            self.db.rollback()
    
    def _update_progress(self, execution: Execution, agent_id: str, state: str, progress: int, message: str):
        """Update execution progress for SSE and send real-time notification"""
        if execution.agent_execution_status is None:
            execution.agent_execution_status = {}
        
        now = datetime.now(timezone.utc).isoformat()
        
        if agent_id not in execution.agent_execution_status:
            execution.agent_execution_status[agent_id] = {}
        
        execution.agent_execution_status[agent_id].update({
            "state": state,
            "progress": progress,
            "message": message,
            "updated_at": now
        })
        
        if state == "running" and not execution.agent_execution_status[agent_id].get("started_at"):
            execution.agent_execution_status[agent_id]["started_at"] = now
        elif state in ["completed", "failed"]:
            execution.agent_execution_status[agent_id]["completed_at"] = now
        
        execution.current_agent = agent_id
        execution.progress = progress  # Update overall progress too
        
        # CRITICAL: Mark JSON column as modified for SQLAlchemy to detect changes
        flag_modified(execution, "agent_execution_status")
        # P7: Protect progress commit — rollback on failure to keep session usable
        try:
            self.db.commit()
        except Exception as e:
            logger.warning(f"Failed to commit progress update for {agent_id}: {e}")
            self.db.rollback()

        # PERF-001: Send real-time notification (fire-and-forget)
        self._send_progress_notification(execution.id, agent_id, state, progress, message)
    
    def _send_progress_notification(self, execution_id: int, agent_id: str, state: str, progress: int, message: str):
        """Send progress notification via PostgreSQL NOTIFY (non-blocking)"""
        if not NOTIFICATIONS_ENABLED:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_notify_progress(execution_id, agent_id, state, progress, message))
        except RuntimeError:
            pass  # No running loop, skip notification
    
    async def _async_notify_progress(self, execution_id: int, agent_id: str, state: str, progress: int, message: str):
        """Async helper to send notification"""
        try:
            service = await get_notification_service()
            await service.notify_execution_progress(
                execution_id=execution_id,
                status=state,
                progress=progress,
                agent=agent_id,
                message=message
            )
        except Exception as e:
            logger.debug(f"Notification failed (non-critical): {e}")

    def _track_tokens(self, agent_id: str, output: Dict, results: Dict):
        """Track tokens per agent"""
        tokens = output.get("metadata", {}).get("tokens_used", 0)
        results["metrics"]["tokens_by_agent"][agent_id] = tokens
        results["metrics"]["total_tokens"] += tokens

    def _save_deliverable(self, execution_id: int, agent_id: str, deliverable_type: str, content: Dict):
        """Save agent deliverable to database"""
        try:
            # Convert dict to JSON string for PostgreSQL
            content_json = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content
            
            # Extract metadata if available
            content_metadata = None
            if isinstance(content, dict) and "metadata" in content:
                content_metadata = content.get("metadata")
            
            deliverable = AgentDeliverable(
                execution_id=execution_id,
                agent_id=None,  # FK to agents table - NULL like V1 (agent_id string not compatible with Integer FK)
                deliverable_type=f"{agent_id}_{deliverable_type}",  # Include agent name in type for clarity
                content=content_json,
                content_metadata=content_metadata,  # JSONB column accepts dict directly
                created_at=datetime.now(timezone.utc)
            )
            self.db.add(deliverable)
            self.db.commit()
            logger.info(f"✅ Saved deliverable: {agent_id}_{deliverable_type} (execution {execution_id})")
        except Exception as e:
            logger.error(f"❌ Failed to save deliverable {agent_id}_{deliverable_type}: {e}")
            import traceback
            traceback.print_exc()
            self.db.rollback()


    # ============================================================================
    # DATABASE-FIRST ITEM METHODS
    # ============================================================================
    
    def _save_deliverable_item(
        self,
        execution_id: int,
        agent_id: str,
        parent_ref: str,
        item_id: str,
        item_type: str,
        content: Dict,
        tokens_used: int = 0,
        model_used: str = None,
        execution_time: float = None
    ):
        """
        Save individual item to deliverable_items table (database-first approach).
        Always saves raw content for recovery.
        """
        try:
            # Determine if parsing was successful
            parse_success = False
            content_parsed = None
            content_raw = None
            parse_error = None
            
            if isinstance(content, dict):
                if "raw" in content and "parse_error" in content:
                    # Parsing failed - store raw
                    content_raw = content.get("raw", "")
                    parse_error = content.get("parse_error", "")
                    parse_success = False
                else:
                    # Parsing succeeded - store both
                    content_parsed = content
                    content_raw = json.dumps(content, ensure_ascii=False)
                    parse_success = True
            else:
                content_raw = str(content)
            
            item = DeliverableItem(
                execution_id=execution_id,
                agent_id=agent_id,
                parent_ref=parent_ref,
                item_id=item_id,
                item_type=item_type,
                content_parsed=content_parsed,
                content_raw=content_raw,
                parse_success=parse_success,
                parse_error=parse_error,
                tokens_used=tokens_used,
                model_used=model_used,
                execution_time_seconds=execution_time
            )
            self.db.add(item)
            self.db.commit()
            logger.debug(f"Saved item {item_id} (parse_success={parse_success})")
            return True
        except Exception as e:
            logger.error(f"Failed to save item {item_id}: {e}")
            self.db.rollback()
            return False
    
    def _save_use_cases_from_result(
        self,
        execution_id: int,
        br_id: str,
        ba_result: Dict,
        tokens_used: int = 0,
        model_used: str = None,
        execution_time: float = None
    ) -> int:
        """
        Parse BA result and save each UC individually.
        Returns count of successfully saved UCs.
        """
        saved_count = 0
        content = ba_result.get("output", {}).get("content", {})
        
        # Case 1: Parsing succeeded - use_cases array present
        if "use_cases" in content:
            use_cases = content.get("use_cases", [])
            for uc in use_cases:
                # F-081: Support batch mode - UC may have its own parent_br
                uc_parent_br = uc.get("parent_br", br_id)
                uc_id = uc.get("id", f"UC-{uc_parent_br[3:]}-{saved_count+1:02d}")
                if self._save_deliverable_item(
                    execution_id=execution_id,
                    agent_id="ba",
                    parent_ref=uc_parent_br,
                    item_id=uc_id,
                    item_type="use_case",
                    content=uc,
                    tokens_used=tokens_used // max(len(use_cases), 1),
                    model_used=model_used,
                    execution_time=execution_time
                ):
                    saved_count += 1
        
        # Case 2: Parsing failed - save raw with parent_ref for recovery
        elif "raw" in content:
            raw_item_id = f"UC-RAW-{br_id[3:]}"
            self._save_deliverable_item(
                execution_id=execution_id,
                agent_id="ba",
                parent_ref=br_id,
                item_id=raw_item_id,
                item_type="use_case_raw",
                content=content,  # Contains raw + parse_error
                tokens_used=tokens_used,
                model_used=model_used,
                execution_time=execution_time
            )
            logger.warning(f"Saved raw content for {br_id} (parsing failed)")
        
        return saved_count
    
    def _get_use_cases(self, execution_id: int, limit: int = None) -> List[Dict]:
        """
        Retrieve Use Cases from deliverable_items table.
        Only returns successfully parsed UCs.
        """
        try:
            query = self.db.query(DeliverableItem).filter(
                DeliverableItem.execution_id == execution_id,
                DeliverableItem.agent_id == "ba",
                DeliverableItem.item_type == "use_case",
                DeliverableItem.parse_success == True
            ).order_by(DeliverableItem.id)
            
            if limit:
                query = query.limit(limit)
            
            items = query.all()
            return [item.content_parsed for item in items]
        except Exception as e:
            logger.error(f"Failed to get use cases: {e}")
            return []
    
    
    def _get_business_requirements_for_sds(self, execution_id: int) -> List[Dict]:
        """
        Get Business Requirements for SDS generation.
        First tries business_requirements table, then falls back to agent_deliverables.
        
        FIX for BUG: When multiple executions exist for same project, 
        _save_extracted_brs may skip saving due to project-level duplicate check,
        leaving business_requirements empty for the current execution.
        """
        try:
            # First try: Get from business_requirements table
            brs_from_table = self.db.query(BusinessRequirement).filter(
                BusinessRequirement.execution_id == execution_id
            ).all()
            
            if brs_from_table:
                logger.info(f"[SDS] Found {len(brs_from_table)} BRs in business_requirements table")
                return [
                    {
                        "id": br.br_id,
                        "title": br.requirement[:100] if br.requirement else br.br_id,
                        "description": br.requirement or "",
                        "priority": br.priority.value if br.priority else "SHOULD"
                    }
                    for br in brs_from_table
                ]
            
            # Fallback: Get from agent_deliverables (Sophie's extraction)
            logger.warning(f"[SDS] No BRs in table for execution {execution_id}, checking agent_deliverables...")
            
            br_deliverable = self.db.query(AgentDeliverable).filter(
                AgentDeliverable.execution_id == execution_id,
                AgentDeliverable.deliverable_type.in_(["br_extraction", "pm_br_extraction", "business_requirements_extraction"])
            ).first()
            
            if br_deliverable and br_deliverable.content:
                content_data = br_deliverable.content
                if isinstance(content_data, str):
                    import json
                    content_data = json.loads(content_data)
                
                # Navigate to business_requirements in the nested structure
                brs = content_data.get("content", {}).get("business_requirements", [])
                if not brs:
                    brs = content_data.get("business_requirements", [])
                
                if brs:
                    logger.info(f"[SDS] Found {len(brs)} BRs in agent_deliverables (fallback)")
                    return [
                        {
                            "id": br.get("id", f"BR-{i+1:03d}"),
                            "title": br.get("title", br.get("requirement", "")[:100]),
                            "description": br.get("description", br.get("requirement", "")),
                            "priority": br.get("priority", "SHOULD")
                        }
                        for i, br in enumerate(brs)
                    ]
            
            logger.error(f"[SDS] No BRs found for execution {execution_id} in any source!")
            return []
            
        except Exception as e:
            logger.error(f"[SDS] Failed to get business requirements: {e}")
            return []

    def _get_use_case_count(self, execution_id: int) -> Dict[str, int]:
        """
        Get statistics about saved Use Cases.
        """
        try:
            total = self.db.query(DeliverableItem).filter(
                DeliverableItem.execution_id == execution_id,
                DeliverableItem.agent_id == "ba"
            ).count()
            
            parsed = self.db.query(DeliverableItem).filter(
                DeliverableItem.execution_id == execution_id,
                DeliverableItem.agent_id == "ba",
                DeliverableItem.parse_success == True
            ).count()
            
            raw = self.db.query(DeliverableItem).filter(
                DeliverableItem.execution_id == execution_id,
                DeliverableItem.agent_id == "ba",
                DeliverableItem.item_type == "use_case_raw"
            ).count()
            
            return {"total": total, "parsed": parsed, "raw_saved": raw}
        except Exception as e:
            logger.error(f"Failed to get UC stats: {e}")
            return {"total": 0, "parsed": 0, "raw_saved": 0}
    def _initialize_validation_gates(self, execution_id: int):
        """Initialize validation gates for the execution"""
        try:
            for gate_config in VALIDATION_GATES:
                gate = ValidationGate(
                    execution_id=execution_id,
                    gate_number=gate_config["gate_number"],
                    gate_name=gate_config["name"],
                    status="pending",
                    required_artifacts=gate_config["required_artifacts"],
                    created_at=datetime.now(timezone.utc)
                )
                self.db.add(gate)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not initialize gates: {e}")
            self.db.rollback()

    def _update_gate_progress(self, execution_id: int, gate_number: int, artifact_type: str, count: int):
        """Update validation gate progress"""
        try:
            gate = self.db.query(ValidationGate).filter(
                ValidationGate.execution_id == execution_id,
                ValidationGate.gate_number == gate_number
            ).first()
            
            if gate:
                if gate.artifacts_collected is None:
                    gate.artifacts_collected = {}
                gate.artifacts_collected[artifact_type] = count
                
                # Check if gate complete
                required = gate.required_artifacts or []
                collected = gate.artifacts_collected.keys()
                if all(r in collected for r in required):
                    gate.status = "passed"
                    gate.completed_at = datetime.now(timezone.utc)
                else:
                    gate.status = "in_progress"
                
                self.db.commit()
        except Exception as e:
            logger.warning(f"Gate update failed: {e}")

    async def _generate_sds_document(
        self,
        project: Project,
        agent_outputs: Dict,
        artifacts: Dict,
        execution_id: int,
        sds_markdown: str = None
    ) -> str:
        """Generate professional DOCX SDS document
        
        If sds_markdown is provided (from Emma write_sds), uses it as the source.
        Otherwise falls back to the professional generator.
        """
        output_dir = str(settings.OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        # If Emma provided markdown, convert to DOCX
        if sds_markdown:
            try:
                from app.services.markdown_to_docx import convert_markdown_to_docx
                output_path = f"{output_dir}/SDS_Exec{execution_id}.docx"
                convert_markdown_to_docx(sds_markdown, output_path, project.name)
                logger.info(f"✅ SDS DOCX generated from Emma markdown: {output_path}")
                return output_path
            except ImportError:
                logger.warning("markdown_to_docx not available, saving as markdown")
                output_path = f"{output_dir}/SDS_Exec{execution_id}.md"
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(sds_markdown)
                return output_path
            except Exception as e:
                logger.error(f"DOCX conversion failed: {e}, saving as markdown")
                output_path = f"{output_dir}/SDS_Exec{execution_id}.md"
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(sds_markdown)
                return output_path
        
        # Fallback: Use professional generator
        output_path = generate_professional_sds(
            project=project,
            agent_outputs=agent_outputs,
            execution_id=execution_id,
            output_dir=output_dir
        )
        
        return output_path

    def _generate_markdown_sds(self, project: Project, artifacts: Dict, execution_id: int) -> str:
        """Fallback: Generate Markdown SDS"""
        output_dir = str(settings.OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        
        md_content = f"""# Solution Design Specification
## {project.name}

**Generated by:** Digital Humans System  
**Date:** {datetime.now().strftime('%B %d, %Y')}

---

## Executive Summary
{artifacts.get('BR_EXTRACTION', {}).get('content', {}).get('project_summary', 'N/A')}

## Business Requirements
{self._format_brs(artifacts.get('BR_EXTRACTION', {}).get('content', {}).get('business_requirements', []))}

## Use Cases
Total: {artifacts.get('USE_CASES', {}).get('total_ucs', 0)} Use Cases generated.

## Architecture
See ARCH-001 artifact for details.

## Gap Analysis
See GAP-001 artifact for details.

## Work Breakdown Structure
See WBS-001 artifact for details.
"""
        
        output_path = f"{output_dir}/SDS_Exec{execution_id}.md"
        with open(output_path, "w") as f:
            f.write(md_content)
        
        return output_path

    def _format_brs(self, brs: List[Dict]) -> str:
        """Format BRs as markdown table"""
        if not brs:
            return "No requirements extracted."
        
        lines = ["| ID | Title | Category | Priority |", "|---|---|---|---|"]
        for br in brs[:10]:  # Limit to 10
            lines.append(f"| {br.get('id', 'N/A')} | {br.get('title', 'N/A')} | {br.get('category', 'N/A')} | {br.get('priority', 'N/A')} |")
        
        return "\n".join(lines)


    def _save_extracted_brs(self, execution_id: int, project_id: int, business_requirements: List[Dict]) -> int:
        """
        Save extracted BRs to business_requirements table for client validation.
        Returns number of BRs saved.
        """
        from app.models.business_requirement import BusinessRequirement, BRStatus, BRPriority, BRSource
        
        saved_count = 0
        for i, br in enumerate(business_requirements):
            br_id = br.get("id", f"BR-{i+1:03d}")
            
            # Check if already exists FOR THIS EXECUTION (not project-level)
            # FIX: Use execution_id instead of project_id to allow re-runs
            existing = self.db.query(BusinessRequirement).filter(
                BusinessRequirement.execution_id == execution_id,
                BusinessRequirement.br_id == br_id
            ).first()
            
            if existing:
                continue  # Skip if already exists for this execution
            
            # Map priority - EMMA-P1-001: Support all priority formats from Sophie
            priority_map = {
                # Format court (MoSCoW standard)
                "must": BRPriority.MUST,
                "should": BRPriority.SHOULD,
                "could": BRPriority.COULD,
                "wont": BRPriority.WONT,
                # Format long (généré par Sophie)
                "must_have": BRPriority.MUST,
                "should_have": BRPriority.SHOULD,
                "could_have": BRPriority.COULD,
                "nice_to_have": BRPriority.COULD,
                "wont_have": BRPriority.WONT,
                "won't_have": BRPriority.WONT,
                # Autres variantes possibles
                "critical": BRPriority.MUST,
                "high": BRPriority.MUST,
                "medium": BRPriority.SHOULD,
                "low": BRPriority.COULD,
                "optional": BRPriority.COULD,
            }
            # Normalize priority string (handle spaces, hyphens, underscores)
            priority_str = br.get("priority", "should").lower().replace("-", "_").replace(" ", "_")
            priority = priority_map.get(priority_str, BRPriority.SHOULD)
            
            # PRPT-01: Extract metadata for detailed BRs
            br_metadata = br.get("metadata", {})
            if not br_metadata:
                # Build metadata from old format for backward compatibility
                br_metadata = {
                    "fields": [],
                    "validation_rules": [],
                    "dependencies": [],
                    "acceptance_criteria": [],
                    "stakeholder": br.get("stakeholder", ""),
                    "title": br.get("title", ""),
                }
            
            br_record = BusinessRequirement(
                execution_id=execution_id,
                project_id=project_id,
                br_id=br_id,
                category=br.get("category", "General"),
                requirement=br.get("requirement", br.get("description", "")),
                priority=priority,
                source=BRSource.EXTRACTED,
                original_text=br.get("requirement", br.get("description", "")),
                status=BRStatus.PENDING,
                order_index=i,
                br_metadata=br_metadata,  # PRPT-01: Store detailed metadata
            )
            
            self.db.add(br_record)
            saved_count += 1
        
        self.db.commit()
        logger.info(f"Saved {saved_count} BRs to database for validation")
        return saved_count

    def _get_validated_brs(self, project_id: int) -> List[Dict]:
        """
        Get validated BRs from database.
        Returns list of BR dicts compatible with agent input.
        """
        from app.models.business_requirement import BusinessRequirement, BRStatus
        
        brs = self.db.query(BusinessRequirement).filter(
            BusinessRequirement.project_id == project_id,
            BusinessRequirement.status != BRStatus.DELETED
        ).order_by(BusinessRequirement.order_index).all()
        
        return [
            {
                "id": br.br_id,
                "title": br.br_id,
                "description": br.requirement,
                "category": br.category or "OTHER",
                "priority": (br.priority.value.upper() + "_HAVE") if br.priority else "SHOULD_HAVE",
                "stakeholder": "Business User"
            }
            for br in brs
        ]

    async def execute_targeted_regeneration(
        self,
        execution_id: int,
        project_id: int,
        agents_to_run: List[str],
        change_request: 'ChangeRequest'
    ) -> Dict[str, Any]:
        """
        Execute targeted re-generation for a Change Request.
        Only runs specified agents and regenerates the SDS.
        """
        logger.info(f"[Targeted Regen] ========== START ==========")
        logger.info(f"[Targeted Regen] Execution: {execution_id}, Project: {project_id}")
        logger.info(f"[Targeted Regen] CR: {change_request.cr_number} - {change_request.title}")
        logger.info(f"[Targeted Regen] Agents to run: {agents_to_run}")
        
        try:
            # Get existing execution and project
            execution = self.db.query(Execution).filter(Execution.id == execution_id).first()
            project = self.db.query(Project).filter(Project.id == project_id).first()
            
            if not execution or not project:
                logger.error(f"[Targeted Regen] Execution or project not found")
                return {"success": False, "error": "Execution or project not found"}
            
            # Load existing artifacts from previous execution
            logger.info(f"[Targeted Regen] Loading existing artifacts...")
            existing_artifacts = self._load_existing_artifacts(execution_id)
            logger.info(f"[Targeted Regen] Found {len(existing_artifacts)} existing artifacts")
            
            # Initialize results
            results = {
                "artifacts": existing_artifacts.copy(),
                "agent_outputs": {},
                "metrics": {"total_tokens": 0, "tokens_by_agent": {}}
            }
            
            # Get validated BRs
            business_requirements = self._get_validated_brs(project_id)
            logger.info(f"[Targeted Regen] Loaded {len(business_requirements)} validated BRs")
            
            # Build CR context to inject into prompts
            cr_context = f"""
=== CHANGE REQUEST ===
Numéro: {change_request.cr_number}
Catégorie: {change_request.category}
Titre: {change_request.title}
Description: {change_request.description}
======================
IMPORTANT: Prends en compte cette modification dans ta génération.
"""
            
            # Run each agent that needs to be re-run
            for agent_id in agents_to_run:
                if agent_id == "ba":
                    logger.info(f"[Targeted Regen] Running BA (Olivia) with CR context...")
                    await self._run_ba_with_context(execution_id, project_id, business_requirements, cr_context, results)
                    
                elif agent_id == "architect":
                    logger.info(f"[Targeted Regen] Running Architect (Marcus) with CR context...")
                    await self._run_architect_with_context(execution_id, project_id, results, cr_context)
                    
                elif agent_id in ["apex", "lwc", "admin", "qa", "devops", "data", "trainer"]:
                    logger.info(f"[Targeted Regen] Running {agent_id} with CR context...")
                    await self._run_sds_expert_with_context(execution_id, project_id, agent_id, results, cr_context)
            
            # Re-generate SDS document
            logger.info(f"[Targeted Regen] Generating new SDS document...")
            try:
                sds_path = self._generate_word_sds(project, results["artifacts"], execution_id)
                results["sds_path"] = sds_path
                logger.info(f"[Targeted Regen] SDS generated: {sds_path}")
            except Exception as e:
                logger.error(f"[Targeted Regen] SDS generation failed: {e}")
                sds_path = self._generate_markdown_sds(project, results["artifacts"], execution_id)
                results["sds_path"] = sds_path
            
            # Create new SDS version
            new_version = self._create_sds_version_for_cr(project, execution, sds_path, change_request)
            
            logger.info(f"[Targeted Regen] ========== COMPLETE ==========")
            logger.info(f"[Targeted Regen] New SDS version: {new_version}")
            logger.info(f"[Targeted Regen] Total tokens: {results['metrics']['total_tokens']}")
            
            return {
                "success": True,
                "new_sds_version": new_version,
                "agents_run": agents_to_run,
                "total_tokens": results["metrics"]["total_tokens"],
                "sds_path": sds_path
            }
            
        except Exception as e:
            logger.error(f"[Targeted Regen] Failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def _load_existing_artifacts(self, execution_id: int) -> Dict[str, Any]:
        """Load existing artifacts from a previous execution."""
        artifacts = {}
        
        deliverables = self.db.query(AgentDeliverable).filter(
            AgentDeliverable.execution_id == execution_id
        ).all()
        
        for d in deliverables:
            if d.content:
                content = d.content if isinstance(d.content, dict) else json.loads(d.content)
                
                # Map deliverable_type to artifact key
                if "br_extraction" in d.deliverable_type:
                    artifacts["BR_EXTRACTION"] = content
                elif "use_cases" in d.deliverable_type:
                    artifacts["USE_CASES"] = content
                elif "as_is" in d.deliverable_type:
                    artifacts["AS_IS"] = content
                elif "gap" in d.deliverable_type:
                    artifacts["GAP"] = content
                elif "solution_design" in d.deliverable_type or "architecture" in d.deliverable_type:
                    artifacts["ARCHITECTURE"] = content
                elif "wbs" in d.deliverable_type:
                    artifacts["WBS"] = content
                elif "apex" in d.deliverable_type:
                    artifacts["APEX_SPECS"] = content
                elif "lwc" in d.deliverable_type:
                    artifacts["LWC_SPECS"] = content
                elif "admin" in d.deliverable_type:
                    artifacts["ADMIN_SPECS"] = content
                elif "qa" in d.deliverable_type:
                    artifacts["QA_SPECS"] = content
                elif "devops" in d.deliverable_type:
                    artifacts["DEVOPS_SPECS"] = content
                elif "data" in d.deliverable_type:
                    artifacts["DATA_SPECS"] = content
                elif "trainer" in d.deliverable_type:
                    artifacts["TRAINER_SPECS"] = content
        
        return artifacts
    
    async def _run_ba_with_context(
        self, 
        execution_id: int, 
        project_id: int, 
        business_requirements: List[Dict],
        cr_context: str,
        results: Dict
    ):
        """Run BA agent with CR context."""
        logger.info(f"[Targeted Regen] BA: Starting Use Case generation with CR context")
        
        # Add CR context to requirements
        input_data = {
            "requirements": business_requirements,
            "change_request_context": cr_context
        }
        
        uc_result = await self._run_agent(
            agent_id="ba",
            mode="generate_uc",
            input_data=input_data,
            execution_id=execution_id,
            project_id=project_id
        )
        
        if uc_result.get("success"):
            results["artifacts"]["USE_CASES"] = uc_result["output"]
            tokens = uc_result["output"]["metadata"].get("tokens_used", 0)
            results["metrics"]["total_tokens"] += tokens
            results["metrics"]["tokens_by_agent"]["ba"] = tokens
            self._save_deliverable(execution_id, "ba", "use_cases_cr", uc_result["output"])
            logger.info(f"[Targeted Regen] BA: Use Cases regenerated ({tokens} tokens)")
        else:
            logger.warning(f"[Targeted Regen] BA: Failed - {uc_result.get('error')}")
    
    async def _run_architect_with_context(
        self,
        execution_id: int,
        project_id: int,
        results: Dict,
        cr_context: str
    ):
        """Run Architect agent with CR context."""
        logger.info(f"[Targeted Regen] Architect: Starting with CR context")
        
        # Run design phase with CR context
        design_input = {
            "use_cases": results["artifacts"].get("USE_CASES", {}).get("content", {}).get("use_cases", []),
            "gaps": results["artifacts"].get("GAP", {}).get("content", {}).get("gaps", []),
            "as_is": results["artifacts"].get("AS_IS", {}).get("content", {}),
            "change_request_context": cr_context
        }
        
        design_result = await self._run_agent(
            agent_id="architect",
            mode="design",
            input_data=design_input,
            execution_id=execution_id,
            project_id=project_id
        )
        
        if design_result.get("success"):
            results["artifacts"]["ARCHITECTURE"] = design_result["output"]
            tokens = design_result["output"]["metadata"].get("tokens_used", 0)
            results["metrics"]["total_tokens"] += tokens
            results["metrics"]["tokens_by_agent"]["architect"] = tokens
            self._save_deliverable(execution_id, "architect", "solution_design_cr", design_result["output"])
            logger.info(f"[Targeted Regen] Architect: Design regenerated ({tokens} tokens)")
        else:
            logger.warning(f"[Targeted Regen] Architect: Design failed - {design_result.get('error')}")
    
    async def _run_sds_expert_with_context(
        self,
        execution_id: int,
        project_id: int,
        agent_id: str,
        results: Dict,
        cr_context: str
    ):
        """Run an SDS expert agent with CR context."""
        logger.info(f"[Targeted Regen] {agent_id}: Starting with CR context")
        
        # Build input based on agent type
        input_data = {
            "architecture": results["artifacts"].get("ARCHITECTURE", {}).get("content", {}),
            "use_cases": results["artifacts"].get("USE_CASES", {}).get("content", {}).get("use_cases", []),
            "change_request_context": cr_context
        }
        
        result = await self._run_agent(
            agent_id=agent_id,
            mode="sds_section",
            input_data=input_data,
            execution_id=execution_id,
            project_id=project_id
        )
        
        artifact_key = f"{agent_id.upper()}_SPECS"
        
        if result.get("success"):
            results["artifacts"][artifact_key] = result["output"]
            tokens = result["output"]["metadata"].get("tokens_used", 0)
            results["metrics"]["total_tokens"] += tokens
            results["metrics"]["tokens_by_agent"][agent_id] = tokens
            self._save_deliverable(execution_id, agent_id, f"{agent_id}_specs_cr", result["output"])
            logger.info(f"[Targeted Regen] {agent_id}: Specs regenerated ({tokens} tokens)")
        else:
            logger.warning(f"[Targeted Regen] {agent_id}: Failed - {result.get('error')}")
    
    def _create_sds_version_for_cr(
        self,
        project: 'Project',
        execution: 'Execution',
        sds_path: Optional[str],
        change_request: 'ChangeRequest'
    ) -> int:
        """Create a new SDS version for a Change Request."""
        import os
        
        current_version = project.current_sds_version or 0
        new_version = current_version + 1
        
        file_name = None
        file_size = None
        if sds_path and os.path.exists(sds_path):
            file_name = os.path.basename(sds_path)
            file_size = os.path.getsize(sds_path)
        
        sds_version = SDSVersion(
            project_id=project.id,
            execution_id=execution.id,
            version_number=new_version,
            file_path=sds_path,
            file_name=file_name or f"SDS_v{new_version}.docx",
            file_size=file_size,
            change_request_id=change_request.id,
            notes=f"Generated for {change_request.cr_number}: {change_request.title}"
        )
        self.db.add(sds_version)
        
        project.current_sds_version = new_version
        self.db.commit()
        
        logger.info(f"[SDS Version] Created v{new_version} for CR {change_request.cr_number}")
        
        return new_version


    def _create_sds_version(self, project: 'Project', execution: 'Execution', sds_path: Optional[str]) -> None:
        """
        Create SDS version entry and update project status.
        Called after successful execution completion.
        """
        from app.models.sds_version import SDSVersion
        from app.models.project import ProjectStatus
        import os
        
        try:
            # Determine version number
            current_version = project.current_sds_version or 0
            new_version = current_version + 1
            
            # Get file info
            file_name = None
            file_size = None
            if sds_path and os.path.exists(sds_path):
                file_name = os.path.basename(sds_path)
                file_size = os.path.getsize(sds_path)
            
            # Create SDS version
            sds_version = SDSVersion(
                project_id=project.id,
                execution_id=execution.id,
                version_number=new_version,
                file_path=sds_path,
                file_name=file_name or f"SDS_v{new_version}.docx",
                file_size=file_size,
                notes=f"Generated from execution #{execution.id}"
            )
            self.db.add(sds_version)
            
            # Update project
            project.current_sds_version = new_version
            project.status = ProjectStatus.SDS_GENERATED
            
            logger.info(f"[SDS] Created version {new_version} for project {project.id}")
            
        except Exception as e:
            logger.error(f"[SDS] Failed to create version: {e}")
            # Don't fail the execution, just log the error


# Background execution helper
async def execute_workflow_background(
    db: Session,  # Not used - we create our own session
    execution_id: int,
    project_id: int,
    selected_agents: List[str] = None,
    include_as_is: bool = False,
    sfdx_metadata: Optional[Dict] = None,
        resume_from: Optional[str] = None  # "phase2" to skip Phase 1
):
    """Background task for workflow execution - creates its own DB session"""
    # Create a new session for background task (original session closes after API response)
    db_session = SessionLocal()
    try:
        service = PMOrchestratorServiceV2(db_session)
        return await service.execute_workflow(
            execution_id=execution_id,
            project_id=project_id,
            selected_agents=selected_agents,
            include_as_is=include_as_is,
            sfdx_metadata=sfdx_metadata,
            resume_from=resume_from
        )
    finally:
        db_session.close()


# ════════════════════════════════════════════════════════════════════════════════
# BUILD PHASE METHODS - Refactored from pm_orchestrator.py
# ════════════════════════════════════════════════════════════════════════════════

class BuildPhaseService:
    """
    Service pour gérer la phase BUILD.
    Séparé de PMOrchestratorServiceV2 pour clarté.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def prepare_build_phase(self, project_id: int, user_id: int) -> Dict[str, Any]:
        """
        Prépare la phase BUILD : vérifie le projet, parse le WBS, crée les TaskExecution.
        
        Returns:
            Dict avec execution_id, tasks_created, ou erreur
        """
        from app.models.project import Project, ProjectStatus
        from app.models.execution import Execution, ExecutionStatus
        from app.models.task_execution import TaskExecution, TaskStatus
        from app.models.agent_deliverable import AgentDeliverable
        
        # 1. Vérifier le projet
        project = self.db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()
        
        if not project:
            return {"success": False, "error": "Project not found", "code": 404}
        
        if project.status != ProjectStatus.SDS_APPROVED:
            return {
                "success": False, 
                "error": f"Project must be in SDS_APPROVED status. Current: {project.status.value}",
                "code": 400
            }
        
        # 2. Récupérer la dernière exécution
        execution = self.db.query(Execution).filter(
            Execution.project_id == project_id
        ).order_by(Execution.id.desc()).first()
        
        if not execution:
            return {"success": False, "error": "No execution found for this project", "code": 400}
        
        # 3. Récupérer le WBS de Marcus
        wbs_deliverable = self.db.query(AgentDeliverable).filter(
            AgentDeliverable.execution_id == execution.id,
            AgentDeliverable.deliverable_type == "architect_wbs"
        ).first()
        
        if not wbs_deliverable:
            return {"success": False, "error": "No WBS found. Run the Design phase first.", "code": 400}
        
        # 4. Parser le WBS
        wbs_data = self._parse_wbs_content(wbs_deliverable.content)
        if not wbs_data:
            return {"success": False, "error": "Failed to parse WBS content", "code": 400}
        
        # 5. Extraire les tâches
        tasks = self._extract_tasks_from_wbs(wbs_data)
        if not tasks:
            return {"success": False, "error": "WBS contains no tasks", "code": 400}
        
        # 5b. Vérifier si des tasks existent déjà pour cette exécution
        existing_tasks = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution.id
        ).count()
        
        if existing_tasks > 0:
            # Tasks already exist - just reuse them
            # Reset status for retry
            self.db.query(TaskExecution).filter(
                TaskExecution.execution_id == execution.id,
                TaskExecution.status.in_([TaskStatus.FAILED, TaskStatus.RUNNING])
            ).update({"status": TaskStatus.PENDING, "attempt_count": 0, "last_error": None}, synchronize_session=False)
            
            execution.status = ExecutionStatus.RUNNING
            project.status = ProjectStatus.BUILD_IN_PROGRESS
            self.db.commit()
            
            return {
                "success": True,
                "execution_id": execution.id,
                "project_id": project_id,
                "tasks_created": existing_tasks
            }
        
        # 6. Créer les TaskExecution (seulement si aucune n'existe)
        agent_mapping = {
            "jordan": "devops", "raj": "admin", "diego": "apex", 
            "zara": "lwc", "elena": "qa", "aisha": "data", 
            "lucas": "trainer", "marcus": "architect"
        }
        
        created_tasks = 0
        for task in tasks:
            assigned = task.get("assigned_agent", task.get("assigned_to", "")).lower()
            agent_id = agent_mapping.get(assigned, assigned)
            
            task_exec = TaskExecution(
                execution_id=execution.id,
                task_id=task.get("id", task.get("task_id", f"TASK-{created_tasks+1:03d}")),
                task_name=task.get("name", task.get("title", "Unnamed task")),
                phase_name=task.get("phase_name", task.get("phase", "Build")),
                assigned_agent=agent_id,
                status=TaskStatus.PENDING,
                depends_on=task.get("dependencies", [])
            )
            self.db.add(task_exec)
            created_tasks += 1
        
        # 7. Mettre à jour les statuts
        execution.status = ExecutionStatus.RUNNING
        project.status = ProjectStatus.BUILD_IN_PROGRESS
        
        self.db.commit()
        
        return {
            "success": True,
            "execution_id": execution.id,
            "project_id": project_id,
            "tasks_created": created_tasks
        }
    
    def _parse_wbs_content(self, content: Any) -> Optional[Dict]:
        """
        Parse le contenu WBS qui peut être dans plusieurs formats.
        """
        import json
        import re
        
        try:
            # Si c'est déjà un dict
            if isinstance(content, dict):
                wbs_content = content
            else:
                wbs_content = json.loads(content)
            
            # Naviguer dans la structure imbriquée
            if "content" in wbs_content and isinstance(wbs_content["content"], dict):
                inner_content = wbs_content["content"]
                
                if "raw" in inner_content and isinstance(inner_content["raw"], str):
                    raw_json = inner_content["raw"]
                    
                    # Nettoyer les fences markdown
                    if raw_json.startswith("```json"):
                        raw_json = raw_json[7:].lstrip()
                    elif raw_json.startswith("```"):
                        raw_json = raw_json[3:].lstrip()
                    
                    if "```" in raw_json:
                        raw_json = raw_json[:raw_json.index("```")]
                    
                    try:
                        return json.loads(raw_json)
                    except json.JSONDecodeError:
                        # Essayer de trouver un objet JSON valide
                        match = re.search(r'\{.*\}', raw_json, re.DOTALL)
                        if match:
                            return json.loads(match.group())
                        return None
                else:
                    return inner_content
            else:
                return wbs_content
                
        except Exception as e:
            logger.error(f"Failed to parse WBS content: {e}")
            return None
    
    def _extract_tasks_from_wbs(self, wbs_data: Dict) -> List[Dict]:
        """
        Extrait les tâches du WBS parsé.
        """
        tasks = []
        
        if "phases" in wbs_data and isinstance(wbs_data["phases"], list):
            for phase in wbs_data["phases"]:
                phase_name = phase.get("name", "Unknown Phase")
                for task in phase.get("tasks", []):
                    task["phase_name"] = phase_name
                    tasks.append(task)
        elif "tasks" in wbs_data:
            tasks = wbs_data["tasks"]
        
        return tasks
    
    def get_build_tasks(self, execution_id: int) -> Dict[str, Any]:
        """
        Récupère les tâches BUILD pour une exécution.
        """
        from app.models.task_execution import TaskExecution
        
        tasks = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution_id
        ).order_by(TaskExecution.id).all()
        
        result = []
        for task in tasks:
            result.append({
                "id": task.id,
                "task_id": task.task_id,
                "task_name": task.task_name,
                "phase_name": task.phase_name,
                "assigned_agent": task.assigned_agent,
                "status": task.status.value if task.status else "pending",
                "attempt_count": task.attempt_count or 0,
                "depends_on": task.depends_on or [],
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            })
        
        return {
            "execution_id": execution_id,
            "tasks": result,
            "total": len(result),
            "completed": sum(1 for t in result if t["status"] == "completed"),
            "failed": sum(1 for t in result if t["status"] == "failed"),
            "running": sum(1 for t in result if t["status"] == "running")
        }
    
    def pause_build(self, execution_id: int) -> Dict[str, Any]:
        """
        Met en pause la phase BUILD.
        """
        from app.models.execution import Execution, ExecutionStatus
        from sqlalchemy.orm.attributes import flag_modified

        
        execution = self.db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            return {"success": False, "error": "Execution not found", "code": 404}
        
        if execution.status.value not in ["running", "building"]:
            return {"success": False, "error": f"Cannot pause. Status is {execution.status.value}", "code": 400}
        
        # Set pause flag
        if not execution.agent_execution_status:
            execution.agent_execution_status = {}
        execution.agent_execution_status["build_paused"] = True
        execution.agent_execution_status["paused_at"] = datetime.now(timezone.utc).isoformat()
        flag_modified(execution, "agent_execution_status")
        
        self.db.commit()
        
        return {
            "success": True,
            "status": "paused",
            "message": "BUILD paused. Current task will complete, then execution will wait.",
            "execution_id": execution_id
        }
    
    def resume_build(self, execution_id: int) -> Dict[str, Any]:
        """
        Reprend la phase BUILD après une pause.
        """
        from app.models.execution import Execution
        from sqlalchemy.orm.attributes import flag_modified

        
        execution = self.db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            return {"success": False, "error": "Execution not found", "code": 404}
        
        if not execution.agent_execution_status or not execution.agent_execution_status.get("build_paused"):
            return {"success": False, "error": "BUILD is not paused", "code": 400}
        
        # Clear pause flag
        execution.agent_execution_status["build_paused"] = False
        execution.agent_execution_status["resumed_at"] = datetime.now(timezone.utc).isoformat()
        flag_modified(execution, "agent_execution_status")
        
        self.db.commit()
        
        return {
            "success": True,
            "status": "resumed",
            "message": "BUILD resumed",
            "execution_id": execution_id
        }

