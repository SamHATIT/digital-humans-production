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

# LLM Logger for debugging (INFRA-002)
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
    print(f"📝 LLM Logger loaded for Olivia", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass

# JSON Cleaner for robust parsing (F-081)
try:
    from app.utils.json_cleaner import clean_llm_json_response
    JSON_CLEANER_AVAILABLE = True
except ImportError:
    JSON_CLEANER_AVAILABLE = False
    def clean_llm_json_response(s): return None, "JSON cleaner not available"

# RAG Service
try:
    from app.services.rag_service import get_salesforce_context
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# ============================================================================
# PROMPT: BR → USE CASES (~100 lines)
def get_uc_generation_prompt(br: dict, rag_context: str = "") -> str:
    br_id = br.get('id', 'BR-XXX')
    br_title = br.get('title', br.get('requirement', '')[:50])
    br_description = br.get('description', br.get('requirement', ''))
    br_category = br.get('category', 'OTHER')
    br_stakeholder = br.get('stakeholder', br.get('metadata', {}).get('stakeholder', 'Business User'))
    
    # PRPT-01 metadata if available
    br_metadata = br.get('metadata', br.get('br_metadata', {}))
    br_fields = br_metadata.get('fields', [])
    br_rules = br_metadata.get('validation_rules', [])
    
    metadata_section = ""
    if br_fields or br_rules:
        metadata_section = f"""
## EXTRACTED DETAILS FROM BR
- **Fields mentioned**: {', '.join(br_fields) if br_fields else 'None specified'}
- **Validation rules**: {', '.join(br_rules) if br_rules else 'None specified'}
"""
    
    rag_section = ""
    if rag_context:
        # Truncate RAG context to avoid verbosity
        rag_section = f"""
## SALESFORCE CONTEXT (use for field names and patterns)
{rag_context[:1500]}
"""
    
    return f'''# USE CASE GENERATION - COMPACT FORMAT

You are **Olivia**, Senior Salesforce Business Analyst.

## MISSION
Generate 3-5 **concise** Use Cases for this BR. Each UC must be:
- **Atomic**: One user goal per UC
- **Testable**: Clear pass/fail criteria
- **Compact**: No filler text, only essential info

## INPUT BR

**{br_id}: {br_title}**
- Category: {br_category}
- Stakeholder: {br_stakeholder}
- Description: {br_description}
{metadata_section}
{rag_section}

## OUTPUT FORMAT (JSON - STRICT)

```json
{{
  "parent_br": "{br_id}",
  "use_cases": [
    {{
      "id": "UC-{br_id[3:]}-01",
      "title": "Action-oriented title (max 8 words)",
      "actor": "Role (e.g., Sales Rep, System Admin)",
      "trigger": "What starts this UC (e.g., User clicks button)",
      "main_flow": [
        "1. User does X",
        "2. System validates Y", 
        "3. System saves Z"
      ],
      "alt_flows": [
        "1a. If validation fails: show error"
      ],
      "acceptance_criteria": [
        "GIVEN [context] WHEN [action] THEN [result]"
      ],
      "sf_objects": ["Account", "Custom_Object__c"],
      "sf_fields": ["Account.Name", "Custom_Object__c.Status__c"],
      "sf_automation": "Record-Triggered Flow / Apex Trigger / None"
    }}
  ]
}}
```

## RULES (CRITICAL)

1. **3-5 UCs only** - More is waste, less is incomplete
2. **Max 6 steps** in main_flow - If more needed, split into separate UC
3. **Max 3 alt_flows** - Focus on critical paths only
4. **Max 4 acceptance criteria** - Use GIVEN/WHEN/THEN format
5. **Specific Salesforce objects** - No generic "data object", use real SF names
6. **Real field names** - Use API names (MyField__c), not labels
7. **One automation type** per UC - Flow OR Trigger, not both
8. **No redundancy** - If UC-01 covers "create record", UC-02 should NOT repeat it

## ANTI-PATTERNS TO AVOID

❌ "User performs action" → ✅ "User clicks Save button"
❌ "System processes data" → ✅ "System runs validation rule"
❌ "Record is updated" → ✅ "Account.Status__c = 'Qualified'"
❌ Long paragraphs → ✅ Short numbered steps
❌ 10+ acceptance criteria → ✅ 3-4 key testable criteria

---

**Generate Use Cases for {br_id}. Output ONLY valid JSON, no markdown fences or explanations.**
'''



# F-081: Batch mode prompt for processing 2 BRs at once
def get_uc_generation_prompt_batch(brs: list, rag_context: str = "") -> str:
    """Generate UC prompt for 1 or 2 BRs at once (F-081 optimization)"""
    br_sections = []
    br_ids = []
    
    for br in brs:
        br_id = br.get('id', 'BR-XXX')
        br_ids.append(br_id)
        br_title = br.get('title', br.get('requirement', '')[:50])
        br_description = br.get('description', br.get('requirement', ''))
        br_category = br.get('category', 'OTHER')
        br_stakeholder = br.get('stakeholder', br.get('metadata', {}).get('stakeholder', 'Business User'))
        
        br_metadata = br.get('metadata', br.get('br_metadata', {}))
        br_fields = br_metadata.get('fields', [])
        
        fields_text = f"Fields: {', '.join(br_fields)}" if br_fields else ""
        
        br_sections.append(f"""### {br_id}: {br_title}
- Category: {br_category} | Stakeholder: {br_stakeholder}
- {br_description[:500]}
{fields_text}""")
    
    brs_text = "\n\n".join(br_sections)
    br_count = len(brs)
    
    rag_section = f"\n## SALESFORCE CONTEXT\n{rag_context[:1200]}\n" if rag_context else ""
    
    return f"""# USE CASE GENERATION - {br_count} BR{"s" if br_count > 1 else ""}

You are **Olivia**, Senior Salesforce Business Analyst.

## INPUT BRs

{brs_text}
{rag_section}

## OUTPUT FORMAT

Return a JSON object with "results" array. Each result has "parent_br" and "use_cases" array.
Generate 3-5 Use Cases per BR with: id, title, actor, trigger, main_flow (max 6 steps), 
alt_flows (max 3), acceptance_criteria (GIVEN/WHEN/THEN), sf_objects, sf_fields, sf_automation.

## RULES
- UC IDs: UC-XXX-01, UC-XXX-02 (XXX = BR number)
- Real Salesforce object/field names with __c suffix
- One automation type per UC (Flow/Apex/None)
- Max 6 main_flow steps, max 4 acceptance criteria

Output ONLY valid JSON, no markdown fences."""


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
    parser.add_argument('--mode', default='generate_uc', help='Agent mode')
    
    args = parser.parse_args()
    
    try:
        start_time = time.time()
        
        # Read input BR
        print(f"📖 Reading BR from {args.input}...", file=sys.stderr)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        # Handle single BR, wrapped BR, or batch of BRs (F-081)
        brs = []
        if 'business_requirements' in input_data:
            # Batch mode: list of BRs
            brs = input_data['business_requirements']
        elif 'business_requirement' in input_data:
            brs = [input_data['business_requirement']]
        elif 'id' in input_data and str(input_data.get('id', '')).startswith('BR-'):
            brs = [input_data]
        else:
            raise ValueError("Input must contain business_requirement(s) with 'id' starting with 'BR-'")
        
        batch_mode = len(brs) > 1
        br_ids = [br.get('id', 'BR-XXX') for br in brs]
        print(f"✅ Processing {len(brs)} BR(s): {', '.join(br_ids)}", file=sys.stderr)
        
        # For compatibility, keep single br reference
        br = brs[0]
        br_id = br_ids[0]
        
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
        # F-081: Use batch prompt if multiple BRs
        if batch_mode:
            prompt = get_uc_generation_prompt_batch(brs, rag_context)
        else:
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
            input_tokens = response.get("input_tokens", 0)
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
            input_tokens = response.usage.input_tokens
            model_used = "claude-sonnet-4-20250514"
            provider_used = "anthropic"
        
        print(f"✅ Using {provider_used} / {model_used}", file=sys.stderr)
        
        execution_time = time.time() - start_time
        print(f"✅ Generated {len(content)} characters in {execution_time:.1f}s", file=sys.stderr)
        print(f"📊 Tokens used: {tokens_used}", file=sys.stderr)
        
        # Log LLM interaction for debugging (INFRA-002)
        if LLM_LOGGER_AVAILABLE:
            try:
                log_llm_interaction(
                    agent_id="olivia",
                    prompt=prompt,
                    response=content,
                    execution_id=args.execution_id,
                    task_id=None,
                    agent_mode=args.mode,
                    rag_context=None,
                    previous_feedback=None,
                    parsed_files=None,
                    tokens_input=input_tokens,
                    tokens_output=tokens_used,
                    model=model_used,
                    provider=provider_used,
                    execution_time_seconds=execution_time,
                    success=True,
                    error_message=None
                )
                print(f"📝 LLM interaction logged", file=sys.stderr)
            except Exception as e:
                print(f"⚠️ Failed to log LLM interaction: {e}", file=sys.stderr)
        
        # Parse JSON output (with json_cleaner and batch support - F-081)
        try:
            # Use robust json_cleaner
            if JSON_CLEANER_AVAILABLE:
                parsed_content, parse_error = clean_llm_json_response(content)
                if parsed_content is None:
                    raise json.JSONDecodeError(parse_error or "Parse error", content, 0)
            else:
                clean_content = content.strip()
                if clean_content.startswith('```'):
                    clean_content = clean_content.split('\n', 1)[1] if '\n' in clean_content else clean_content[3:]
                if clean_content.endswith('```'):
                    clean_content = clean_content[:-3]
                parsed_content = json.loads(clean_content.strip())
            
            # F-081: Handle batch response format {"results": [...]}
            if 'results' in parsed_content and isinstance(parsed_content['results'], list):
                # Batch response - flatten all use_cases with their parent_br
                all_use_cases = []
                for result in parsed_content['results']:
                    parent_br = result.get('parent_br', br_id)
                    for uc in result.get('use_cases', []):
                        uc['parent_br'] = parent_br  # Tag each UC with its parent
                        all_use_cases.append(uc)
                parsed_content = {"use_cases": all_use_cases, "batch_mode": True, "parent_brs": br_ids}
                uc_count = len(all_use_cases)
                print(f"✅ Batch mode: Generated {uc_count} Use Cases for {len(br_ids)} BRs", file=sys.stderr)
            else:
                # Single BR response
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
