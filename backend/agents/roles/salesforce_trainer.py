#!/usr/bin/env python3
"""
Salesforce Trainer (Lucas) Agent - Two Modes
Mode 1: sds_strategy - Training Strategy for SDS document
Mode 2: delivery - Concrete training materials (guides, video scripts)
"""
import os, sys, argparse, json
from pathlib import Path
from datetime import datetime
import time

# LLM imports
sys.path.insert(0, "/app")
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


# ============================================================================
# MODE 1: SDS STRATEGY - Training & Adoption Strategy for SDS
# ============================================================================
def get_sds_strategy_prompt(solution_design: str, use_cases: str) -> str:
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
        "□ Verify contact information",
        "□ Confirm budget range",
        "□ Identify decision maker",
        "□ Set next steps"
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
# MAIN EXECUTION
# ============================================================================
def main():
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
        start_time = time.time()
        
        # Read input
        print(f"📖 Reading input from {args.input}...", file=sys.stderr)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        # Get RAG context
        rag_context = ""
        if args.use_rag and RAG_AVAILABLE:
            try:
                query = f"Salesforce training best practices user adoption"
                rag_context = get_salesforce_context(query, n_results=3, agent_type="trainer")
                print(f"📚 RAG context loaded ({len(rag_context)} chars)", file=sys.stderr)
            except Exception as e:
                print(f"⚠️ RAG unavailable: {e}", file=sys.stderr)
        
        # Select prompt based on mode
        if args.mode == 'sds_strategy':
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
        
        print(f"🤖 Generating {args.mode} output...", file=sys.stderr)
        
        # Generate
        if LLM_SERVICE_AVAILABLE:
            response = generate_llm_response(prompt, max_tokens=8000, temperature=0.3)
            content = response.get('content', '')
            tokens_used = response.get('tokens_used', 0)
        else:
            content = '{"error": "LLM service not available"}'
            tokens_used = 0
        
        # Parse JSON
        try:
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                content = content.split('```')[1].split('```')[0]
            parsed = json.loads(content.strip())
        except json.JSONDecodeError:
            parsed = {"raw_content": content, "parse_error": True}
        
        # Build output
        execution_time = time.time() - start_time
        output = {
            "agent": "trainer",
            "mode": args.mode,
            "artifact_type": artifact_type,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
            "timestamp": datetime.now().isoformat(),
            "tokens_used": tokens_used,
            "execution_time_seconds": round(execution_time, 2),
            "content": parsed
        }
        
        # Write output
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Output written to {args.output}", file=sys.stderr)
        print(f"📊 Tokens: {tokens_used}, Time: {execution_time:.2f}s", file=sys.stderr)
        
        return output
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        error_output = {"error": str(e), "agent": "trainer", "mode": args.mode}
        with open(args.output, 'w') as f:
            json.dump(error_output, f, indent=2)
        sys.exit(1)


if __name__ == "__main__":
    main()
