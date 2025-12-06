#!/usr/bin/env python3
"""
Salesforce Business Analyst (Olivia) Agent - Refactored Version
Generates Use Cases (UC) from a single Business Requirement (BR)
Uses RAG for Salesforce best practices enrichment
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
# PROMPT: BR → USE CASES (~100 lines)
# ============================================================================
def get_uc_generation_prompt(br: dict, rag_context: str = "") -> str:
    br_id = br.get('id', 'BR-XXX')
    br_title = br.get('title', 'Untitled')
    br_description = br.get('description', '')
    br_category = br.get('category', 'OTHER')
    br_stakeholder = br.get('stakeholder', 'Business User')
    
    rag_section = ""
    if rag_context:
        rag_section = f"""
## SALESFORCE BEST PRACTICES (from RAG)
Use this expert context to inform your Use Case design:

{rag_context}

---
"""
    
    return f'''# 📋 USE CASE GENERATION FOR BUSINESS REQUIREMENT

You are **Olivia**, a Senior Salesforce Business Analyst.

## YOUR MISSION
Generate **detailed Use Cases (UC)** for the given Business Requirement.
Each UC must be:
- **Specific**: Describes a concrete user interaction
- **Testable**: Has clear acceptance criteria
- **Salesforce-aligned**: Uses Salesforce terminology and patterns
- **Traceable**: Links back to the parent BR

## INPUT: BUSINESS REQUIREMENT

**{br_id}: {br_title}**
- Description: {br_description}
- Category: {br_category}
- Stakeholder: {br_stakeholder}

{rag_section}

## OUTPUT FORMAT (JSON)
Generate 3-5 Use Cases with this structure:
- "parent_br": "{br_id}"
- "use_cases": Array of UC objects, each with:
  - "id": "UC-{br_id[3:]}-01", "UC-{br_id[3:]}-02", etc.
  - "title": Clear action-oriented title
  - "actor": Primary user role
  - "preconditions": Array of conditions that must be true before
  - "main_flow": Array of numbered steps (what the user/system does)
  - "alternative_flows": Array of alternative scenarios
  - "postconditions": Array of expected outcomes
  - "acceptance_criteria": Array of testable criteria
  - "salesforce_components": Object with:
    - "objects": Array of Salesforce objects involved
    - "fields": Array of key fields (use __c for custom)
    - "automation": Array of automation needed (Flow, Trigger, etc.)
    - "ui_components": Array of UI elements needed

## RULES
1. Generate 3-5 Use Cases per BR (not more, not less)
2. Use Salesforce standard objects where possible (Lead, Account, Opportunity, etc.)
3. Custom objects/fields must follow naming conventions (end with __c)
4. Be specific about automation type (Record-Triggered Flow, Screen Flow, Apex Trigger)
5. Include realistic field names and picklist values
6. Acceptance criteria must be measurable and testable
7. Consider error handling in alternative flows

## EXAMPLE OUTPUT STRUCTURE
For BR "Lead Qualification":
- UC-001-01: Sales Rep Qualifies Lead via Score
- UC-001-02: System Auto-Qualifies High-Score Lead
- UC-001-03: Manager Reviews Borderline Leads

---

**Generate Use Cases for {br_id} now. Output ONLY valid JSON, no markdown fences.**
'''

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description='Olivia BA Agent - UC Generation')
    parser.add_argument('--input', required=True, help='Input JSON file with BR')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--execution-id', type=int, default=0, help='Execution ID')
    parser.add_argument('--project-id', type=int, default=0, help='Project ID')
    parser.add_argument('--use-rag', action='store_true', default=True, help='Use RAG for context')
    
    args = parser.parse_args()
    
    try:
        start_time = time.time()
        
        # Read input BR
        print(f"📖 Reading BR from {args.input}...", file=sys.stderr)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        # Handle both direct BR object and wrapped format
        if 'business_requirement' in input_data:
            br = input_data['business_requirement']
        elif 'id' in input_data and input_data['id'].startswith('BR-'):
            br = input_data
        else:
            raise ValueError("Input must contain a Business Requirement with 'id' starting with 'BR-'")
        
        br_id = br.get('id', 'BR-XXX')
        print(f"✅ Processing {br_id}: {br.get('title', 'Untitled')}", file=sys.stderr)
        
        # Get RAG context if available
        rag_context = ""
        if args.use_rag and RAG_AVAILABLE:
            try:
                # Build query from BR content
                query = f"Salesforce {br.get('category', '')} {br.get('title', '')} {br.get('description', '')}"
                print(f"🔍 Querying RAG: {query[:80]}...", file=sys.stderr)
                rag_context = get_salesforce_context(query[:500], n_results=5, agent_type="business_analyst")
                print(f"✅ RAG context: {len(rag_context)} chars", file=sys.stderr)
            except Exception as e:
                print(f"⚠️ RAG error: {e}", file=sys.stderr)
                rag_context = ""
        
        # Build prompt
        prompt = get_uc_generation_prompt(br, rag_context)
        system_prompt = "You are Olivia, a Senior Salesforce Business Analyst. Generate detailed Use Cases from the Business Requirement. Output ONLY valid JSON."
        
        print(f"📝 Prompt size: {len(prompt)} characters", file=sys.stderr)
        
        # Call LLM
        if LLM_SERVICE_AVAILABLE:
            print(f"🤖 Calling Claude API (BA tier)...", file=sys.stderr)
            response = generate_llm_response(
                prompt=prompt,
                agent_type="ba",
                system_prompt=system_prompt,
                max_tokens=8000,
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
                max_tokens=8000,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            model_used = "claude-sonnet-4-20250514"
            provider_used = "anthropic"
        
        print(f"✅ Using {provider_used} / {model_used}", file=sys.stderr)
        
        execution_time = time.time() - start_time
        print(f"✅ Generated {len(content)} characters in {execution_time:.1f}s", file=sys.stderr)
        print(f"📊 Tokens used: {tokens_used}", file=sys.stderr)
        
        # Parse JSON output
        try:
            clean_content = content.strip()
            if clean_content.startswith('```'):
                clean_content = clean_content.split('\n', 1)[1] if '\n' in clean_content else clean_content[3:]
            if clean_content.endswith('```'):
                clean_content = clean_content[:-3]
            clean_content = clean_content.strip()
            
            parsed_content = json.loads(clean_content)
            uc_count = len(parsed_content.get('use_cases', []))
            print(f"✅ Generated {uc_count} Use Cases for {br_id}", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error: {e}", file=sys.stderr)
            parsed_content = {"raw": content, "parse_error": str(e)}
            uc_count = 0
        
        # Build output
        output_data = {
            "agent_id": "ba",
            "agent_name": "Olivia (Business Analyst)",
            "execution_id": args.execution_id,
            "project_id": args.project_id,
            "deliverable_type": "use_case_specification",
            "parent_br": br_id,
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "uc_count": uc_count,
                "rag_used": bool(rag_context),
                "rag_context_length": len(rag_context),
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
