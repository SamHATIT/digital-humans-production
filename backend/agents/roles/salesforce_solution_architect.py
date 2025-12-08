#!/usr/bin/env python3
"""
Salesforce Solution Architect (Marcus) Agent - Refactored Version
4 distinct modes:
1. design: UC → Architecture globale (ARCH-001)
2. as_is: SFDX metadata → Résumé structuré (ASIS-001)  
3. gap: ARCH + ASIS → Deltas (GAP-001)
4. wbs: GAP → Tâches + Planning (WBS-001)
"""

import os
import time
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

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
# PROMPT 1: SOLUTION DESIGN (UC → Architecture)
# ============================================================================
def get_design_prompt(use_cases: list, project_summary: str, rag_context: str = "") -> str:
    uc_text = ""
    for uc in use_cases[:15]:  # Limit to avoid token overflow
        uc_text += f"\n**{uc.get('id', 'UC-XXX')}: {uc.get('title', 'Untitled')}**\n"
        uc_text += f"- Actor: {uc.get('actor', 'User')}\n"
        sf = uc.get('salesforce_components', {})
        if sf:
            uc_text += f"- Objects: {', '.join(sf.get('objects', []))}\n"
            uc_text += f"- Automation: {', '.join(sf.get('automation', []))}\n"
    
    rag_section = f"\n## SALESFORCE BEST PRACTICES (RAG)\n{rag_context}\n---\n" if rag_context else ""
    
    return f'''# 🏗️ SOLUTION DESIGN SPECIFICATION

You are **Marcus**, a Salesforce Certified Technical Architect (CTA).

## YOUR MISSION
Create a **High-Level Solution Design** from the Use Cases provided.

## PROJECT CONTEXT
{project_summary}

## USE CASES TO ARCHITECT
{uc_text}
{rag_section}

## OUTPUT FORMAT (JSON)
Generate a solution design with:
- "artifact_id": "ARCH-001"
- "title": "Solution Design Specification"
- "data_model": Object with:
  - "standard_objects": Array of objects, each with: {{"api_name": "Case", "purpose": "...", "customizations": [...]}}
  - "custom_objects": Array of objects, each with: {{"api_name": "Error_Log__c", "purpose": "...", "fields": [...]}}
  - "relationships": Array of object relationships
  - "erd_mermaid": ERD diagram in Mermaid syntax
- "security_model": Object with:
  - "profiles": Array of profiles needed
  - "permission_sets": Array of permission sets
  - "sharing_rules": Summary of sharing approach
  - "field_level_security": Key FLS considerations
- "automation_design": Object with:
  - "flows": Array of Flows with purpose
  - "triggers": Array of Apex triggers if needed
  - "scheduled_jobs": Array of batch/scheduled processes
- "integration_points": Array of external integrations with:
  - "system": External system name
  - "direction": Inbound/Outbound/Bidirectional
  - "method": API type (REST, SOAP, etc.)
  - "frequency": Real-time, Batch, etc.
- "ui_components": Object with:
  - "lightning_pages": Array of custom pages
  - "lwc_components": Array of LWC needed
  - "quick_actions": Array of actions
- "technical_considerations": Array of key technical decisions
- "risks": Array of technical risks identified

## RULES
1. Use Salesforce standard objects before creating custom ones
2. Prefer declarative (Flows) over code (Apex) where possible
3. Follow Salesforce naming conventions
4. Consider governor limits in design
5. ERD must use valid Mermaid erDiagram syntax
6. Be specific about object and field API names

---

**Generate the Solution Design now. Output ONLY valid JSON.**
'''

# ============================================================================
# PROMPT 2: AS-IS ANALYSIS (SFDX → Summary)
# ============================================================================
def get_as_is_prompt(sfdx_metadata: str) -> str:
    sfdx_metadata_truncated = sfdx_metadata[:15000] if len(sfdx_metadata) > 15000 else sfdx_metadata
    return f'''# 📊 AS-IS ANALYSIS

You are **Marcus**, a Salesforce Certified Technical Architect.

## YOUR MISSION
Analyze the existing Salesforce org metadata and create a structured summary.

## SFDX METADATA EXTRACT
{sfdx_metadata_truncated}  <!-- Truncate to avoid token overflow -->

## OUTPUT FORMAT (JSON)
Generate an As-Is analysis with:
- "artifact_id": "ASIS-001"
- "title": "Current State Analysis"
- "data_model_summary": Object with:
  - "custom_objects_count": Number
  - "key_objects": Array of main objects with field counts
  - "relationships_summary": Brief description
- "automation_summary": Object with:
  - "flows_count": Number
  - "triggers_count": Number
  - "key_automations": Array of main automations
- "security_summary": Object with:
  - "profiles_count": Number
  - "permission_sets_count": Number
  - "sharing_model": Brief description
- "integration_summary": Object with:
  - "connected_apps": Array
  - "named_credentials": Array
  - "external_services": Array
- "ui_summary": Object with:
  - "lightning_pages_count": Number
  - "lwc_components": Array
  - "custom_tabs": Array
- "technical_debt": Array of issues identified
- "recommendations": Array of quick wins

## RULES
1. Focus on summarizing, not listing everything
2. Identify patterns and anti-patterns
3. Highlight technical debt
4. Note deprecated features in use

---

**Generate the As-Is Analysis now. Output ONLY valid JSON.**
'''

# ============================================================================
# PROMPT 3: GAP ANALYSIS (ARCH + ASIS → Deltas)
# ============================================================================
def get_gap_prompt(arch_summary: str, asis_summary: str) -> str:
    return f'''# 🔍 GAP ANALYSIS

You are **Marcus**, a Salesforce Certified Technical Architect.

## YOUR MISSION
Compare the Target Architecture with the Current State to identify gaps.

## TARGET ARCHITECTURE (ARCH-001)
{arch_summary}

## CURRENT STATE (ASIS-001)
{asis_summary}

## OUTPUT FORMAT (JSON)
Generate a gap analysis with:
- "artifact_id": "GAP-001"
- "title": "Gap Analysis"
- "gaps": Array of gap objects, each with:
  - "id": "GAP-001-01", "GAP-001-02", etc.
  - "category": One of DATA_MODEL, AUTOMATION, SECURITY, INTEGRATION, UI, OTHER
  - "current_state": What exists now
  - "target_state": What is needed
  - "gap_description": Clear description of the delta
  - "complexity": One of LOW, MEDIUM, HIGH
  - "effort_days": Estimated effort in days
  - "dependencies": Array of other gap IDs this depends on
  - "assigned_agent": Which agent should handle (Diego, Zara, Raj, etc.)
- "summary": Object with:
  - "total_gaps": Number
  - "by_category": Object with counts per category
  - "by_complexity": Object with counts per complexity
  - "total_effort_days": Sum of all efforts
- "migration_considerations": Array of data migration notes
- "risk_areas": Array of high-risk changes

## RULES
1. Be specific about what exists vs what's needed
2. Realistic effort estimates (consider testing)
3. Identify dependencies between gaps
4. Assign appropriate agent for each gap
5. Flag breaking changes

---

**Generate the Gap Analysis now. Output ONLY valid JSON.**
'''

# ============================================================================
# PROMPT 4: WBS (GAP → Tasks + Planning)
# ============================================================================
def get_wbs_prompt(gap_analysis: str, project_constraints: str = "") -> str:
    return f'''# 📅 WORK BREAKDOWN STRUCTURE - ENRICHED

You are **Marcus**, a Salesforce Certified Technical Architect.

## MISSION
Create a detailed Work Breakdown Structure from the Gap Analysis.
Each task MUST have validation criteria and clear agent assignment.

## GAP ANALYSIS
{gap_analysis}

## PROJECT CONSTRAINTS
{project_constraints if project_constraints else "Standard Salesforce implementation timeline"}

## OUTPUT FORMAT (JSON - STRICT)

```json
{{
  "artifact_id": "WBS-001",
  "title": "Work Breakdown Structure",
  "phases": [
    {{
      "id": "PHASE-01",
      "name": "Phase name",
      "duration_weeks": 2,
      "tasks": [
        {{
          "id": "TASK-001",
          "name": "Task name (action verb + object)",
          "description": "Brief description (1-2 sentences max)",
          "gap_refs": ["GAP-001-01"],
          "assigned_agent": "Raj",
          "effort_days": 2,
          "dependencies": [],
          "deliverables": ["Deliverable 1"],
          "validation_criteria": [
            "DONE WHEN: [specific measurable outcome]",
            "VERIFIED BY: [how Elena/reviewer checks it]"
          ],
          "test_approach": "Unit test / Manual test / UAT"
        }}
      ]
    }}
  ],
  "milestones": [...],
  "resource_allocation": {{...}},
  "critical_path": ["TASK-001", "TASK-005", ...],
  "risks_and_mitigations": [...]
}}
```

## AVAILABLE AGENTS (ONLY these 8)

| Agent | Role | Handles |
|-------|------|---------|
| Diego | Apex Developer | Apex classes, triggers, batch, integration code |
| Zara | LWC Developer | LWC, Aura, custom UI components |
| Raj | SF Admin | Objects, fields, flows, validation rules, profiles |
| Elena | QA Engineer | Test plans, test execution, UAT, bugs |
| Jordan | DevOps | CI/CD, deployments, environments, releases |
| Aisha | Data Migration | Data mapping, ETL, migration, data validation |
| Lucas | Trainer | Training docs, user guides, training sessions |
| Marcus | Architect | Architecture reviews, design oversight |

## TASK ASSIGNMENT RULES (STRICT)

- **Config (no code)** → Raj: objects, fields, page layouts, flows, validation rules, profiles, permission sets
- **Apex code** → Diego: classes, triggers, batch, schedulable, REST/SOAP
- **UI code** → Zara: LWC, Aura, Lightning pages
- **Testing** → Elena: ALL test tasks (unit, integration, UAT)
- **Deploy** → Jordan: ALL deployment/pipeline tasks
- **Data** → Aisha: ALL data migration tasks
- **Docs** → Lucas: ALL training/documentation tasks
- **Review** → Marcus: architecture reviews only

## VALIDATION CRITERIA FORMAT (REQUIRED for each task)

Each task MUST have 1-3 validation_criteria using this format:
- "DONE WHEN: [specific outcome that can be verified]"
- "VERIFIED BY: [how the reviewer/Elena checks this is complete]"

**Good examples:**
- "DONE WHEN: Custom object Account_Score__c created with 5 fields"
- "VERIFIED BY: Run SOQL query, check field count in Setup"
- "DONE WHEN: All unit tests pass with >80% coverage"
- "VERIFIED BY: Deploy to scratch org, run apex:test:run"

**Bad examples (avoid):**
- "DONE WHEN: Task is complete" ❌ (too vague)
- "VERIFIED BY: Check it works" ❌ (not specific)

## GENERAL RULES

1. **30-60 tasks** total - fewer means too coarse, more means micromanagement
2. **Max 10 tasks per phase** - split large phases
3. **Every task has validation_criteria** - NO exceptions
4. **Respect dependencies** - no circular refs
5. **Balance workload** - no agent should have >40% of tasks
6. **Include test tasks** - at least 15% of tasks should be Elena's
7. **Include deploy tasks** - at least 5% of tasks should be Jordan's

---

**Generate the WBS now. Output ONLY valid JSON, no markdown fences.**
'''

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description='Marcus Architect Agent')
    parser.add_argument('--mode', required=False, default='design', 
                        choices=['design', 'as_is', 'gap', 'wbs'],
                        help='Operation mode')
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
        print(f"✅ Input loaded", file=sys.stderr)
        
        # Get RAG context for design mode
        rag_context = ""
        if args.mode == 'design' and args.use_rag and RAG_AVAILABLE:
            try:
                query = f"Salesforce architecture design patterns data model"
                print(f"🔍 Querying RAG...", file=sys.stderr)
                rag_context = get_salesforce_context(query, n_results=5, agent_type="solution_architect")
                print(f"✅ RAG context: {len(rag_context)} chars", file=sys.stderr)
            except Exception as e:
                print(f"⚠️ RAG error: {e}", file=sys.stderr)
        
        # Build prompt based on mode
        if args.mode == 'design':
            use_cases = input_data.get('use_cases', [])
            project_summary = input_data.get('project_summary', '')
            prompt = get_design_prompt(use_cases, project_summary, rag_context)
            deliverable_type = "solution_design"
            artifact_prefix = "ARCH"
            
        elif args.mode == 'as_is':
            sfdx_metadata = input_data.get('sfdx_metadata', json.dumps(input_data))
            prompt = get_as_is_prompt(sfdx_metadata)
            deliverable_type = "as_is_analysis"
            artifact_prefix = "ASIS"
            
        elif args.mode == 'gap':
            arch_summary = json.dumps(input_data.get('architecture', {}), indent=2)
            asis_summary = json.dumps(input_data.get('as_is', {}), indent=2)
            prompt = get_gap_prompt(arch_summary, asis_summary)
            deliverable_type = "gap_analysis"
            artifact_prefix = "GAP"
            
        else:  # wbs
            gap_analysis = json.dumps(input_data.get('gaps', input_data), indent=2)
            constraints = input_data.get('constraints', '')
            prompt = get_wbs_prompt(gap_analysis, constraints)
            deliverable_type = "work_breakdown_structure"
            artifact_prefix = "WBS"
        
        system_prompt = f"You are Marcus, a Salesforce CTA. Generate {deliverable_type}. Output ONLY valid JSON."
        
        print(f"📝 Mode: {args.mode}", file=sys.stderr)
        print(f"📝 Prompt size: {len(prompt)} characters", file=sys.stderr)
        
        # Call LLM
        if LLM_SERVICE_AVAILABLE:
            print(f"🤖 Calling Claude API (Architect tier)...", file=sys.stderr)
            response = generate_llm_response(
                prompt=prompt,
                agent_type="architect",
                system_prompt=system_prompt,
                max_tokens=16000,
                temperature=0.4
            )
            content = response["content"]
            tokens_used = response["tokens_used"]
            model_used = response["model"]
            provider_used = response["provider"]
        else:
            # Fallback to direct Anthropic
            print(f"🤖 Calling Anthropic API directly...", file=sys.stderr)
            from anthropic import Anthropic
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            
            client = Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=16000,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            model_used = "claude-sonnet-4-20250514"
            provider_used = "anthropic"
        
        print(f"✅ Using {provider_used} / {model_used}", file=sys.stderr)
        
        execution_time = time.time() - start_time
        print(f"✅ Generated {len(content)} chars in {execution_time:.1f}s", file=sys.stderr)
        print(f"📊 Tokens used: {tokens_used}", file=sys.stderr)
        
        # Parse JSON output
        try:
            clean_content = content.strip()
            if clean_content.startswith('```'):
                clean_content = clean_content.split('\n', 1)[1]
            if clean_content.endswith('```'):
                clean_content = clean_content[:-3]
            clean_content = clean_content.strip()
            
            parsed_content = json.loads(clean_content)
            print(f"✅ JSON parsed successfully", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error: {e}", file=sys.stderr)
            parsed_content = {"raw": content, "parse_error": str(e)}
        
        # Build output
        output_data = {
            "agent_id": "architect",
            "agent_name": "Marcus (Solution Architect)",
            "mode": args.mode,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
            "deliverable_type": deliverable_type,
            "artifact_id": f"{artifact_prefix}-001",
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "rag_used": bool(rag_context),
                "generated_at": datetime.now().isoformat()
            }
        }
        
        # Save output
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ SUCCESS: Output saved to {args.output}", file=sys.stderr)
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
        
        sys.exit(0)
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
