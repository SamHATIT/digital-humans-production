#!/usr/bin/env python3
"""
Salesforce Admin Agent - Raj
Dual Mode: spec (for SDS) | build (for real metadata/config)
"""
import os, sys, argparse, json, time
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


SPEC_PROMPT = """# ⚙️ SALESFORCE ADMIN - SPECIFICATION MODE

You are Raj, an expert Salesforce Administrator.
Generate comprehensive admin configuration SPECIFICATIONS for the SDS document.

## INPUT REQUIREMENTS
{requirements}

## DELIVERABLES
1. **Object Model** - Custom objects, fields, relationships
2. **Security Model** - Profiles, permission sets, sharing rules
3. **Automation** - Flows, Process Builder, Workflow Rules
4. **Validation Rules** - Data quality enforcement
5. **Page Layouts** - Record page configurations
6. **Reports & Dashboards** - Analytics requirements

## FORMAT
Use clear markdown with detailed specifications for each component.
"""


BUILD_PROMPT = """# ⚙️ SALESFORCE METADATA GENERATION - BUILD MODE

You are Raj, generating REAL, DEPLOYABLE Salesforce metadata XML.

## TASK TO IMPLEMENT
**Task ID:** {task_id}
**Task Name:** {task_name}
**Description:** {task_description}

## ARCHITECTURE CONTEXT
{architecture_context}

## CRITICAL OUTPUT FORMAT
Generate complete Salesforce metadata XML. For EACH file, use this EXACT format:

For Custom Fields:
```xml
<!-- FILE: force-app/main/default/objects/ObjectName__c/fields/FieldName__c.field-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>FieldName__c</fullName>
    <label>Field Label</label>
    <type>Text</type>
    <length>255</length>
</CustomField>
```

For Permission Sets:
```xml
<!-- FILE: force-app/main/default/permissionsets/PermSetName.permissionset-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<PermissionSet xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>Permission Set Name</label>
    <!-- permissions -->
</PermissionSet>
```

For Flows:
```xml
<!-- FILE: force-app/main/default/flows/FlowName.flow-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <!-- flow definition -->
</Flow>
```

For Validation Rules:
```xml
<!-- FILE: force-app/main/default/objects/ObjectName__c/validationRules/RuleName.validationRule-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<ValidationRule xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>RuleName</fullName>
    <active>true</active>
    <errorConditionFormula>/* formula */</errorConditionFormula>
    <errorMessage>Error message</errorMessage>
</ValidationRule>
```

## ADMIN BEST PRACTICES
1. Use API names with __c suffix for custom
2. Include all required metadata elements
3. Use proper data types and lengths
4. Follow naming conventions (PascalCase)
5. Add descriptions for documentation

## GENERATE THE METADATA NOW:
"""


def generate_spec(requirements: str, project_name: str, execution_id: str, rag_context: str = "") -> dict:
    prompt = SPEC_PROMPT.format(requirements=requirements[:25000])
    if correction_context:
        prompt += correction_context
    
    if rag_context:
        prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"
    
    print(f"⚙️ Raj SPEC mode...", file=sys.stderr)
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model="claude-sonnet-4-20250514", max_tokens=8000, temperature=0.3)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=8000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
    
    return {
        "agent_id": "raj", "agent_name": "Raj (Salesforce Admin)", "mode": "spec",
        "execution_id": str(execution_id), "deliverable_type": "admin_specification",
        "content": {"raw_markdown": content},
        "metadata": {"tokens_used": tokens_used, "execution_time_seconds": round(time.time() - start_time, 2)}
    }


def generate_build(task: dict, architecture_context: str, execution_id: str, rag_context: str = "", previous_feedback: str = "") -> dict:
    task_id = task.get('task_id', 'UNKNOWN')
    task_name = task.get('name', task.get('title', 'Unnamed Task'))
    task_description = task.get('description', '')
    
    correction_context = ""
    if previous_feedback:
        correction_context = f"""
## CORRECTION NEEDED - PREVIOUS ATTEMPT FAILED
Elena (QA) found issues:
{previous_feedback}

FIX THESE ISSUES.
"""
    
    prompt = BUILD_PROMPT.format(task_id=task_id, task_name=task_name, 
                                  task_description=task_description,
                                  architecture_context=architecture_context[:10000])
    if rag_context:
        prompt += f"\n\n## ADMIN BEST PRACTICES (RAG)\n{rag_context[:1500]}\n"
    
    print(f"⚙️ Raj BUILD mode - generating metadata for {task_id}...", file=sys.stderr)
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model="claude-sonnet-4-20250514", max_tokens=8000, temperature=0.2)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=8000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
    
    files = _parse_xml_files(content)
    print(f"✅ Generated {len(files)} file(s)", file=sys.stderr)
    
    return {
        "agent_id": "raj", "agent_name": "Raj (Salesforce Admin)", "mode": "build",
        "task_id": task_id, "execution_id": str(execution_id),
        "deliverable_type": "admin_metadata", "success": len(files) > 0,
        "content": {"raw_response": content, "files": files, "file_count": len(files)},
        "metadata": {"tokens_used": tokens_used, "execution_time_seconds": round(time.time() - start_time, 2)}
    }


def _parse_xml_files(content: str) -> dict:
    import re
    files = {}
    pattern = r'```(?:xml)\s*\n<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)```'
    matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
    for filepath, code in matches:
        if filepath.strip() and code.strip():
            files[filepath.strip()] = code.strip()
    return files


def main():
    parser = argparse.ArgumentParser(description='Raj - Salesforce Admin (Dual Mode)')
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
                rag_context = get_salesforce_context("Salesforce admin metadata flows validation rules", n_results=3, agent_type="admin")
            except: pass
        
        if args.mode == 'spec':
            result = generate_spec(input_content, args.project_id, args.execution_id, rag_context)
        else:
            try:
                input_data = json.loads(input_content)
            except:
                input_data = {"task": {"name": "Task", "description": input_content}}
            result = generate_build(input_data.get('task', input_data), 
                                   input_data.get('architecture_context', ''), 
                                   args.execution_id, rag_context)
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"success": result.get("success", True), "mode": args.mode}))
        
    except Exception as e:
        with open(args.output, 'w') as f:
            json.dump({"agent_id": "raj", "success": False, "error": str(e)}, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
