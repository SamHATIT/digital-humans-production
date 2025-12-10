#!/usr/bin/env python3
"""
Salesforce Data Migration Agent - Aisha
Dual Mode: spec (for SDS) | build (for real migration artifacts)
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
    print(f"📝 [Aisha] LLM Logger loaded", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ [Aisha] LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass


SPEC_PROMPT = """# 📊 DATA MIGRATION - SPECIFICATION MODE

You are Aisha, an expert Salesforce Data Migration Specialist.
Generate comprehensive data migration SPECIFICATIONS for the SDS document.

## INPUT REQUIREMENTS
{requirements}

## DELIVERABLES
1. **Data Assessment** - Source systems, volumes, quality
2. **Migration Strategy** - Approach, tools, phases
3. **Data Mapping** - Source to target field mappings
4. **Transformation Rules** - Data cleansing, enrichment
5. **Validation Plan** - Pre/post migration checks
6. **Rollback Strategy** - Recovery procedures

## FORMAT
Use clear markdown with detailed specifications.
"""


BUILD_PROMPT = """# 📊 DATA MIGRATION ARTIFACTS - BUILD MODE

You are Aisha, generating REAL data migration artifacts.

## TASK TO IMPLEMENT
**Task ID:** {task_id}
**Task Name:** {task_name}
**Description:** {task_description}

## ARCHITECTURE CONTEXT
{architecture_context}

## CRITICAL OUTPUT FORMAT
Generate complete migration artifacts. For EACH file, use this format:

For CSV Templates:
```csv
// FILE: data/migration/ObjectName_template.csv
Id,Field1__c,Field2__c,Relationship__r.ExternalId__c
,Value1,Value2,REF-001
```

For Data Loader Process Conf:
```xml
<!-- FILE: data/config/ObjectName-insert.process-conf.xml -->
<!DOCTYPE process>
<process>
    <operation>insert</operation>
    <mappingFile>ObjectName_mapping.sdl</mappingFile>
    <csvFile>ObjectName_data.csv</csvFile>
</process>
```

For Mapping Files:
```
// FILE: data/config/ObjectName_mapping.sdl
# Salesforce Data Loader Mapping
Field1__c=Source_Field1
Field2__c=Source_Field2
```

For Validation Queries:
```sql
// FILE: data/validation/ObjectName_validation.sql
-- Pre-migration count
SELECT COUNT(*) FROM SourceTable;

-- Post-migration validation
SELECT COUNT(*) FROM ObjectName__c WHERE Migration_Batch__c = 'BATCH001';
```

For Apex Data Scripts (if needed):
```apex
// FILE: scripts/apex/DataMigration_ObjectName.apex
// Anonymous Apex for complex transformations
List<ObjectName__c> records = new List<ObjectName__c>();
// ... logic
insert records;
```

## MIGRATION BEST PRACTICES
1. Include External ID fields for upserts
2. Handle relationships via External IDs
3. Include validation queries
4. Batch large volumes (10k records max)
5. Document transformation logic

## GENERATE THE ARTIFACTS NOW:
"""


def generate_spec(requirements: str, project_name: str, execution_id: str, rag_context: str = "") -> dict:
    prompt = SPEC_PROMPT.format(requirements=requirements[:25000])
    if correction_context:
        prompt += correction_context
    
    if rag_context:
        prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"
    
    print(f"📊 Aisha SPEC mode...", file=sys.stderr)
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
    

    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="aisha",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=None,
                agent_mode="spec",
                rag_context=rag_context if rag_context else None,
                tokens_output=tokens_used,
                model="claude-sonnet-4-20250514" if LLM_SERVICE_AVAILABLE else "gpt-4o-mini",
                provider="anthropic" if LLM_SERVICE_AVAILABLE else "openai",
                execution_time_seconds=round(time.time() - start_time, 2),
                success=True
            )
            print(f"📝 [Aisha SPEC] LLM interaction logged", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Aisha SPEC] Failed to log: {e}", file=sys.stderr)

    return {
        "agent_id": "aisha", "agent_name": "Aisha (Data Migration)", "mode": "spec",
        "execution_id": str(execution_id), "deliverable_type": "migration_specification",
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
        prompt += f"\n\n## MIGRATION BEST PRACTICES (RAG)\n{rag_context[:1500]}\n"
    
    print(f"📊 Aisha BUILD mode - generating artifacts for {task_id}...", file=sys.stderr)
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
    
    files = _parse_files(content)
    print(f"✅ Generated {len(files)} file(s)", file=sys.stderr)
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="aisha",
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
            print(f"📝 [Aisha BUILD] LLM interaction logged", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Aisha BUILD] Failed to log: {e}", file=sys.stderr)

    return {
        "agent_id": "aisha", "agent_name": "Aisha (Data Migration)", "mode": "build",
        "task_id": task_id, "execution_id": str(execution_id),
        "deliverable_type": "migration_artifacts", "success": len(files) > 0,
        "content": {"raw_response": content, "files": files, "file_count": len(files)},
        "metadata": {"tokens_used": tokens_used, "execution_time_seconds": round(time.time() - start_time, 2)}
    }


def _parse_files(content: str) -> dict:
    import re
    files = {}
    patterns = [
        r'```(?:csv)\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
        r'```(?:xml)\s*\n<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)```',
        r'```(?:sql)\s*\n--\s*FILE:\s*(\S+)\s*\n(.*?)```',
        r'```(?:apex)\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
        r'```\s*\n//\s*FILE:\s*(\S+)\s*\n(.*?)```',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        for filepath, code in matches:
            if filepath.strip() and code.strip():
                files[filepath.strip()] = code.strip()
    return files


def main():
    parser = argparse.ArgumentParser(description='Aisha - Data Migration (Dual Mode)')
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
                rag_context = get_salesforce_context("Salesforce data migration data loader ETL", n_results=3, agent_type="data_migration")
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
            json.dump({"agent_id": "aisha", "success": False, "error": str(e)}, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
