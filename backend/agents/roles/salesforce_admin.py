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

# LLM Logging for debugging
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
    print(f"📝 [Raj] LLM Logger loaded", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ [Raj] LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass


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

You are Raj, generating REAL, DEPLOYABLE Salesforce metadata XML for API version 59.0.

## TASK TO IMPLEMENT
**Task ID:** {task_id}
**Task Name:** {task_name}
**Description:** {task_description}

## ARCHITECTURE CONTEXT
{architecture_context}

## ⚠️ CRITICAL RULES - READ CAREFULLY

### RULE 1: SEPARATE FILES FOR OBJECTS AND FIELDS
- CustomObject file contains ONLY object-level properties (label, pluralLabel, nameField, sharingModel)
- CustomField files are SEPARATE - one file per field in the fields/ subfolder
- NEVER put <fields> or <CustomField> elements inside a CustomObject file

### RULE 2: FORBIDDEN PROPERTIES (API 59.0)
These properties will cause deployment failure - NEVER use them:
- enableChangeDataCapture
- enableEnhancedLookup  
- enableHistory
- enableBulkApi
- enableReports
- enableSearch
- enableFeeds
- enableStreamingApi

### RULE 3: FILE STRUCTURE
```
force-app/main/default/objects/ObjectName__c/
├── ObjectName__c.object-meta.xml          (object definition ONLY)
└── fields/
    ├── Field1__c.field-meta.xml           (one file per field)
    └── Field2__c.field-meta.xml
```

## EXACT TEMPLATES TO USE

### Custom Object (ONLY these properties allowed)
```xml
<!-- FILE: force-app/main/default/objects/{{ObjectName}}__c/{{ObjectName}}__c.object-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <deploymentStatus>Deployed</deploymentStatus>
    <label>{{Object Label}}</label>
    <pluralLabel>{{Object Labels}}</pluralLabel>
    <nameField>
        <label>{{Object}} Name</label>
        <type>Text</type>
    </nameField>
    <sharingModel>ReadWrite</sharingModel>
</CustomObject>
```

### Text Field
```xml
<!-- FILE: force-app/main/default/objects/{{ObjectName}}__c/fields/{{FieldName}}__c.field-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{{FieldName}}__c</fullName>
    <label>{{Field Label}}</label>
    <type>Text</type>
    <length>255</length>
    <required>false</required>
</CustomField>
```

### Lookup Field
```xml
<!-- FILE: force-app/main/default/objects/{{ObjectName}}__c/fields/{{RelatedObject}}__c.field-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{{RelatedObject}}__c</fullName>
    <label>{{Related Object}}</label>
    <type>Lookup</type>
    <referenceTo>{{RelatedObject}}__c</referenceTo>
    <relationshipLabel>{{Labels}}</relationshipLabel>
    <relationshipName>{{Name}}</relationshipName>
</CustomField>
```

### Picklist Field
```xml
<!-- FILE: force-app/main/default/objects/{{ObjectName}}__c/fields/{{FieldName}}__c.field-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{{FieldName}}__c</fullName>
    <label>{{Field Label}}</label>
    <type>Picklist</type>
    <valueSet>
        <restricted>true</restricted>
        <valueSetDefinition>
            <sorted>false</sorted>
            <value><fullName>Value1</fullName><default>true</default><label>Value 1</label></value>
            <value><fullName>Value2</fullName><default>false</default><label>Value 2</label></value>
        </valueSetDefinition>
    </valueSet>
</CustomField>
```

### URL Field
```xml
<!-- FILE: force-app/main/default/objects/{{ObjectName}}__c/fields/{{FieldName}}__c.field-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{{FieldName}}__c</fullName>
    <label>{{Field Label}}</label>
    <type>Url</type>
</CustomField>
```

### LongTextArea Field
```xml
<!-- FILE: force-app/main/default/objects/{{ObjectName}}__c/fields/{{FieldName}}__c.field-meta.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{{FieldName}}__c</fullName>
    <label>{{Field Label}}</label>
    <type>LongTextArea</type>
    <length>32768</length>
    <visibleLines>5</visibleLines>
</CustomField>
```

## OUTPUT FORMAT
For each file:
1. <!-- FILE: path/to/file.xml --> comment
2. Complete XML content
3. Blank line before next file

## ⚠️ COMPLETENESS CHECKLIST - VERIFY BEFORE SUBMITTING
Before generating, ensure:
□ Each CustomObject has ONLY: deploymentStatus, label, pluralLabel, nameField, sharingModel
□ Each CustomField is in a SEPARATE file under fields/ folder
□ NO forbidden properties (enableChangeDataCapture, enableHistory, etc.)
□ All XML is well-formed with proper closing tags
□ All required fields for the type are present
□ File paths follow exact Salesforce structure

## GENERATE COMPLETE, VALID METADATA NOW:
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
                                         model="claude-sonnet-4-20250514", max_tokens=16000, temperature=0.3)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=16000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
    

    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="raj",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=None,
                agent_mode="spec",
                rag_context=rag_context if rag_context else None,
                tokens_output=tokens_used,
                model=model_used if 'model_used' in dir() else "unknown",
                provider="anthropic" if LLM_SERVICE_AVAILABLE else "openai",
                execution_time_seconds=round(time.time() - start_time, 2),
                success=True
            )
            print(f"📝 [Raj SPEC] LLM interaction logged", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Raj SPEC] Failed to log: {e}", file=sys.stderr)

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
    
    # CRITICAL: Add Elena's feedback if this is a retry
    if correction_context:
        prompt += correction_context
        
    if rag_context:
        prompt += f"\n\n## ADMIN BEST PRACTICES (RAG)\n{rag_context[:1500]}\n"
    
    print(f"⚙️ Raj BUILD mode - generating metadata for {task_id}...", file=sys.stderr)
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model="claude-sonnet-4-20250514", max_tokens=16000, temperature=0.2)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
        model_used = "claude-sonnet-4-20250514"
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=16000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
        model_used = "gpt-4o-mini"
    
    execution_time = round(time.time() - start_time, 2)
    files = _parse_xml_files(content)
    print(f"✅ Generated {len(files)} file(s)", file=sys.stderr)
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="raj",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=task_id,
                agent_mode="build",
                rag_context=rag_context if rag_context else None,
                previous_feedback=previous_feedback if previous_feedback else None,
                parsed_files={"files": list(files.keys()), "count": len(files)},
                tokens_output=tokens_used,
                model=model_used,
                provider="anthropic" if "claude" in model_used else "openai",
                execution_time_seconds=execution_time,
                success=len(files) > 0,
                error_message=None if len(files) > 0 else "No files parsed"
            )
            print(f"📝 [Raj BUILD] LLM interaction logged", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Raj BUILD] Failed to log: {e}", file=sys.stderr)

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
