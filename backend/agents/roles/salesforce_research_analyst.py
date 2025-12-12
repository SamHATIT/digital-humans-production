#!/usr/bin/env python3
"""
Salesforce Research Analyst (Emma) Agent
Based on MetaGPT Researcher pattern - Adapted for UC Analysis, Validation, and SDS Writing

Three modes:
- analyze: Cluster and digest all Use Cases for Marcus
- validate: Check 100% coverage of UCs by Solution Design  
- write_sds: Generate professional SDS document

Inspired by: metagpt/roles/researcher.py
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

# LLM imports
# Path for Docker container
sys.path.insert(0, "/app")
# Path for local testing
sys.path.insert(0, "/root/workspace/digital-humans-production/backend")
try:
    from app.services.llm_service import generate_llm_response, LLMProvider
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

# LLM Logger for debugging
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
    print(f"📝 LLM Logger loaded for Emma", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass


# ============================================================================
# PROMPTS - MODE ANALYZE (inspired by CollectLinks + ConductResearch)
# ============================================================================

ANALYZE_SYSTEM = """You are Emma, a Research Analyst specialized in Salesforce project analysis.
Your goal is to analyze Use Cases and create structured digests for solution architects."""

CLUSTER_UCS_PROMPT = """# USE CASE CLUSTERING ANALYSIS

## INPUT DATA
Total Use Cases: {uc_count}
Business Requirements: {br_count}

### Use Cases (JSON):
{use_cases_json}

### Business Requirements (JSON):
{business_requirements_json}

## YOUR TASK
Analyze all Use Cases and group them by:
1. Parent Business Requirement (BR-XXX)
2. Salesforce Object patterns
3. Automation type (Flow, Trigger, Batch)

## OUTPUT FORMAT (JSON)
```json
{{
  "clusters": [
    {{
      "cluster_id": "CL-001",
      "parent_br": "BR-001",
      "uc_ids": ["UC-001-01", "UC-001-02"],
      "theme": "Customer Feedback Management",
      "sf_objects": ["Account", "Feedback__c"],
      "automation_types": ["Record-Triggered Flow"],
      "complexity": "medium"
    }}
  ],
  "cross_cutting": {{
    "shared_objects": ["Account"],
    "shared_automations": []
  }},
  "statistics": {{
    "total_ucs": {uc_count},
    "total_clusters": 0,
    "ucs_per_cluster_avg": 0
  }}
}}
```

## RULES
1. EVERY UC must belong to exactly ONE cluster
2. Group by parent_br first, then by object affinity
3. Identify objects used across multiple clusters as "shared_objects"
4. Complexity: low (<3 UCs), medium (3-6 UCs), high (>6 UCs)

Output ONLY valid JSON, no markdown fences.
"""

GENERATE_DIGEST_PROMPT = """# UC DIGEST GENERATION

## CLUSTERS ANALYSIS
{clusters_json}

## YOUR TASK
Generate a comprehensive UC Digest that Marcus (Solution Architect) can use to design the solution.
The digest must capture ALL requirements without exceeding context limits.

## OUTPUT FORMAT (JSON)
```json
{{
  "digest_id": "DIGEST-001",
  "generated_at": "{timestamp}",
  "project_summary": {{
    "total_brs": 0,
    "total_ucs": 0,
    "complexity_score": "medium"
  }},
  "by_requirement": {{
    "BR-001": {{
      "title": "...",
      "uc_count": 3,
      "sf_objects": ["Account", "Custom__c"],
      "sf_fields": {{
        "Account": ["Name", "Industry"],
        "Custom__c": ["Status__c", "Amount__c"]
      }},
      "automations": [
        {{"type": "Record-Triggered Flow", "purpose": "..."}}
      ],
      "ui_components": ["LWC AccountFeedback", "Related List"],
      "actors": ["Sales Rep", "Admin"],
      "key_acceptance_criteria": ["GIVEN... WHEN... THEN..."]
    }}
  }},
  "cross_cutting_concerns": {{
    "shared_objects": ["Account"],
    "integrations": [],
    "security_considerations": [],
    "data_migration_needs": []
  }},
  "recommendations": [
    "Consider using standard Case object instead of custom Feedback__c",
    "Consolidate validation rules into single flow"
  ]
}}
```

## RULES
1. EVERY UC from every cluster MUST be represented
2. Extract ALL sf_objects and sf_fields from UCs
3. Deduplicate objects/fields within each BR
4. Provide actionable recommendations based on patterns
5. Keep field lists complete but not verbose

Output ONLY valid JSON, no markdown fences.
"""


# ============================================================================
# PROMPTS - MODE VALIDATE (inspired by WebBrowseAndSummarize pattern)
# ============================================================================

VALIDATE_SYSTEM = """You are Emma, a QA Research Analyst ensuring 100% coverage of requirements.
Your goal is to verify every Use Case element is addressed in the Solution Design."""

MAP_ELEMENTS_PROMPT = """# ELEMENT MAPPING: UC → SOLUTION

## USE CASES
{use_cases_json}

## SOLUTION DESIGN
{solution_design_json}

## YOUR TASK
For EACH Use Case, map its elements to the Solution Design components.

## OUTPUT FORMAT (JSON)
```json
{{
  "mappings": [
    {{
      "uc_id": "UC-001-01",
      "uc_title": "Create Feedback Record",
      "elements": [
        {{
          "element_type": "sf_object",
          "element_value": "Feedback__c",
          "solution_component": "Custom Object: Feedback__c",
          "coverage_status": "covered",
          "notes": ""
        }},
        {{
          "element_type": "sf_field",
          "element_value": "Feedback__c.Rating__c",
          "solution_component": "Field: Rating__c (Picklist)",
          "coverage_status": "covered",
          "notes": ""
        }},
        {{
          "element_type": "automation",
          "element_value": "Record-Triggered Flow",
          "solution_component": "Flow: Feedback_After_Insert",
          "coverage_status": "covered",
          "notes": ""
        }}
      ]
    }}
  ],
  "summary": {{
    "total_elements": 0,
    "covered": 0,
    "partial": 0,
    "missing": 0
  }}
}}
```

## COVERAGE STATUS VALUES
- "covered": Element fully addressed in solution
- "partial": Element partially addressed, needs clarification
- "missing": Element NOT found in solution design

Output ONLY valid JSON, no markdown fences.
"""

COVERAGE_REPORT_PROMPT = """# COVERAGE REPORT GENERATION

## ELEMENT MAPPINGS
{mappings_json}

## YOUR TASK
Generate a comprehensive coverage report with score and gaps.

## OUTPUT FORMAT (JSON)
```json
{{
  "report_id": "COVERAGE-001",
  "generated_at": "{timestamp}",
  "coverage_score": 94.5,
  "status": "NEEDS_REVISION",
  "summary": {{
    "total_ucs": 0,
    "fully_covered_ucs": 0,
    "partial_ucs": 0,
    "missing_ucs": 0,
    "total_elements": 0,
    "covered_elements": 0
  }},
  "gaps": [
    {{
      "gap_id": "GAP-001",
      "uc_id": "UC-003-02",
      "element_type": "automation",
      "element_value": "Batch job for monthly aggregation",
      "severity": "high",
      "recommendation": "Add Batch Apex class for monthly feedback aggregation"
    }}
  ],
  "recommendations_for_marcus": [
    "Add missing Batch Apex for UC-003-02",
    "Clarify validation rule for Rating__c field"
  ]
}}
```

## STATUS VALUES
- "APPROVED": coverage_score >= 100
- "NEEDS_REVISION": coverage_score < 100

Output ONLY valid JSON, no markdown fences.
"""


# ============================================================================
# PROMPTS - MODE WRITE_SDS
# ============================================================================

WRITE_SDS_SYSTEM = """You are Emma, a Technical Writer creating professional Salesforce SDS documents.
Your goal is to produce clear, comprehensive, client-ready documentation."""

WRITE_SECTION_PROMPT = """# SDS SECTION WRITING

## SECTION TO WRITE
Section: {section_name}
Template guidance: {section_template}

## AVAILABLE DATA
{section_data}

## YOUR TASK
Write this section of the SDS document in professional, clear French.
Use formal tone, avoid jargon, be specific with Salesforce terminology.

## OUTPUT FORMAT
Return the section content in Markdown format.
Include:
- Clear headers (##, ###)
- Tables where appropriate
- Bullet points for lists
- Technical details with explanations

Write the section content directly, no JSON wrapper.
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_json_response(content: str) -> Dict:
    """Clean and parse JSON from LLM response"""
    clean = content.strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[1] if '\n' in clean else clean[3:]
    if clean.endswith('```'):
        clean = clean[:-3]
    clean = clean.strip()
    if clean.startswith('json'):
        clean = clean[4:].strip()
    return json.loads(clean)


def calculate_coverage_score(mappings: Dict) -> float:
    """Calculate coverage percentage from mappings"""
    summary = mappings.get("summary", {})
    total = summary.get("total_elements", 0)
    covered = summary.get("covered", 0)
    partial = summary.get("partial", 0)
    
    if total == 0:
        return 100.0
    
    # Partial counts as 50%
    score = ((covered + partial * 0.5) / total) * 100
    return round(score, 1)


# ============================================================================
# MODE HANDLERS
# ============================================================================

async def run_analyze_mode(input_data: Dict, execution_id: int, args) -> Dict:
    """
    Mode ANALYZE: Cluster UCs and generate digest for Marcus
    Inspired by: CollectLinks → WebBrowseAndSummarize → ConductResearch
    """
    start_time = time.time()
    
    use_cases = input_data.get("use_cases", [])
    business_requirements = input_data.get("business_requirements", [])
    
    print(f"📊 Analyzing {len(use_cases)} UCs from {len(business_requirements)} BRs", file=sys.stderr)
    
    # Step 1: Cluster UCs (equivalent to CollectLinks - decompose & organize)
    print(f"🔍 Step 1/2: Clustering Use Cases...", file=sys.stderr)
    
    cluster_prompt = CLUSTER_UCS_PROMPT.format(
        uc_count=len(use_cases),
        br_count=len(business_requirements),
        use_cases_json=json.dumps(use_cases[:50], indent=2),  # Limit for context
        business_requirements_json=json.dumps(business_requirements, indent=2)
    )
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=cluster_prompt,
            agent_type="research",  # Uses appropriate tier
            system_prompt=ANALYZE_SYSTEM,
            max_tokens=8000,
            temperature=0.3
        )
        clusters_content = response["content"]
        tokens_step1 = response["tokens_used"]
        model_used = response["model"]
        provider_used = response["provider"]
    else:
        raise ValueError("LLM Service not available")
    
    try:
        clusters = parse_json_response(clusters_content)
        print(f"✅ Created {len(clusters.get('clusters', []))} clusters", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"⚠️ Cluster JSON parse error: {e}", file=sys.stderr)
        clusters = {"clusters": [], "error": str(e)}
    
    # Step 2: Generate Digest (equivalent to ConductResearch - synthesize)
    print(f"📝 Step 2/2: Generating UC Digest...", file=sys.stderr)
    
    digest_prompt = GENERATE_DIGEST_PROMPT.format(
        clusters_json=json.dumps(clusters, indent=2),
        timestamp=datetime.now().isoformat()
    )
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=digest_prompt,
            agent_type="research",
            system_prompt=ANALYZE_SYSTEM,
            max_tokens=12000,
            temperature=0.3
        )
        digest_content = response["content"]
        tokens_step2 = response["tokens_used"]
    
    try:
        digest = parse_json_response(digest_content)
        print(f"✅ Generated digest with {len(digest.get('by_requirement', {}))} BR sections", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"⚠️ Digest JSON parse error: {e}", file=sys.stderr)
        digest = {"raw": digest_content, "parse_error": str(e)}
    
    execution_time = time.time() - start_time
    total_tokens = tokens_step1 + tokens_step2
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        log_llm_interaction(
            agent_id="emma",
            prompt=f"[ANALYZE] Cluster + Digest for {len(use_cases)} UCs",
            response=json.dumps(digest)[:2000],
            execution_id=execution_id,
            agent_mode="analyze",
            tokens_output=total_tokens,
            model=model_used,
            provider=provider_used,
            execution_time_seconds=execution_time,
            success=True
        )
    
    return {
        "agent_id": "research_analyst",
        "agent_name": "Emma (Research Analyst)",
        "execution_id": execution_id,
        "mode": "analyze",
        "deliverable_type": "uc_digest",
        "content": {
            "clusters": clusters,
            "digest": digest
        },
        "metadata": {
            "tokens_used": total_tokens,
            "model": model_used,
            "provider": provider_used,
            "execution_time_seconds": round(execution_time, 2),
            "uc_count": len(use_cases),
            "br_count": len(business_requirements),
            "cluster_count": len(clusters.get("clusters", [])),
            "generated_at": datetime.now().isoformat()
        }
    }


async def run_validate_mode(input_data: Dict, execution_id: int, args) -> Dict:
    """
    Mode VALIDATE: Check 100% coverage of UCs by Solution Design
    Inspired by: WebBrowseAndSummarize (detailed analysis) → ConductResearch (report)
    """
    start_time = time.time()
    
    use_cases = input_data.get("use_cases", [])
    solution_design = input_data.get("solution_design", {})
    
    print(f"🔍 Validating coverage of {len(use_cases)} UCs against Solution Design", file=sys.stderr)
    
    # Step 1: Map elements (equivalent to WebBrowseAndSummarize - detailed extraction)
    print(f"📋 Step 1/2: Mapping UC elements to Solution...", file=sys.stderr)
    
    map_prompt = MAP_ELEMENTS_PROMPT.format(
        use_cases_json=json.dumps(use_cases[:30], indent=2),  # Batch if needed
        solution_design_json=json.dumps(solution_design, indent=2)
    )
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=map_prompt,
            agent_type="research",
            system_prompt=VALIDATE_SYSTEM,
            max_tokens=10000,
            temperature=0.2
        )
        mappings_content = response["content"]
        tokens_step1 = response["tokens_used"]
        model_used = response["model"]
        provider_used = response["provider"]
    else:
        raise ValueError("LLM Service not available")
    
    try:
        mappings = parse_json_response(mappings_content)
        print(f"✅ Mapped {len(mappings.get('mappings', []))} UCs", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"⚠️ Mappings JSON parse error: {e}", file=sys.stderr)
        mappings = {"mappings": [], "error": str(e)}
    
    # Step 2: Generate coverage report (equivalent to ConductResearch)
    print(f"📊 Step 2/2: Generating Coverage Report...", file=sys.stderr)
    
    report_prompt = COVERAGE_REPORT_PROMPT.format(
        mappings_json=json.dumps(mappings, indent=2),
        timestamp=datetime.now().isoformat()
    )
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=report_prompt,
            agent_type="research",
            system_prompt=VALIDATE_SYSTEM,
            max_tokens=8000,
            temperature=0.2
        )
        report_content = response["content"]
        tokens_step2 = response["tokens_used"]
    
    try:
        coverage_report = parse_json_response(report_content)
        coverage_score = coverage_report.get("coverage_score", 0)
        print(f"✅ Coverage Score: {coverage_score}%", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"⚠️ Report JSON parse error: {e}", file=sys.stderr)
        coverage_report = {"raw": report_content, "parse_error": str(e), "coverage_score": 0}
        coverage_score = 0
    
    execution_time = time.time() - start_time
    total_tokens = tokens_step1 + tokens_step2
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        log_llm_interaction(
            agent_id="emma",
            prompt=f"[VALIDATE] Coverage check for {len(use_cases)} UCs",
            response=json.dumps(coverage_report)[:2000],
            execution_id=execution_id,
            agent_mode="validate",
            tokens_output=total_tokens,
            model=model_used,
            provider=provider_used,
            execution_time_seconds=execution_time,
            success=True
        )
    
    return {
        "agent_id": "research_analyst",
        "agent_name": "Emma (Research Analyst)",
        "execution_id": execution_id,
        "mode": "validate",
        "deliverable_type": "coverage_report",
        "content": {
            "mappings": mappings,
            "coverage_report": coverage_report,
            "coverage_score": coverage_score,
            "status": "APPROVED" if coverage_score >= 100 else "NEEDS_REVISION"
        },
        "metadata": {
            "tokens_used": total_tokens,
            "model": model_used,
            "provider": provider_used,
            "execution_time_seconds": round(execution_time, 2),
            "uc_count": len(use_cases),
            "coverage_score": coverage_score,
            "gaps_count": len(coverage_report.get("gaps", [])),
            "generated_at": datetime.now().isoformat()
        }
    }


async def run_write_sds_mode(input_data: Dict, execution_id: int, args) -> Dict:
    """
    Mode WRITE_SDS: Generate professional SDS document
    Writes section by section following template
    """
    start_time = time.time()
    
    template = input_data.get("template", {})
    project_info = input_data.get("project_info", {})
    business_requirements = input_data.get("business_requirements", [])
    use_cases = input_data.get("use_cases", [])
    solution_design = input_data.get("solution_design", {})
    
    print(f"📄 Writing SDS document for project: {project_info.get('name', 'Unknown')}", file=sys.stderr)
    
    # Define SDS sections to write
    sections = [
        ("executive_summary", "Executive Summary", {"project_info": project_info, "br_count": len(business_requirements)}),
        ("business_requirements", "Business Requirements", {"brs": business_requirements}),
        ("functional_specifications", "Functional Specifications", {"use_cases": use_cases[:20]}),
        ("technical_architecture", "Technical Architecture", {"solution": solution_design}),
        ("data_model", "Data Model", {"solution": solution_design}),
        ("security_model", "Security Model", {"solution": solution_design}),
        ("implementation_plan", "Implementation Plan", {"solution": solution_design}),
    ]
    
    sds_content = {}
    total_tokens = 0
    model_used = ""
    provider_used = ""
    
    for section_id, section_name, section_data in sections:
        print(f"📝 Writing section: {section_name}...", file=sys.stderr)
        
        section_prompt = WRITE_SECTION_PROMPT.format(
            section_name=section_name,
            section_template=template.get(section_id, "Standard section format"),
            section_data=json.dumps(section_data, indent=2)[:8000]
        )
        
        if LLM_SERVICE_AVAILABLE:
            response = generate_llm_response(
                prompt=section_prompt,
                agent_type="research",
                system_prompt=WRITE_SDS_SYSTEM,
                max_tokens=4000,
                temperature=0.4
            )
            sds_content[section_id] = response["content"]
            total_tokens += response["tokens_used"]
            model_used = response["model"]
            provider_used = response["provider"]
    
    execution_time = time.time() - start_time
    print(f"✅ SDS document generated with {len(sds_content)} sections", file=sys.stderr)
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        log_llm_interaction(
            agent_id="emma",
            prompt=f"[WRITE_SDS] Document for {project_info.get('name', 'Unknown')}",
            response=f"Generated {len(sds_content)} sections",
            execution_id=execution_id,
            agent_mode="write_sds",
            tokens_output=total_tokens,
            model=model_used,
            provider=provider_used,
            execution_time_seconds=execution_time,
            success=True
        )
    
    return {
        "agent_id": "research_analyst",
        "agent_name": "Emma (Research Analyst)",
        "execution_id": execution_id,
        "mode": "write_sds",
        "deliverable_type": "sds_document",
        "content": {
            "sections": sds_content,
            "project_name": project_info.get("name", "Unknown"),
            "generated_at": datetime.now().isoformat()
        },
        "metadata": {
            "tokens_used": total_tokens,
            "model": model_used,
            "provider": provider_used,
            "execution_time_seconds": round(execution_time, 2),
            "sections_count": len(sds_content),
            "generated_at": datetime.now().isoformat()
        }
    }


# ============================================================================
# MAIN EXECUTION (follows same pattern as other agents)
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Emma Research Analyst Agent')
    parser.add_argument('--input', required=True, help='Input JSON file')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--mode', required=True, choices=['analyze', 'validate', 'write_sds'], 
                        help='Execution mode')
    parser.add_argument('--execution-id', type=int, default=0, help='Execution ID')
    parser.add_argument('--project-id', type=int, default=0, help='Project ID')
    
    args = parser.parse_args()
    
    try:
        # Read input
        print(f"📖 Reading input from {args.input}...", file=sys.stderr)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        print(f"🚀 Running Emma in mode: {args.mode}", file=sys.stderr)
        
        # Run appropriate mode
        import asyncio
        
        if args.mode == "analyze":
            result = asyncio.run(run_analyze_mode(input_data, args.execution_id, args))
        elif args.mode == "validate":
            result = asyncio.run(run_validate_mode(input_data, args.execution_id, args))
        elif args.mode == "write_sds":
            result = asyncio.run(run_write_sds_mode(input_data, args.execution_id, args))
        else:
            raise ValueError(f"Unknown mode: {args.mode}")
        
        # Save output
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Output saved to {args.output}", file=sys.stderr)
        
        # Print summary to stdout for agent_executor
        print(json.dumps({
            "success": True,
            "mode": args.mode,
            "deliverable_type": result["deliverable_type"],
            "metadata": result["metadata"]
        }))
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
