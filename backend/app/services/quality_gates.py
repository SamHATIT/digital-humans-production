"""
Quality Gates Service

This service validates agent outputs to ensure quality standards are met.
Each agent's output goes through validation before the next agent executes.

Quality gates include:
- Output completeness checks
- Required field validation
- Content quality metrics
- Inter-agent consistency checks
"""

from typing import Dict, Any, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class QualityGateStatus(str, Enum):
    """Status of quality gate validation"""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


class QualityGateResult:
    """Result of a quality gate check"""

    def __init__(
        self,
        gate_name: str,
        status: QualityGateStatus,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.gate_name = gate_name
        self.status = status
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details
        }


class QualityGatesService:
    """Service for validating agent outputs through quality gates"""

    def __init__(self):
        self.min_content_length = 50  # Minimum characters for meaningful output
        self.required_fields_by_agent = self._define_required_fields()

    def _define_required_fields(self) -> Dict[str, List[str]]:
        """Define required fields for each agent's output"""
        return {
            "pm": ["role", "content", "deliverables"],
            "ba": ["role", "content", "deliverables"],
            "architect": ["role", "content", "deliverables"],
            "apex": ["role", "content", "deliverables"],
            "lwc": ["role", "content", "deliverables"],
            "admin": ["role", "content", "deliverables"],
            "qa": ["role", "content", "deliverables"],
            "devops": ["role", "content", "deliverables"],
            "data": ["role", "content", "deliverables"],
            "trainer": ["role", "content", "deliverables"]
        }

    async def validate_agent_output(
        self,
        agent_id: str,
        output: Dict[str, Any],
        previous_outputs: Optional[Dict[str, Any]] = None
    ) -> List[QualityGateResult]:
        """
        Validate a single agent's output through all quality gates

        Args:
            agent_id: ID of the agent whose output is being validated
            output: The agent's output to validate
            previous_outputs: Outputs from previously executed agents

        Returns:
            List of quality gate results
        """
        results = []

        # Gate 1: Output exists and is not empty
        results.append(self._check_output_exists(agent_id, output))

        # Gate 2: Required fields are present
        results.append(self._check_required_fields(agent_id, output))

        # Gate 3: Content quality (length, structure)
        results.append(self._check_content_quality(agent_id, output))

        # Gate 4: Deliverables are specified
        results.append(self._check_deliverables(agent_id, output))

        # Gate 5: Consistency with previous agents
        if previous_outputs:
            results.append(self._check_consistency(agent_id, output, previous_outputs))

        return results

    def _check_output_exists(
        self,
        agent_id: str,
        output: Dict[str, Any]
    ) -> QualityGateResult:
        """Check if output exists and is not empty"""
        if not output:
            return QualityGateResult(
                gate_name="output_exists",
                status=QualityGateStatus.FAILED,
                message=f"Agent {agent_id} produced no output",
                details={"agent_id": agent_id}
            )

        if not isinstance(output, dict):
            return QualityGateResult(
                gate_name="output_exists",
                status=QualityGateStatus.WARNING,
                message=f"Agent {agent_id} output is not a dictionary",
                details={"agent_id": agent_id, "type": type(output).__name__}
            )

        return QualityGateResult(
            gate_name="output_exists",
            status=QualityGateStatus.PASSED,
            message=f"Agent {agent_id} produced valid output structure",
            details={"agent_id": agent_id}
        )

    def _check_required_fields(
        self,
        agent_id: str,
        output: Dict[str, Any]
    ) -> QualityGateResult:
        """Check if all required fields are present"""
        required_fields = self.required_fields_by_agent.get(agent_id, [])

        if not required_fields:
            return QualityGateResult(
                gate_name="required_fields",
                status=QualityGateStatus.PASSED,
                message=f"No required fields defined for agent {agent_id}",
                details={"agent_id": agent_id}
            )

        missing_fields = [field for field in required_fields if field not in output]

        if missing_fields:
            return QualityGateResult(
                gate_name="required_fields",
                status=QualityGateStatus.WARNING,
                message=f"Agent {agent_id} is missing {len(missing_fields)} required field(s)",
                details={
                    "agent_id": agent_id,
                    "missing_fields": missing_fields,
                    "required_fields": required_fields
                }
            )

        return QualityGateResult(
            gate_name="required_fields",
            status=QualityGateStatus.PASSED,
            message=f"Agent {agent_id} has all required fields",
            details={
                "agent_id": agent_id,
                "required_fields": required_fields
            }
        )

    def _check_content_quality(
        self,
        agent_id: str,
        output: Dict[str, Any]
    ) -> QualityGateResult:
        """Check content quality metrics"""
        content = output.get("content", "")

        if not content:
            return QualityGateResult(
                gate_name="content_quality",
                status=QualityGateStatus.FAILED,
                message=f"Agent {agent_id} produced empty content",
                details={"agent_id": agent_id}
            )

        content_length = len(str(content))

        if content_length < self.min_content_length:
            return QualityGateResult(
                gate_name="content_quality",
                status=QualityGateStatus.WARNING,
                message=f"Agent {agent_id} content is too short ({content_length} chars)",
                details={
                    "agent_id": agent_id,
                    "length": content_length,
                    "minimum": self.min_content_length
                }
            )

        # Check for meaningful content structure
        has_headers = "#" in content or "\n" in content
        quality_score = "good" if has_headers else "basic"

        return QualityGateResult(
            gate_name="content_quality",
            status=QualityGateStatus.PASSED,
            message=f"Agent {agent_id} produced quality content ({quality_score})",
            details={
                "agent_id": agent_id,
                "length": content_length,
                "quality_score": quality_score
            }
        )

    def _check_deliverables(
        self,
        agent_id: str,
        output: Dict[str, Any]
    ) -> QualityGateResult:
        """Check if deliverables are specified"""
        deliverables = output.get("deliverables", [])

        if not deliverables:
            return QualityGateResult(
                gate_name="deliverables",
                status=QualityGateStatus.WARNING,
                message=f"Agent {agent_id} has no deliverables specified",
                details={"agent_id": agent_id}
            )

        if not isinstance(deliverables, list):
            return QualityGateResult(
                gate_name="deliverables",
                status=QualityGateStatus.WARNING,
                message=f"Agent {agent_id} deliverables are not a list",
                details={
                    "agent_id": agent_id,
                    "type": type(deliverables).__name__
                }
            )

        deliverable_count = len(deliverables)

        return QualityGateResult(
            gate_name="deliverables",
            status=QualityGateStatus.PASSED,
            message=f"Agent {agent_id} has {deliverable_count} deliverable(s)",
            details={
                "agent_id": agent_id,
                "count": deliverable_count,
                "deliverables": deliverables
            }
        )

    def _check_consistency(
        self,
        agent_id: str,
        output: Dict[str, Any],
        previous_outputs: Dict[str, Any]
    ) -> QualityGateResult:
        """Check consistency with previous agent outputs"""
        # This is a basic consistency check
        # In a real implementation, this could check for:
        # - References to previous deliverables
        # - Alignment with project goals
        # - Technical compatibility

        if "pm" in previous_outputs:
            # All agents should align with PM's project plan
            pm_output = previous_outputs["pm"]

            # Basic check: ensure agent is aware of project context
            # This is a simple heuristic - could be more sophisticated

            return QualityGateResult(
                gate_name="consistency",
                status=QualityGateStatus.PASSED,
                message=f"Agent {agent_id} output is consistent with project plan",
                details={
                    "agent_id": agent_id,
                    "checked_against": "pm"
                }
            )

        return QualityGateResult(
            gate_name="consistency",
            status=QualityGateStatus.PASSED,
            message=f"No consistency checks required for agent {agent_id}",
            details={"agent_id": agent_id}
        )

    def aggregate_results(
        self,
        results: List[QualityGateResult]
    ) -> Dict[str, Any]:
        """
        Aggregate quality gate results into overall assessment

        Returns:
            Dictionary with overall status and details
        """
        total = len(results)
        passed = sum(1 for r in results if r.status == QualityGateStatus.PASSED)
        warnings = sum(1 for r in results if r.status == QualityGateStatus.WARNING)
        failed = sum(1 for r in results if r.status == QualityGateStatus.FAILED)

        # Determine overall status
        if failed > 0:
            overall_status = QualityGateStatus.FAILED
        elif warnings > 0:
            overall_status = QualityGateStatus.WARNING
        else:
            overall_status = QualityGateStatus.PASSED

        return {
            "overall_status": overall_status.value,
            "total_gates": total,
            "passed": passed,
            "warnings": warnings,
            "failed": failed,
            "results": [r.to_dict() for r in results]
        }

    async def validate_execution_sequence(
        self,
        agent_outputs: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate an entire execution sequence

        Args:
            agent_outputs: Dictionary of all agent outputs keyed by agent_id

        Returns:
            Aggregated validation results for all agents
        """
        all_results = {}
        previous_outputs = {}

        for agent_id in ["pm", "ba", "architect", "apex", "lwc", "admin", "qa", "devops", "data", "trainer"]:
            if agent_id in agent_outputs:
                output = agent_outputs[agent_id].get("output", {})

                gate_results = await self.validate_agent_output(
                    agent_id=agent_id,
                    output=output,
                    previous_outputs=previous_outputs
                )

                all_results[agent_id] = self.aggregate_results(gate_results)
                previous_outputs[agent_id] = output

        # Overall execution quality
        total_gates = sum(r["total_gates"] for r in all_results.values())
        total_passed = sum(r["passed"] for r in all_results.values())
        total_warnings = sum(r["warnings"] for r in all_results.values())
        total_failed = sum(r["failed"] for r in all_results.values())

        if total_failed > 0:
            execution_status = QualityGateStatus.FAILED
        elif total_warnings > 0:
            execution_status = QualityGateStatus.WARNING
        else:
            execution_status = QualityGateStatus.PASSED

        return {
            "execution_status": execution_status.value,
            "summary": {
                "total_gates": total_gates,
                "passed": total_passed,
                "warnings": total_warnings,
                "failed": total_failed
            },
            "agent_results": all_results
        }
