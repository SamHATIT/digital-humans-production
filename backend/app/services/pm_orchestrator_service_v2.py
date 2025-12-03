"""
PM Orchestrator Service V2 - Complete SDS Workflow

Workflow:
1. Sophie PM → extract_br (atomic BRs from raw requirements)
2. Olivia BA → called N times (1 per BR) → generates UCs
3. Marcus Architect → 4 sequential calls (as_is, gap, design, wbs)
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
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.database import SessionLocal
from app.models.project import Project
from app.models.execution import Execution, ExecutionStatus
from app.models.agent_deliverable import AgentDeliverable
from app.models.deliverable_item import DeliverableItem
try:
    from app.models.validation_gate import ValidationGate
    HAS_VALIDATION_GATE = True
except ImportError:
    HAS_VALIDATION_GATE = False
# ValidationGate peut ne pas exister, on le gère dynamiquement
import logging
from app.salesforce_config import salesforce_config
from app.services.document_generator import generate_professional_sds, ProfessionalDocumentGenerator

logger = logging.getLogger(__name__)

# Agent script paths
AGENTS_PATH = Path("/app/agents/roles")

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
}

# Validation gates configuration
VALIDATION_GATES = [
    {"gate_number": 1, "name": "Requirements Analysis", "required_artifacts": ["BR", "UC"], "agents": ["pm", "ba"]},
    {"gate_number": 2, "name": "Solution Design", "required_artifacts": ["ARCH", "GAP", "WBS"], "agents": ["architect"]},
    {"gate_number": 3, "name": "Technical Specifications", "required_artifacts": ["APEX", "LWC", "CONFIG"], "agents": ["apex", "lwc", "admin"]},
]


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
        sfdx_metadata: Optional[Dict] = None
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
            
            # ========================================
            # PHASE 1: Sophie PM - Extract BRs
            # ========================================
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
            # self._update_gate_progress(  # Disabled
            # execution_id, 1, "BR", len(business_requirements))
            
            logger.info(f"[Phase 1] ✅ Extracted {len(business_requirements)} Business Requirements")
            self._update_progress(execution, "pm", "completed", 15, f"Extracted {len(business_requirements)} BRs")
            
            # ========================================
            # ========================================
            # PHASE 2: Olivia BA - Generate UCs per BR (DATABASE-FIRST)
            # ========================================
            logger.info(f"[Phase 2] Olivia BA - Generating Use Cases (database-first)")
            self._update_progress(execution, "ba", "running", 18, "Starting Use Case generation...")
            
            ba_tokens_total = 0
            ba_ucs_saved = 0
            
            for i, br in enumerate(business_requirements):
                br_id = br.get("id", f"BR-{i+1:03d}")
                progress = 18 + ((i + 1) / len(business_requirements)) * 27  # 18-45%
                
                self._update_progress(execution, "ba", "running", int(progress), 
                                      f"Processing {br_id} ({i+1}/{len(business_requirements)})...")
                
                uc_result = await self._run_agent(
                    agent_id="ba",
                    input_data={"business_requirement": br},
                    execution_id=execution_id,
                    project_id=project_id
                )
                
                if uc_result.get("success"):
                    # Extract metadata
                    metadata = uc_result["output"].get("metadata", {})
                    tokens_used = metadata.get("tokens_used", 0)
                    model_used = metadata.get("model", "unknown")
                    exec_time = metadata.get("execution_time_seconds", 0)
                    
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
            self._update_progress(execution, "ba", "completed", 45, f"Generated {uc_stats["parsed"]} UCs")
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
            
            # 3.2: Gap Analysis (Compare requirements vs current state)
            self._update_progress(execution, "architect", "running", 58, "Identifying gaps...")
            
            gap_result = await self._run_agent(
                agent_id="architect",
                mode="gap",
                input_data={
                    "requirements": br_result["output"]["content"].get("business_requirements", []),
                    "use_cases": self._get_use_cases(execution_id, 15),
                    "as_is": results["artifacts"].get("AS_IS", {}).get("content", {})
                },
                execution_id=execution_id,
                project_id=project_id
            )
            
            if gap_result.get("success"):
                results["artifacts"]["GAP"] = gap_result["output"]
                architect_tokens += gap_result["output"]["metadata"].get("tokens_used", 0)
                self._save_deliverable(execution_id, "architect", "gap_analysis", gap_result["output"])
                logger.info(f"[Phase 3.2] ✅ Gap Analysis (GAP-001)")
            else:
                results["artifacts"]["GAP"] = {"artifact_id": "GAP-001", "content": {"gaps": []}}
                logger.warning(f"[Phase 3.2] ⚠️ Gap Analysis failed")
            
            # 3.3: Solution Design (Design solution to address gaps)
            self._update_progress(execution, "architect", "running", 66, "Designing solution...")
            
            design_result = await self._run_agent(
                agent_id="architect",
                mode="design",
                input_data={
                    "project_summary": br_result["output"]["content"].get("project_summary", ""),
                    "use_cases": self._get_use_cases(execution_id, 15),
                    "gaps": results["artifacts"].get("GAP", {}).get("content", {}).get("gaps", []),
                    "as_is": results["artifacts"].get("AS_IS", {}).get("content", {})
                },
                execution_id=execution_id,
                project_id=project_id
            )
            
            if design_result.get("success"):
                results["artifacts"]["ARCHITECTURE"] = design_result["output"]
                architect_tokens += design_result["output"]["metadata"].get("tokens_used", 0)
                self._save_deliverable(execution_id, "architect", "solution_design", design_result["output"])
                logger.info(f"[Phase 3.3] ✅ Solution Design (ARCH-001)")
            
            # 3.4: WBS (Break down implementation tasks)
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
                logger.info(f"[Phase 3.4] ✅ WBS (WBS-001)")
            
            results["agent_outputs"]["architect"] = {
                "design": results["artifacts"].get("ARCHITECTURE"),
                "as_is": results["artifacts"].get("AS_IS"),
                "gap": results["artifacts"].get("GAP"),
                "wbs": results["artifacts"].get("WBS")
            }
            results["metrics"]["tokens_by_agent"]["architect"] = architect_tokens
            results["metrics"]["total_tokens"] += architect_tokens
            
            self._update_progress(execution, "architect", "completed", 75, "Architecture complete")
            
            # ========================================
            # PHASE 4: SDS Expert Agents (Systematic)
            # ========================================
            # These 4 experts enrich the SDS with specialized sections:
            # - Aisha (Data): Data Migration Strategy
            # - Lucas (Trainer): Training & Change Management Plan
            # - Elena (QA): Test Strategy & QA Approach
            # - Jordan (DevOps): CI/CD & Deployment Strategy
            
            SDS_EXPERTS = ["data", "trainer", "qa", "devops"]
            logger.info(f"[Phase 4] SDS Expert Agents: {SDS_EXPERTS}")
            
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
            
            for i, agent_id in enumerate(SDS_EXPERTS):
                progress = expert_progress_start + ((i + 1) / len(SDS_EXPERTS)) * (expert_progress_end - expert_progress_start)
                agent_name = AGENT_CONFIG[agent_id]["display_name"]
                
                self._update_progress(execution, agent_id, "running", int(progress), f"{agent_name} creating specifications...")
                
                # Build expert-specific input
                expert_input = dict(common_context)
                
                # Add expert-specific context
                if agent_id == "data":
                    expert_input["focus"] = "data_migration"
                elif agent_id == "trainer":
                    expert_input["focus"] = "training_adoption"
                elif agent_id == "qa":
                    expert_input["focus"] = "quality_assurance"
                elif agent_id == "devops":
                    expert_input["focus"] = "deployment_cicd"
                
                try:
                    expert_result = await self._run_agent(
                        agent_id=agent_id,
                        input_data=expert_input,
                        execution_id=execution_id,
                        project_id=project_id
                    )
                    
                    if expert_result.get("success"):
                        results["agent_outputs"][agent_id] = expert_result["output"]
                        results["artifacts"][f"{agent_id.upper()}_SPECS"] = expert_result["output"]
                        self._track_tokens(agent_id, expert_result["output"], results)
                        self._save_deliverable(execution_id, agent_id, f"{agent_id}_specifications", expert_result["output"])
                        logger.info(f"[Phase 4] ✅ {agent_name} completed")
                        self._update_progress(execution, agent_id, "completed", int(progress), f"{agent_name} done")
                    else:
                        logger.warning(f"[Phase 4] ⚠️ {agent_name} failed: {expert_result.get('error')}")
                        self._update_progress(execution, agent_id, "failed", int(progress), f"Failed: {expert_result.get('error', 'Unknown')[:50]}")
                except Exception as e:
                    logger.error(f"[Phase 4] ❌ {agent_name} exception: {str(e)}")
                    self._update_progress(execution, agent_id, "failed", int(progress), f"Error: {str(e)[:50]}")
            
            # ========================================
            # PHASE 5: Sophie PM - Consolidate SDS
            # ========================================
            logger.info(f"[Phase 5] Sophie PM - Consolidating SDS Document")
            self._update_progress(execution, "pm", "running", 92, "Generating SDS Document...")
            
            # Generate SDS using document generator
            try:
                sds_path = await self._generate_sds_document(
                    project=project,
                    agent_outputs=results["agent_outputs"],
                    artifacts=results["artifacts"],
                    execution_id=execution_id
                )
                results["sds_path"] = sds_path
                execution.sds_document_path = sds_path
                logger.info(f"[Phase 5] ✅ SDS Document: {sds_path}")
            except Exception as e:
                logger.error(f"[Phase 5] SDS generation failed: {e}")
                # Fallback to markdown
                sds_path = self._generate_markdown_sds(project, results["artifacts"], execution_id)
                results["sds_path"] = sds_path
                execution.sds_document_path = sds_path
            
            self._update_progress(execution, "pm", "completed", 98, "SDS Document generated")
            
            # ========================================
            # FINALIZE
            # ========================================
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            execution.total_tokens_used = results["metrics"]["total_tokens"]
            self.db.commit()
            
            logger.info(f"[Complete] Execution {execution_id} finished")
            logger.info(f"[Metrics] Total tokens: {results['metrics']['total_tokens']}")
            logger.info(f"[Metrics] By agent: {results['metrics']['tokens_by_agent']}")
            
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
            
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)
            self.db.commit()
            
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
            
            # Note for Marcus
            "note": "Full metadata available in DB - query salesforce_metadata deliverable for details"
        }
        
        return summary

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
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300  # 5 min timeout
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
            return {"success": False, "error": "Timeout (5 min)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _init_agent_status(self, selected_agents: List[str]) -> Dict:
        """Initialize agent execution status"""
        # Core agents always included
        agents = ["pm", "ba", "architect"]
        # SDS Expert agents (always included for complete SDS)
        SDS_EXPERTS = ["data", "trainer", "qa", "devops"]
        agents.extend(SDS_EXPERTS)
        # Add any additional selected agents
        agents.extend([a for a in selected_agents if a not in agents])
        
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

    def _update_progress(self, execution: Execution, agent_id: str, state: str, progress: int, message: str):
        """Update execution progress for SSE"""
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
        self.db.commit()

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
                uc_id = uc.get("id", f"UC-{br_id[3:]}-{saved_count+1:02d}")
                if self._save_deliverable_item(
                    execution_id=execution_id,
                    agent_id="ba",
                    parent_ref=br_id,
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
        execution_id: int
    ) -> str:
        """Generate professional DOCX SDS document"""
        output_dir = "/app/outputs"
        os.makedirs(output_dir, exist_ok=True)
        
        # Use professional generator
        output_path = generate_professional_sds(
            project=project,
            agent_outputs=agent_outputs,
            execution_id=execution_id,
            output_dir=output_dir
        )
        
        return output_path

    def _generate_markdown_sds(self, project: Project, artifacts: Dict, execution_id: int) -> str:
        """Fallback: Generate Markdown SDS"""
        output_dir = "/app/outputs"
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


# Background execution helper
async def execute_workflow_background(
    db: Session,  # Not used - we create our own session
    execution_id: int,
    project_id: int,
    selected_agents: List[str] = None,
    include_as_is: bool = False,
    sfdx_metadata: Optional[Dict] = None
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
            sfdx_metadata=sfdx_metadata
        )
    finally:
        db_session.close()
