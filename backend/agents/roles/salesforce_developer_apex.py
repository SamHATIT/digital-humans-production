#!/usr/bin/env python3
"""
Salesforce Apex Developer Agent - Diego
Dual Mode: spec (for SDS) | build (for real code generation)

Mode spec: Generate specifications document for SDS
Mode build: Generate real, deployable Apex code for a specific WBS task
"""
import os
import sys
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

# Setup path for imports
sys.path.insert(0, "/app")

# LLM imports
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
# SPEC MODE PROMPT (existing - for SDS)
# ============================================================================
SPEC_PROMPT = """# 💻 SALESFORCE APEX DEVELOPER - SPECIFICATION MODE

You are Diego, a Salesforce Platform Developer II Certified expert.
Generate comprehensive Apex code SPECIFICATIONS (not actual code) for the SDS document.

## INPUT REQUIREMENTS
{requirements}

## YOUR DELIVERABLES
1. **Architecture Overview** - High-level design of Apex classes
2. **Class Specifications** - For each class: purpose, methods, parameters
3. **Trigger Specifications** - Trigger handlers with events and logic
4. **Integration Specifications** - REST/SOAP callout designs
5. **Test Strategy** - Test class outlines with scenarios

## FORMAT
Use clear markdown with sections. Focus on WHAT will be built, not the actual code.
This goes into the Solution Design Specification document.
"""


# ============================================================================
# BUILD MODE PROMPT (new - for real code)
# ============================================================================
BUILD_PROMPT = """# 💻 APEX CODE GENERATION - BUILD MODE

You are Diego, generating REAL, DEPLOYABLE Apex code for Salesforce.

## TASK TO IMPLEMENT
**Task ID:** {task_id}
**Task Name:** {task_name}
**Description:** {task_description}

## ARCHITECTURE CONTEXT
{architecture_context}

## VALIDATION CRITERIA
{validation_criteria}

## CRITICAL OUTPUT FORMAT
Generate REAL Apex code. For EACH file, use this EXACT format:

```apex
// FILE: force-app/main/default/classes/ClassName.cls
public class ClassName {{
    // Real implementation here
}}
```

```xml
// FILE: force-app/main/default/classes/ClassName.cls-meta.xml
<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <status>Active</status>
</ApexClass>
```

For triggers:
```apex
// FILE: force-app/main/default/triggers/TriggerName.trigger
trigger TriggerName on ObjectName (before insert, after update) {{
    // Implementation
}}
```

## APEX RULES - MUST FOLLOW
1. **Bulkification**: Use List<SObject>, never single records
2. **No SOQL/DML in loops**: Query before loop, DML after
3. **Security**: Use WITH SECURITY_ENFORCED or check permissions
4. **Governor Limits**: Stay well under limits
5. **Error Handling**: Try-catch with meaningful messages
6. **No System.error()**: Use System.debug(LoggingLevel.ERROR, msg)
7. **ASCII only**: No emojis in code or comments

## GENERATE THE CODE NOW
Implement the task with production-quality code:
"""


# ============================================================================
# SPEC MODE FUNCTION
# ============================================================================
def generate_spec(requirements: str, project_name: str, execution_id: str, rag_context: str = "") -> dict:
    """Generate specifications for SDS document (existing behavior)"""
    
    prompt = SPEC_PROMPT.format(requirements=requirements[:25000])
    
    if rag_context:
        prompt += f"\n\n## SALESFORCE BEST PRACTICES (RAG)\n{rag_context[:2000]}\n"
    
    print(f"🔧 Diego SPEC mode - generating specifications...", file=sys.stderr)
    
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=prompt,
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            temperature=0.3
        )
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
        model_used = response.get('model', 'claude-sonnet-4-20250514')
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
            temperature=0.3
        )
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
        model_used = "gpt-4o-mini"
    
    execution_time = time.time() - start_time
    
    return {
        "agent_id": "diego",
        "agent_name": "Diego (Apex Developer)",
        "mode": "spec",
        "execution_id": str(execution_id),
        "project_id": project_name,
        "deliverable_type": "apex_specification",
        "content": {
            "raw_markdown": content,
            "sections": _parse_sections(content)
        },
        "metadata": {
            "tokens_used": tokens_used,
            "model": model_used,
            "execution_time_seconds": round(execution_time, 2),
            "generated_at": datetime.now().isoformat()
        }
    }


# ============================================================================
# BUILD MODE FUNCTION
# ============================================================================
def generate_build(task: dict, architecture_context: str, execution_id: str, rag_context: str = "", previous_feedback: str = "") -> dict:
    """Generate real, deployable Apex code for a WBS task"""
    
    task_id = task.get('task_id', 'UNKNOWN')
    task_name = task.get('name', task.get('title', 'Unnamed Task'))
    task_description = task.get('description', '')
    validation_criteria = task.get('validation_criteria', task.get('acceptance_criteria', []))
    
    if isinstance(validation_criteria, list):
        validation_criteria = '\n'.join(f"- {c}" for c in validation_criteria)
    
    # Add correction context if retry
    correction_context = ""
    if previous_feedback:
        correction_context = f"""
## ⚠️ CORRECTION NEEDED - PREVIOUS ATTEMPT FAILED
Elena (QA) reviewed your code and found issues:
{previous_feedback}

YOU MUST FIX THESE ISSUES IN THIS ATTEMPT.
"""
    
    prompt = BUILD_PROMPT.format(
        task_id=task_id,
        task_name=task_name,
        task_description=task_description,
        architecture_context=architecture_context[:10000],
        validation_criteria=validation_criteria
    )
    
    if correction_context:
        prompt += correction_context
    
    if rag_context:
        prompt += f"\n\n## SALESFORCE BEST PRACTICES (RAG)\n{rag_context[:1500]}\n"
    
    print(f"🔧 Diego BUILD mode - generating code for {task_id}...", file=sys.stderr)
    
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=prompt,
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            temperature=0.2  # Lower for more deterministic code
        )
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
        model_used = response.get('model', 'claude-sonnet-4-20250514')
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
            temperature=0.2
        )
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
        model_used = "gpt-4o-mini"
    
    execution_time = time.time() - start_time
    
    # Parse generated files from response
    files = _parse_code_files(content)
    
    print(f"✅ Generated {len(files)} file(s) in {execution_time:.1f}s", file=sys.stderr)
    
    return {
        "agent_id": "diego",
        "agent_name": "Diego (Apex Developer)",
        "mode": "build",
        "task_id": task_id,
        "execution_id": str(execution_id),
        "deliverable_type": "apex_code",
        "success": len(files) > 0,
        "content": {
            "raw_response": content,
            "files": files,
            "file_count": len(files)
        },
        "metadata": {
            "tokens_used": tokens_used,
            "model": model_used,
            "execution_time_seconds": round(execution_time, 2),
            "generated_at": datetime.now().isoformat()
        }
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def _parse_sections(content: str) -> list:
    """Parse markdown sections"""
    sections = []
    current = None
    for line in content.split('\n'):
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            title = line.lstrip('#').strip()
            current = {"title": title, "level": level, "content": ""}
            sections.append(current)
        elif current:
            current["content"] += line + "\n"
    return sections


def _parse_code_files(content: str) -> dict:
    """Parse code blocks with FILE: comments into {path: content} dict"""
    import re
    files = {}
    
    # Pattern: ```lang\n// FILE: path\ncode```
    patterns = [
        r'```(?:apex|cls|trigger)\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
        r'```(?:xml)\s*\n(?://|<!--)\s*FILE:\s*(\S+?)(?:\s*-->)?\s*\n(.*?)```',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        for filepath, code in matches:
            filepath = filepath.strip()
            code = code.strip()
            if filepath and code:
                files[filepath] = code
                print(f"  📄 Parsed: {filepath}", file=sys.stderr)
    
    return files


# ============================================================================
# MAIN
# ============================================================================
def main():
    parser = argparse.ArgumentParser(description='Diego - Apex Developer Agent (Dual Mode)')
    parser.add_argument('--mode', required=True, choices=['spec', 'build'],
                        help='spec: Specifications for SDS | build: Real code for WBS task')
    parser.add_argument('--input', required=True, help='Input file (requirements or task JSON)')
    parser.add_argument('--output', required=True, help='Output JSON file')
    parser.add_argument('--execution-id', default='0', help='Execution ID')
    parser.add_argument('--project-id', default='unknown', help='Project ID')
    parser.add_argument('--use-rag', action='store_true', default=True, help='Use RAG context')
    
    args = parser.parse_args()
    
    try:
        # Read input
        print(f"📖 Reading input from {args.input}...", file=sys.stderr)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()
        
        # Get RAG context
        rag_context = ""
        if args.use_rag and RAG_AVAILABLE:
            try:
                query = "Apex best practices bulkification governor limits security"
                rag_context = get_salesforce_context(query, n_results=3, agent_type="apex_developer")
                print(f"📚 RAG context: {len(rag_context)} chars", file=sys.stderr)
            except Exception as e:
                print(f"⚠️ RAG error: {e}", file=sys.stderr)
        
        # Execute based on mode
        if args.mode == 'spec':
            result = generate_spec(
                requirements=input_content,
                project_name=args.project_id,
                execution_id=args.execution_id,
                rag_context=rag_context
            )
        else:  # build
            # Parse input as JSON for build mode
            try:
                input_data = json.loads(input_content)
            except json.JSONDecodeError:
                input_data = {"task": {"name": "Task", "description": input_content}}
            
            task = input_data.get('task', input_data)
            architecture = input_data.get('architecture_context', input_data.get('context', ''))
            
            previous_feedback = input_data.get('previous_feedback', '')
            result = generate_build(
                task=task,
                architecture_context=architecture,
                execution_id=args.execution_id,
                rag_context=rag_context,
                previous_feedback=previous_feedback
            )
        
        # Write output
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Output written to {args.output}", file=sys.stderr)
        
        # Also print summary to stdout for agent_executor
        print(json.dumps({"success": True, "mode": args.mode, "output": args.output}))
        
    except Exception as e:
        error_result = {
            "agent_id": "diego",
            "mode": args.mode,
            "success": False,
            "error": str(e)
        }
        with open(args.output, 'w') as f:
            json.dump(error_result, f, indent=2)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
