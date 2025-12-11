#!/usr/bin/env python3
"""
Salesforce LWC Developer Agent - Zara
Dual Mode: spec (for SDS) | build (for real component generation)
"""
import os
import sys

# Configure path for imports when running as subprocess
if '/app' not in sys.path:
    sys.path.insert(0, '/app')

# LLM Logger for debugging
try:
    from app.services.llm_logger import log_llm_interaction
    DB_AVAILABLE = True
    print(f"📝 LLM Logger loaded", file=sys.stderr)
except ImportError as e:
    DB_AVAILABLE = False
    print(f"⚠️ LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass
import argparse
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, "/app")

try:
    from app.services.llm_service import generate_llm_response, LLMProvider
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

try:
    from app.services.rag_service import get_salesforce_context
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False


# ============================================================================
# SPEC MODE PROMPT
# ============================================================================
SPEC_PROMPT = """# ⚡ LWC DEVELOPER - SPECIFICATION MODE

You are Zara, an expert Salesforce LWC Developer.
Generate comprehensive LWC component SPECIFICATIONS for the SDS document.

## INPUT REQUIREMENTS
{requirements}

## YOUR DELIVERABLES
1. **Component Architecture** - List of components with hierarchy
2. **Component Specifications** - For each: purpose, properties, events, wire adapters
3. **UI/UX Guidelines** - Design patterns, accessibility (WCAG 2.1)
4. **Data Flow** - How components communicate (events, pubsub, LMS)
5. **Integration Points** - Apex controllers, wire services

## FORMAT
Use clear markdown. Focus on WHAT will be built, not actual code.
"""


# ============================================================================
# BUILD MODE PROMPT
# ============================================================================
BUILD_PROMPT = """# ⚡ LWC CODE GENERATION - BUILD MODE

You are Zara, generating REAL, DEPLOYABLE Lightning Web Components.

## TASK TO IMPLEMENT
**Task ID:** {task_id}
**Task Name:** {task_name}
**Description:** {task_description}

## ARCHITECTURE CONTEXT
{architecture_context}

## VALIDATION CRITERIA
{validation_criteria}

## CRITICAL OUTPUT FORMAT
Generate a complete LWC component. For EACH file, use this EXACT format:

```html
<!-- FILE: force-app/main/default/lwc/componentName/componentName.html -->
<template>
    <!-- Your template here -->
</template>
```

```javascript
// FILE: force-app/main/default/lwc/componentName/componentName.js
import {{ LightningElement, api, wire }} from 'lwc';

export default class ComponentName extends LightningElement {{
    // Your code here
}}
```

```css
/* FILE: force-app/main/default/lwc/componentName/componentName.css */
/* Your styles here */
```

```xml
<!-- FILE: force-app/main/default/lwc/componentName/componentName.js-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<LightningComponentBundle xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <isExposed>true</isExposed>
    <targets>
        <target>lightning__RecordPage</target>
        <target>lightning__AppPage</target>
    </targets>
</LightningComponentBundle>
```

## LWC RULES - MUST FOLLOW
1. **Reactive**: Use @track only when needed, prefer @api for public props
2. **Wire**: Use wire adapters for data, handle errors
3. **Events**: CustomEvent for child-to-parent, LMS for unrelated
4. **Accessibility**: ARIA labels, keyboard navigation, focus management
5. **Performance**: Avoid unnecessary renders, use if:true
6. **Security**: No innerHTML, sanitize user input

## ⚠️ COMPLETENESS CHECKLIST - VERIFY BEFORE SUBMITTING
Before generating, ensure:
□ HTML: All tags properly opened AND closed (no incomplete templates)
□ HTML: All referenced variables exist in the JS file
□ JS: All methods referenced in HTML are fully implemented (not just signatures)
□ JS: All imports are present (LightningElement, api, wire, track, etc.)
□ JS: Error handling with try-catch for async operations
□ CSS: All classes referenced in HTML have style rules
□ META: Correct targets for where the component will be used

## GENERATE COMPLETE, WORKING CODE NOW:
"""


def generate_spec(requirements: str, project_name: str, execution_id: str, rag_context: str = "") -> dict:
    prompt = SPEC_PROMPT.format(requirements=requirements[:25000])
    if correction_context:
        prompt += correction_context
    
    if rag_context:
        prompt += f"\n\n## SALESFORCE LWC BEST PRACTICES (RAG)\n{rag_context[:2000]}\n"
    
    print(f"🔧 Zara SPEC mode - generating specifications...", file=sys.stderr)
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC, 
                                         model="claude-sonnet-4-20250514", max_tokens=16000, temperature=0.3)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
        model_used = response.get('model', 'claude-sonnet-4-20250514')
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=16000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
        model_used = "gpt-4o-mini"
    
    return {
        "agent_id": "zara", "agent_name": "Zara (LWC Developer)", "mode": "spec",
        "execution_id": str(execution_id), "project_id": project_name,
        "deliverable_type": "lwc_specification",
        "content": {"raw_markdown": content},
        "metadata": {"tokens_used": tokens_used, "model": model_used, 
                    "execution_time_seconds": round(time.time() - start_time, 2)}
    }


def generate_build(task: dict, architecture_context: str, execution_id: str, rag_context: str = "", previous_feedback: str = "", solution_design: dict = None, gap_context: str = "") -> dict:
    task_id = task.get('task_id', 'UNKNOWN')
    task_name = task.get('name', task.get('title', 'Unnamed Task'))
    task_description = task.get('description', '')
    validation_criteria = task.get('validation_criteria', [])
    if isinstance(validation_criteria, list):
        validation_criteria = '\n'.join(f"- {c}" for c in validation_criteria)
    
    correction_context = ""
    if previous_feedback:
        correction_context = f"""
## CORRECTION NEEDED - PREVIOUS ATTEMPT FAILED
Elena (QA) found issues:
{previous_feedback}

FIX THESE ISSUES.
"""
    
    prompt = BUILD_PROMPT.format(task_id=task_id, task_name=task_name, task_description=task_description,
                                  architecture_context=architecture_context[:10000], validation_criteria=validation_criteria)
    
    # CRITICAL: Add Elena's feedback if this is a retry
    if correction_context:
        prompt += correction_context
        
    if rag_context:
        prompt += f"\n\n## LWC BEST PRACTICES (RAG)\n{rag_context[:1500]}\n"
    
    # BUG-044/046: Include Solution Design from Marcus
    if solution_design:
        sd_text = ""
        if solution_design.get("data_model"):
            sd_text += f"### Data Model\n{solution_design['data_model']}\n\n"
        if solution_design.get("lwc_components"):
            sd_text += f"### LWC Components\n{solution_design['lwc_components']}\n\n"
        if solution_design.get("ui_mockups"):
            sd_text += f"### UI Mockups\n{solution_design['ui_mockups']}\n\n"
        if sd_text:
            prompt += f"\n\n## SOLUTION DESIGN (Marcus)\n{sd_text[:5000]}\n"
    
    # BUG-045: Include GAP context
    if gap_context:
        prompt += f"\n\n## GAP ANALYSIS CONTEXT\n{gap_context[:3000]}\n"
    
    print(f"🔧 Zara BUILD mode - generating LWC for {task_id}...", file=sys.stderr)
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model="claude-sonnet-4-20250514", max_tokens=16000, temperature=0.2)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
        model_used = response.get('model', 'claude-sonnet-4-20250514')
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=16000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
        model_used = "gpt-4o-mini"
    
    files = _parse_code_files(content)
    execution_time = round(time.time() - start_time, 2)
    print(f"✅ Generated {len(files)} file(s) in {execution_time}s", file=sys.stderr)
    
    # Log LLM interaction for debugging
    if DB_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="zara",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=task_id,
                agent_mode="build",
                rag_context=rag_context if rag_context else None,
                previous_feedback=previous_feedback if previous_feedback else None,
                parsed_files={"files": list(files.keys()), "count": len(files)},
                tokens_input=None,  # Not available from response
                tokens_output=tokens_used,
                model=model_used,
                provider="anthropic" if "claude" in model_used else "openai",
                execution_time_seconds=execution_time,
                success=len(files) > 0,
                error_message=None if len(files) > 0 else "No files parsed from response"
            )
        except Exception as e:
            print(f"⚠️ Failed to log LLM interaction: {e}", file=sys.stderr)
    
    return {
        "agent_id": "zara", "agent_name": "Zara (LWC Developer)", "mode": "build",
        "task_id": task_id, "execution_id": str(execution_id),
        "deliverable_type": "lwc_code", "success": len(files) > 0,
        "content": {"raw_response": content, "files": files, "file_count": len(files)},
        "metadata": {"tokens_used": tokens_used, "model": model_used,
                    "execution_time_seconds": execution_time}
    }


def _parse_code_files(content: str) -> dict:
    import re
    files = {}
    patterns = [
        r'```(?:html)\s*\n<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)```',
        r'```(?:javascript|js)\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
        r'```(?:css)\s*\n/\*\s*FILE:\s*(\S+)\s*\*/\s*\n(.*?)```',
        r'```(?:xml)\s*\n<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)```',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        for filepath, code in matches:
            if filepath.strip() and code.strip():
                files[filepath.strip()] = code.strip()
    return files


def main():
    parser = argparse.ArgumentParser(description='Zara - LWC Developer Agent (Dual Mode)')
    parser.add_argument('--mode', required=True, choices=['spec', 'build'])
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--execution-id', default='0')
    parser.add_argument('--project-id', default='unknown')
    parser.add_argument('--use-rag', action='store_true', default=True)
    args = parser.parse_args()
    
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()
        
        rag_context = ""
        if args.use_rag and RAG_AVAILABLE:
            try:
                rag_context = get_salesforce_context("LWC best practices wire events accessibility", n_results=3, agent_type="lwc_developer")
            except: pass
        
        if args.mode == 'spec':
            result = generate_spec(input_content, args.project_id, args.execution_id, rag_context)
        else:
            try:
                input_data = json.loads(input_content)
            except:
                input_data = {"task": {"name": "Task", "description": input_content}}
            result = generate_build(
                input_data.get('task', input_data), 
                input_data.get('architecture_context', ''), 
                args.execution_id, 
                rag_context, 
                input_data.get('previous_feedback', ''),
                input_data.get('solution_design'),
                input_data.get('gap_context', '')
            )
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"success": True, "mode": args.mode}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
