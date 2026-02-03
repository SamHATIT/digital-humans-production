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

## SECURITY RULES
- NEVER include actual credentials, API keys, or secrets in specifications
- Use placeholders like {{API_KEY}}, {{TO_BE_CONFIGURED}} for sensitive values
- Recommend Named Credentials for external integrations

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

### RULE 4: NEVER INCLUDE CREDENTIALS OR SECRETS (SECURITY)
NEVER generate any of the following in metadata files:
- Passwords, API keys, tokens, secrets
- OAuth consumer keys/secrets
- Session IDs or access tokens
- Hardcoded usernames with passwords
- Connection strings with credentials
- Named Credential passwords (use placeholders like {{CREDENTIAL}})
- Remote Site certificates or private keys

If integration requires credentials, use:
- Named Credentials (without actual secrets)
- Custom Settings marked as Protected
- Custom Metadata with isProtected=true
- Placeholder values: "{{API_KEY}}", "{{TO_BE_CONFIGURED}}"

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


def generate_build(task: dict, architecture_context: str, execution_id: str, rag_context: str = "", previous_feedback: str = "", solution_design: dict = None, gap_context: str = "") -> dict:
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
    
    # BUG-044/046: Include Solution Design from Marcus
    if solution_design:
        sd_text = ""
        if solution_design.get("data_model"):
            sd_text += f"### Data Model\n{solution_design['data_model']}\n\n"
        if solution_design.get("process_flows"):
            sd_text += f"### Process Flows\n{solution_design['process_flows']}\n\n"
        if solution_design.get("integrations"):
            sd_text += f"### Integrations\n{solution_design['integrations']}\n\n"
        if sd_text:
            prompt += f"\n\n## SOLUTION DESIGN (Marcus)\n{sd_text[:5000]}\n"
    
    # BUG-045: Include GAP context
    if gap_context:
        prompt += f"\n\n## GAP ANALYSIS CONTEXT\n{gap_context[:3000]}\n"
    
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
    """Parse XML files from LLM output - handles both formats:
    1. With backticks: ```xml <!-- FILE: path --> code ```
    2. Without backticks: <!-- FILE: path --> code
    """
    import re
    files = {}
    
    # Pattern 1: With ```xml blocks
    pattern1 = r'```(?:xml)?\s*\n<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)```'
    matches = re.findall(pattern1, content, re.DOTALL | re.IGNORECASE)
    for filepath, code in matches:
        if filepath.strip() and code.strip():
            files[filepath.strip()] = code.strip()
    
    # Pattern 2: Without backticks - match <!-- FILE: path --> followed by content until next FILE or end
    if not files:
        pattern2 = r'<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)(?=<!--\s*FILE:|$)'
        matches = re.findall(pattern2, content, re.DOTALL | re.IGNORECASE)
        for filepath, code in matches:
            if filepath.strip() and code.strip():
                # Remove trailing backticks or whitespace
                cleaned = re.sub(r'\s*```\s*$', '', code.strip())
                files[filepath.strip()] = cleaned
    
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
                rag_context = get_salesforce_context("Salesforce admin object relationships Master-Detail Lookup Rollup Summary field validation rules standard objects Case Account Contact", n_results=5, agent_type="admin")
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
        print(json.dumps({"success": result.get("success", True), "mode": args.mode}))
        
    except Exception as e:
        with open(args.output, 'w') as f:
            json.dump({"agent_id": "raj", "success": False, "error": str(e)}, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()


# ═══════════════════════════════════════════════════════════════
# BUILD V2 - JSON OUTPUT (Tooling API)
# ═══════════════════════════════════════════════════════════════

BUILD_V2_PHASE1_PROMPT = """# ⚙️ RAJ - DATA MODEL GENERATION (BUILD v2 - Phase 1)

You are Raj, generating a JSON plan for Salesforce data model creation via Tooling API.

## TASK
**Target Object:** {target_object}
**Description:** {task_description}

## EXISTING DATA MODEL (from previous batches)
{existing_context}

## SOLUTION DESIGN REFERENCE
{solution_design}

## OUTPUT FORMAT
Generate a JSON plan with operations to execute. Each operation will be processed by Tooling API.

```json
{
  "phase": 1,
  "phase_name": "data_model",
  "target_object": "{target_object}",
  "operations": [
    {
      "order": 1,
      "type": "create_object",
      "api_name": "ObjectName__c",
      "label": "Object Label",
      "plural_label": "Object Labels",
      "sharing_model": "ReadWrite",
      "name_field_type": "Text",
      "description": "Description"
    },
    {
      "order": 2,
      "type": "create_field",
      "object": "ObjectName__c",
      "api_name": "FieldName__c",
      "label": "Field Label",
      "field_type": "Text|Number|Date|DateTime|Checkbox|Picklist|Lookup|MasterDetail|Currency|Percent|Email|Phone|Url|LongTextArea|Formula|AutoNumber",
      "length": 255,
      "required": false,
      "description": "Field description"
    }
  ]
}
```

## FIELD TYPE SPECIFICATIONS

### Text
```json
{"field_type": "Text", "length": 255, "required": false}
```

### LongTextArea
```json
{"field_type": "LongTextArea", "length": 32768, "visible_lines": 5}
```

### Number/Currency/Percent
```json
{"field_type": "Number", "precision": 18, "scale": 2}
```

### Picklist
```json
{
  "field_type": "Picklist",
  "values": [
    {"api_name": "Value1", "label": "Value 1", "default": true},
    {"api_name": "Value2", "label": "Value 2", "default": false}
  ],
  "restricted": true
}
```

### Lookup
```json
{
  "field_type": "Lookup",
  "reference_to": "Account",
  "relationship_name": "Formations",
  "relationship_label": "Formations"
}
```

### MasterDetail
```json
{
  "field_type": "MasterDetail",
  "reference_to": "ParentObject__c",
  "relationship_name": "Children",
  "relationship_label": "Child Records"
}
```

### Formula
```json
{
  "field_type": "Formula",
  "formula": "IF(Status__c = 'Active', 1, 0)",
  "return_type": "Number|Text|Date|Checkbox|Currency|Percent",
  "precision": 18,
  "scale": 0
}
```

### Record Type
```json
{"type": "create_record_type", "object": "ObjectName__c", "api_name": "TypeName", "label": "Type Label"}
```

### List View
```json
{
  "type": "create_list_view",
  "object": "ObjectName__c",
  "api_name": "All_Records",
  "label": "All Records",
  "columns": ["Name", "Field1__c", "Field2__c"],
  "filter_scope": "Everything"
}
```

### Simple Validation Rule (Phase 1 only - no cross-object references)
```json
{
  "type": "create_validation_rule",
  "object": "ObjectName__c",
  "api_name": "Required_When_Active",
  "active": true,
  "formula": "AND(ISPICKVAL(Status__c, 'Active'), ISBLANK(Field__c))",
  "error_message": "Field is required when status is Active",
  "error_field": "Field__c"
}
```

## RULES
1. Generate ONLY the object specified in target_object
2. Do NOT recreate objects/fields from existing_context
3. Use EXACT API naming conventions (PascalCase__c for objects, PascalCase__c for fields)
4. Order operations correctly: object first, then fields, then record types, then validation rules
5. Simple validation rules only - no VLOOKUP or cross-object references

## GENERATE THE JSON PLAN NOW:
"""

BUILD_V2_PHASE4_PROMPT = """# ⚙️ RAJ - AUTOMATION GENERATION (BUILD v2 - Phase 4)

You are Raj, generating automation configurations.

## TASK
**Automation Type:** {automation_type}
**Description:** {task_description}

## AVAILABLE DATA MODEL
{data_model_context}

## AVAILABLE APEX CLASSES
{apex_context}

## OUTPUT FORMAT
For Validation Rules (complex), generate JSON:
```json
{
  "phase": 4,
  "phase_name": "automation",
  "operations": [
    {
      "order": 1,
      "type": "complex_validation_rule",
      "object": "ObjectName__c",
      "api_name": "CrossObject_Validation",
      "active": true,
      "formula": "RelatedObject__r.Status__c != 'Active'",
      "error_message": "Related object must be active",
      "error_field": "RelatedObject__c"
    }
  ]
}
```

For Flows, generate XML file with marker:
```
// FILE: force-app/main/default/flows/FlowName.flow-meta.xml
<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
...
</Flow>
```

## FLOW TYPES
- Record-Triggered Flow: triggers on record create/update/delete
- Screen Flow: user-facing wizard
- Auto-Launched Flow: called from Apex or Process Builder
- Scheduled Flow: runs on schedule

## GENERATE NOW:
"""

BUILD_V2_PHASE5_PROMPT = """# ⚙️ RAJ - SECURITY CONFIGURATION (BUILD v2 - Phase 5)

You are Raj, generating security configurations.

## TASK
**Security Type:** {security_type}
**Description:** {task_description}

## AVAILABLE DATA MODEL
{data_model_context}

## AVAILABLE COMPONENTS
{components_context}

## OUTPUT FORMAT

### Permission Set (JSON)
```json
{
  "phase": 5,
  "phase_name": "security",
  "operations": [
    {
      "order": 1,
      "type": "create_permission_set",
      "api_name": "Formation_Manager",
      "label": "Formation Manager",
      "description": "Full access to Formation management",
      "object_permissions": [
        {
          "object": "Formation__c",
          "allow_create": true,
          "allow_read": true,
          "allow_edit": true,
          "allow_delete": false,
          "view_all": true,
          "modify_all": false
        }
      ],
      "field_permissions": [
        {"field": "Formation__c.Titre__c", "readable": true, "editable": true},
        {"field": "Formation__c.Statut__c", "readable": true, "editable": true}
      ]
    }
  ]
}
```

### Page Layout (XML - use SFDX deploy)
```
// FILE: force-app/main/default/layouts/Formation__c-Formation Layout.layout-meta.xml
<?xml version="1.0" encoding="UTF-8"?>
<Layout xmlns="http://soap.sforce.com/2006/04/metadata">
...
</Layout>
```

### Profile modifications (XML - use SFDX deploy)
Profiles should be retrieved first, modified, then deployed.

## RULES
1. Permission Sets should cover all objects/fields from the data model
2. Include both object-level and field-level permissions
3. Follow least-privilege principle

## GENERATE NOW:
"""


def generate_build_v2(
    phase: int,
    target: str,
    task_description: str,
    context: dict,
    execution_id: str,
    rag_context: str = ""
) -> dict:
    """
    Generate BUILD v2 output (JSON plan for Tooling API).
    
    Args:
        phase: 1 (data_model), 4 (automation), or 5 (security)
        target: Target object/component name
        task_description: What to generate
        context: Dict with existing_context, data_model_context, apex_context, etc.
        execution_id: Execution ID for logging
        rag_context: RAG context if available
    
    Returns:
        Dict with JSON plan or files
    """
    import time
    
    if phase == 1:
        prompt = BUILD_V2_PHASE1_PROMPT.replace(
            "{target_object}", target
        ).replace(
            "{task_description}", task_description
        ).replace(
            "{existing_context}", context.get("existing_context", "None")
        ).replace(
            "{solution_design}", context.get("solution_design", "Not provided")
        )
    elif phase == 4:
        prompt = BUILD_V2_PHASE4_PROMPT.replace(
            "{automation_type}", target
        ).replace(
            "{task_description}", task_description
        ).replace(
            "{data_model_context}", context.get("data_model_context", "Not provided")
        ).replace(
            "{apex_context}", context.get("apex_context", "Not provided")
        )
    elif phase == 5:
        prompt = BUILD_V2_PHASE5_PROMPT.replace(
            "{security_type}", target
        ).replace(
            "{task_description}", task_description
        ).replace(
            "{data_model_context}", context.get("data_model_context", "Not provided")
        ).replace(
            "{components_context}", context.get("components_context", "Not provided")
        )
    else:
        return {"success": False, "error": f"Invalid phase for Raj: {phase}"}
    
    if rag_context:
        prompt += f"\n\n## SALESFORCE BEST PRACTICES\n{rag_context[:2000]}\n"
    
    print(f"⚙️ Raj BUILD v2 Phase {phase} - {target}...", file=sys.stderr)
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=prompt,
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            temperature=0.2
        )
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000
        )
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
    
    execution_time = round(time.time() - start_time, 2)
    
    # Parse JSON from response
    result = _parse_build_v2_response(content, phase)
    
    # Log interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="raj",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=target,
                agent_mode=f"build_v2_phase{phase}",
                tokens_output=tokens_used,
                model="claude-sonnet-4-20250514",
                provider="anthropic",
                execution_time_seconds=execution_time,
                success=result.get("success", False)
            )
        except Exception as e:
            print(f"⚠️ [Raj BUILD v2] Failed to log: {e}", file=sys.stderr)
    
    result["agent_id"] = "raj"
    result["agent_name"] = "Raj (Salesforce Admin)"
    result["mode"] = f"build_v2_phase{phase}"
    result["execution_id"] = str(execution_id)
    result["target"] = target
    result["metadata"] = {
        "tokens_used": tokens_used,
        "execution_time_seconds": execution_time
    }
    
    return result


def _parse_build_v2_response(content: str, phase: int) -> dict:
    """Parse BUILD v2 response - extract JSON and/or XML files."""
    import re
    
    result = {
        "success": False,
        "operations": [],
        "files": {}
    }
    
    # Try to extract JSON block
    json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
    if json_match:
        try:
            json_data = json.loads(json_match.group(1))
            result["operations"] = json_data.get("operations", [])
            result["phase"] = json_data.get("phase", phase)
            result["phase_name"] = json_data.get("phase_name", "")
            result["target_object"] = json_data.get("target_object", "")
            result["success"] = len(result["operations"]) > 0
        except json.JSONDecodeError as e:
            print(f"⚠️ [Raj] JSON parse error: {e}", file=sys.stderr)
    
    # Also extract any XML files (for flows, layouts)
    xml_files = _parse_xml_files(content)
    if xml_files:
        result["files"] = xml_files
        result["success"] = True
    
    # If no JSON but we have the raw content, try to parse it directly
    if not result["operations"] and not result["files"]:
        try:
            # Maybe the whole response is JSON
            json_data = json.loads(content.strip())
            result["operations"] = json_data.get("operations", [])
            result["success"] = len(result["operations"]) > 0
        except:
            pass
    
    return result
