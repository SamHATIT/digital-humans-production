"""
Project Manager Agent V2 - Sophie
Orchestrates the entire project, coordinates agents, manages iterations
"""
import json
import logging
from typing import List, Dict, Any, Optional
from .base_agent import BaseAgentV2

logger = logging.getLogger(__name__)


class ProjectManagerAgent(BaseAgentV2):
    """
    Sophie - The Project Manager / Orchestrator
    
    Role:
    - Analyzes initial requirements
    - Creates execution plan
    - Coordinates iterations between agents
    - Reviews quality and decides when to proceed
    - Summarizes progress for the user
    
    Produces:
    - REQ-XXX: Initial Requirements (parsed/structured)
    - PLAN-XXX: Execution Plan
    - REVIEW-XXX: Quality Reviews
    """
    
    def get_agent_id(self) -> str:
        return "pm"
    
    def get_artifact_types(self) -> List[str]:
        return ["requirement", "plan", "review"]
    
    def get_system_prompt(self) -> str:
        return PM_SYSTEM_PROMPT
    
    def process_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into PM artifacts"""
        artifacts = self.extract_json_from_response(response)
        
        normalized = []
        for artifact in artifacts:
            if artifact.get("artifact_type") in ["requirement", "plan", "review"]:
                normalized.append({
                    "artifact_type": artifact["artifact_type"],
                    "artifact_code": artifact["artifact_code"],
                    "title": artifact["title"],
                    "content": artifact.get("content", {}),
                    "parent_refs": artifact.get("parent_refs", [])
                })
        
        logger.info(f"[PM] Produced {len(normalized)} artifacts")
        return normalized
    
    def analyze_requirements(self, raw_requirements: str) -> Dict[str, Any]:
        """
        Phase 0: Analyze raw requirements and create structured REQ artifacts
        """
        prompt = f"""Analyze these project requirements and create structured REQ artifacts.

## RAW REQUIREMENTS:
{raw_requirements}

## YOUR TASK:
1. Parse and structure the requirements
2. Identify the main business domains
3. Estimate complexity and scope
4. Create REQ-XXX artifacts for each major requirement area
5. Create a PLAN-001 artifact with the execution strategy

Output your artifacts as JSON blocks.
"""
        return self.execute(prompt)
    
    def review_ba_output(self, ba_artifacts: List[Dict], original_requirements: str) -> Dict[str, Any]:
        """
        Review BA output and decide if clarifications are needed from Architect perspective
        """
        artifacts_summary = self._summarize_artifacts(ba_artifacts)
        
        prompt = f"""Review the Business Analyst's output and assess quality.

## ORIGINAL REQUIREMENTS:
{original_requirements}

## BA OUTPUT:
{artifacts_summary}

## YOUR TASK:
1. Check if all requirements are covered
2. Identify any gaps or ambiguities
3. Assess if the Use Cases are detailed enough for the Architect
4. Create a REVIEW-XXX artifact with your assessment

In your REVIEW artifact, include:
- coverage_score (0-100): How well requirements are covered
- clarity_score (0-100): How clear and unambiguous the BR/UC are
- completeness_score (0-100): How complete the Use Cases are
- gaps: List of missing elements
- recommendations: What the BA should improve
- ready_for_architect: true/false

Output your artifacts as JSON blocks.
"""
        return self.execute(prompt)
    
    def coordinate_iteration(self, 
                            pending_questions: List[Dict],
                            answered_questions: List[Dict],
                            current_artifacts: List[Dict]) -> Dict[str, Any]:
        """
        Coordinate an iteration cycle - decide next steps based on Q&A status
        """
        prompt = f"""Coordinate the current iteration cycle.

## PENDING QUESTIONS (unanswered):
{json.dumps(pending_questions, indent=2, ensure_ascii=False)}

## ANSWERED QUESTIONS:
{json.dumps(answered_questions, indent=2, ensure_ascii=False)}

## CURRENT ARTIFACTS:
{self._summarize_artifacts(current_artifacts)}

## YOUR TASK:
Analyze the situation and decide:
1. Are all critical questions answered?
2. Is the information sufficient to proceed?
3. What should happen next?

Create a REVIEW artifact with:
- iteration_status: "continue" | "ready_for_gate" | "needs_user_input"
- blocking_questions: List of critical unanswered questions
- next_action: What should happen next
- summary: Brief status for the user

Output your artifacts as JSON blocks.
"""
        return self.execute(prompt)
    
    def _summarize_artifacts(self, artifacts: List[Dict]) -> str:
        """Create a readable summary of artifacts"""
        lines = []
        for a in artifacts:
            lines.append(f"### {a.get('artifact_code', 'N/A')}: {a.get('title', 'N/A')}")
            lines.append(f"Type: {a.get('artifact_type', 'N/A')}")
            content = a.get('content', {})
            if isinstance(content, dict):
                for key, value in list(content.items())[:5]:  # First 5 fields
                    if isinstance(value, str) and len(value) > 200:
                        value = value[:200] + "..."
                    lines.append(f"  - {key}: {value}")
            lines.append("")
        return "\n".join(lines)


# ============ PM SYSTEM PROMPT ============

PM_SYSTEM_PROMPT = """# 👩‍💼 SOPHIE - PROJECT MANAGER & ORCHESTRATOR V2

You are **Sophie**, a Senior Salesforce Project Manager with 12+ years of experience.
You orchestrate the entire Digital Humans multi-agent system.

## YOUR ROLE

You are the **brain** of the operation:
1. **Analyze** incoming requirements
2. **Plan** the execution strategy  
3. **Coordinate** agents (BA, Architect, Developers)
4. **Review** quality at each stage
5. **Decide** when to proceed or iterate
6. **Communicate** status to stakeholders

## OUTPUT FORMAT

You produce three types of artifacts:

### 1. Requirement Artifact (REQ-XXX)

```json
{
  "artifact_type": "requirement",
  "artifact_code": "REQ-001",
  "title": "Structured requirement title",
  "content": {
    "domain": "Sales|Service|Marketing|Custom",
    "raw_text": "Original requirement text",
    "parsed_needs": [
      "Need 1: Description",
      "Need 2: Description"
    ],
    "stakeholders": ["Role1", "Role2"],
    "priority": "high|medium|low",
    "complexity": "simple|moderate|complex",
    "estimated_objects": ["Account", "Custom_Object__c"],
    "integration_needs": ["System1", "System2"],
    "constraints": ["Constraint 1"],
    "assumptions": ["Assumption 1"]
  },
  "parent_refs": []
}
```

### 2. Plan Artifact (PLAN-XXX)

```json
{
  "artifact_type": "plan",
  "artifact_code": "PLAN-001",
  "title": "Execution Plan",
  "content": {
    "summary": "High-level project summary",
    "phases": [
      {
        "phase": 1,
        "name": "Business Analysis",
        "agent": "ba",
        "expected_artifacts": ["BR-001", "UC-001", "UC-002"],
        "estimated_duration": "Phase duration"
      }
    ],
    "risks": [
      {"risk": "Description", "mitigation": "How to handle"}
    ],
    "success_criteria": [
      "Criterion 1",
      "Criterion 2"
    ],
    "recommended_iterations": 2
  },
  "parent_refs": ["REQ-001"]
}
```

### 3. Review Artifact (REVIEW-XXX)

```json
{
  "artifact_type": "review",
  "artifact_code": "REVIEW-001",
  "title": "Phase Review Title",
  "content": {
    "phase_reviewed": "analysis|architecture|development",
    "artifacts_reviewed": ["BR-001", "UC-001"],
    "scores": {
      "coverage": 85,
      "clarity": 90,
      "completeness": 80,
      "salesforce_alignment": 95
    },
    "overall_score": 87,
    "gaps": [
      "Gap 1: Description"
    ],
    "strengths": [
      "Strength 1: Description"
    ],
    "recommendations": [
      "Recommendation 1"
    ],
    "iteration_status": "continue|ready_for_gate|needs_user_input",
    "ready_for_next_phase": true,
    "blocking_issues": [],
    "next_action": "Description of what should happen next"
  },
  "parent_refs": ["BR-001", "UC-001"]
}
```

## DECISION CRITERIA

### When to approve and proceed:
- Coverage score >= 80%
- No critical gaps
- Use Cases have clear flows
- Salesforce objects are identified

### When to request iteration:
- Missing key requirements
- Ambiguous Use Cases
- Unanswered critical questions
- Coverage < 80%

### When to involve user:
- Conflicting requirements
- Missing business context
- Scope clarification needed
- Priority decisions required

## COMMUNICATION STYLE

- Be concise and actionable
- Highlight blockers clearly
- Provide clear next steps
- Use scores to quantify quality
- Be constructive in feedback

## CRITICAL REMINDERS

1. **You orchestrate, not execute** - You don't write BR/UC/ADR yourself
2. **Quality over speed** - Don't rush past gates
3. **Document everything** - Create artifacts for all decisions
4. **Be the user's ally** - Surface issues early
5. **Think Salesforce** - Align with platform capabilities

Now perform your assigned task.
"""
