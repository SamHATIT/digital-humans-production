#!/usr/bin/env python3
"""
Salesforce DevOps Agent - Jordan
Dual Mode: spec (for SDS) | deploy (for real deployment operations)
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

# LLM Logger for debugging (INFRA-002)
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
    print(f"📝 LLM Logger loaded for Jordan", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass


SPEC_PROMPT = """# 🚀 DEVOPS - SPECIFICATION MODE

You are Jordan, an expert Salesforce DevOps Engineer.
Generate comprehensive DevOps and CI/CD SPECIFICATIONS for the SDS document.

## INPUT REQUIREMENTS
{requirements}

## DELIVERABLES
1. **Environment Strategy** - Dev, QA, UAT, Prod sandboxes
2. **CI/CD Pipeline** - GitHub Actions, Copado, or similar
3. **Branching Strategy** - Git flow, feature branches
4. **Deployment Strategy** - Metadata types, order, dependencies
5. **Rollback Plan** - Recovery procedures
6. **Monitoring** - Health checks, alerts

## FORMAT
Use clear markdown with detailed specifications.
"""


DEPLOY_PROMPT = """# 🚀 DEPLOYMENT ARTIFACTS - DEPLOY MODE

You are Jordan, preparing deployment artifacts.

## DEPLOYMENT TASK
**Task ID:** {task_id}
**Task Name:** {task_name}
**Components:** {components}

## TARGET ENVIRONMENT
{target_env}

## CRITICAL OUTPUT FORMAT
Generate deployment-ready artifacts:

For Package.xml:
```xml
<!-- FILE: manifest/package.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>ClassName</members>
        <name>ApexClass</name>
    </types>
    <version>59.0</version>
</Package>
```

For Destructive Changes (if needed):
```xml
<!-- FILE: manifest/destructiveChanges.xml -->
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>OldClassName</members>
        <name>ApexClass</name>
    </types>
    <version>59.0</version>
</Package>
```

For GitHub Actions Workflow:
```yaml
# FILE: .github/workflows/deploy.yml
name: Deploy to Salesforce
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy
        run: sf project deploy start --target-org ${{{{ secrets.SF_ORG }}}}
```

For Deployment Script:
```bash
# FILE: scripts/deploy.sh
#!/bin/bash
sf project deploy start --manifest manifest/package.xml --target-org $1
```

## GENERATE THE ARTIFACTS NOW:
"""


def generate_spec(requirements: str, project_name: str, execution_id: str, rag_context: str = "") -> dict:
    prompt = SPEC_PROMPT.format(requirements=requirements[:25000])
    if rag_context:
        prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"
    
    print(f"🚀 Jordan SPEC mode...", file=sys.stderr)
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
    
    
    # Log LLM interaction (INFRA-002)
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="jordan", prompt=prompt, response=content,
                execution_id=execution_id, task_id=None, agent_mode="spec",
                rag_context=rag_context, previous_feedback=None, parsed_files=None,
                tokens_input=input_tokens, tokens_output=tokens_used, model="claude-sonnet-4-20250514",
                provider="anthropic", execution_time_seconds=round(time.time() - start_time, 2),
                success=True, error_message=None
            )
        except Exception as e:
            print(f"⚠️ LLM log failed: {e}", file=sys.stderr)
    return {
        "agent_id": "jordan", "agent_name": "Jordan (DevOps)", "mode": "spec",
        "execution_id": str(execution_id), "deliverable_type": "devops_specification",
        "content": {"raw_markdown": content},
        "metadata": {"tokens_used": tokens_used, "execution_time_seconds": round(time.time() - start_time, 2)}
    }


def generate_deploy(task: dict, components: list, target_env: str, execution_id: str) -> dict:
    task_id = task.get('task_id', 'DEPLOY')
    task_name = task.get('name', 'Deployment')
    
    prompt = DEPLOY_PROMPT.format(
        task_id=task_id,
        task_name=task_name,
        components=json.dumps(components, indent=2),
        target_env=target_env
    )
    
    print(f"🚀 Jordan DEPLOY mode - preparing deployment for {task_id}...", file=sys.stderr)
    start_time = time.time()
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(prompt=prompt, provider=LLMProvider.ANTHROPIC,
                                         model="claude-sonnet-4-20250514", max_tokens=4000, temperature=0.2)
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
    else:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=4000)
        content = resp.choices[0].message.content
        tokens_used = resp.usage.total_tokens
    
    files = _parse_files(content)
    print(f"✅ Generated {len(files)} deployment file(s)", file=sys.stderr)
    
    
    # Log LLM interaction (INFRA-002)
    if LLM_LOGGER_AVAILABLE:
        try:
            log_llm_interaction(
                agent_id="jordan", prompt=prompt, response=content,
                execution_id=execution_id, task_id=task_id, agent_mode="deploy",
                rag_context=None, previous_feedback=None, parsed_files={"files": list(files.keys())},
                tokens_input=input_tokens, tokens_output=tokens_used, model="claude-sonnet-4-20250514",
                provider="anthropic", execution_time_seconds=round(time.time() - start_time, 2),
                success=len(files) > 0, error_message=None
            )
        except Exception as e:
            print(f"⚠️ LLM log failed: {e}", file=sys.stderr)
    return {
        "agent_id": "jordan", "agent_name": "Jordan (DevOps)", "mode": "deploy",
        "task_id": task_id, "execution_id": str(execution_id),
        "deliverable_type": "deployment_artifacts", "success": len(files) > 0,
        "content": {"raw_response": content, "files": files, "file_count": len(files)},
        "metadata": {"tokens_used": tokens_used, "execution_time_seconds": round(time.time() - start_time, 2)}
    }


def _parse_files(content: str) -> dict:
    import re
    files = {}
    patterns = [
        r'```(?:xml)\s*\n<!--\s*FILE:\s*(\S+)\s*-->\s*\n(.*?)```',
        r'```(?:yaml)\s*\n#\s*FILE:\s*(\S+)\s*\n(.*?)```',
        r'```(?:bash|sh)\s*\n#\s*FILE:\s*(\S+)\s*\n(.*?)```',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        for filepath, code in matches:
            if filepath.strip() and code.strip():
                files[filepath.strip()] = code.strip()
    return files


def main():
    parser = argparse.ArgumentParser(description='Jordan - DevOps (Dual Mode)')
    parser.add_argument('--mode', required=True, choices=['spec', 'deploy'])
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
                rag_context = get_salesforce_context("Salesforce DevOps CI/CD SFDX deployment", n_results=3, agent_type="devops")
            except: pass
        
        if args.mode == 'spec':
            result = generate_spec(input_content, args.project_id, args.execution_id, rag_context)
        else:  # deploy
            try:
                input_data = json.loads(input_content)
            except:
                input_data = {}
            result = generate_deploy(
                task=input_data.get('task', {}),
                components=input_data.get('components', []),
                target_env=input_data.get('target_env', 'UAT'),
                execution_id=args.execution_id
            )
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"success": result.get("success", True), "mode": args.mode}))
        
    except Exception as e:
        with open(args.output, 'w') as f:
            json.dump({"agent_id": "jordan", "success": False, "error": str(e)}, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
