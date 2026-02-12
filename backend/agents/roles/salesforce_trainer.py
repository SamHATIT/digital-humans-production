#!/usr/bin/env python3
"""
Salesforce Trainer (Lucas) Agent - Two Modes
Mode 1: sds_strategy - Training Strategy for SDS document
Mode 2: delivery - Concrete training materials (guides, video scripts)

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (TrainerAgent.run()) or CLI (python salesforce_trainer.py --mode ...).
"""

import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# LLM imports - clean imports for direct import mode
try:
    from app.services.llm_service import generate_llm_response, LLMProvider
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

# RAG Service
try:
    from app.services.rag_service import get_salesforce_context
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# LLM Logger for debugging (INFRA-002)
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
except ImportError:
    LLM_LOGGER_AVAILABLE = False
    def log_llm_interaction(*args, **kwargs): pass

# Prompt Service for externalized prompts
try:
    from prompts.prompt_service import PromptService
    PROMPT_SERVICE = PromptService()
except ImportError:
    PROMPT_SERVICE = None


# ============================================================================
# MODE 1: SDS STRATEGY - Training & Adoption Strategy for SDS
# ============================================================================
def get_sds_strategy_prompt(solution_design: str, use_cases: str) -> str:
    # Try external prompt first
    if PROMPT_SERVICE:
        try:
            return PROMPT_SERVICE.render("lucas_trainer", "sds_strategy", {
                "solution_design": solution_design[:3000],
                "use_cases": use_cases[:2000],
            })
        except Exception as e:
            logger.warning(f"PromptService fallback for lucas_trainer/sds_strategy: {e}")

    # FALLBACK: original f-string prompt
    return f'''# 🎓 TRAINING & ADOPTION STRATEGY (SDS Section)

You are **Lucas**, a Salesforce Certified Instructor and Change Management expert.

## MISSION
Generate the **Training & Adoption Strategy** section for the Solution Design Specification.
This is a HIGH-LEVEL strategic plan, NOT detailed training materials.

## INPUT CONTEXT
### Solution Design Summary
{solution_design[:3000]}

### Key Use Cases
{use_cases[:2000]}

## OUTPUT FORMAT (JSON)

```json
{{
  "artifact_id": "TRAIN-STRATEGY-001",
  "title": "Training & Adoption Strategy",
  "executive_summary": "2-3 sentence overview of training approach",
  "audience_analysis": {{
    "user_personas": [
      {{
        "role": "Sales Representative",
        "count_estimate": "50-100",
        "sf_experience": "Beginner",
        "key_features": ["Lead Management", "Opportunity Tracking"],
        "training_priority": "High"
      }}
    ],
    "total_users_estimate": "100-200"
  }},
  "training_approach": {{
    "methodology": "Blended Learning (virtual + self-paced)",
    "phasing": [
      {{
        "phase": "Phase 1: Core Users",
        "duration": "Week 1-2",
        "audience": "Sales Reps, Service Agents",
        "focus": "Basic navigation, daily tasks"
      }}
    ],
    "delivery_methods": ["Virtual instructor-led", "Video tutorials", "Quick reference guides"]
  }},
  "curriculum_outline": [
    {{
      "module": "M1: Salesforce Fundamentals",
      "duration": "2 hours",
      "topics": ["Navigation", "Record management", "Search"],
      "audience": "All users"
    }}
  ],
  "adoption_metrics": {{
    "kpis": [
      {{
        "metric": "Login Rate",
        "target": ">90% weekly",
        "measurement": "Salesforce Reports"
      }}
    ],
    "success_criteria": "80% user adoption within 30 days"
  }},
  "change_management": {{
    "communication_plan": "Weekly updates via email + Chatter",
    "champions_program": "5-10 super users per department",
    "feedback_channels": ["Chatter group", "Monthly survey"]
  }},
  "resource_requirements": {{
    "trainers": "2 FTE for 4 weeks",
    "materials": "User guides, video scripts, job aids",
    "tools": "Salesforce Trailhead, video conferencing"
  }},
  "timeline": {{
    "prep_weeks": 2,
    "delivery_weeks": 4,
    "reinforcement_weeks": 4,
    "key_milestones": ["Material ready", "Pilot training", "Full rollout", "Adoption review"]
  }},
  "risks": [
    {{
      "risk": "Low user engagement",
      "mitigation": "Gamification with badges and leaderboards"
    }}
  ]
}}
```

## RULES
1. Keep it STRATEGIC - no detailed step-by-step guides here
2. Focus on WHO, WHEN, HOW MUCH - not HOW TO
3. Realistic timelines based on user count
4. Measurable success criteria
5. Consider different learning styles

---

**Generate the Training Strategy now. Output ONLY valid JSON.**
'''


# ============================================================================
# MODE 2: DELIVERY - Concrete Training Materials
# ============================================================================
def get_delivery_prompt(solution_design: str, training_strategy: str) -> str:
    # Try external prompt first
    if PROMPT_SERVICE:
        try:
            return PROMPT_SERVICE.render("lucas_trainer", "delivery", {
                "solution_design": solution_design[:2000],
                "training_strategy": training_strategy[:1500],
            })
        except Exception as e:
            logger.warning(f"PromptService fallback for lucas_trainer/delivery: {e}")

    # FALLBACK: original f-string prompt
    return f'''# 🎓 TRAINING MATERIALS DELIVERY

You are **Lucas**, a Salesforce Certified Instructor creating concrete training materials.

## MISSION
Generate **detailed, ready-to-use training materials** including user guides and video scripts.

## INPUT CONTEXT
### Solution Design
{solution_design[:2000]}

### Training Strategy
{training_strategy[:1500]}

## OUTPUT FORMAT (JSON)

```json
{{
  "artifact_id": "TRAIN-DELIVERY-001",
  "title": "Training Materials Package",
  "quick_start_guide": {{
    "title": "Quick Start Guide",
    "audience": "All Users",
    "sections": [
      {{
        "title": "1. Logging In",
        "steps": [
          "1. Open browser and go to [Your Salesforce URL]",
          "2. Enter your username (email address)",
          "3. Enter your password",
          "4. Click 'Log In'"
        ],
        "tips": ["Bookmark the URL for quick access", "Use 'Remember Me' on trusted devices"],
        "screenshot_placeholder": "[Screenshot: Login page with fields highlighted]"
      }}
    ],
    "page_count": 8
  }},
  "role_guides": [
    {{
      "role": "Sales Representative",
      "title": "Sales Rep Daily Tasks Guide",
      "sections": [
        {{
          "title": "Managing Your Leads",
          "content": "Step-by-step instructions...",
          "best_practices": ["Review leads daily", "Update status within 24h"]
        }}
      ],
      "page_count": 12
    }}
  ],
  "video_scripts": [
    {{
      "id": "VID-001",
      "title": "Welcome to Salesforce",
      "duration_minutes": 5,
      "script": {{
        "intro": {{
          "timestamp": "0:00-0:30",
          "visual": "Animated logo, welcome screen",
          "narration": "Welcome to Salesforce! In this video, you'll learn..."
        }},
        "sections": [
          {{
            "timestamp": "0:30-2:00",
            "title": "Dashboard Overview",
            "visual": "Screen recording: Dashboard navigation",
            "narration": "When you log in, you'll see your personalized dashboard...",
            "key_points": ["Pipeline metrics", "Recent records", "Tasks due today"]
          }}
        ],
        "outro": {{
          "timestamp": "4:30-5:00",
          "visual": "Summary slide with QR code",
          "narration": "You now know the basics! Scan this QR code for more resources.",
          "cta": "Complete Module 1 quiz in Trailhead"
        }}
      }}
    }}
  ],
  "job_aids": [
    {{
      "title": "Lead Conversion Checklist",
      "format": "One-page PDF",
      "content": [
        "[] Verify contact information",
        "[] Confirm budget range",
        "[] Identify decision maker",
        "[] Set next steps"
      ]
    }}
  ],
  "faq": [
    {{
      "question": "How do I reset my password?",
      "answer": "Click 'Forgot Password' on login page, enter email, check inbox for reset link."
    }}
  ],
  "exercises": [
    {{
      "title": "Exercise 1: Create Your First Lead",
      "objective": "Practice lead creation with all required fields",
      "steps": ["Navigate to Leads tab", "Click New", "Fill required fields", "Save"],
      "expected_result": "New lead appears in your Recent Items"
    }}
  ]
}}
```

## RULES
1. Be SPECIFIC - actual steps, not vague descriptions
2. Include screenshot placeholders with descriptions
3. Video scripts must have timestamps
4. Job aids must fit on one page
5. FAQs must answer real user questions
6. Exercises must be hands-on

---

**Generate the Training Materials now. Output ONLY valid JSON.**
'''


# ============================================================================
# TRAINER AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class TrainerAgent:
    """
    Lucas (Trainer) Agent - Training Strategy + Delivery Materials.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - sds_strategy: Training & Adoption Strategy for SDS document
        - delivery: Concrete training materials (guides, video scripts)

    Usage (import):
        agent = TrainerAgent()
        result = agent.run({"mode": "sds_strategy", "input_content": "..."})

    Usage (CLI):
        python salesforce_trainer.py --mode sds_strategy --input input.json --output output.json
    """

    VALID_MODES = ("sds_strategy", "delivery")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "sds_strategy" or "delivery"
                - input_content: string content (JSON string or raw text)
                - execution_id: int (optional, default 0)
                - project_id: int (optional, default 0)

        Returns:
            dict with agent output including "success" key.
            On success: full output dict with agent_id, content, metadata, etc.
            On failure: {"success": False, "error": "..."}
        """
        mode = task_data.get("mode", "sds_strategy")
        input_content = task_data.get("input_content", "")
        execution_id = task_data.get("execution_id", 0)
        project_id = task_data.get("project_id", 0)

        if mode not in self.VALID_MODES:
            return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

        if not input_content:
            return {"success": False, "error": "No input_content provided"}

        try:
            return self._execute(mode, input_content, execution_id, project_id)
        except Exception as e:
            logger.error(f"TrainerAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _execute(
        self,
        mode: str,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Core execution logic shared by all modes."""
        start_time = time.time()

        # Parse input content as JSON (from run_agent_task) or use as raw text
        try:
            input_data = json.loads(input_content) if isinstance(input_content, str) else input_content
        except (json.JSONDecodeError, TypeError):
            input_data = {"context": input_content}

        # Get RAG context
        rag_context = self._get_rag_context(project_id=project_id)

        # Select prompt and artifact type based on mode
        if mode == "sds_strategy":
            solution_design = input_data.get('solution_design', input_data.get('context', ''))
            use_cases = input_data.get('use_cases', '')
            prompt = get_sds_strategy_prompt(solution_design, use_cases)
            artifact_type = "trainer_sds_strategy"
        else:  # delivery
            solution_design = input_data.get('solution_design', '')
            training_strategy = input_data.get('training_strategy', '')
            prompt = get_delivery_prompt(solution_design, training_strategy)
            artifact_type = "trainer_delivery_materials"

        if rag_context:
            prompt += f"\n\n## SALESFORCE TRAINING BEST PRACTICES (RAG)\n{rag_context[:1500]}\n"

        logger.info(f"TrainerAgent mode={mode}, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(prompt, execution_id=execution_id)

        execution_time = time.time() - start_time
        logger.info(
            f"TrainerAgent generated {len(content)} chars in {execution_time:.1f}s, "
            f"tokens={tokens_used}, model={model_used}"
        )

        # Log LLM interaction (INFRA-002)
        self._log_interaction(
            mode=mode,
            prompt=prompt,
            content=content,
            execution_id=execution_id,
            input_tokens=input_tokens,
            tokens_used=tokens_used,
            model_used=model_used,
            provider_used=provider_used,
            execution_time=execution_time,
        )

        # Parse JSON response
        parsed_content = self._parse_response(content)

        # Build output
        output_data = {
            "success": True,
            "agent_id": "trainer",
            "agent_name": "Lucas (Trainer)",
            "mode": mode,
            "artifact_type": artifact_type,
            "deliverable_type": artifact_type,
            "execution_id": execution_id,
            "project_id": project_id,
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": datetime.now().isoformat(),
            },
        }

        return output_data

    def _get_rag_context(self, project_id: int = 0) -> str:
        """Fetch RAG context for training best practices."""
        if not RAG_AVAILABLE:
            return ""
        try:
            query = "Salesforce training best practices user adoption"
            rag_context = get_salesforce_context(query, n_results=3, agent_type="trainer", project_id=project_id or None)
            logger.info(f"RAG context loaded ({len(rag_context)} chars)")
            return rag_context
        except Exception as e:
            logger.warning(f"RAG unavailable: {e}")
            return ""

    def _call_llm(self, prompt: str, execution_id: int = 0) -> tuple:
        """
        Call LLM via llm_service.

        Returns:
            tuple of (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            logger.debug("Calling LLM via llm_service")
            response = generate_llm_response(prompt, max_tokens=8000, temperature=0.3, execution_id=execution_id)
            return (
                response.get('content', ''),
                response.get('tokens_used', 0),
                response.get('input_tokens', 0),
                response.get('model', 'unknown'),
                response.get('provider', 'unknown'),
            )
        else:
            logger.error("LLM service not available")
            return ('{"error": "LLM service not available"}', 0, 0, "none", "none")

    def _parse_response(self, content: str) -> Any:
        """Parse JSON from LLM response, stripping code fences if present."""
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {"raw_content": content, "parse_error": True}

    def _log_interaction(
        self,
        mode: str,
        prompt: str,
        content: str,
        execution_id: int,
        input_tokens: int,
        tokens_used: int,
        model_used: str,
        provider_used: str,
        execution_time: float,
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="lucas",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=None,
                agent_mode=mode,
                rag_context=None,
                previous_feedback=None,
                parsed_files=None,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider=provider_used,
                execution_time_seconds=round(execution_time, 2),
                success=True,
                error_message=None,
            )
            logger.debug("LLM interaction logged (INFRA-002)")
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")


# ============================================================================
# CLI MODE -- Backward compatibility for subprocess invocation
# ============================================================================
if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path

    # Ensure backend is on sys.path for CLI mode
    _backend_dir = str(Path(__file__).resolve().parent.parent.parent)
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)

    # Re-import after sys.path fix (module-level imports may have failed in CLI mode)
    if not LLM_SERVICE_AVAILABLE:
        try:
            from app.services.llm_service import generate_llm_response, LLMProvider
            LLM_SERVICE_AVAILABLE = True
        except ImportError:
            pass

    if not RAG_AVAILABLE:
        try:
            from app.services.rag_service import get_salesforce_context
            RAG_AVAILABLE = True
        except ImportError:
            pass

    parser = argparse.ArgumentParser(description='Lucas Trainer Agent - Two Modes')
    parser.add_argument('--mode', required=True, choices=['sds_strategy', 'delivery'],
                        help='sds_strategy: Training strategy for SDS | delivery: Concrete materials')
    parser.add_argument('--input', required=True, help='Input JSON file')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--execution-id', type=int, default=0)
    parser.add_argument('--project-id', type=int, default=0)
    parser.add_argument('--use-rag', action='store_true', default=True)

    args = parser.parse_args()

    try:
        logger.info("Reading input from %s...", args.input)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()
        logger.info("Read %d characters", len(input_content))

        agent = TrainerAgent()
        result = agent.run({
            "mode": args.mode,
            "input_content": input_content,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
        })

        if result.get("success"):
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.info("SUCCESS: Output saved to %s", args.output)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            sys.exit(0)
        else:
            logger.error("ERROR: %s", result.get('error'))
            sys.exit(1)

    except Exception as e:
        logger.error("ERROR: %s", str(e), exc_info=True)
        sys.exit(1)
