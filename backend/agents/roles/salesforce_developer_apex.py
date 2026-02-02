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

# LLM Logging for debugging
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
    print(f"📝 [Diego] LLM Logger loaded", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ [Diego] LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass


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

## ⚠️ CRITICAL RULES - MUST FOLLOW

### RULE 1: NO EXTERNAL DEPENDENCIES
- DO NOT create or reference custom Exception classes (like SharingException)
- Use standard Salesforce exceptions: AuraHandledException, DMLException, etc.
- All classes you reference MUST be included in your output OR be standard Salesforce classes

### RULE 2: SELF-CONTAINED CODE
- Every class you use must either:
  a) Be a standard Salesforce class (System.*, Schema.*, Database.*, etc.)
  b) Be included in your output files
- If you need a helper class, CREATE IT in the output

### RULE 3: STANDARD EXCEPTIONS TO USE
Instead of custom exceptions, use:
- `AuraHandledException` - For LWC/Aura errors with user-friendly messages
- `System.QueryException` - For SOQL issues  
- `System.DmlException` - For DML issues
- `System.JSONException` - For JSON parsing issues
- `IllegalArgumentException` - For invalid parameters

### RULE 4: OUTPUT FORMAT
For EACH file, use this EXACT format:

```apex
// FILE: force-app/main/default/classes/ClassName.cls
public class ClassName {{
    // Implementation
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

### RULE 5: APEX BEST PRACTICES
1. **Bulkification**: Use List<SObject>, Map<Id, SObject>
2. **No SOQL/DML in loops**: Query before, DML after
3. **Security**: WITH SECURITY_ENFORCED or isAccessible checks
4. **Error Handling**: Try-catch with AuraHandledException for user messages
5. **No hardcoded IDs**: Use Custom Metadata or Custom Settings

### RULE 5b: SOQL CLAUSE ORDER (CRITICAL!)
⚠️ SOQL clauses MUST be in THIS EXACT ORDER:
1. SELECT
2. FROM  
3. WHERE (optional)
4. WITH SECURITY_ENFORCED (MUST be BEFORE GROUP BY!)
5. GROUP BY (optional)
6. HAVING (optional)
7. ORDER BY (optional)
8. LIMIT (optional)

❌ WRONG (will cause "Unexpected token WITH" error):
```
[SELECT AccountId, COUNT(Id) cnt FROM Case WHERE Status = 'Open' GROUP BY AccountId WITH SECURITY_ENFORCED]
```

✅ CORRECT:
```
[SELECT AccountId, COUNT(Id) cnt FROM Case WHERE Status = 'Open' WITH SECURITY_ENFORCED GROUP BY AccountId]
```

### RULE 6: TEST CLASS REQUIREMENTS
- Include @isTest annotation
- Use @testSetup for test data
- Aim for 85%+ code coverage
- Test positive, negative, and bulk scenarios

## EXAMPLE: CORRECT ERROR HANDLING
```apex
public class MyService {{
    public static void doSomething(List<Id> recordIds) {{
        if (recordIds == null || recordIds.isEmpty()) {{
            throw new AuraHandledException('No records provided');
        }}
        try {{
            // Business logic
        }} catch (DmlException e) {{
            throw new AuraHandledException('Save failed: ' + e.getMessage());
        }}
    }}
}}
```

## ⚠️ CRITICAL: COMPLETE CODE ONLY
- Generate COMPLETE, FULLY IMPLEMENTED code
- DO NOT truncate methods or leave "// TODO" comments
- Every method must have full implementation
- If code is too long, prioritize core functionality but COMPLETE it

## ⚠️ COMPLETENESS CHECKLIST - VERIFY BEFORE SUBMITTING
Before generating, ensure:
□ All classes compile independently (no missing dependencies)
□ All methods have complete implementations (not just signatures)
□ All referenced classes are either standard SF classes OR included in output
□ Use AuraHandledException for errors (not custom exception classes)
□ Test class covers all methods with @isTest annotation
□ All SOQL queries use WITH SECURITY_ENFORCED
□ Meta XML files included for each class

## GENERATE COMPLETE, DEPLOYABLE CODE NOW:
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
            max_tokens=16000,
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
            max_tokens=16000,
            temperature=0.3
        )
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
        model_used = "gpt-4o-mini"
    
    execution_time = time.time() - start_time
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="diego",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=None,
                agent_mode="spec",
                rag_context=rag_context if rag_context else None,
                tokens_output=tokens_used,
                model=model_used,
                provider="anthropic" if "claude" in model_used else "openai",
                execution_time_seconds=execution_time,
                success=True
            )
            print(f"📝 [Diego SPEC] LLM interaction logged", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Diego SPEC] Failed to log: {e}", file=sys.stderr)

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
# BUILD V2 - SANITIZE FUNCTIONS
# ============================================================================

def sanitize_apex_code(content: str) -> str:
    """
    Corrige les erreurs LLM courantes dans le code Apex.
    
    Fixes:
    - WITH SECURITY_ENFORCED mal placé (après GROUP BY au lieu d'avant)
    - Double point-virgule
    - Espaces excessifs
    """
    import re
    
    # Fix 1: WITH SECURITY_ENFORCED mal placé après GROUP BY
    # Pattern: GROUP BY ... WITH SECURITY_ENFORCED → WITH SECURITY_ENFORCED GROUP BY ...
    content = re.sub(
        r'(GROUP\s+BY\s+[^\]]+?)\s+(WITH\s+SECURITY_ENFORCED)',
        r'\2 \1', content, flags=re.IGNORECASE
    )
    
    # Fix 2: WITH SECURITY_ENFORCED mal placé après ORDER BY
    content = re.sub(
        r'(ORDER\s+BY\s+[^\]]+?)\s+(WITH\s+SECURITY_ENFORCED)',
        r'\2 \1', content, flags=re.IGNORECASE
    )
    
    # Fix 3: Double point-virgule
    content = re.sub(r';;', ';', content)
    
    # Fix 4: Espaces multiples → simple
    content = re.sub(r' {2,}', ' ', content)
    
    return content


def validate_apex_structure(content: str) -> dict:
    """
    Valide la structure du code Apex.
    
    Returns:
        Dict avec valid=True/False et issues[]
    """
    issues = []
    
    # Check balanced braces
    open_braces = content.count('{')
    close_braces = content.count('}')
    if open_braces != close_braces:
        issues.append({
            "severity": "critical",
            "issue": f"Accolades déséquilibrées: {open_braces} ouvrantes vs {close_braces} fermantes"
        })
    
    # Check starts with valid modifier
    content_stripped = content.strip()
    valid_starts = ['@isTest', '@IsTest', 'public', 'private', 'global', 'abstract', 'virtual', 'with sharing', 'without sharing']
    has_valid_start = any(content_stripped.startswith(s) for s in valid_starts)
    if not has_valid_start and content_stripped:
        issues.append({
            "severity": "warning",
            "issue": "Ne commence pas par un modificateur d'accès valide"
        })
    
    # Check for common custom exception references (should use standard ones)
    custom_exceptions = ['SharingException', 'ValidationException', 'BusinessException', 'CustomException']
    for exc in custom_exceptions:
        if exc in content and f'class {exc}' not in content:
            issues.append({
                "severity": "warning",
                "issue": f"Référence à {exc} sans définition - utiliser AuraHandledException"
            })
    
    return {
        "valid": len([i for i in issues if i["severity"] == "critical"]) == 0,
        "issues": issues
    }

# ============================================================================
# BUILD MODE FUNCTION
# ============================================================================
def generate_build(task: dict, architecture_context: str, execution_id: str, rag_context: str = "", previous_feedback: str = "", solution_design: dict = None, gap_context: str = "") -> dict:
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
    
    # BUG-044/046: Include Solution Design from Marcus
    if solution_design:
        sd_text = ""
        if solution_design.get("data_model"):
            sd_text += f"### Data Model\n{solution_design['data_model']}\n\n"
        if solution_design.get("apex_classes"):
            sd_text += f"### Apex Classes\n{solution_design['apex_classes']}\n\n"
        if solution_design.get("triggers"):
            sd_text += f"### Triggers\n{solution_design['triggers']}\n\n"
        if sd_text:
            prompt += f"\n\n## SOLUTION DESIGN (Marcus)\n{sd_text[:5000]}\n"
    
    # BUG-045: Include GAP context
    if gap_context:
        prompt += f"\n\n## GAP ANALYSIS CONTEXT\n{gap_context[:3000]}\n"
    
    print(f"🔧 Diego BUILD mode - generating code for {task_id}...", file=sys.stderr)
    
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=prompt,
            provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
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
            max_tokens=16000,
            temperature=0.2
        )
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
        model_used = "gpt-4o-mini"
    
    execution_time = time.time() - start_time
    
    # Parse generated files from response
    files = _parse_code_files(content)
    
    
    # BUILD V2: Sanitize Apex code
    for path, code in files.items():
        if path.endswith(".cls") or path.endswith(".trigger"):
            files[path] = sanitize_apex_code(code)
    print(f"✅ Generated {len(files)} file(s) in {execution_time:.1f}s", file=sys.stderr)
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="diego",
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
                error_message=None if len(files) > 0 else "No files parsed from response"
            )
            print(f"📝 [Diego BUILD] LLM interaction logged", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Diego BUILD] Failed to log: {e}", file=sys.stderr)

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
                previous_feedback=previous_feedback,
                solution_design=input_data.get('solution_design'),
                gap_context=input_data.get('gap_context', '')
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
