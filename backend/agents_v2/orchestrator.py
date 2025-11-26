"""
V2 Orchestrator - Real multi-agent coordination with iterations
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.artifact_service import ArtifactService
from app.schemas.artifact import (
    ArtifactCreate, ArtifactTypeEnum,
    QuestionCreate, QuestionAnswer
)
from .pm_agent import ProjectManagerAgent
from .ba_agent import BusinessAnalystAgent
from .architect_agent import ArchitectAgent

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3  # Maximum Q&A cycles before forcing gate


class OrchestratorV2:
    """
    Orchestrates V2 agent execution with PM coordination and iterations.
    
    Real Workflow:
    
    Phase 0: PM Analysis
        PM analyzes raw requirements → REQ artifacts + PLAN
        
    Phase 1: Business Analysis  
        BA produces BR/UC → PM reviews → Gate 1
        
    Phase 2: Architecture (with iterations)
        Architect reads BR/UC
        Architect poses questions → BA answers
        [Iterate until clear or max iterations]
        Architect produces ADR/SPEC
        PM reviews → Gate 2
    """
    
    def __init__(self, execution_id: int, db: Session):
        self.execution_id = execution_id
        self.db = db
        self.artifact_service = ArtifactService(db)
        self.iteration_count = 0
    
    # ============ INITIALIZATION ============
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize gates for this execution"""
        try:
            existing = self.artifact_service.list_gates(self.execution_id)
            if existing:
                return {
                    "success": True,
                    "execution_id": self.execution_id,
                    "message": "Execution already initialized",
                    "gates": [g.to_dict() for g in existing]
                }
            
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
        
        # Get pending questions
        pending_questions = self.artifact_service.list_questions(
            self.execution_id, status="pending"
        )
        
        return {
            "execution_id": self.execution_id,
            "current_gate": progress["current_gate"],
            "progress_percent": progress["progress_percent"],
            "gates": progress["gates"],
            "artifacts": stats,
            "pending_questions": len(pending_questions),
            "iteration_count": self.iteration_count
        }
    
    # ============ PHASE 0: PM ANALYSIS ============
    
    def run_phase_0_pm_analysis(self, raw_requirements: str) -> Dict[str, Any]:
        """
        Phase 0: PM analyzes requirements
        Creates structured REQ artifacts and execution PLAN
        """
        logger.info(f"[Orchestrator] Phase 0: PM Analysis for execution {self.execution_id}")
        
        pm_agent = ProjectManagerAgent(self.execution_id, self.db)
        result = pm_agent.analyze_requirements(raw_requirements)
        
        if not result["success"]:
            return result
        
        # Persist PM artifacts
        artifacts_created = self._persist_artifacts(result["artifacts"], "pm")
        
        return {
            "success": True,
            "phase": "pm_analysis",
            "agent": "pm",
            "artifacts_created": len(artifacts_created),
            "artifacts": artifacts_created,
            "duration_seconds": result["duration_seconds"],
            "next_action": "Run Phase 1 (Business Analysis)"
        }
    
    # ============ PHASE 1: BUSINESS ANALYSIS ============
    
    def run_phase_1_analysis(self, project_requirements: str = None) -> Dict[str, Any]:
        """
        Phase 1: BA produces BR and UC artifacts
        PM reviews quality before Gate 1
        """
        logger.info(f"[Orchestrator] Phase 1: Business Analysis for execution {self.execution_id}")
        
        # Get requirements from REQ artifacts or use provided
        if not project_requirements:
            req_artifacts = self.artifact_service.list_artifacts(
                self.execution_id, artifact_type="requirement"
            )
            if req_artifacts:
                project_requirements = self._build_requirements_text(req_artifacts)
            else:
                return {"success": False, "error": "No requirements found. Run Phase 0 first."}
        
        # Run BA Agent
        ba_agent = BusinessAnalystAgent(self.execution_id, self.db)
        result = ba_agent.execute(project_requirements)
        
        if not result["success"]:
            return result
        
        # Persist BA artifacts
        artifacts_created = self._persist_artifacts(result["artifacts"], "ba")
        
        # PM reviews BA output
        pm_agent = ProjectManagerAgent(self.execution_id, self.db)
        review_result = pm_agent.review_ba_output(artifacts_created, project_requirements)
        
        review_artifacts = []
        if review_result["success"]:
            review_artifacts = self._persist_artifacts(review_result["artifacts"], "pm")
        
        # Check if ready for gate
        ready_for_gate = self._check_review_ready(review_artifacts)
        
        if ready_for_gate:
            # Submit Gate 1
            try:
                gate = self.artifact_service.submit_gate_for_review(self.execution_id, 1)
                gate_status = gate.to_dict()
            except Exception as e:
                gate_status = {"error": str(e)}
        else:
            gate_status = {"status": "not_ready", "reason": "PM review indicates improvements needed"}
        
        return {
            "success": True,
            "phase": "analysis",
            "agent": "ba",
            "artifacts_created": len(artifacts_created),
            "artifacts": artifacts_created,
            "pm_review": review_artifacts,
            "ready_for_gate": ready_for_gate,
            "gate_1_status": gate_status,
            "duration_seconds": result["duration_seconds"],
            "next_action": "Approve Gate 1 to proceed to Phase 2" if ready_for_gate else "Review PM feedback and re-run Phase 1"
        }
    
    # ============ PHASE 2: ARCHITECTURE WITH ITERATIONS ============
    
    def run_phase_2_architecture(self) -> Dict[str, Any]:
        """
        Phase 2: Architecture with BA ↔ Architect iterations
        
        Flow:
        1. Architect reviews BR/UC
        2. Architect poses questions if needed
        3. BA answers questions
        4. Repeat until clear or max iterations
        5. Architect produces ADR/SPEC
        6. PM reviews → Gate 2
        """
        logger.info(f"[Orchestrator] Phase 2: Architecture for execution {self.execution_id}")
        
        # Check Gate 1 is approved
        gate1 = self.artifact_service.get_gate(self.execution_id, 1)
        if not gate1 or gate1.status != "approved":
            return {
                "success": False,
                "error": "Gate 1 must be approved before Phase 2",
                "gate_1_status": gate1.status if gate1 else "not_found"
            }
        
        # Get approved BA artifacts for context
        ba_artifacts = self.artifact_service.list_artifacts(
            self.execution_id, status="approved", current_only=True
        )
        ba_artifacts_dict = [a.to_dict() for a in ba_artifacts if a.artifact_type in ["business_req", "use_case"]]
        
        # Build context
        context_text = self._build_requirements_from_artifacts(ba_artifacts_dict)
        
        # Run Architect - first pass (may generate questions)
        architect_agent = ArchitectAgent(self.execution_id, self.db)
        
        # Get any existing answered questions
        answered_questions = self.artifact_service.list_questions(
            self.execution_id, status="answered"
        )
        answered_dict = [q.to_dict() for q in answered_questions]
        
        result = architect_agent.execute(
            context_text,
            ba_artifacts_dict,
            answered_dict
        )
        
        if not result["success"]:
            return result
        
        # Separate artifacts and questions from response
        adr_spec_artifacts = [a for a in result["artifacts"] if a["artifact_type"] in ["adr", "spec"]]
        question_artifacts = [a for a in result["artifacts"] if a["artifact_type"] == "question"]
        
        # If architect has questions, create them and trigger BA iteration
        if question_artifacts and self.iteration_count < MAX_ITERATIONS:
            return self._handle_architect_questions(
                question_artifacts,
                ba_artifacts_dict,
                context_text,
                result["duration_seconds"]
            )
        
        # No questions or max iterations - persist ADR/SPEC
        artifacts_created = self._persist_artifacts(adr_spec_artifacts, "architect")
        
        # PM reviews architecture
        pm_agent = ProjectManagerAgent(self.execution_id, self.db)
        all_artifacts = ba_artifacts_dict + artifacts_created
        review_result = pm_agent.review_ba_output(all_artifacts, context_text)  # Reuse review method
        
        review_artifacts = []
        if review_result["success"]:
            review_artifacts = self._persist_artifacts(review_result["artifacts"], "pm")
        
        # Submit Gate 2
        try:
            gate = self.artifact_service.submit_gate_for_review(self.execution_id, 2)
            gate_status = gate.to_dict()
        except Exception as e:
            gate_status = {"error": str(e)}
        
        return {
            "success": True,
            "phase": "architecture",
            "agent": "architect",
            "artifacts_created": len(artifacts_created),
            "artifacts": artifacts_created,
            "pm_review": review_artifacts,
            "iterations_used": self.iteration_count,
            "gate_2_status": gate_status,
            "duration_seconds": result["duration_seconds"],
            "next_action": "Approve Gate 2 to proceed to Phase 3 (Development)"
        }
    
    def _handle_architect_questions(
        self,
        question_artifacts: List[Dict],
        ba_artifacts: List[Dict],
        context_text: str,
        duration: float
    ) -> Dict[str, Any]:
        """
        Handle iteration: Architect asked questions, BA must answer
        """
        self.iteration_count += 1
        logger.info(f"[Orchestrator] Iteration {self.iteration_count}: Architect posed {len(question_artifacts)} questions")
        
        # Create question records
        questions_created = []
        for q in question_artifacts:
            try:
                question_code = self.artifact_service.get_next_question_code(self.execution_id)
                question = self.artifact_service.create_question(QuestionCreate(
                    execution_id=self.execution_id,
                    question_code=question_code,
                    from_agent="architect",
                    to_agent=q.get("to_agent", "ba"),
                    context=q.get("content", {}).get("context", q.get("context", "")),
                    question=q.get("content", {}).get("question", q.get("question", "")),
                    related_artifacts=q.get("related_artifacts", q.get("parent_refs", []))
                ))
                questions_created.append(question.to_dict())
            except Exception as e:
                logger.error(f"Failed to create question: {e}")
        
        # Now run BA to answer the questions
        ba_agent = BusinessAnalystAgent(self.execution_id, self.db)
        
        # Build prompt for BA to answer questions
        answer_prompt = self._build_answer_prompt(questions_created, ba_artifacts)
        
        ba_result = ba_agent.execute(answer_prompt, ba_artifacts, [])
        
        if ba_result["success"]:
            # Extract answers from BA response and update questions
            self._process_ba_answers(ba_result["raw_response"], questions_created)
        
        return {
            "success": True,
            "phase": "architecture_iteration",
            "iteration": self.iteration_count,
            "questions_asked": len(questions_created),
            "questions": questions_created,
            "ba_responded": ba_result["success"],
            "duration_seconds": duration,
            "next_action": f"Continue Phase 2 (iteration {self.iteration_count}/{MAX_ITERATIONS})",
            "auto_continue": True  # Signal to continue automatically
        }
    
    def continue_phase_2(self) -> Dict[str, Any]:
        """Continue Phase 2 after an iteration"""
        return self.run_phase_2_architecture()
    
    # ============ HELPER METHODS ============
    
    def _persist_artifacts(self, artifacts: List[Dict], producer: str) -> List[Dict]:
        """Persist artifacts to database"""
        created = []
        for artifact_data in artifacts:
            try:
                # Determine artifact type enum
                artifact_type_str = artifact_data["artifact_type"]
                try:
                    artifact_type = ArtifactTypeEnum(artifact_type_str)
                except ValueError:
                    logger.warning(f"Unknown artifact type: {artifact_type_str}")
                    continue
                
                artifact = self.artifact_service.create_artifact(ArtifactCreate(
                    execution_id=self.execution_id,
                    artifact_type=artifact_type,
                    artifact_code=artifact_data["artifact_code"],
                    title=artifact_data["title"],
                    producer_agent=producer,
                    content=artifact_data["content"],
                    parent_refs=artifact_data.get("parent_refs", [])
                ))
                created.append(artifact.to_dict())
            except Exception as e:
                logger.error(f"Failed to create artifact {artifact_data.get('artifact_code')}: {e}")
        return created
    
    def _build_requirements_text(self, req_artifacts: List) -> str:
        """Build requirements text from REQ artifacts"""
        lines = ["# PROJECT REQUIREMENTS\n"]
        for req in req_artifacts:
            content = req.content if hasattr(req, 'content') else req.get('content', {})
            lines.append(f"## {req.artifact_code if hasattr(req, 'artifact_code') else req.get('artifact_code')}")
            lines.append(f"{content.get('raw_text', content.get('description', ''))}\n")
        return "\n".join(lines)
    
    def _build_requirements_from_artifacts(self, artifacts: List[Dict]) -> str:
        """Build context from BR/UC artifacts"""
        lines = ["# APPROVED BUSINESS REQUIREMENTS AND USE CASES\n"]
        
        brs = [a for a in artifacts if a["artifact_type"] == "business_req"]
        ucs = [a for a in artifacts if a["artifact_type"] == "use_case"]
        
        for br in brs:
            lines.append(f"## {br['artifact_code']}: {br['title']}")
            content = br.get("content", {})
            lines.append(f"Description: {content.get('description', 'N/A')}")
            lines.append(f"Business Value: {content.get('business_value', 'N/A')}")
            lines.append("")
        
        for uc in ucs:
            lines.append(f"## {uc['artifact_code']}: {uc['title']}")
            content = uc.get("content", {})
            lines.append(f"Parent BR: {content.get('parent_br', uc.get('parent_refs', ['N/A'])[0] if uc.get('parent_refs') else 'N/A')}")
            lines.append(f"Description: {content.get('description', 'N/A')}")
            actors = content.get("actors", {})
            lines.append(f"Primary Actor: {actors.get('primary', 'N/A')}")
            main_flow = content.get("main_flow", [])
            if main_flow:
                lines.append("Main Flow:")
                for step in main_flow[:5]:
                    lines.append(f"  {step.get('step')}. {step.get('action', step.get('actor', 'N/A'))}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_answer_prompt(self, questions: List[Dict], ba_artifacts: List[Dict]) -> str:
        """Build prompt for BA to answer Architect's questions"""
        lines = ["# QUESTIONS FROM ARCHITECT - PLEASE ANSWER\n"]
        lines.append("The Solution Architect has questions about your BR/UC artifacts.")
        lines.append("Please answer each question to help clarify the requirements.\n")
        
        for q in questions:
            lines.append(f"## {q['question_code']}")
            lines.append(f"**Context:** {q['context']}")
            lines.append(f"**Question:** {q['question']}")
            if q.get('related_artifacts'):
                lines.append(f"**Related to:** {', '.join(q['related_artifacts'])}")
            lines.append("")
        
        lines.append("\nProvide your answers in this format for each question:")
        lines.append("```json")
        lines.append('{')
        lines.append('  "question_code": "Q-001",')
        lines.append('  "answer": "Your detailed answer",')
        lines.append('  "recommendation": "Optional recommendation for architect"')
        lines.append('}')
        lines.append("```")
        
        return "\n".join(lines)
    
    def _process_ba_answers(self, ba_response: str, questions: List[Dict]) -> None:
        """Extract answers from BA response and update question records"""
        try:
            answers = BaseAgentV2.extract_json_from_response(ba_response)
            
            for answer_data in answers:
                question_code = answer_data.get("question_code")
                if question_code:
                    try:
                        self.artifact_service.answer_question(
                            question_code,
                            self.execution_id,
                            QuestionAnswer(
                                answer=answer_data.get("answer", ""),
                                recommendation=answer_data.get("recommendation")
                            )
                        )
                    except Exception as e:
                        logger.error(f"Failed to save answer for {question_code}: {e}")
        except Exception as e:
            logger.error(f"Failed to process BA answers: {e}")
    
    def _check_review_ready(self, review_artifacts: List[Dict]) -> bool:
        """Check if PM review indicates ready for gate"""
        for review in review_artifacts:
            content = review.get("content", {})
            if content.get("ready_for_next_phase") is False:
                return False
            if content.get("iteration_status") == "needs_user_input":
                return False
            overall_score = content.get("overall_score", 0)
            if overall_score < 70:
                return False
        return True
    
    # ============ GATE ACTIONS ============
    
    def approve_current_gate(self) -> Dict[str, Any]:
        """Approve the current pending gate"""
        progress = self.artifact_service.get_gates_progress(self.execution_id)
        current = progress["current_gate"]
        
        if not current:
            return {"success": False, "error": "No pending gate to approve"}
        
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
            "reason": reason
        }


# Import for answer extraction
from .base_agent import BaseAgentV2
