#!/usr/bin/env python3
"""
Marcus AS-IS V2 Module
Optimized As-Is analysis using preprocessed metadata
Cost: ~$0.15-0.30 vs $3-10 for raw metadata

Usage:
    from app.services.salesforce.marcus_as_is_v2 import (
        fetch_and_preprocess_metadata,
        get_as_is_prompt_v2
    )
"""

import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import settings

# Import metadata services
from .metadata_fetcher import MetadataFetcher
from .metadata_preprocessor import MetadataPreprocessor


def fetch_and_preprocess_metadata(
    org_alias: str = "digital-humans-dev",
    project_id: Optional[str] = None,
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run the full metadata pipeline:
    1. Fetch metadata via Tooling API
    2. Preprocess and analyze for red flags
    3. Return summary ready for Marcus
    
    Args:
        org_alias: SFDX org alias
        project_id: Optional project ID for path organization
        output_dir: Optional custom output directory
        
    Returns:
        Dict with success/error and summary data
    """
    # Determine output path
    if output_dir:
        out_path = output_dir
    elif project_id:
        out_path = str(settings.METADATA_DIR / str(project_id))
    else:
        out_path = tempfile.mkdtemp(prefix="metadata_")
    
    try:
        # Step 1: Fetch metadata
        print(f"Fetching metadata from org: {org_alias}...", file=sys.stderr)
        fetcher = MetadataFetcher(org_alias)
        fetch_result = fetcher.fetch_all_metadata(out_path)
        
        if not fetch_result.get("success"):
            return {"success": False, "error": fetch_result.get("error", "Fetch failed")}
        
        print(f"Fetched: {fetch_result.get('metadata_counts', {})}", file=sys.stderr)
        
        # Step 2: Preprocess and analyze
        print(f"Analyzing metadata...", file=sys.stderr)
        preprocessor = MetadataPreprocessor(fetch_result["raw_data_path"])
        summary = preprocessor.generate_summary(f"{out_path}/metadata_summary.json")
        
        debt_score = summary.get('technical_debt_score', 0)
        flag_count = summary.get('red_flags', {}).get('total_count', 0)
        print(f"Analysis complete. Technical Debt: {debt_score}/100, Red Flags: {flag_count}", file=sys.stderr)
        
        return {
            "success": True,
            "summary": summary,
            "output_dir": out_path,
            "fetch_stats": fetch_result.get("metadata_counts", {})
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_as_is_prompt_v2(metadata_summary: Dict[str, Any]) -> str:
    """
    Generate optimized prompt for Marcus using preprocessed metadata summary.
    
    This version receives already analyzed metadata with RED FLAGS,
    making it much more efficient: ~3k tokens vs ~50-200k tokens.
    
    Args:
        metadata_summary: Output from MetadataPreprocessor
        
    Returns:
        Prompt string for LLM
    """
    # Extract key sections
    exec_summary = metadata_summary.get('executive_summary', {})
    key_stats = exec_summary.get('key_stats', {})
    red_flags = metadata_summary.get('red_flags', {})
    debt_score = metadata_summary.get('technical_debt_score', 0)
    
    # Format red flags section
    red_flags_text = ""
    critical_flags = [
        f for f in red_flags.get('items', []) 
        if f.get('severity') in ['CRITICAL', 'HIGH']
    ]
    if critical_flags:
        red_flags_text = "\n### CRITICAL/HIGH ISSUES DETECTED\n"
        for flag in critical_flags[:10]:  # Top 10
            red_flags_text += (
                f"- **{flag.get('type')}** ({flag.get('severity')}): "
                f"{flag.get('component')} - {flag.get('description')}\n"
            )
            red_flags_text += f"  Recommendation: {flag.get('recommendation')}\n"
    
    # Extract component data
    data_model = metadata_summary.get('data_model', {}).get('custom_objects', {})
    automation = metadata_summary.get('automation', {})
    security = metadata_summary.get('security', {})
    integrations = metadata_summary.get('integrations', {})
    ui = metadata_summary.get('ui_components', {})
    
    # Build prompt
    prompt = f"""# AS-IS ANALYSIS (Intelligent Mode)

You are **Marcus**, a Salesforce Certified Technical Architect (CTA).

## YOUR MISSION
Analyze the preprocessed metadata summary and provide strategic recommendations.
The metadata has been pre-analyzed by an automated system - interpret the findings
and provide architectural guidance.

## ORG HEALTH OVERVIEW
- Complexity Level: {exec_summary.get('org_complexity', 'UNKNOWN')}
- Technical Debt Score: {debt_score}/100 (higher = more debt)
- Red Flags: {red_flags.get('total_count', 0)} total
  - CRITICAL: {red_flags.get('by_severity', {}).get('CRITICAL', 0)}
  - HIGH: {red_flags.get('by_severity', {}).get('HIGH', 0)}
  - MEDIUM: {red_flags.get('by_severity', {}).get('MEDIUM', 0)}
  - LOW: {red_flags.get('by_severity', {}).get('LOW', 0)}

## KEY METRICS
| Component | Count |
|-----------|-------|
| Custom Objects | {key_stats.get('custom_objects', 0)} |
| Apex Classes | {key_stats.get('apex_classes', 0)} |
| Apex Triggers | {key_stats.get('apex_triggers', 0)} |
| Flows | {key_stats.get('flows', 0)} |
| LWC Components | {key_stats.get('lwc_components', 0)} |
| Integrations | {key_stats.get('integrations', 0)} |
| Profiles | {security.get('profiles_count', 0)} |
| Permission Sets | {security.get('permission_sets_count', 0)} |
{red_flags_text}

## DETAILED FINDINGS

### Data Model
- Custom Objects: {data_model.get('count', 0)}
- Total Custom Fields: {data_model.get('total_custom_fields', 0)}
- Objects with 50+ fields: {len(data_model.get('objects_with_many_fields', []))}

### Automation
- Flows: {automation.get('flows', {}).get('count', 0)}
  - By Type: {json.dumps(automation.get('flows', {}).get('by_type', {}))}
  - Deprecated (Process Builder/Workflow): {len(automation.get('flows', {}).get('deprecated_types', []))}
- Triggers: {automation.get('apex_triggers', {}).get('count', 0)}
  - By Object: {json.dumps(automation.get('apex_triggers', {}).get('by_object', {}))}
- Validation Rules: {automation.get('validation_rules', {}).get('count', 0)} ({automation.get('validation_rules', {}).get('active_count', 0)} active)

### Code Quality
- Apex Classes: {metadata_summary.get('code', {}).get('apex_classes', {}).get('count', 0)}
- Test Classes: {len(metadata_summary.get('code', {}).get('apex_classes', {}).get('test_classes', []))}
- Complex Classes (>5k chars): {len(metadata_summary.get('code', {}).get('apex_classes', {}).get('complex_classes', []))}

### UI Components
- Lightning Pages: {ui.get('lightning_pages_count', 0)}
- LWC Components: {ui.get('lwc_count', 0)}
- Aura Components: {ui.get('aura_count', 0)} (consider migration to LWC)

### Integrations
- Connected Apps: {len(integrations.get('connected_apps', []))}
- Named Credentials: {len(integrations.get('named_credentials', []))}

## OUTPUT FORMAT (JSON)
Generate an As-Is analysis with:
- "artifact_id": "ASIS-001"
- "title": "Current State Analysis"
- "org_health": Object with:
  - "complexity_rating": LOW/MEDIUM/HIGH/VERY_HIGH
  - "technical_debt_score": 0-100
  - "overall_assessment": 2-3 sentence summary
- "data_model_analysis": Object with:
  - "strengths": Array of positive findings
  - "concerns": Array of issues
  - "recommendations": Array of improvements
- "automation_analysis": Object with:
  - "patterns_detected": Array (e.g., "Trigger handler pattern")
  - "anti_patterns": Array of issues
  - "modernization_needed": Array of deprecated features to migrate
- "code_quality": Object with:
  - "test_coverage_assessment": Description
  - "critical_issues": Array from red flags
  - "refactoring_candidates": Array
- "security_analysis": Object with:
  - "profile_strategy": Assessment
  - "permission_set_usage": Assessment  
  - "recommendations": Array
- "integration_landscape": Object with:
  - "external_systems": Array
  - "risks": Array
- "technical_debt": Object with:
  - "score": 0-100
  - "top_issues": Array (max 5)
  - "remediation_priority": Array ordered by importance
- "strategic_recommendations": Array of top 5 priorities
- "quick_wins": Array of easy improvements

## RULES
1. Use the red flags as primary input for issues
2. Be strategic, not just descriptive
3. Prioritize recommendations by impact
4. Consider Salesforce best practices
5. Flag anything blocking future scalability
6. Suggest modernization paths for deprecated features

---

**Generate the As-Is Analysis now. Output ONLY valid JSON.**
"""
    
    return prompt


# ============================================================================
# CLI Interface for standalone testing
# ============================================================================
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Marcus AS-IS V2")
    parser.add_argument("--org", default="digital-humans-dev", help="SFDX org alias")
    parser.add_argument("--output", help="Output directory")
    parser.add_argument("--project-id", help="Project ID")
    
    args = parser.parse_args()
    
    result = fetch_and_preprocess_metadata(
        org_alias=args.org,
        project_id=args.project_id,
        output_dir=args.output
    )
    
    if result.get("success"):
        print("\n" + "="*60)
        print("METADATA ANALYSIS COMPLETE")
        print("="*60)
        
        summary = result["summary"]
        print(f"Technical Debt Score: {summary.get('technical_debt_score', 0)}/100")
        print(f"Org Complexity: {summary.get('executive_summary', {}).get('org_complexity', 'UNKNOWN')}")
        print(f"Red Flags: {summary.get('red_flags', {}).get('total_count', 0)}")
        
        print("\nGenerating prompt...")
        prompt = get_as_is_prompt_v2(summary)
        print(f"Prompt size: {len(prompt)} chars (~{len(prompt)//4} tokens)")
        
        print(f"\nOutput saved to: {result.get('output_dir')}")
    else:
        print(f"ERROR: {result.get('error')}")
