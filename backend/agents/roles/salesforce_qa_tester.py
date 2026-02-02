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



# ============================================================================
# BUILD V2 - ELENA STRUCTURAL VALIDATION
# ============================================================================

def structural_validation(files: dict, phase: int) -> dict:
    """
    Validation structurelle pré-LLM.
    Vérifie la syntaxe et la structure avant de soumettre au LLM.
    
    Args:
        files: Dict {path: content}
        phase: Numéro de phase (1-6)
        
    Returns:
        Dict avec valid=True/False et issues[]
    """
    import xml.etree.ElementTree as ET
    import json as json_module
    
    issues = []
    
    # Vérifications communes - XML valide
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
                    plan = json_module.loads(content)
                    objects_seen = set()
                    for op in plan.get("operations", []):
                        if op.get("type") == "create_object":
                            api_name = op.get("api_name", "")
                            if api_name in objects_seen:
                                issues.append({
                                    "severity": "warning",
                                    "issue": f"Objet dupliqué: {api_name}"
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
                                    "issue": f"Champ référence objet inexistant: {obj}"
                                })
                except json_module.JSONDecodeError:
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
                        "issue": f"Accolades déséquilibrées: {open_b} ouvrantes vs {close_b} fermantes"
                    })
                
                # Check starts with valid modifier
                content_stripped = content.strip()
                valid_starts = ['@isTest', '@IsTest', 'public', 'private', 'global', 'abstract', 'virtual']
                has_valid = any(content_stripped.startswith(s) for s in valid_starts)
                if not has_valid and content_stripped:
                    issues.append({
                        "file": path,
                        "severity": "warning",
                        "issue": "Ne commence pas par un modificateur d'accès valide"
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
                        "issue": "Ne référence pas LightningElement"
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

Revois ce modèle de données Salesforce. Vérifie :
- Cohérence avec le SDS (tous les objets/champs du SDS sont présents)
- Relations correctes (Lookup vs Master-Detail selon la cardinalité)
- Naming conventions (API names en PascalCase + __c)
- Pas de champs en doublon entre objets
- Record Types pertinents
- Validation rules avec des formules syntaxiquement correctes

PLAN JSON À REVOIR:
{code_content}
""",
    
    2: """## REVIEW PHASE 2: BUSINESS LOGIC (APEX)

Revois cet ensemble de classes Apex. Vérifie :
- Chaque classe est self-contained (pas de référence à une classe non incluse ni non standard)
- Bulkification correcte (pas de SOQL/DML dans les boucles)
- Tests avec couverture suffisante (classes @isTest présentes)
- Gestion d'erreur avec AuraHandledException
- Les objets/champs référencés existent dans le modèle de données

MODÈLE DE DONNÉES DISPONIBLE:
{data_model_context}

CODE APEX À REVOIR:
{code_content}
""",
    
    3: """## REVIEW PHASE 3: UI COMPONENTS (LWC)

Revois ces composants Lightning Web Components. Vérifie :
- Nommage camelCase des composants
- Fichiers requis présents (html, js, js-meta.xml)
- Import correct de LightningElement
- Décorateurs @api, @wire, @track utilisés correctement
- Appels Apex avec @wire ou import imperatif
- Pas de dépendances circulaires

CLASSES APEX DISPONIBLES:
{apex_context}

COMPOSANTS LWC À REVOIR:
{code_content}
""",
    
    4: """## REVIEW PHASE 4: AUTOMATION

Revois ces automatisations Salesforce. Vérifie :
- Flows : structure correcte, pas de boucles infinies possibles
- Validation Rules complexes : formules syntaxiquement correctes
- Pas de conflits entre automatisations
- Ordre d'exécution respecté

MODÈLE DE DONNÉES:
{data_model_context}

AUTOMATISATIONS À REVOIR:
{code_content}
""",
    
    5: """## REVIEW PHASE 5: SECURITY & ACCESS

Revois ces configurations de sécurité. Vérifie :
- Permission Sets couvrent tous les objets/champs nécessaires
- Principe du moindre privilège respecté
- Sharing Rules cohérentes avec le modèle
- Page Layouts appropriés par profil/record type

MODÈLE DE DONNÉES:
{data_model_context}

CONFIGURATION SÉCURITÉ À REVOIR:
{code_content}
""",
    
    6: """## REVIEW PHASE 6: DATA MIGRATION

Revois ces scripts de migration de données. Vérifie :
- Mappings SDL corrects (colonnes source → champs cible)
- Scripts Apex anonymous sécurisés (pas d'injection)
- Ordre d'import respecte les dépendances (parents avant enfants)
- Requêtes SOQL de validation pertinentes

MODÈLE DE DONNÉES:
{data_model_context}

SCRIPTS MIGRATION À REVOIR:
{code_content}
"""
}


def get_phase_review_prompt(phase: int, code_content: str, context: dict = None) -> str:
    """
    Retourne le prompt de review adapté à la phase.
    
    Args:
        phase: Numéro de phase (1-6)
        code_content: Contenu à revoir
        context: Contexte additionnel (data_model_context, apex_context, etc.)
        
    Returns:
        Prompt formaté
    """
    context = context or {}
    
    template = PHASE_REVIEW_PROMPTS.get(phase, PHASE_REVIEW_PROMPTS[2])
    
    return template.format(
        code_content=code_content[:30000],  # Limite pour éviter overflow
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
        phase: Numéro de phase (1-6)
        aggregated_output: Output agrégé de la phase
        context: Contexte (data model, apex classes, etc.)
        execution_id: ID d'exécution
        
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
                "feedback_for_developer": "Erreurs structurelles détectées avant review LLM. Corrigez ces problèmes d'abord.",
                "requires_llm_review": False
            }
    
    # Step 2: Préparer le contenu pour review LLM
    if phase == 1 and operations:
        # Phase 1: JSON plan
        import json
        code_content = json.dumps({"operations": operations}, indent=2, ensure_ascii=False)
    elif files:
        # Autres phases: fichiers
        code_content = "\n\n".join([
            f"=== {path} ===\n{content}"
            for path, content in list(files.items())[:20]  # Limite 20 fichiers
        ])
    else:
        code_content = "Aucun contenu à revoir"
    
    # Step 3: Générer le prompt adapté à la phase
    prompt = get_phase_review_prompt(phase, code_content, context)
    
    # Note: L'appel LLM sera fait par le PhasedBuildExecutor qui appelle cette fonction
    return {
        "phase": phase,
        "prompt": prompt,
        "validation_type": "llm",
        "structural_validation": {"valid": True, "issues": []},
        "requires_llm_review": True
    }

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
        review_data = {"verdict": "FAIL", "summary": "Review impossible - format de réponse invalide", "issues": [{"severity": "critical", "description": "Parse error on review output"}], "feedback_for_developer": "Elena n'a pas pu produire un avis structuré. Resoumettez sans modification."}
    
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
