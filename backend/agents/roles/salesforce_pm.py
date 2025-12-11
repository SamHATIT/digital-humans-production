#!/usr/bin/env python3
"""
Salesforce Project Manager (Sophie) Agent
Two distinct roles:
1. extract_br: Extract atomic Business Requirements from raw input
2. consolidate_sds: Consolidate all artifacts into final SDS document
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
    print(f"📝 LLM Logger loaded for Sophie", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass

# ============================================================================
# PROMPT 1: EXTRACT BUSINESS REQUIREMENTS
# ============================================================================
def get_extract_br_prompt(requirements: str) -> str:
    return f'''# 📋 BUSINESS REQUIREMENTS EXTRACTION

You are **Sophie**, a Senior Project Manager specialized in requirements analysis.

## YOUR MISSION
Extract **atomic Business Requirements (BR)** from the raw user input.
Each BR must be:
- **Atomic**: One single, testable requirement
- **Clear**: Unambiguous and precise
- **Independent**: Can be analyzed separately
- **Traceable**: Has a unique ID (BR-001, BR-002, etc.)

## OUTPUT FORMAT (JSON)
Output a JSON object with this structure:
- "project_summary": Brief 2-3 sentence summary of the project
- "business_requirements": Array of BR objects, each with:
  - "id": "BR-001", "BR-002", etc.
  - "title": Short descriptive title (max 10 words)
  - "description": Clear description (1-3 sentences)
  - "category": One of DATA_MODEL, AUTOMATION, INTEGRATION, UI_UX, REPORTING, SECURITY, OTHER
  - "priority": One of MUST_HAVE, SHOULD_HAVE, NICE_TO_HAVE
  - "stakeholder": Who needs this (e.g., "Sales Manager", "System Admin")
  - "metadata": Object containing:
    - "fields": Array of specific field names mentioned (e.g., ["Customer.Phone", "Order.Amount"])
    - "validation_rules": Array of business rules (e.g., ["Amount must be > 0", "Date cannot be in past"])
    - "dependencies": Array of related BR IDs (e.g., ["BR-001", "BR-003"])
    - "acceptance_criteria": Array of testable criteria (e.g., ["User can create record", "System validates input"])
- "constraints": Array of technical or business constraints
- "assumptions": Array of assumptions made

## RULES
1. Extract 10-30 atomic BRs depending on project complexity
2. **EXTRACT SPECIFIC DETAILS**:
   - When user mentions a field (e.g., "track the customer's phone number"), add it to metadata.fields
   - When user mentions a rule (e.g., "discount cannot exceed 30%"), add it to metadata.validation_rules
   - When a BR depends on another (e.g., "products need an order"), note the dependency
3. Do NOT add Salesforce-specific details (that's the BA's job)
4. Do NOT design solutions (that's the Architect's job)
5. Focus on WHAT is needed, not HOW to implement
6. Group related requirements under appropriate categories
7. Preserve the business intent from the original text
8. If something is unclear, list it as an assumption

## EXAMPLE
For input: "We need to track customer phone and email. Discounts cannot exceed 30%."

Output should include:
- metadata.fields: ["Customer.Phone", "Customer.Email", "Order.Discount"]
- metadata.validation_rules: ["Discount <= 30%"]
- metadata.acceptance_criteria: ["User can enter phone", "System rejects discount > 30%"]

---

## RAW REQUIREMENTS TO ANALYZE:

{requirements}

---

**Extract all Business Requirements now. Output ONLY valid JSON, no markdown fences or extra text.**
'''

def get_consolidate_sds_prompt(artifacts: str) -> str:
    return f'''# 📄 SOLUTION DESIGN SPECIFICATION - FINAL DOCUMENT

You are **Sophie**, a Senior Project Manager creating the final SDS document.

## YOUR MISSION
Consolidate all agent artifacts into a **professional, well-formatted** Solution Design Specification.

## CRITICAL FORMATTING RULES

### Mermaid Diagrams
All diagrams MUST use proper Mermaid syntax wrapped in code blocks:

**ERD Diagram Example:**
```mermaid
erDiagram
    Account ||--o{{ Opportunity : has
    Opportunity ||--o{{ OpportunityLineItem : contains
    Product2 ||--o{{ OpportunityLineItem : "product for"
    Opportunity ||--o{{ Trade_In__c : includes
```

**Flow Diagram Example:**
```mermaid
flowchart TD
    A[Start: New Opportunity] --> B{{Multi-Product?}}
    B -->|Yes| C[Add Products]
    B -->|No| D[Standard Flow]
    C --> E[Calculate Total]
    E --> F[End]
```

**Sequence Diagram Example:**
```mermaid
sequenceDiagram
    participant User
    participant Salesforce
    participant ExternalAPI
    User->>Salesforce: Create Trade-In
    Salesforce->>ExternalAPI: Get Valuation
    ExternalAPI-->>Salesforce: Return Value
    Salesforce-->>User: Display Quote
```

### Tables
Use proper Markdown tables with headers:
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |

## DOCUMENT STRUCTURE (15-25 pages max)

### 1. Executive Summary (1 page max)
- **Project Name**: [Name]
- **Date**: [Date]
- **Version**: 1.0
- **Overview**: 3-5 sentences describing the project
- **Key Objectives**: 3-5 bullet points
- **Success Criteria**: Measurable outcomes

### 2. Business Requirements Summary (2-3 pages)
Create a table:
| BR ID | Title | Category | Priority | Status |
|-------|-------|----------|----------|--------|

Then add **BR to UC Traceability Matrix**:
| BR ID | Related Use Cases |
|-------|-------------------|

### 3. Solution Architecture (4-5 pages)

#### 3.1 Data Model
- Include the **ERD diagram** from ARCH-001 using Mermaid erDiagram
- List custom objects with key fields
- Document relationships

#### 3.2 Security Model
| Profile/Permission Set | Description | Key Permissions |
|------------------------|-------------|-----------------|

#### 3.3 Automation Design
- **Flows**: List with purpose
- **Triggers**: Only if necessary
- Include a **Process Flow diagram** using Mermaid flowchart

#### 3.4 Integration Architecture
| System | Direction | Method | Frequency |
|--------|-----------|--------|-----------|

Include a **Sequence Diagram** for key integrations

### 4. Gap Analysis Summary (2-3 pages)
From GAP-001:
| Gap ID | Category | Description | Effort | Assigned To |
|--------|----------|-------------|--------|-------------|

### 5. Implementation Plan (3-4 pages)
From WBS-001:

#### 5.1 Project Phases
| Phase | Duration | Key Deliverables |
|-------|----------|------------------|

#### 5.2 Timeline (Gantt-style using Mermaid)
```mermaid
gantt
    title Project Timeline
    dateFormat  YYYY-MM-DD
    section Foundation
    Security Setup     :a1, 2024-01-01, 2w
    section Build
    Data Model        :a2, after a1, 3w
```

#### 5.3 Resource Allocation
| Agent/Role | Allocation | Primary Responsibilities |
|------------|------------|--------------------------|

### 6. Risks and Mitigations (1 page)
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|

### 7. Appendix
- Reference to detailed artifacts (ARCH-001, ASIS-001, GAP-001, WBS-001)
- Glossary of terms
- Do NOT copy full artifact content

## OUTPUT RULES
1. Output clean Markdown only
2. All Mermaid diagrams must be syntactically correct
3. Use proper heading hierarchy (# ## ### ####)
4. Tables must have header separators (|---|)
5. Keep content concise - reference artifacts instead of copying
6. Include page breaks as: `---` between major sections
7. No JSON output - pure Markdown document

---

## ARTIFACTS TO CONSOLIDATE:

{artifacts}

---

**Generate the complete SDS document now in Markdown format.**
'''

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description='Sophie PM Agent')
    parser.add_argument('--mode', required=True, choices=['extract_br', 'consolidate_sds'],
                        help='Operation mode')
    parser.add_argument('--input', required=True, help='Input file path')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--execution-id', type=int, default=0, help='Execution ID')
    parser.add_argument('--project-id', type=int, default=0, help='Project ID')
    
    args = parser.parse_args()
    
    try:
        start_time = time.time()
        
        # Read input
        print(f"📖 Reading input from {args.input}...", file=sys.stderr)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()
        print(f"✅ Read {len(input_content)} characters", file=sys.stderr)
        
        # Select prompt based on mode
        if args.mode == 'extract_br':
            prompt = get_extract_br_prompt(input_content)
            system_prompt = "You are Sophie, a Senior Project Manager. Extract atomic business requirements from the input. Output ONLY valid JSON, no markdown code fences."
            deliverable_type = "business_requirements_extraction"
            agent_role = "PM - BR Extraction"
            max_tokens = 8000
            temperature = 0.3
        else:  # consolidate_sds
            prompt = get_consolidate_sds_prompt(input_content)
            system_prompt = "You are Sophie, a Senior Project Manager. Create a professional SDS document in clean Markdown format with properly formatted Mermaid diagrams."
            deliverable_type = "solution_design_specification"
            agent_role = "PM - SDS Consolidation"
            max_tokens = 16000
            temperature = 0.4
        
        print(f"📝 Mode: {args.mode}", file=sys.stderr)
        print(f"📝 Prompt size: {len(prompt)} characters", file=sys.stderr)
        
        # Call LLM
        if LLM_SERVICE_AVAILABLE:
            print(f"🤖 Calling Claude API (PM tier)...", file=sys.stderr)
            response = generate_llm_response(
                prompt=prompt,
                agent_type="pm",
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature
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
                max_tokens=max_tokens,
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
        
        # Log LLM interaction for debugging (INFRA-002)
        if LLM_LOGGER_AVAILABLE:
            try:
                log_llm_interaction(
                    agent_id="sophie",
                    prompt=prompt,
                    response=content,
                    execution_id=args.execution_id,
                    task_id=None,
                    agent_mode=args.mode,
                    rag_context=None,
                    previous_feedback=None,
                    parsed_files=None,
                    tokens_input=None,
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
        
        # Parse content based on mode
        if args.mode == 'extract_br':
            # Parse JSON output
            try:
                clean_content = content.strip()
                if clean_content.startswith('```'):
                    clean_content = clean_content.split('\n', 1)[1] if '\n' in clean_content else clean_content[3:]
                if clean_content.endswith('```'):
                    clean_content = clean_content[:-3]
                clean_content = clean_content.strip()
                
                parsed_content = json.loads(clean_content)
                br_count = len(parsed_content.get('business_requirements', []))
                print(f"✅ Extracted {br_count} Business Requirements", file=sys.stderr)
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parse error: {e}", file=sys.stderr)
                parsed_content = {"raw": content, "parse_error": str(e)}
        else:
            # For SDS, content is markdown - store as-is
            parsed_content = {"markdown": content}
            # Count Mermaid diagrams
            mermaid_count = content.count('```mermaid')
            print(f"✅ SDS generated with {mermaid_count} Mermaid diagrams", file=sys.stderr)
        
        # Build output
        output_data = {
            "agent_id": "pm",
            "agent_name": "Sophie (Project Manager)",
            "agent_role": agent_role,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
            "deliverable_type": deliverable_type,
            "mode": args.mode,
            "content": parsed_content,
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": datetime.now().isoformat()
            }
        }
        
        # Add mode-specific metadata
        if args.mode == 'extract_br' and isinstance(parsed_content, dict) and 'business_requirements' in parsed_content:
            output_data["metadata"]["br_count"] = len(parsed_content['business_requirements'])
            output_data["metadata"]["categories"] = list(set(
                br.get('category', 'OTHER') 
                for br in parsed_content['business_requirements']
            ))
        elif args.mode == 'consolidate_sds':
            output_data["metadata"]["mermaid_diagrams_count"] = content.count('```mermaid')
            output_data["metadata"]["tables_count"] = content.count('|---|')
        
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
