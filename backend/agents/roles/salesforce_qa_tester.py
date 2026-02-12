#!/usr/bin/env python3
"""
Salesforce QA Engineer Agent - Elena
Dual Mode: spec (for SDS) | test (for validating BUILD code)

P3 Refactoring: Transformed from subprocess-only script to importable class.
Can be used via direct import (QATesterAgent.run()) or CLI (python salesforce_qa_tester.py --mode ...).

Module-level utility functions (structural_validation, review_phase_output, etc.)
are preserved for direct import by phased_build_executor.py.
"""

import json
import time
import logging
import xml.etree.ElementTree as ET
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

# Prompt Service for externalized prompts
try:
    from prompts.prompt_service import PromptService
    PROMPT_SERVICE = PromptService()
except ImportError:
    PROMPT_SERVICE = None


# ============================================================================
# PROMPTS
# ============================================================================

SPEC_PROMPT = """# QA ENGINEER - SPECIFICATION MODE
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

CODE_REVIEW_PROMPT = """# CODE VALIDATION
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


# ============================================================================
# BUILD V2 - ELENA STRUCTURAL VALIDATION
# These functions are kept module-level for direct import by
# phased_build_executor.py and tests.
# ============================================================================

def structural_validation(files: dict, phase: int) -> dict:
    """
    Validation structurelle pre-LLM.
    Verifie la syntaxe et la structure avant de soumettre au LLM.

    Args:
        files: Dict {path: content}
        phase: Numero de phase (1-6)

    Returns:
        Dict avec valid=True/False et issues[]
    """
    issues = []

    # Verifications communes - XML valide
    for path, content in files.items():
        if path.endswith('.xml'):
            try:
                ET.fromstring(content)
            except ET.ParseError as e:
                issues.append({
                    "file": path,
                    "severity": "critical",
                    "issue": f"XML invalide: {str(e)[:100]}"
                })

    # Phase 1: Data Model (JSON)
    if phase == 1:
        for path, content in files.items():
            if path.endswith('.json') or content.strip().startswith('{'):
                try:
                    plan = json.loads(content)
                    objects_seen = set()
                    for op in plan.get("operations", []):
                        if op.get("type") == "create_object":
                            api_name = op.get("api_name", "")
                            if api_name in objects_seen:
                                issues.append({
                                    "severity": "warning",
                                    "issue": f"Objet duplique: {api_name}"
                                })
                            objects_seen.add(api_name)
                        if op.get("type") == "create_field":
                            obj = op.get("object", "")
                            if obj not in objects_seen and not obj.endswith("__c"):
                                # Standard object, ok
                                pass
                            elif obj not in objects_seen:
                                issues.append({
                                    "severity": "critical",
                                    "issue": f"Champ reference objet inexistant: {obj}"
                                })
                except json.JSONDecodeError:
                    pass  # Not JSON, skip

    # Phase 2: Apex
    if phase == 2:
        for path, content in files.items():
            if path.endswith('.cls') or path.endswith('.trigger'):
                # Check balanced braces
                open_b = content.count('{')
                close_b = content.count('}')
                if open_b != close_b:
                    issues.append({
                        "file": path,
                        "severity": "critical",
                        "issue": f"Accolades desequilibrees: {open_b} ouvrantes vs {close_b} fermantes"
                    })

                # Check starts with valid modifier
                content_stripped = content.strip()
                valid_starts = ['@isTest', '@IsTest', 'public', 'private', 'global', 'abstract', 'virtual']
                has_valid = any(content_stripped.startswith(s) for s in valid_starts)
                if not has_valid and content_stripped:
                    issues.append({
                        "file": path,
                        "severity": "warning",
                        "issue": "Ne commence pas par un modificateur d'acces valide"
                    })

    # Phase 3: LWC
    if phase == 3:
        for path, content in files.items():
            if path.endswith('.js') and '/lwc/' in path and not path.endswith('.js-meta.xml'):
                if 'export default class' not in content:
                    issues.append({
                        "file": path,
                        "severity": "critical",
                        "issue": "Manque 'export default class'"
                    })
                if 'LightningElement' not in content:
                    issues.append({
                        "file": path,
                        "severity": "warning",
                        "issue": "Ne reference pas LightningElement"
                    })

    has_critical = any(i.get('severity') == 'critical' for i in issues)
    return {
        "valid": not has_critical,
        "issues": issues,
        "phase": phase
    }


# Prompts de review par phase
PHASE_REVIEW_PROMPTS = {
    1: """## REVIEW PHASE 1: DATA MODEL

Revois ce modele de donnees Salesforce. Verifie :
- Coherence avec le SDS (tous les objets/champs du SDS sont presents)
- Relations correctes (Lookup vs Master-Detail selon la cardinalite)
- Naming conventions (API names en PascalCase + __c)
- Pas de champs en doublon entre objets
- Record Types pertinents
- Validation rules avec des formules syntaxiquement correctes

PLAN JSON A REVOIR:
{code_content}
""",

    2: """## REVIEW PHASE 2: BUSINESS LOGIC (APEX)

Revois cet ensemble de classes Apex. Verifie :
- Chaque classe est self-contained (pas de reference a une classe non incluse ni non standard)
- Bulkification correcte (pas de SOQL/DML dans les boucles)
- Tests avec couverture suffisante (classes @isTest presentes)
- Gestion d'erreur avec AuraHandledException
- Les objets/champs references existent dans le modele de donnees

MODELE DE DONNEES DISPONIBLE:
{data_model_context}

CODE APEX A REVOIR:
{code_content}
""",

    3: """## REVIEW PHASE 3: UI COMPONENTS (LWC)

Revois ces composants Lightning Web Components. Verifie :
- Nommage camelCase des composants
- Fichiers requis presents (html, js, js-meta.xml)
- Import correct de LightningElement
- Decorateurs @api, @wire, @track utilises correctement
- Appels Apex avec @wire ou import imperatif
- Pas de dependances circulaires

CLASSES APEX DISPONIBLES:
{apex_context}

COMPOSANTS LWC A REVOIR:
{code_content}
""",

    4: """## REVIEW PHASE 4: AUTOMATION

Revois ces automatisations Salesforce. Verifie :
- Flows : structure correcte, pas de boucles infinies possibles
- Validation Rules complexes : formules syntaxiquement correctes
- Pas de conflits entre automatisations
- Ordre d'execution respecte

MODELE DE DONNEES:
{data_model_context}

AUTOMATISATIONS A REVOIR:
{code_content}
""",

    5: """## REVIEW PHASE 5: SECURITY & ACCESS

Revois ces configurations de securite. Verifie :
- Permission Sets couvrent tous les objets/champs necessaires
- Principe du moindre privilege respecte
- Sharing Rules coherentes avec le modele
- Page Layouts appropries par profil/record type

MODELE DE DONNEES:
{data_model_context}

CONFIGURATION SECURITE A REVOIR:
{code_content}
""",

    6: """## REVIEW PHASE 6: DATA MIGRATION

Revois ces scripts de migration de donnees. Verifie :
- Mappings SDL corrects (colonnes source -> champs cible)
- Scripts Apex anonymous securises (pas d'injection)
- Ordre d'import respecte les dependances (parents avant enfants)
- Requetes SOQL de validation pertinentes

MODELE DE DONNEES:
{data_model_context}

SCRIPTS MIGRATION A REVOIR:
{code_content}
"""
}


def get_phase_review_prompt(phase: int, code_content: str, context: dict = None) -> str:
    """
    Retourne le prompt de review adapte a la phase.

    Args:
        phase: Numero de phase (1-6)
        code_content: Contenu a revoir
        context: Contexte additionnel (data_model_context, apex_context, etc.)

    Returns:
        Prompt formate
    """
    context = context or {}

    template = PHASE_REVIEW_PROMPTS.get(phase, PHASE_REVIEW_PROMPTS[2])

    return template.format(
        code_content=code_content[:30000],  # Limite pour eviter overflow
        data_model_context=context.get("data_model_context", "Non fourni"),
        apex_context=context.get("apex_context", "Non fourni")
    )


async def review_phase_output(
    phase: int,
    aggregated_output: dict,
    context: dict = None,
    execution_id: str = "0"
) -> dict:
    """
    Review BUILD v2: validation structurelle puis LLM review.

    Args:
        phase: Numero de phase (1-6)
        aggregated_output: Output agrege de la phase
        context: Contexte (data model, apex classes, etc.)
        execution_id: ID d'execution

    Returns:
        Dict avec verdict, issues, feedback
    """
    files = aggregated_output.get("files", {})
    operations = aggregated_output.get("operations", [])

    # Step 1: Validation structurelle
    if files:
        struct_validation = structural_validation(files, phase)
        if not struct_validation["valid"]:
            return {
                "verdict": "FAIL",
                "phase": phase,
                "validation_type": "structural",
                "issues": struct_validation["issues"],
                "feedback_for_developer": "Erreurs structurelles detectees avant review LLM. Corrigez ces problemes d'abord.",
                "requires_llm_review": False
            }

    # Step 2: Preparer le contenu pour review LLM
    if phase == 1 and operations:
        # Phase 1: JSON plan
        code_content = json.dumps({"operations": operations}, indent=2, ensure_ascii=False)
    elif files:
        # Autres phases: fichiers
        code_content = "\n\n".join([
            f"=== {path} ===\n{content}"
            for path, content in list(files.items())[:20]  # Limite 20 fichiers
        ])
    else:
        code_content = "Aucun contenu a revoir"

    # Step 3: Generer le prompt adapte a la phase
    prompt = get_phase_review_prompt(phase, code_content, context)

    # Note: L'appel LLM sera fait par le PhasedBuildExecutor qui appelle cette fonction
    return {
        "phase": phase,
        "prompt": prompt,
        "validation_type": "llm",
        "structural_validation": {"valid": True, "issues": []},
        "requires_llm_review": True
    }


def generate_test(input_data: dict, execution_id: str) -> dict:
    """
    Validate code from Diego/Zara - return PASS/FAIL with feedback.

    Kept as module-level function for backward compat with phased_build_executor.py.
    The QATesterAgent class delegates to this function internally.
    """
    code_files = input_data.get("code_files", input_data.get("files", {}))
    task_info = input_data.get("task", {})
    validation_criteria = input_data.get(
        "validation_criteria",
        task_info.get("validation_criteria", "Code should be functional and follow best practices")
    )

    if not code_files:
        return {
            "agent_id": "elena", "mode": "test", "success": False,
            "verdict": "FAIL", "feedback": "No code files provided"
        }

    logger.info(f"Elena TEST mode - reviewing {len(code_files)} file(s)")
    start_time = time.time()
    model_used = "claude-sonnet-4-20250514"

    # Build code content for review - show FULL content for each file
    code_parts = []
    for fp, content in code_files.items():
        logger.debug(f"  {fp}: {len(content)} chars")
        code_parts.append(f"### FILE: {fp}\n```\n{content}\n```")

    code_content = "\n\n".join(code_parts)
    total_code_chars = len(code_content)
    logger.info(f"  Total code content: {total_code_chars} chars")

    # Format validation criteria
    if isinstance(validation_criteria, list):
        criteria_text = "\n".join(f"- {c}" for c in validation_criteria)
    else:
        criteria_text = str(validation_criteria)

    # Try external prompt via PromptService, fallback to constant
    if PROMPT_SERVICE:
        try:
            prompt = PROMPT_SERVICE.render("elena_qa", "code_review", {
                "code_content": code_content[:80000],
                "task_info": json.dumps(task_info, indent=2),
                "validation_criteria": criteria_text,
            })
        except Exception as e:
            logger.warning(f"PromptService fallback for elena_qa/code_review: {e}")
            prompt = CODE_REVIEW_PROMPT.format(
                code_content=code_content[:80000],
                task_info=json.dumps(task_info, indent=2),
                validation_criteria=criteria_text
            )
    else:
        prompt = CODE_REVIEW_PROMPT.format(
            code_content=code_content[:80000],  # Increased limit
            task_info=json.dumps(task_info, indent=2),
            validation_criteria=criteria_text
        )

    logger.info(f"  Prompt length: {len(prompt)} chars")

    tokens_used = 0
    input_tokens = 0
    review_text = "{}"

    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=prompt, provider=LLMProvider.ANTHROPIC,
            model=model_used, max_tokens=4000, temperature=0.1,
            execution_id=execution_id
        )
        review_text = response.get('content', '{}')
        tokens_used = response.get('tokens_used', 0)
        input_tokens = response.get('input_tokens', 0)
    else:
        try:
            from openai import OpenAI
            client = OpenAI()
            model_used = "gpt-4o-mini"
            resp = client.chat.completions.create(
                model=model_used,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4000,
            )
            review_text = resp.choices[0].message.content
            tokens_used = resp.usage.total_tokens
            input_tokens = resp.usage.prompt_tokens
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    execution_time = round(time.time() - start_time, 2)

    # Parse response
    review_data = _parse_review_json(review_text)

    verdict = review_data.get("verdict", "PASS").upper()
    logger.info(f"  Verdict: {verdict}")
    if verdict == "FAIL":
        logger.info(f"  Feedback: {review_data.get('feedback_for_developer', 'N/A')[:200]}")

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
        except Exception as e:
            logger.warning(f"Failed to log LLM interaction: {e}")

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


def _parse_review_json(review_text: str) -> dict:
    """Parse JSON review response from LLM, handling markdown code blocks."""
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
        return json.loads(review_text_clean)
    except Exception as parse_err:
        logger.warning(f"Failed to parse review JSON: {parse_err}")
        return {
            "verdict": "FAIL",
            "summary": "Review impossible - format de reponse invalide",
            "issues": [{"severity": "critical", "description": "Parse error on review output"}],
            "feedback_for_developer": "Elena n'a pas pu produire un avis structure. Resoumettez sans modification."
        }


# ============================================================================
# QA TESTER AGENT CLASS -- Importable + CLI compatible
# ============================================================================
class QATesterAgent:
    """
    Elena (QA Tester) Agent - Spec + Test modes.

    P3 refactoring: importable class replacing subprocess-only script.
    Used by agent_executor.py for direct invocation (no subprocess overhead).

    Modes:
        - spec (alias: sds_strategy): Generate QA/testing specifications for SDS document
        - test: Validate BUILD code from Diego/Zara, return PASS/FAIL

    Usage (import):
        agent = QATesterAgent()
        result = agent.run({"mode": "spec", "input_content": "..."})

    Usage (CLI):
        python salesforce_qa_tester.py --mode spec --input input.json --output output.json

    Note: Module-level functions (structural_validation, review_phase_output, generate_test)
    are preserved for direct import by phased_build_executor.py.
    """

    VALID_MODES = ("spec", "test")

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point. Executes the agent and returns structured result.

        Args:
            task_data: dict with keys:
                - mode: "spec" or "test"
                - input_content: string content (raw text for spec, JSON string for test)
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

        # Map sds_strategy alias to spec
        if mode == "sds_strategy":
            mode = "spec"

        if mode not in self.VALID_MODES:
            return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

        if not input_content:
            return {"success": False, "error": "No input_content provided"}

        try:
            if mode == "spec":
                return self._execute_spec(input_content, execution_id, project_id)
            else:
                return self._execute_test(input_content, execution_id, project_id)
        except Exception as e:
            logger.error(f"QATesterAgent error in mode '{mode}': {e}", exc_info=True)
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
        """Execute spec mode: generate QA/testing specifications for SDS."""
        start_time = time.time()

        # Get RAG context for spec mode only
        rag_context = self._get_rag_context(project_id=project_id)

        # Build prompt - try PromptService first, fallback to constant
        if PROMPT_SERVICE:
            try:
                prompt = PROMPT_SERVICE.render("elena_qa", "spec", {
                    "requirements": input_content[:25000],
                })
            except Exception as e:
                logger.warning(f"PromptService fallback for elena_qa/spec: {e}")
                prompt = SPEC_PROMPT.format(requirements=input_content[:25000])
        else:
            prompt = SPEC_PROMPT.format(requirements=input_content[:25000])
        if rag_context:
            prompt += f"\n\n## BEST PRACTICES\n{rag_context[:2000]}\n"

        logger.info(f"QATesterAgent mode=spec, prompt_size={len(prompt)} chars")

        # Call LLM
        content, tokens_used, input_tokens, model_used, provider_used = self._call_llm(
            prompt, max_tokens=16000, temperature=0.3, execution_id=execution_id
        )

        execution_time = time.time() - start_time
        logger.info(
            f"QATesterAgent spec generated {len(content)} chars in {execution_time:.1f}s, "
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
            "agent_id": "elena",
            "agent_name": "Elena (QA Engineer)",
            "mode": "spec",
            "execution_id": str(execution_id),
            "deliverable_type": "qa_specification",
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
    # TEST MODE
    # ------------------------------------------------------------------
    def _execute_test(
        self,
        input_content: str,
        execution_id: int,
        project_id: int,
    ) -> Dict[str, Any]:
        """Execute test mode: validate BUILD code from Diego/Zara."""
        # Parse input JSON
        try:
            input_data = json.loads(input_content) if isinstance(input_content, str) else input_content
        except (json.JSONDecodeError, TypeError):
            input_data = {"files": {}}

        # Delegate to module-level generate_test for consistency with
        # phased_build_executor.py which imports it directly
        result = generate_test(input_data, str(execution_id))

        # Ensure success key is present
        if "success" not in result:
            result["success"] = result.get("verdict", "FAIL") == "PASS"

        return result

    # ------------------------------------------------------------------
    # LLM / RAG / Logger helpers
    # ------------------------------------------------------------------
    def _call_llm(
        self, prompt: str, max_tokens: int = 8000, temperature: float = 0.3,
        execution_id: int = 0
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
                execution_id=execution_id,
            )
            content = response.get("content", "")
            tokens_used = response.get("tokens_used", 0)
            input_tokens = response.get("input_tokens", 0)
            return content, tokens_used, input_tokens, "claude-sonnet-4-20250514", "anthropic"

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
        """Fetch RAG context for QA testing best practices."""
        if not RAG_AVAILABLE:
            return ""
        try:
            return get_salesforce_context(
                "Apex testing best practices",
                n_results=3,
                agent_type="qa_tester",
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
        success: bool = True,
    ) -> None:
        """Log LLM interaction for debugging (INFRA-002)."""
        if not LLM_LOGGER_AVAILABLE:
            return
        try:
            log_llm_interaction(
                agent_id="elena",
                prompt=prompt,
                response=content,
                execution_id=execution_id,
                task_id=task_id,
                agent_mode=mode,
                rag_context=rag_context if rag_context else None,
                previous_feedback=None,
                parsed_files=None,
                tokens_input=input_tokens,
                tokens_output=tokens_used,
                model=model_used,
                provider=provider_used,
                execution_time_seconds=round(execution_time, 2),
                success=success,
                error_message=None,
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

        agent = QATesterAgent()
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
        error_result = {"agent_id": "elena", "mode": args.mode, "success": False, "error": str(e)}
        with open(args.output, 'w') as f:
            json.dump(error_result, f)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
