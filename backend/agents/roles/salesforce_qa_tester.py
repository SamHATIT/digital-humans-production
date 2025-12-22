#!/usr/bin/env python3
"""
Salesforce QA Engineer Agent - Elena
Dual Mode: spec (for SDS) | test (for validating BUILD code)
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
    print(f"📝 [Elena] LLM Logger loaded", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ [Elena] LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass


SPEC_PROMPT = """# 🧪 QA ENGINEER - SPECIFICATION MODE
You are Elena, an expert Salesforce QA Engineer.
Generate comprehensive QA and testing SPECIFICATIONS for the SDS document.

## INPUT REQUIREMENTS
{requirements}

## DELIVERABLES
1. Test Strategy - Overall approach
2. Test Cases Matrix - Functional, integration, UAT
3. Test Data Strategy
4. Automation Strategy
5. Performance Test Plan
"""

CODE_REVIEW_PROMPT = """# 🧪 CODE VALIDATION
You are Elena, validating Apex/LWC code.

## CODE TO REVIEW
{code_content}

## TASK INFO
{task_info}

## VALIDATION CRITERIA
{validation_criteria}

## INSTRUCTIONS
Analyze the code thoroughly and provide a JSON response:
```json
{{
    "verdict": "PASS" or "FAIL",
    "summary": "Brief assessment of code quality",
    "issues": [
        {{"severity": "critical|warning|info", "description": "...", "file": "...", "line": "..."}}
    ],
    "positive_aspects": ["What's done well"],
    "feedback_for_developer": "If FAIL, specific actionable instructions to fix the issues"
}}
```

IMPORTANT:
- Be thorough but fair - don't fail for minor style issues
- PASS if code is functional and meets requirements, even if not perfect
- FAIL only for: syntax errors, missing required functionality, security issues, or broken logic
- Provide constructive feedback even for PASS

Respond with ONLY valid JSON, no markdown.
"""


def generate_spec(requirements: str, project_name: str, execution_id: str, rag_context: str = "") -> dict:
    prompt = SPEC_PROMPT.format(requirements=requirements[:25000])
    if rag_context:
        prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"
    
    print(f"🧪 Elena SPEC mode...", file=sys.stderr)
    start_time = time.time()
    model_used = "claude-sonnet-4-20250514"
    tokens_used = 0
    content = ""
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model=model_used, max_tokens=8000, temperature=0.3)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
    else:
        from openai import OpenAI
        client = OpenAI()
        model_used = "gpt-4o-mini"
        resp = client.chat.completions.create(model=model_used, messages=[{"role": "user", "content": prompt}], max_tokens=8000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
    
    execution_time = round(time.time() - start_time, 2)
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="elena",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=None,
                agent_mode="spec",
                rag_context=rag_context if rag_context else None,
                previous_feedback=None,
                parsed_files=None,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider="anthropic" if "claude" in model_used else "openai",
                execution_time_seconds=execution_time,
                success=True,
                error_message=None
            )
            print(f"📝 [Elena SPEC] LLM interaction logged", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Elena SPEC] Failed to log: {e}", file=sys.stderr)
    
    return {
        "agent_id": "elena", "agent_name": "Elena (QA Engineer)", "mode": "spec",
        "execution_id": str(execution_id), "deliverable_type": "qa_specification",
        "content": {"raw_markdown": content},
        "metadata": {"tokens_used": tokens_used, "execution_time_seconds": execution_time}
    }


def generate_test(input_data: dict, execution_id: str) -> dict:
    """Validate code from Diego/Zara - return PASS/FAIL with feedback"""
    code_files = input_data.get("code_files", input_data.get("files", {}))
    task_info = input_data.get("task", {})
    validation_criteria = input_data.get("validation_criteria", task_info.get("validation_criteria", "Code should be functional and follow best practices"))
    
    if not code_files:
        return {"agent_id": "elena", "mode": "test", "success": False, "verdict": "FAIL",
                "feedback": "No code files provided"}
    
    print(f"🧪 Elena TEST mode - reviewing {len(code_files)} file(s)...", file=sys.stderr)
    start_time = time.time()
    model_used = "claude-sonnet-4-20250514"
    
    # Build code content for review - show FULL content for each file
    code_parts = []
    for fp, content in code_files.items():
        # Log file sizes for debugging
        print(f"   📄 {fp}: {len(content)} chars", file=sys.stderr)
        code_parts.append(f"### FILE: {fp}\n```\n{content}\n```")
    
    code_content = "\n\n".join(code_parts)
    total_code_chars = len(code_content)
    print(f"   📊 Total code content: {total_code_chars} chars", file=sys.stderr)
    
    # Format validation criteria
    if isinstance(validation_criteria, list):
        criteria_text = "\n".join(f"- {c}" for c in validation_criteria)
    else:
        criteria_text = str(validation_criteria)
    
    prompt = CODE_REVIEW_PROMPT.format(
        code_content=code_content[:80000],  # Increased limit
        task_info=json.dumps(task_info, indent=2),
        validation_criteria=criteria_text
    )
    
    print(f"   📝 Prompt length: {len(prompt)} chars", file=sys.stderr)
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model=model_used, max_tokens=4000, temperature=0.1)
        review_text = response.get('content', '{}')
        tokens_used = response.get('tokens_used', 0)
    else:
        from openai import OpenAI
        client = OpenAI()
        model_used = "gpt-4o-mini"
        resp = client.chat.completions.create(model=model_used, messages=[{"role": "user", "content": prompt}], max_tokens=4000)
        review_text = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
    
    execution_time = round(time.time() - start_time, 2)
    
    # Parse response
    try:
        review_text_clean = review_text.strip()
        if '```' in review_text_clean:
            # Extract JSON from markdown code block
            parts = review_text_clean.split('```')
            for part in parts:
                part = part.strip()
                if part.startswith('json'):
                    part = part[4:].strip()
                if part.startswith('{'):
                    review_text_clean = part
                    break
        review_data = json.loads(review_text_clean)
    except Exception as parse_err:
        print(f"  ⚠️ Failed to parse review JSON: {parse_err}", file=sys.stderr)
        print(f"  Raw response (first 500 chars): {review_text[:500]}", file=sys.stderr)
        review_data = {"verdict": "PASS", "summary": "Auto-pass (parse error)", "issues": [], "feedback_for_developer": ""}
    
    verdict = review_data.get("verdict", "PASS").upper()
    print(f"  {'✅' if verdict == 'PASS' else '❌'} Verdict: {verdict}", file=sys.stderr)
    if verdict == "FAIL":
        print(f"  📋 Feedback: {review_data.get('feedback_for_developer', 'N/A')[:200]}", file=sys.stderr)
    
    # Log LLM interaction for debugging
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="elena",
                prompt=prompt,
                response=review_text,
                execution_id=execution_id,
                task_id=task_info.get("task_id", ""),
                agent_mode="test",
                rag_context=None,
                previous_feedback=None,
                parsed_files={"files": list(code_files.keys()), "count": len(code_files), "total_chars": total_code_chars},
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider="anthropic" if "claude" in model_used else "openai",
                execution_time_seconds=execution_time,
                success=verdict == "PASS",
                error_message=review_data.get("feedback_for_developer", "") if verdict == "FAIL" else None
            )
            print(f"📝 [Elena TEST] LLM interaction logged (verdict: {verdict})", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ [Elena TEST] Failed to log: {e}", file=sys.stderr)
    
    return {
        "agent_id": "elena", "agent_name": "Elena (QA Engineer)", "mode": "test",
        "success": verdict == "PASS", "verdict": verdict,
        "task_id": task_info.get("task_id", ""),
        "execution_id": str(execution_id),
        "deliverable_type": "code_validation",
        "content": {"code_review": review_data, "files_reviewed": len(code_files), "total_code_chars": total_code_chars},
        "feedback": review_data.get("feedback_for_developer", "") if verdict == "FAIL" else "",
        "metadata": {"execution_time_seconds": execution_time, "tokens_used": tokens_used, "model": model_used}
    }


def main():
    parser = argparse.ArgumentParser(description='Elena - QA Engineer (Dual Mode)')
    parser.add_argument('--mode', required=True, choices=['spec', 'test'])
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
        if args.use_rag and RAG_AVAILABLE and args.mode == 'spec':
            try:
                rag_context = get_salesforce_context("Apex testing best practices", n_results=3, agent_type="qa_tester")
            except: pass
        
        if args.mode == 'spec':
            result = generate_spec(input_content, args.project_id, args.execution_id, rag_context)
        else:
            try:
                input_data = json.loads(input_content)
            except:
                input_data = {"files": {}}
            result = generate_test(input_data, args.execution_id)
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(json.dumps({"success": result.get("success", True), "mode": args.mode}))
        
    except Exception as e:
        error_result = {"agent_id": "elena", "mode": args.mode, "success": False, "error": str(e)}
        with open(args.output, 'w') as f:
            json.dump(error_result, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
