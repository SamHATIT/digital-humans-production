#!/usr/bin/env python3
"""
Salesforce LWC Developer Agent - Zara
Dual Mode: spec (for SDS) | build (for real component generation)

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (LWCDeveloperAgent.run()) or CLI (python salesforce_developer_lwc.py --mode ...).

Module-level utility functions (validate_lwc_naming, validate_lwc_structure,
parse_lwc_files_robust, generate_build) are preserved for direct import by
phased_build_executor.py and tests.
"""

import re
import json
import time
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
# SPEC MODE PROMPT
# ============================================================================
SPEC_PROMPT = """# LWC DEVELOPER - SPECIFICATION MODE

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
BUILD_PROMPT = """# LWC CODE GENERATION - BUILD MODE

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

## COMPLETENESS CHECKLIST - VERIFY BEFORE SUBMITTING
Before generating, ensure:
- HTML: All tags properly opened AND closed (no incomplete templates)
- HTML: All referenced variables exist in the JS file
- JS: All methods referenced in HTML are fully implemented (not just signatures)
- JS: All imports are present (LightningElement, api, wire, track, etc.)
- JS: Error handling with try-catch for async operations
- CSS: All classes referenced in HTML have style rules
- META: Correct targets for where the component will be used

## GENERATE COMPLETE, WORKING CODE NOW:
"""


# ============================================================================
# BUILD V2 - LWC VALIDATION AND PARSING
# These functions are kept module-level for direct import by
# phased_build_executor.py and tests.
# ============================================================================

def validate_lwc_naming(component_name: str) -> str:
    """
    Force le nommage camelCase pour les composants LWC.

    Args:
        component_name: Nom du composant (peut contenir _ ou -)

    Returns:
        Nom en camelCase valide pour LWC
    """
    # Si deja en camelCase sans _ ou -, retourner tel quel
    if '_' not in component_name and '-' not in component_name:
        # Assurer que la premiere lettre est minuscule
        return component_name[0].lower() + component_name[1:] if component_name else component_name

    # Split sur _ et -
    parts = re.split(r'[_-]', component_name)

    # Premier mot en minuscules, suivants avec majuscule initiale
    result = parts[0].lower()
    for part in parts[1:]:
        if part:
            result += part.capitalize()

    return result


def validate_lwc_structure(files: dict) -> dict:
    """
    Valide la structure des fichiers LWC.

    Args:
        files: Dict {path: content}

    Returns:
        Dict avec valid=True/False et issues[]
    """
    issues = []
    components = {}

    # Grouper les fichiers par composant
    for path in files.keys():
        if '/lwc/' in path:
            match = re.search(r'/lwc/([^/]+)/', path)
            if match:
                comp_name = match.group(1)
                if comp_name not in components:
                    components[comp_name] = []
                components[comp_name].append(path)

    for comp_name, comp_files in components.items():
        # Verifier nommage camelCase
        if '_' in comp_name or '-' in comp_name:
            issues.append({
                "severity": "critical",
                "component": comp_name,
                "issue": f"Nom invalide '{comp_name}' - doit etre en camelCase"
            })

        # Verifier fichiers requis
        has_js = any(f.endswith('.js') and not f.endswith('.js-meta.xml') for f in comp_files)
        has_meta = any(f.endswith('.js-meta.xml') for f in comp_files)
        has_html = any(f.endswith('.html') for f in comp_files)

        if not has_js:
            issues.append({
                "severity": "critical",
                "component": comp_name,
                "issue": "Fichier .js manquant"
            })

        if not has_meta:
            issues.append({
                "severity": "critical",
                "component": comp_name,
                "issue": "Fichier .js-meta.xml manquant"
            })

    # Verifier contenu des fichiers JS
    for path, content in files.items():
        if path.endswith('.js') and '/lwc/' in path and not path.endswith('.js-meta.xml'):
            if 'export default class' not in content:
                issues.append({
                    "severity": "critical",
                    "file": path,
                    "issue": "Manque 'export default class'"
                })

            if 'LightningElement' not in content:
                issues.append({
                    "severity": "warning",
                    "file": path,
                    "issue": "Ne reference pas LightningElement"
                })

    return {
        "valid": len([i for i in issues if i["severity"] == "critical"]) == 0,
        "issues": issues,
        "components": list(components.keys())
    }


def parse_lwc_files_robust(content: str) -> dict:
    """
    Parse les fichiers LWC avec fallback progressif.

    Strategies:
    1. Regex avec backticks et FILE markers
    2. Markers textuels sans backticks
    3. Extraction par blocs de code

    Returns:
        Dict {path: content}
    """
    files = {}

    # Strategie 1: Regex avec backticks (format standard)
    patterns = [
        r'```(?:html)?\s*\n<!--\s*FILE:\s*(force-app/[^\s]+)\s*-->\s*\n(.*?)```',
        r'```(?:javascript|js)?\s*\n//\s*FILE:\s*(force-app/[^\s]+)\s*\n(.*?)```',
        r'```(?:css)?\s*\n/\*\s*FILE:\s*(force-app/[^\s]+)\s*\*/\s*\n(.*?)```',
        r'```(?:xml)?\s*\n<!--\s*FILE:\s*(force-app/[^\s]+)\s*-->\s*\n(.*?)```',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        for filepath, code in matches:
            if filepath.strip() and code.strip():
                files[filepath.strip()] = code.strip()

    if files:
        return files

    # Strategie 2: Markers sans backticks
    pattern2 = r'(?://|<!--)\s*FILE:\s*(force-app/[^\s]+?)(?:\s*-->)?\s*\n(.*?)(?=(?://|<!--)\s*FILE:|$)'
    matches = re.findall(pattern2, content, re.DOTALL)
    for filepath, code in matches:
        if filepath.strip() and code.strip():
            # Nettoyer le code des backticks residuels
            cleaned = re.sub(r'^```\w*\n?', '', code.strip())
            cleaned = re.sub(r'\n?```$', '', cleaned)
            files[filepath.strip()] = cleaned.strip()

    if files:
        return files

    # Strategie 3: Blocs de code avec detection de type
    code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)

    for lang, code in code_blocks:
        # Essayer de trouver un FILE marker dans le code
        file_match = re.search(r'(?://|<!--)\s*FILE:\s*(force-app/[^\s]+)', code)
        if file_match:
            filepath = file_match.group(1)
            # Retirer la ligne FILE du code
            clean_code = re.sub(r'(?://|<!--)\s*FILE:[^\n]+\n?', '', code).strip()
            if filepath and clean_code:
                files[filepath] = clean_code

    return files


def generate_build(task: dict, architecture_context: str, execution_id: str, rag_context: str = "", previous_feedback: str = "", solution_design: dict = None, gap_context: str = "") -> dict:
    """
    Generate LWC build artifacts.

    Kept as module-level function for backward compat with phased_build_executor.py.
    The LWCDeveloperAgent class delegates to this function internally.
    """
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

    prompt = BUILD_PROMPT.format(
        task_id=task_id, task_name=task_name,
        task_description=task_description,
        architecture_context=architecture_context[:10000],
        validation_criteria=validation_criteria,
    )

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

    logger.info(f"Zara BUILD mode - generating LWC for {task_id}, prompt_size={len(prompt)} chars")
    start_time = time.time()

    tokens_used = 0
    input_tokens = 0
    model_used = "claude-sonnet-4-20250514"
    content = ""

    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=prompt, provider=LLMProvider.ANTHROPIC,
            model="claude-sonnet-4-20250514", max_tokens=16000, temperature=0.2,
        )
        content = response.get('content', '')
        tokens_used = response.get('tokens_used', 0)
        input_tokens = response.get('input_tokens', 0)
        model_used = response.get('model', 'claude-sonnet-4-20250514')
    else:
        try:
            from openai import OpenAI
            client = OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=16000,
            )
            content = resp.choices[0].message.content
            tokens_used = resp.usage.total_tokens
            input_tokens = resp.usage.prompt_tokens
            model_used = "gpt-4o-mini"
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    files = parse_lwc_files_robust(content)
    execution_time = round(time.time() - start_time, 2)

    # BUILD V2: Validate and fix LWC naming
    fixed_files = {}
    for path, code in files.items():
        if "/lwc/" in path:
            match = re.search(r"/lwc/([^/]+)/", path)
            if match:
                old_name = match.group(1)
                new_name = validate_lwc_naming(old_name)
                if old_name != new_name:
                    path = path.replace(f"/lwc/{old_name}/", f"/lwc/{new_name}/")
                    logger.info(f"Fixed LWC name: {old_name} -> {new_name}")
        fixed_files[path] = code
    files = fixed_files
    logger.info(f"Generated {len(files)} file(s) in {execution_time}s")

    # Log LLM interaction for debugging
    if LLM_LOGGER_AVAILABLE:
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
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider="anthropic" if "claude" in model_used else "openai",
                execution_time_seconds=execution_time,
                success=len(files) > 0,
                error_message=None if len(files) > 0 else "No files parsed from response"
            )
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")

    return {
        "agent_id": "zara", "agent_name": "Zara (LWC Developer)", "mode": "build",
        "task_id": task_id, "execution_id": str(execution_id),
        "deliverable_type": "lwc_code", "success": len(files) > 0,
        "content": {"raw_response": content, "files": files, "file_count": len(files)},
        "metadata": {"tokens_used": tokens_used, "model": model_used,
                     "execution_time_seconds": execution_time}
    }


# ============================================================================
# LWC DEVELOPER AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class LWCDeveloperAgent:
    """
    Zara (LWC Developer) Agent - Spec + Build modes.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - spec (alias: generate): Generate LWC component specifications for SDS document
        - build: Generate real LWC components (HTML, JS, CSS, meta.xml)

    Usage (import):
        agent = LWCDeveloperAgent()
        result = agent.run({"mode": "spec", "input_content": "..."})

    Usage (CLI):
        python salesforce_developer_lwc.py --mode spec --input input.json --output output.json

    Note: Module-level functions (validate_lwc_naming, validate_lwc_structure,
    parse_lwc_files_robust, generate_build) are preserved for direct import by
    phased_build_executor.py and tests.
    """

    VALID_MODES = ("spec", "build")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "spec" or "build"
                - input_content: string content (raw text for spec, JSON string for build)
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

        # Map aliases to canonical modes
        if mode == "generate":
            mode = "spec"

        if mode not in self.VALID_MODES:
            return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

        if not input_content:
            return {"success": False, "error": "No input_content provided"}

        try:
            if mode == "spec":
                return self._execute_spec(input_content, execution_id, project_id)
            else:
                return self._execute_build(input_content, execution_id, project_id)
        except Exception as e:
            logger.error(f"LWCDeveloperAgent error in mode '{mode}': {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # SPEC MODE
    # ------------------------------------------------------------------
    def _execute_spec(
        self,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Execute spec mode: generate LWC component specifications for SDS."""
        start_time = time.time()

        # Get RAG context
        rag_context = self._get_rag_context(project_id=project_id)

        # Build prompt
        prompt = SPEC_PROMPT.format(requirements=input_content[:25000])
        if rag_context:
            prompt += f"\n\n## SALESFORCE LWC BEST PRACTICES (RAG)\n{rag_context[:2000]}\n"

        logger.info(f"LWCDeveloperAgent mode=spec, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, max_tokens=16000, temperature=0.3
        )

        execution_time = time.time() - start_time
        logger.info(
            f"LWCDeveloperAgent spec generated {len(content)} chars in {execution_time:.1f}s, "
            f"tokens={tokens_used}, model={model_used}"
        )

        # Log LLM interaction
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

        return {
            "success": True,
            "agent_id": "zara",
            "agent_name": "Zara (LWC Developer)",
            "mode": "spec",
            "execution_id": str(execution_id),
            "project_id": project_id,
            "deliverable_type": "lwc_specification",
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

    # ------------------------------------------------------------------
    # BUILD MODE
    # ------------------------------------------------------------------
    def _execute_build(
        self,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Execute build mode: generate real LWC components."""
        # Parse input data
        try:
            input_data = json.loads(input_content) if isinstance(input_content, str) else input_content
        except (json.JSONDecodeError, TypeError):
            input_data = {"task": {"name": "Task", "description": str(input_content)}}

        task = input_data.get("task", input_data)

        # Get RAG context
        rag_context = self._get_rag_context(project_id=project_id)

        # Delegate to module-level generate_build for consistency with
        # phased_build_executor.py which imports it directly
        result = generate_build(
            task,
            input_data.get("architecture_context", ""),
            str(execution_id),
            rag_context,
            input_data.get("previous_feedback", ""),
            input_data.get("solution_design"),
            input_data.get("gap_context", ""),
        )

        # Ensure success key
        if "success" not in result:
            result["success"] = result.get("content", {}).get("file_count", 0) > 0

        return result

    # ------------------------------------------------------------------
    # LLM / RAG / Logger helpers
    # ------------------------------------------------------------------
    def _call_llm(
        self, prompt: str, max_tokens: int = 16000, temperature: float = 0.3
    ) -> tuple:
        """
        Call LLM service with fallback to direct OpenAI.

        Returns:
            (content, tokens_used, input_tokens, model_used, provider_used)
        """
        if LLM_SERVICE_AVAILABLE:
            response = generate_llm_response(
                prompt=prompt,
                provider=LLMProvider.ANTHROPIC,
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.get("content", "")
            tokens_used = response.get("tokens_used", 0)
            input_tokens = response.get("input_tokens", 0)
            model_used = response.get("model", "claude-sonnet-4-20250514")
            return content, tokens_used, input_tokens, model_used, "anthropic"

        # Fallback to OpenAI
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
            return content, tokens_used, input_tokens, "gpt-4o-mini", "openai"
        except Exception as e:
            logger.error(f"LLM call failed (no provider available): {e}")
            raise

    def _get_rag_context(self, project_id: int = 0) -> str:
        """Fetch RAG context for LWC best practices."""
        if not RAG_AVAILABLE:
            return ""
        try:
            return get_salesforce_context(
                "LWC best practices wire events accessibility",
                n_results=3,
                agent_type="lwc_developer",
                project_id=project_id or None,
            )
        except Exception as e:
            logger.warning(f"RAG context retrieval failed: {e}")
            return ""

    def _log_interaction(
        self,
        mode: str,
        prompt: str,
        content: str,
        execution_id: int,
        input_tokens: int = 0,
        tokens_used: int = 0,
        model_used: str = "",
        provider_used: str = "",
        execution_time: float = 0.0,
        rag_context: str = "",
        task_id: Optional[str] = None,
        previous_feedback: Optional[str] = None,
        parsed_files: Optional[Dict] = None,
        success: bool = True,
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="zara",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=task_id,
                agent_mode=mode,
                rag_context=rag_context if rag_context else None,
                previous_feedback=previous_feedback if previous_feedback else None,
                parsed_files=parsed_files,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider=provider_used,
                execution_time_seconds=round(execution_time, 2),
                success=success,
                error_message=None if success else "No files parsed",
            )
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")


# ============================================================================
# CLI MODE - Backward compatible subprocess entry point
# ============================================================================

if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path

    # Add backend root to sys.path for CLI mode
    _backend_root = str(Path(__file__).resolve().parent.parent.parent)
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

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

        agent = LWCDeveloperAgent()
        result = agent.run({
            "mode": args.mode,
            "input_content": input_content,
            "execution_id": args.execution_id,
            "project_id": args.project_id,
        })

        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(json.dumps({"success": result.get("success", True), "mode": args.mode}))

    except Exception as e:
        error_result = {"agent_id": "zara", "success": False, "error": str(e)}
        with open(args.output, 'w') as f:
            json.dump(error_result, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
