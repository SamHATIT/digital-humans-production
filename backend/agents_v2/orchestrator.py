"""
V2 Orchestrator - Coordinates agents and manages execution flow
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.artifact_service import ArtifactService
from app.schemas.artifact import ArtifactCreate, ArtifactTypeEnum
from .ba_agent import BusinessAnalystAgent
from .architect_agent import ArchitectAgent

logger = logging.getLogger(__name__)


class OrchestratorV2:
    """
    Orchestrates V2 agent execution with artifact-based workflow.
    
    Workflow:
    1. Initialize gates for execution
    2. Run BA agent → produces BR and UC artifacts
    3. Submit Gate 1 for validation
    4. [User approves Gate 1]
    5. Run Architect agent → produces ADR and SPEC artifacts
    6. Submit Gate 2 for validation
    7. [Continue with other agents...]
    """
    
    def __init__(self, execution_id: int, db: Session):
        self.execution_id = execution_id
        self.db = db
        self.artifact_service = ArtifactService(db)
        self.current_phase = None
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize gates for this execution"""
        try:
            gates = self.artifact_service.initialize_gates(self.execution_id)
            return {
                "success": True,
                "execution_id": self.execution_id,
                "gates_created": len(gates),
                "message": "Execution initialized with 6 validation gates"
            }
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return {"success": False, "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get current execution status"""
        progress = self.artifact_service.get_gates_progress(self.execution_id)
        stats = self.artifact_service.get_artifacts_stats(self.execution_id)
        
        return {
            "execution_id": self.execution_id,
            "current_gate": progress["current_gate"],
            "progress_percent": progress["progress_percent"],
            "gates": progress["gates"],
            "artifacts": stats
        }
    
    def run_phase_1_analysis(self, project_requirements: str) -> Dict[str, Any]:
        """
        Phase 1: Business Analysis
        Run BA agent to produce BR and UC artifacts
        """
        self.current_phase = "analysis"
        logger.info(f"[Orchestrator] Starting Phase 1: Analysis for execution {self.execution_id}")
        
        # Create BA agent and execute
        ba_agent = BusinessAnalystAgent(self.execution_id, self.db)
        result = ba_agent.execute(project_requirements)
        
        if not result["success"]:
            return result
        
        # Persist artifacts
        artifacts_created = []
        for artifact_data in result["artifacts"]:
            try:
                artifact = self.artifact_service.create_artifact(ArtifactCreate(
                    execution_id=self.execution_id,
                    artifact_type=ArtifactTypeEnum(artifact_data["artifact_type"]),
                    artifact_code=artifact_data["artifact_code"],
                    title=artifact_data["title"],
                    producer_agent="ba",
                    content=artifact_data["content"],
                    parent_refs=artifact_data.get("parent_refs", [])
                ))
                artifacts_created.append(artifact.to_dict())
            except Exception as e:
                logger.error(f"Failed to create artifact {artifact_data.get('artifact_code')}: {e}")
        
        # Submit Gate 1 for review
        try:
            gate = self.artifact_service.submit_gate_for_review(self.execution_id, 1)
            gate_status = gate.to_dict()
        except Exception as e:
            logger.error(f"Failed to submit Gate 1: {e}")
            gate_status = {"error": str(e)}
        
        return {
            "success": True,
            "phase": "analysis",
            "agent": "ba",
            "artifacts_created": len(artifacts_created),
            "artifacts": artifacts_created,
            "gate_1_status": gate_status,
            "duration_seconds": result["duration_seconds"],
            "next_action": "Approve Gate 1 to proceed to Phase 2 (Architecture)"
        }
    
    def run_phase_2_architecture(self) -> Dict[str, Any]:
        """
        Phase 2: Architecture Design
        Run Architect agent to produce ADR and SPEC artifacts
        Requires Gate 1 to be approved
        """
        self.current_phase = "architecture"
        logger.info(f"[Orchestrator] Starting Phase 2: Architecture for execution {self.execution_id}")
        
        # Check Gate 1 is approved
        gate1 = self.artifact_service.get_gate(self.execution_id, 1)
        if not gate1 or gate1.status != "approved":
            return {
                "success": False,
                "error": "Gate 1 must be approved before running Phase 2",
                "gate_1_status": gate1.status if gate1 else "not_found"
            }
        
        # Get context (approved BR and UC artifacts)
        context_artifacts = self.artifact_service.list_artifacts(
            self.execution_id,
            status="approved",
            current_only=True
        )
        context_artifacts_dict = [a.to_dict() for a in context_artifacts]
        
        # Get answered questions
        context_questions = self.artifact_service.list_questions(self.execution_id)
        context_questions_dict = [q.to_dict() for q in context_questions]
        
        # Build requirements summary from artifacts
        requirements_summary = self._build_requirements_from_artifacts(context_artifacts_dict)
        
        # Create Architect agent and execute
        architect_agent = ArchitectAgent(self.execution_id, self.db)
        result = architect_agent.execute(
            requirements_summary,
            context_artifacts_dict,
            context_questions_dict
        )
        
        if not result["success"]:
            return result
        
        # Persist artifacts
        artifacts_created = []
        for artifact_data in result["artifacts"]:
            try:
                artifact = self.artifact_service.create_artifact(ArtifactCreate(
                    execution_id=self.execution_id,
                    artifact_type=ArtifactTypeEnum(artifact_data["artifact_type"]),
                    artifact_code=artifact_data["artifact_code"],
                    title=artifact_data["title"],
                    producer_agent="architect",
                    content=artifact_data["content"],
                    parent_refs=artifact_data.get("parent_refs", [])
                ))
                artifacts_created.append(artifact.to_dict())
            except Exception as e:
                logger.error(f"Failed to create artifact {artifact_data.get('artifact_code')}: {e}")
        
        # Submit Gate 2 for review
        try:
            gate = self.artifact_service.submit_gate_for_review(self.execution_id, 2)
            gate_status = gate.to_dict()
        except Exception as e:
            logger.error(f"Failed to submit Gate 2: {e}")
            gate_status = {"error": str(e)}
        
        return {
            "success": True,
            "phase": "architecture",
            "agent": "architect",
            "artifacts_created": len(artifacts_created),
            "artifacts": artifacts_created,
            "gate_2_status": gate_status,
            "duration_seconds": result["duration_seconds"],
            "next_action": "Approve Gate 2 to proceed to Phase 3 (Development)"
        }
    
    def _build_requirements_from_artifacts(self, artifacts: List[Dict]) -> str:
        """Build a requirements summary from BR and UC artifacts"""
        lines = ["# PROJECT REQUIREMENTS (from approved artifacts)\n"]
        
        # Group by type
        brs = [a for a in artifacts if a["artifact_type"] == "business_req"]
        ucs = [a for a in artifacts if a["artifact_type"] == "use_case"]
        
        # Add BRs
        if brs:
            lines.append("## Business Requirements\n")
            for br in brs:
                lines.append(f"### {br['artifact_code']}: {br['title']}")
                content = br.get("content", {})
                if content.get("description"):
                    lines.append(f"**Description:** {content['description']}")
                if content.get("business_value"):
                    lines.append(f"**Business Value:** {content['business_value']}")
                if content.get("success_criteria"):
                    lines.append("**Success Criteria:**")
                    for sc in content["success_criteria"]:
                        lines.append(f"  - {sc}")
                lines.append("")
        
        # Add UCs
        if ucs:
            lines.append("## Use Cases\n")
            for uc in ucs:
                lines.append(f"### {uc['artifact_code']}: {uc['title']}")
                content = uc.get("content", {})
                if content.get("description"):
                    lines.append(f"**Description:** {content['description']}")
                if content.get("actors"):
                    actors = content["actors"]
                    lines.append(f"**Primary Actor:** {actors.get('primary', 'N/A')}")
                if content.get("main_flow"):
                    lines.append("**Main Flow:**")
                    for step in content["main_flow"][:5]:  # Limit to first 5 steps
                        lines.append(f"  {step.get('step', '?')}. {step.get('action', 'N/A')}")
                if content.get("salesforce_objects"):
                    lines.append(f"**Salesforce Objects:** {', '.join(content.get('data_requirements', {}).get('salesforce_objects', []))}")
                lines.append("")
        
        return "\n".join(lines)
    
    def approve_current_gate(self) -> Dict[str, Any]:
        """Approve the current pending gate"""
        progress = self.artifact_service.get_gates_progress(self.execution_id)
        current = progress["current_gate"]
        
        if not current:
            return {"success": False, "error": "No pending gate to approve"}
        
        # Check gate is ready for approval
        gate = self.artifact_service.get_gate(self.execution_id, current)
        if gate.status != "ready":
            return {
                "success": False,
                "error": f"Gate {current} is not ready for approval (status: {gate.status})"
            }
        
        approved_gate = self.artifact_service.approve_gate(self.execution_id, current)
        
        return {
            "success": True,
            "gate_approved": current,
            "gate": approved_gate.to_dict(),
            "next_gate": current + 1 if current < 6 else None
        }
    
    def reject_current_gate(self, reason: str) -> Dict[str, Any]:
        """Reject the current pending gate"""
        progress = self.artifact_service.get_gates_progress(self.execution_id)
        current = progress["current_gate"]
        
        if not current:
            return {"success": False, "error": "No pending gate to reject"}
        
        rejected_gate = self.artifact_service.reject_gate(self.execution_id, current, reason)
        
        return {
            "success": True,
            "gate_rejected": current,
            "gate": rejected_gate.to_dict(),
            "reason": reason,
            "next_action": "Review and fix rejected artifacts, then re-run the phase"
        }
