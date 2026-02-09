#!/usr/bin/env python3
"""
Salesforce DevOps Agent - Jordan
Dual Mode: spec (for SDS) | deploy (for real deployment operations)

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (DevOpsAgent.run()) or CLI (python salesforce_devops.py --mode ...).
"""

import os
import re
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# LLM imports - clean imports for direct import mode
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

# LLM Logger for debugging (INFRA-002)
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
except ImportError:
    LLM_LOGGER_AVAILABLE = False
    def log_llm_interaction(*args, **kwargs): pass


# ============================================================================
# PROMPTS
# ============================================================================

SPEC_PROMPT = """# DEVOPS - SPECIFICATION MODE

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


DEPLOY_PROMPT = """# DEPLOYMENT ARTIFACTS - DEPLOY MODE

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


# ============================================================================
# DEVOPS AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class DevOpsAgent:
    """
    Jordan (DevOps) Agent - Spec + Deploy modes.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - spec: Generate DevOps/CI/CD specifications for SDS document
        - deploy: Generate deployment-ready artifacts (package.xml, scripts, etc.)

    Usage (import):
        agent = DevOpsAgent()
        result = agent.run({"mode": "spec", "input_content": "..."})

    Usage (CLI):
        python salesforce_devops.py --mode spec --input input.json --output output.json
    """

    VALID_MODES = ("spec", "deploy")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "spec" or "deploy"
                - input_content: string content (raw text for spec, JSON string for deploy)
                - execution_id: int (optional, default 0)
                - project_id: int (optional, default 0)

        Returns:
            dict with agent output including "success" key.
            On success: full output dict with agent_id, content, metadata, etc.
            On failure: {"success": False, "error": "..."}
        """
        mode = task_data.get("mode", "spec")
        input_content = task_data.get("input_content", "")
        execution_id = task_data.get("execution_id", 0)
        project_id = task_data.get("project_id", 0)

        if mode not in self.VALID_MODES:
            return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

        if not input_content:
            return {"success": False, "error": "No input_content provided"}

        try:
            if mode == "spec":
                return self._execute_spec(input_content, execution_id, project_id)
            else:
                return self._execute_deploy(input_content, execution_id, project_id)
        except Exception as e:
            logger.error(f"DevOpsAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _execute_spec(
        self,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Execute spec mode: generate DevOps specifications for SDS."""
        start_time = time.time()

        # Get RAG context for spec mode
        rag_context = self._get_rag_context(project_id=project_id)

        # Build prompt
        prompt = SPEC_PROMPT.format(requirements=input_content[:25000])
        if rag_context:
            prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"

        logger.info(f"DevOpsAgent mode=spec, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, max_tokens=8000, temperature=0.3
        )

        execution_time = time.time() - start_time
        logger.info(
            f"DevOpsAgent spec generated {len(content)} chars in {execution_time:.1f}s, "
            f"tokens={tokens_used}, model={model_used}"
        )

        # Log LLM interaction (INFRA-002)
        self._log_interaction(
            mode="spec",
            prompt=prompt,
            content=content,
            execution_id=execution_id,
            input_tokens=input_tokens,
            tokens_used=tokens_used,
            model_used=model_used,
            provider_used=provider_used,
            execution_time=execution_time,
            rag_context=rag_context,
        )

        # Build output
        output_data = {
            "success": True,
            "agent_id": "jordan",
            "agent_name": "Jordan (DevOps)",
            "mode": "spec",
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": "devops_specification",
            "content": {"raw_markdown": content},
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": datetime.now().isoformat(),
            },
        }

        return output_data

    def _execute_deploy(
        self,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Execute deploy mode: generate deployment artifacts."""
        start_time = time.time()

        # Parse input JSON for deploy data
        try:
            input_data = json.loads(input_content) if isinstance(input_content, str) else input_content
        except (json.JSONDecodeError, TypeError):
            input_data = {}

        task = input_data.get('task', {})
        task_id = task.get('task_id', 'DEPLOY')
        task_name = task.get('name', 'Deployment')
        components = input_data.get('components', [])
        target_env = input_data.get('target_env', 'UAT')

        # Build prompt
        prompt = DEPLOY_PROMPT.format(
            task_id=task_id,
            task_name=task_name,
            components=json.dumps(components, indent=2),
            target_env=target_env,
        )

        logger.info(f"DevOpsAgent mode=deploy, task_id={task_id}, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, max_tokens=4000, temperature=0.2
        )

        # Parse files from response
        files = self._parse_files(content)
        logger.info(f"Generated {len(files)} deployment file(s)")

        execution_time = time.time() - start_time
        logger.info(
            f"DevOpsAgent deploy completed in {execution_time:.1f}s, "
            f"tokens={tokens_used}, files={len(files)}"
        )

        # Log LLM interaction (INFRA-002)
        self._log_interaction(
            mode="deploy",
            prompt=prompt,
            content=content,
            execution_id=execution_id,
            task_id=task_id,
            input_tokens=input_tokens,
            tokens_used=tokens_used,
            model_used=model_used,
            provider_used=provider_used,
            execution_time=execution_time,
            parsed_files={"files": list(files.keys())},
        )

        # Build output
        output_data = {
            "success": len(files) > 0,
            "agent_id": "jordan",
            "agent_name": "Jordan (DevOps)",
            "mode": "deploy",
            "task_id": task_id,
            "execution_id": execution_id,
            "project_id": project_id,
            "deliverable_type": "deployment_artifacts",
            "content": {"raw_response": content, "files": files, "file_count": len(files)},
            "metadata": {
                "tokens_used": tokens_used,
                "model": model_used,
                "provider": provider_used,
                "execution_time_seconds": round(execution_time, 2),
                "content_length": len(content),
                "generated_at": datetime.now().isoformat(),
            },
        }

        return output_data

    def _get_rag_context(self, project_id: int = 0) -> str:
        """Fetch RAG context for DevOps best practices (spec mode only)."""
        if not RAG_AVAILABLE:
            return ""
        try:
            rag_context = get_salesforce_context(
                "Salesforce DevOps CI/CD SFDX deployment", n_results=3, agent_type="devops", project_id=project_id or None
            )
            logger.info(f"RAG context loaded ({len(rag_context)} chars)")
            return rag_context
        except Exception as e:
            logger.warning(f"RAG unavailable: {e}")
            return ""

    def _call_llm(self, prompt: str, max_tokens: int = 8000, temperature: float = 0.3) -> tuple:
        """
        Call LLM via llm_service or OpenAI fallback.

        Returns:
            tuple of (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            logger.debug("Calling LLM via llm_service (Anthropic)")
            response = generate_llm_response(
                prompt=prompt,
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return (
                response.get('content', ''),
                response.get('tokens_used', 0),
                response.get('input_tokens', 0),
                response.get('model', 'claude-sonnet-4-20250514'),
                response.get('provider', 'anthropic'),
            )
        else:
            # Fallback to direct OpenAI API (original behavior)
            logger.warning("llm_service unavailable, falling back to direct OpenAI API")
            try:
                from openai import OpenAI
                client = OpenAI()
                resp = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                )
                content = resp.choices[0].message.content
                tokens_used = resp.usage.total_tokens
                input_tokens = resp.usage.prompt_tokens
                return (content, tokens_used, input_tokens, "gpt-4o-mini", "openai")
            except Exception as e:
                logger.error(f"OpenAI fallback failed: {e}")
                return ('{"error": "LLM service not available"}', 0, 0, "none", "none")

    def _parse_files(self, content: str) -> Dict[str, str]:
        """Parse deployment files from LLM response using code block patterns."""
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

    def _log_interaction(
        self,
        mode: str,
        prompt: str,
        content: str,
        execution_id: int,
        input_tokens: int,
        tokens_used: int,
        model_used: str,
        provider_used: str,
        execution_time: float,
        task_id: Optional[str] = None,
        rag_context: Optional[str] = None,
        parsed_files: Optional[Dict] = None,
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="jordan",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=task_id,
                agent_mode=mode,
                rag_context=rag_context,
                previous_feedback=None,
                parsed_files=parsed_files,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider=provider_used,
                execution_time_seconds=round(execution_time, 2),
                success=True,
                error_message=None,
            )
            logger.debug("LLM interaction logged (INFRA-002)")
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")


# ============================================================================
# CLI MODE -- Backward compatibility for subprocess invocation
# ============================================================================
if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path

    # Ensure backend is on sys.path for CLI mode
    _backend_dir = str(Path(__file__).resolve().parent.parent.parent)
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)

    # Re-import after sys.path fix (module-level imports may have failed in CLI mode)
    if not LLM_SERVICE_AVAILABLE:
        try:
            from app.services.llm_service import generate_llm_response, LLMProvider
            LLM_SERVICE_AVAILABLE = True
        except ImportError:
            pass

    if not RAG_AVAILABLE:
        try:
            from app.services.rag_service import get_salesforce_context
            RAG_AVAILABLE = True
        except ImportError:
            pass

    parser = argparse.ArgumentParser(description='Jordan - DevOps (Dual Mode)')
    parser.add_argument('--mode', required=True, choices=['spec', 'deploy'])
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--execution-id', default='0')
    parser.add_argument('--project-id', default='unknown')
    parser.add_argument('--use-rag', action='store_true', default=True)
    args = parser.parse_args()

    try:
        logger.info("Reading input from %s...", args.input)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_content = f.read()
        logger.info("Read %d characters", len(input_content))

        agent = DevOpsAgent()
        result = agent.run({
            "mode": args.mode,
            "input_content": input_content,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
        })

        # Write output file
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Print summary to stdout (original behavior)
        print(json.dumps({"success": result.get("success", True), "mode": args.mode}))

        if not result.get("success"):
            logger.error("ERROR: %s", result.get('error'))
            sys.exit(1)

    except Exception as e:
        with open(args.output, 'w') as f:
            json.dump({"agent_id": "jordan", "success": False, "error": str(e)}, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
