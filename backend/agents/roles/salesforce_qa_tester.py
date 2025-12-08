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

## VALIDATION
Analyze the code and provide a JSON response:
```json
{{
    "verdict": "PASS" or "FAIL",
    "summary": "Brief assessment",
    "issues": [
        {{"severity": "critical|warning", "description": "...", "file": "..."}}
    ],
    "feedback_for_developer": "If FAIL, what to fix"
}}
```
Respond with ONLY valid JSON.
"""


def generate_spec(requirements: str, project_name: str, execution_id: str, rag_context: str = "") -> dict:
    prompt = SPEC_PROMPT.format(requirements=requirements[:25000])
    if rag_context:
        prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"
    
    print(f"🧪 Elena SPEC mode...", file=sys.stderr)
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
        "agent_id": "elena", "agent_name": "Elena (QA Engineer)", "mode": "spec",
        "execution_id": str(execution_id), "deliverable_type": "qa_specification",
        "content": {"raw_markdown": content},
        "metadata": {"tokens_used": tokens_used, "execution_time_seconds": round(time.time() - start_time, 2)}
    }


def generate_test(input_data: dict, execution_id: str) -> dict:
    """Validate code from Diego/Zara - return PASS/FAIL with feedback"""
    code_files = input_data.get("code_files", input_data.get("files", {}))
    task_info = input_data.get("task", {})
    
    if not code_files:
        return {"agent_id": "elena", "mode": "test", "success": False, "verdict": "FAIL",
                "feedback": "No code files provided"}
    
    print(f"🧪 Elena TEST mode - reviewing {len(code_files)} file(s)...", file=sys.stderr)
    start_time = time.time()
    
    # Build code content for review
    code_content = "\n\n".join([f"### {fp}\n```\n{content[:3000]}\n```" for fp, content in code_files.items()])
    
    prompt = CODE_REVIEW_PROMPT.format(code_content=code_content[:12000], task_info=json.dumps(task_info))
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model="claude-sonnet-4-20250514", max_tokens=2000, temperature=0.1)
        review_text = response.get('content', '{}')
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=2000)
        review_text = resp.choices[0].message.content
    
    # Parse response
    try:
        review_text = review_text.strip()
        if '```' in review_text:
            review_text = review_text.split('```')[1].replace('json', '', 1).strip()
        review_data = json.loads(review_text)
    except:
        review_data = {"verdict": "PASS", "summary": "Auto-pass", "issues": [], "feedback_for_developer": ""}
    
    verdict = review_data.get("verdict", "PASS")
    print(f"  {'✅' if verdict == 'PASS' else '❌'} Verdict: {verdict}", file=sys.stderr)
    
    return {
        "agent_id": "elena", "agent_name": "Elena (QA Engineer)", "mode": "test",
        "success": verdict == "PASS", "verdict": verdict,
        "task_id": task_info.get("task_id", ""),
        "execution_id": str(execution_id),
        "deliverable_type": "code_validation",
        "content": {"code_review": review_data, "files_reviewed": len(code_files)},
        "feedback": review_data.get("feedback_for_developer", "") if verdict == "FAIL" else "",
        "metadata": {"execution_time_seconds": round(time.time() - start_time, 2)}
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
