#!/usr/bin/env python3
"""
Salesforce Research Analyst (Emma) Agent
Based on MetaGPT Researcher pattern - Adapted for UC Analysis, Validation, and SDS Writing

Three modes:
- analyze: Cluster and digest all Use Cases for Marcus
- validate: Check 100% coverage of UCs by Solution Design  
- write_sds: Generate professional SDS document

Inspired by: metagpt/roles/researcher.py
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from collections import defaultdict

# LLM imports
# Path for Docker container
sys.path.insert(0, "/app")
# Path for local testing
sys.path.insert(0, "/root/workspace/digital-humans-production/backend")
try:
    from app.services.llm_service import generate_llm_response, LLMProvider
    LLM_SERVICE_AVAILABLE = True
except ImportError:
    LLM_SERVICE_AVAILABLE = False

# LLM Logger for debugging
try:
    from app.services.llm_logger import log_llm_interaction
    LLM_LOGGER_AVAILABLE = True
    print(f"📝 LLM Logger loaded for Emma", file=sys.stderr)
except ImportError as e:
    LLM_LOGGER_AVAILABLE = False
    print(f"⚠️ LLM Logger unavailable: {e}", file=sys.stderr)
    def log_llm_interaction(*args, **kwargs): pass


# ============================================================================
# PROMPTS - MODE ANALYZE (inspired by CollectLinks + ConductResearch)
# ============================================================================

ANALYZE_SYSTEM = """You are Emma, a Research Analyst specialized in Salesforce project analysis.
Your goal is to analyze Use Cases and create structured digests for solution architects."""

CLUSTER_UCS_PROMPT = """# USE CASE CLUSTERING ANALYSIS

## INPUT DATA
Total Use Cases: {uc_count}
Business Requirements: {br_count}

### Use Cases (JSON):
{use_cases_json}

### Business Requirements (JSON):
{business_requirements_json}

## YOUR TASK
Analyze all Use Cases and group them by:
1. Parent Business Requirement (BR-XXX)
2. Salesforce Object patterns
3. Automation type (Flow, Trigger, Batch)

## OUTPUT FORMAT (JSON)
```json
{{
  "clusters": [
    {{
      "cluster_id": "CL-001",
      "parent_br": "BR-001",
      "uc_ids": ["UC-001-01", "UC-001-02"],
      "theme": "Customer Feedback Management",
      "sf_objects": ["Account", "Feedback__c"],
      "automation_types": ["Record-Triggered Flow"],
      "complexity": "medium"
    }}
  ],
  "cross_cutting": {{
    "shared_objects": ["Account"],
    "shared_automations": []
  }},
  "statistics": {{
    "total_ucs": {uc_count},
    "total_clusters": 0,
    "ucs_per_cluster_avg": 0
  }}
}}
```

## RULES
1. EVERY UC must belong to exactly ONE cluster
2. Group by parent_br first, then by object affinity
3. Identify objects used across multiple clusters as "shared_objects"
4. Complexity: low (<3 UCs), medium (3-6 UCs), high (>6 UCs)

Output ONLY valid JSON, no markdown fences.
"""

GENERATE_DIGEST_PROMPT = """# UC DIGEST GENERATION

## CLUSTERS ANALYSIS
{clusters_json}

## YOUR TASK
Generate a comprehensive UC Digest that Marcus (Solution Architect) can use to design the solution.
The digest must capture ALL requirements without exceeding context limits.

## OUTPUT FORMAT (JSON)
```json
{{
  "digest_id": "DIGEST-001",
  "generated_at": "{timestamp}",
  "project_summary": {{
    "total_brs": 0,
    "total_ucs": 0,
    "complexity_score": "medium"
  }},
  "by_requirement": {{
    "BR-001": {{
      "title": "...",
      "uc_count": 3,
      "sf_objects": ["Account", "Custom__c"],
      "sf_fields": {{
        "Account": ["Name", "Industry"],
        "Custom__c": ["Status__c", "Amount__c"]
      }},
      "automations": [
        {{"type": "Record-Triggered Flow", "purpose": "..."}}
      ],
      "ui_components": ["LWC AccountFeedback", "Related List"],
      "actors": ["Sales Rep", "Admin"],
      "key_acceptance_criteria": ["GIVEN... WHEN... THEN..."]
    }}
  }},
  "cross_cutting_concerns": {{
    "shared_objects": ["Account"],
    "integrations": [],
    "security_considerations": [],
    "data_migration_needs": []
  }},
  "recommendations": [
    "Consider using standard Case object instead of custom Feedback__c",
    "Consolidate validation rules into single flow"
  ]
}}
```

## RULES
1. EVERY UC from every cluster MUST be represented
2. Extract ALL sf_objects and sf_fields from UCs
3. Deduplicate objects/fields within each BR
4. Provide actionable recommendations based on patterns
5. Keep field lists complete but not verbose

Output ONLY valid JSON, no markdown fences.
"""


# ============================================================================
# PROMPTS - MODE VALIDATE (inspired by WebBrowseAndSummarize pattern)
# ============================================================================

VALIDATE_SYSTEM = """You are Emma, a QA Research Analyst ensuring 100% coverage of requirements.
Your goal is to verify every Use Case element is addressed in the Solution Design."""

MAP_ELEMENTS_PROMPT = """# ELEMENT MAPPING: UC → SOLUTION

## USE CASES
{use_cases_json}

## SOLUTION DESIGN
{solution_design_json}

## YOUR TASK
For EACH Use Case, map its elements to the Solution Design components.

## OUTPUT FORMAT (JSON)
```json
{{
  "mappings": [
    {{
      "uc_id": "UC-001-01",
      "uc_title": "Create Feedback Record",
      "elements": [
        {{
          "element_type": "sf_object",
          "element_value": "Feedback__c",
          "solution_component": "Custom Object: Feedback__c",
          "coverage_status": "covered",
          "notes": ""
        }},
        {{
          "element_type": "sf_field",
          "element_value": "Feedback__c.Rating__c",
          "solution_component": "Field: Rating__c (Picklist)",
          "coverage_status": "covered",
          "notes": ""
        }},
        {{
          "element_type": "automation",
          "element_value": "Record-Triggered Flow",
          "solution_component": "Flow: Feedback_After_Insert",
          "coverage_status": "covered",
          "notes": ""
        }}
      ]
    }}
  ],
  "summary": {{
    "total_elements": 0,
    "covered": 0,
    "partial": 0,
    "missing": 0
  }}
}}
```

## COVERAGE STATUS VALUES
- "covered": Element fully addressed in solution
- "partial": Element partially addressed, needs clarification
- "missing": Element NOT found in solution design

Output ONLY valid JSON, no markdown fences.
"""

COVERAGE_REPORT_PROMPT = """# COVERAGE REPORT GENERATION

## ELEMENT MAPPINGS
{mappings_json}

## YOUR TASK
Generate a comprehensive coverage report with score and gaps.

## OUTPUT FORMAT (JSON)
```json
{{
  "report_id": "COVERAGE-001",
  "generated_at": "{timestamp}",
  "coverage_score": 94.5,
  "status": "NEEDS_REVISION",
  "summary": {{
    "total_ucs": 0,
    "fully_covered_ucs": 0,
    "partial_ucs": 0,
    "missing_ucs": 0,
    "total_elements": 0,
    "covered_elements": 0
  }},
  "gaps": [
    {{
      "gap_id": "GAP-001",
      "uc_id": "UC-003-02",
      "element_type": "automation",
      "element_value": "Batch job for monthly aggregation",
      "severity": "high",
      "recommendation": "Add Batch Apex class for monthly feedback aggregation"
    }}
  ],
  "recommendations_for_marcus": [
    "Add missing Batch Apex for UC-003-02",
    "Clarify validation rule for Rating__c field"
  ]
}}
```

## STATUS VALUES
- "APPROVED": coverage_score >= 100
- "NEEDS_REVISION": coverage_score < 100

Output ONLY valid JSON, no markdown fences.
"""


# ============================================================================
# PROMPTS - MODE WRITE_SDS
# ============================================================================

WRITE_SDS_SYSTEM = """You are Emma, a Technical Writer specialized in Salesforce Solution Design Specifications.

## YOUR EXPERTISE
- Professional technical documentation in French
- Salesforce terminology and best practices
- Clear, structured, client-ready documents
- Transforming technical data into readable prose

## WRITING STYLE
- Professional but accessible language
- Active voice preferred
- Avoid jargon without explanation
- Use concrete examples where helpful
- Each section flows naturally to the next

## IMPORTANT RULES
- DO NOT copy-paste JSON - transform data into readable text
- DO include specific numbers, names, and details from the source data
- DO reference related sections where appropriate

## CRITICAL: ANTI-HALLUCINATION RULES
- NEVER invent component names, LWC names, Flow names, or Apex class names not in the source data
- NEVER fabricate workshops, meetings, or dates not mentioned in the sources
- NEVER create fictional statistics, percentages, or metrics
- If data is missing for a section, write: "Information non disponible dans les données sources"
- If a table would be empty, state: "Aucune donnée disponible pour ce tableau"
- ONLY use information explicitly present in the provided JSON sources
- When uncertain, be explicit: "Selon les données fournies..." or "D'après l'analyse..."
"""

WRITE_FULL_SDS_PROMPT = """# GÉNÉRATION DU DOCUMENT SDS

## INFORMATIONS PROJET
{project_info_json}

## STRUCTURE DU TEMPLATE
{template_json}

## DONNÉES SOURCE

### Business Requirements (Sophie):
{business_requirements_json}

### UC Digest (Emma analyze):
{uc_digest_json}

### Use Cases Complets (pour Annexe A.1):
{use_cases_json}

### Solution Design (Marcus):
{solution_design_json}

### Coverage Report (Emma validate):
{coverage_report_json}

### Work Breakdown Structure (Marcus):
{wbs_json}

### Spécifications QA (Elena):
{qa_specs_json}

### Spécifications DevOps (Jordan):
{devops_specs_json}

### Spécifications Formation (Lucas):
{training_specs_json}

### Spécifications Data (Aisha):
{data_specs_json}

## VOTRE TÂCHE
Générez un document SDS complet et professionnel en français selon la structure du template.

Pour chaque section:
1. Extrayez les données pertinentes des sources
2. Transformez en prose fluide et professionnelle
3. Incluez tableaux et descriptions de diagrammes où approprié
4. Assurez la traçabilité entre BRs → UCs → Composants Solution

## FORMAT DE SORTIE
Générez le document SDS complet en **Markdown** avec:
- Page de titre (nom projet, client, date, version)
- Table des matières
- Toutes les sections du template
- Séparateurs entre sections majeures (---)
- Hiérarchie de titres (# ## ### ####)
- Tableaux pour données structurées
- Diagrammes Mermaid si disponibles (ERD, workflows)

## CHECKLIST QUALITÉ
☐ Tous les BRs documentés avec descriptions complètes
☐ Tous les UCs traçables vers BRs
☐ Composants solution adressent les gaps identifiés
☐ Tâches WBS liées aux composants solution
☐ Aucun texte placeholder
☐ AUCUNE information inventée - uniquement les données sources
☐ Si données manquantes: "Information non disponible"
☐ Document fluide de section en section

Générez le document SDS maintenant:
"""

WRITE_SECTION_PROMPT = """# ÉCRITURE DE SECTION SDS

## SECTION À RÉDIGER
**Numéro:** {section_id}
**Titre:** {section_title}
**Description:** {section_description}

## DONNÉES SOURCE
{section_data_json}

## FORMAT ATTENDU: {format_type}

## SOUS-SECTIONS À INCLURE
{subsections_list}

## INSTRUCTIONS
Rédigez cette section du document SDS en français professionnel:
- Ton formel mais accessible
- Terminologie Salesforce précise
- Transformez les données JSON en prose fluide
- Incluez des tableaux si pertinent
- Longueur appropriée au contenu

Rédigez le contenu directement en Markdown:
"""

# Section-specific guidance for better output
SECTION_GUIDANCE = {
    "1": "Résumé exécutif: contexte, périmètre, recommandations clés, estimation effort",
    "2": "Contexte métier: présentation client, enjeux, parties prenantes, contraintes",
    "3": "Exigences métier: tableau récapitulatif puis détail par BR avec priorités MoSCoW",
    "4": "Spécifications fonctionnelles: UCs par BR, acteurs, matrice traçabilité",
    "5": "Architecture technique: modèle données (ERD), objets, sécurité, automatisations, intégrations",
    "6": "Plan implémentation: phases, estimation efforts, dépendances, risques",
    "7": "Stratégie test: approche QA, critères acceptation, plan UAT",
    "8": "Déploiement: stratégie, environnements, rollback",
    "9": "Formation: plan formation, documentation, support post-déploiement",
    "A": "Annexes: UCs détaillés, WBS complet, dictionnaire données, glossaire"
}



# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_json_response(content: str) -> Dict:
    """Clean and parse JSON from LLM response"""
    clean = content.strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[1] if '\n' in clean else clean[3:]
    if clean.endswith('```'):
        clean = clean[:-3]
    clean = clean.strip()
    if clean.startswith('json'):
        clean = clean[4:].strip()
    return json.loads(clean)


def calculate_coverage_score(mappings: Dict) -> float:
    """Calculate coverage percentage from mappings"""
    summary = mappings.get("summary", {})
    total = summary.get("total_elements", 0)
    covered = summary.get("covered", 0)
    partial = summary.get("partial", 0)
    
    if total == 0:
        return 100.0
    
    # Partial counts as 50%
    score = ((covered + partial * 0.5) / total) * 100
    return round(score, 1)


# ============================================================================
# MODE HANDLERS
# ============================================================================

async def run_analyze_mode(input_data: Dict, execution_id: int, args) -> Dict:
    """
    Mode ANALYZE: Cluster UCs and generate digest for Marcus
    Inspired by: CollectLinks → WebBrowseAndSummarize → ConductResearch
    """
    start_time = time.time()
    
    use_cases = input_data.get("use_cases", [])
    business_requirements = input_data.get("business_requirements", [])
    
    print(f"📊 Analyzing {len(use_cases)} UCs from {len(business_requirements)} BRs", file=sys.stderr)
    
    # Step 1: Cluster UCs (equivalent to CollectLinks - decompose & organize)
    print(f"🔍 Step 1/2: Clustering Use Cases...", file=sys.stderr)
    
    cluster_prompt = CLUSTER_UCS_PROMPT.format(
        uc_count=len(use_cases),
        br_count=len(business_requirements),
        use_cases_json=json.dumps(use_cases[:200], indent=2),  # Increased limit
        business_requirements_json=json.dumps(business_requirements, indent=2)
    )
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=cluster_prompt,
            agent_type="research",  # Uses appropriate tier
            system_prompt=ANALYZE_SYSTEM,
            max_tokens=8000,
            temperature=0.3
        )
        clusters_content = response["content"]
        tokens_step1 = response["tokens_used"]
        model_used = response["model"]
        provider_used = response["provider"]
    else:
        raise ValueError("LLM Service not available")
    
    try:
        clusters = parse_json_response(clusters_content)
        print(f"✅ Created {len(clusters.get('clusters', []))} clusters", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"⚠️ Cluster JSON parse error: {e}", file=sys.stderr)
        clusters = {"clusters": [], "error": str(e)}
    
    # Step 2: Generate Digest (equivalent to ConductResearch - synthesize)
    print(f"📝 Step 2/2: Generating UC Digest...", file=sys.stderr)
    
    digest_prompt = GENERATE_DIGEST_PROMPT.format(
        clusters_json=json.dumps(clusters, indent=2),
        timestamp=datetime.now().isoformat()
    )
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=digest_prompt,
            agent_type="research",
            system_prompt=ANALYZE_SYSTEM,
            max_tokens=12000,
            temperature=0.3
        )
        digest_content = response["content"]
        tokens_step2 = response["tokens_used"]
    
    try:
        digest = parse_json_response(digest_content)
        print(f"✅ Generated digest with {len(digest.get('by_requirement', {}))} BR sections", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"⚠️ Digest JSON parse error: {e}", file=sys.stderr)
        digest = {"raw": digest_content, "parse_error": str(e)}
    
    execution_time = time.time() - start_time
    total_tokens = tokens_step1 + tokens_step2
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        log_llm_interaction(
            agent_id="emma",
            prompt=f"[ANALYZE] Cluster + Digest for {len(use_cases)} UCs",
            response=json.dumps(digest)[:2000],
            execution_id=execution_id,
            agent_mode="analyze",
            tokens_output=total_tokens,
            model=model_used,
            provider=provider_used,
            execution_time_seconds=execution_time,
            success=True
        )
    
    return {
        "agent_id": "research_analyst",
        "agent_name": "Emma (Research Analyst)",
        "execution_id": execution_id,
        "mode": "analyze",
        "deliverable_type": "uc_digest",
        "content": {
            "clusters": clusters,
            "digest": digest
        },
        "metadata": {
            "tokens_used": total_tokens,
            "model": model_used,
            "provider": provider_used,
            "execution_time_seconds": round(execution_time, 2),
            "uc_count": len(use_cases),
            "br_count": len(business_requirements),
            "cluster_count": len(clusters.get("clusters", [])),
            "generated_at": datetime.now().isoformat()
        }
    }


async def run_validate_mode(input_data: Dict, execution_id: int, args) -> Dict:
    """
    Mode VALIDATE: Check 100% coverage of UCs by Solution Design
    Inspired by: WebBrowseAndSummarize (detailed analysis) → ConductResearch (report)
    
    BATCHING: Process UCs in batches of 15 to avoid JSON continuation issues.
    """
    start_time = time.time()
    
    use_cases = input_data.get("use_cases", [])
    solution_design = input_data.get("solution_design", {})
    
    print(f"🔍 Validating coverage of {len(use_cases)} UCs against Solution Design", file=sys.stderr)
    
    # Step 1: Map elements with BATCHING (to avoid JSON continuation issues)
    print(f"📋 Step 1/2: Mapping UC elements to Solution...", file=sys.stderr)
    
    BATCH_SIZE = 5  # Optimal size to avoid JSON truncation
    all_mappings = []
    tokens_step1 = 0
    model_used = "unknown"
    provider_used = "unknown"
    
    # Process UCs in batches
    num_batches = (len(use_cases) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"   Processing {len(use_cases)} UCs in {num_batches} batches of {BATCH_SIZE}", file=sys.stderr)
    
    for batch_idx in range(num_batches):
        batch_start = batch_idx * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, len(use_cases))
        batch_ucs = use_cases[batch_start:batch_end]
        
        print(f"   📦 Batch {batch_idx + 1}/{num_batches}: UCs {batch_start + 1}-{batch_end}", file=sys.stderr)
        
        map_prompt = MAP_ELEMENTS_PROMPT.format(
            use_cases_json=json.dumps(batch_ucs, indent=2),
            solution_design_json=json.dumps(solution_design, indent=2)
        )
        
        if LLM_SERVICE_AVAILABLE:
            response = generate_llm_response(
                prompt=map_prompt,
                agent_type="research",
                system_prompt=VALIDATE_SYSTEM,
                max_tokens=8000,  # Increased to avoid continuation
                temperature=0.2
            )
            mappings_content = response["content"]
            tokens_step1 += response["tokens_used"]
            model_used = response["model"]
            provider_used = response["provider"]
        else:
            raise ValueError("LLM Service not available")
        
        try:
            batch_mappings = parse_json_response(mappings_content)
            batch_list = batch_mappings.get('mappings', [])
            all_mappings.extend(batch_list)
            print(f"   ✅ Batch {batch_idx + 1}: {len(batch_list)} mappings", file=sys.stderr)
        except json.JSONDecodeError as e:
            print(f"   ⚠️ Batch {batch_idx + 1} parse error: {e}", file=sys.stderr)
            # Continue with other batches
    
    # Combine all mappings
    mappings = {"mappings": all_mappings}
    print(f"✅ Total mapped: {len(all_mappings)} UCs", file=sys.stderr)
    
    # Step 2: Generate coverage report (equivalent to ConductResearch)
    print(f"📊 Step 2/2: Generating Coverage Report...", file=sys.stderr)
    
    report_prompt = COVERAGE_REPORT_PROMPT.format(
        mappings_json=json.dumps(mappings, indent=2),
        timestamp=datetime.now().isoformat()
    )
    
    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=report_prompt,
            agent_type="research",
            system_prompt=VALIDATE_SYSTEM,
            max_tokens=8000,
            temperature=0.2
        )
        report_content = response["content"]
        tokens_step2 = response["tokens_used"]
    
    try:
        coverage_report = parse_json_response(report_content)
        coverage_score = coverage_report.get("coverage_score", 0)
        print(f"✅ Coverage Score: {coverage_score}%", file=sys.stderr)
    except json.JSONDecodeError as e:
        print(f"⚠️ Report JSON parse error: {e}", file=sys.stderr)
        coverage_report = {"raw": report_content, "parse_error": str(e), "coverage_score": 0}
        coverage_score = 0
    
    execution_time = time.time() - start_time
    total_tokens = tokens_step1 + tokens_step2
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        log_llm_interaction(
            agent_id="emma",
            prompt=f"[VALIDATE] Coverage check for {len(use_cases)} UCs",
            response=json.dumps(coverage_report)[:2000],
            execution_id=execution_id,
            agent_mode="validate",
            tokens_output=total_tokens,
            model=model_used,
            provider=provider_used,
            execution_time_seconds=execution_time,
            success=True
        )
    
    return {
        "agent_id": "research_analyst",
        "agent_name": "Emma (Research Analyst)",
        "execution_id": execution_id,
        "mode": "validate",
        "deliverable_type": "coverage_report",
        "content": {
            "mappings": mappings,
            "coverage_report": coverage_report,
            "coverage_score": coverage_score,
            "status": "APPROVED" if coverage_score >= 100 else "NEEDS_REVISION"
        },
        "metadata": {
            "tokens_used": total_tokens,
            "model": model_used,
            "provider": provider_used,
            "execution_time_seconds": round(execution_time, 2),
            "uc_count": len(use_cases),
            "coverage_score": coverage_score,
            "gaps_count": len(coverage_report.get("gaps", [])),
            "generated_at": datetime.now().isoformat()
        }
    }


async def run_write_sds_mode(input_data: Dict, execution_id: int, args) -> Dict:
    """
    Mode WRITE_SDS: Generate professional SDS document
    
    Uses the SDS Template Service to structure the document.
    Generates section by section following the template.
    Combines all agent deliverables into a cohesive document.
    """
    start_time = time.time()
    
    # Get template from service or input
    try:
        from app.services.sds_template_service import get_sds_template_service
        template_service = get_sds_template_service()
        template = template_service.get_default_template()
        print(f"📋 Using template: {template.get('template_name', 'Unknown')}", file=sys.stderr)
    except ImportError:
        print(f"⚠️ Template service not available, using input template", file=sys.stderr)
        template = input_data.get("template", {})
    
    # Gather all source data
    project_info = input_data.get("project_info", {})
    business_requirements = input_data.get("business_requirements", [])
    use_cases = input_data.get("use_cases", [])
    uc_digest = input_data.get("uc_digest", {})
    solution_design = input_data.get("solution_design", {})
    coverage_report = input_data.get("coverage_report", {})
    wbs = input_data.get("wbs", {})
    qa_specs = input_data.get("qa_specs", {})
    devops_specs = input_data.get("devops_specs", {})
    training_specs = input_data.get("training_specs", {})
    data_specs = input_data.get("data_specs", {})
    
    project_name = project_info.get("name", "Projet Salesforce")
    print(f"📄 Writing SDS document for: {project_name}", file=sys.stderr)
    print(f"   Sources: {len(business_requirements)} BRs, {len(use_cases)} UCs", file=sys.stderr)
    
    # Prepare consolidated sources for template
    sources = {
        "project_info": project_info,
        "business_requirements": business_requirements,
        "use_cases": use_cases,
        "uc_digest": uc_digest,
        "solution_design": solution_design,
        "coverage_report": coverage_report,
        "wbs": wbs,
        "qa_specs": qa_specs,
        "devops_specs": devops_specs,
        "training_specs": training_specs,
        "data_specs": data_specs
    }
    
    # Check data size to decide approach
    total_data_size = len(json.dumps(sources, default=str))
    use_single_call = total_data_size < 150000  # ~150KB threshold (Claude handles 200K tokens)
    
    sds_sections = {}
    total_tokens = 0
    model_used = ""
    provider_used = ""
    
    if use_single_call:
        # Single call for entire document
        print(f"📝 Generating full document (single call, {total_data_size} bytes)...", file=sys.stderr)
        
        full_prompt = WRITE_FULL_SDS_PROMPT.format(
            project_info_json=json.dumps(project_info, indent=2, ensure_ascii=False, default=str)[:5000],
            template_json=json.dumps(template.get("sections", []), indent=2)[:5000],
            business_requirements_json=json.dumps(business_requirements, indent=2, ensure_ascii=False, default=str)[:30000],
            uc_digest_json=json.dumps(uc_digest, indent=2, ensure_ascii=False, default=str)[:50000],
            use_cases_json=json.dumps(use_cases, indent=2, ensure_ascii=False, default=str)[:80000],  # Full UCs for Annexe A.1
            solution_design_json=json.dumps(solution_design, indent=2, ensure_ascii=False, default=str)[:60000],
            coverage_report_json=json.dumps(coverage_report, indent=2, ensure_ascii=False, default=str)[:20000],
            wbs_json=json.dumps(wbs, indent=2, ensure_ascii=False, default=str)[:60000],
            qa_specs_json=json.dumps(qa_specs, indent=2, ensure_ascii=False, default=str)[:30000],
            devops_specs_json=json.dumps(devops_specs, indent=2, ensure_ascii=False, default=str)[:30000],
            training_specs_json=json.dumps(training_specs, indent=2, ensure_ascii=False, default=str)[:30000],
            data_specs_json=json.dumps(data_specs, indent=2, ensure_ascii=False, default=str)[:30000]
        )
        
        if LLM_SERVICE_AVAILABLE:
            response = generate_llm_response(
                prompt=full_prompt,
                agent_type="research",
                system_prompt=WRITE_SDS_SYSTEM,
                max_tokens=16000,
                temperature=0.4
            )
            sds_sections["full_document"] = response["content"]
            total_tokens = response["tokens_used"]
            model_used = response["model"]
            provider_used = response["provider"]
        
        print(f"✅ Full document generated ({len(sds_sections.get('full_document', ''))} chars)", file=sys.stderr)
        
    else:
        # Section by section for larger projects
        template_sections = template.get("sections", [])
        print(f"📝 Generating section by section ({len(template_sections)} sections)...", file=sys.stderr)
        
        for section in template_sections:
            section_id = section.get("id", "")
            section_title = section.get("title", "")
            section_desc = section.get("description", "")
            subsections = section.get("subsections", [])
            
            print(f"   📄 Section {section_id}: {section_title}...", file=sys.stderr)
            
            # Gather data for this section
            section_data = {}
            for subsec in subsections:
                source_path = subsec.get("source", "")
                if source_path and source_path != "auto_generated":
                    # Extract data from sources
                    parts = source_path.split(".")
                    data = sources
                    for part in parts:
                        if isinstance(data, dict):
                            data = data.get(part, {})
                        else:
                            data = {}
                            break
                    section_data[subsec.get("id", "")] = data
            
            # Build subsections list
            subsections_list = "\n".join([
                f"- {s.get('id')}: {s.get('title')} (source: {s.get('source')}, format: {s.get('format', 'prose')})"
                for s in subsections
            ])
            
            # Get section guidance
            guidance = SECTION_GUIDANCE.get(section_id, section_desc)
            
            section_prompt = WRITE_SECTION_PROMPT.format(
                section_id=section_id,
                section_title=section_title,
                section_description=guidance,
                section_data_json=json.dumps(section_data, indent=2, ensure_ascii=False, default=str)[:30000],
                format_type=subsections[0].get("format", "prose") if subsections else "prose",
                subsections_list=subsections_list
            )
            
            if LLM_SERVICE_AVAILABLE:
                response = generate_llm_response(
                    prompt=section_prompt,
                    agent_type="research",
                    system_prompt=WRITE_SDS_SYSTEM,
                    max_tokens=6000,
                    temperature=0.4
                )
                sds_sections[section_id] = {
                    "title": section_title,
                    "content": response["content"]
                }
                total_tokens += response["tokens_used"]
                model_used = response["model"]
                provider_used = response["provider"]
            
            print(f"   ✅ Section {section_id} done", file=sys.stderr)
    
    execution_time = time.time() - start_time
    
    # Assemble final document
    if "full_document" in sds_sections:
        final_document = sds_sections["full_document"]
    else:
        # Combine sections into full document
        doc_parts = []
        doc_parts.append(f"# Solution Design Specification\n## {project_name}\n")
        doc_parts.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")
        doc_parts.append(f"**Version:** 1.0\n")
        doc_parts.append("\n---\n\n## Table des Matières\n")
        
        for section_id, section_data in sds_sections.items():
            if isinstance(section_data, dict):
                doc_parts.append(f"- [{section_data.get('title', section_id)}](#{section_id.lower().replace(' ', '-')})\n")
        
        doc_parts.append("\n---\n")
        
        for section_id, section_data in sds_sections.items():
            if isinstance(section_data, dict):
                doc_parts.append(f"\n# {section_data.get('title', section_id)}\n")
                doc_parts.append(section_data.get("content", ""))
                doc_parts.append("\n---\n")
        
        final_document = "".join(doc_parts)
    
    print(f"✅ SDS document complete: {len(final_document)} chars, {total_tokens} tokens, {execution_time:.1f}s", file=sys.stderr)
    
    # Log LLM interaction
    if LLM_LOGGER_AVAILABLE:
        log_llm_interaction(
            agent_id="emma",
            prompt=f"[WRITE_SDS] Document for {project_name}",
            response=f"Generated {len(sds_sections)} sections, {len(final_document)} chars",
            execution_id=execution_id,
            agent_mode="write_sds",
            tokens_output=total_tokens,
            model=model_used,
            provider=provider_used,
            execution_time_seconds=execution_time,
            success=True
        )
    
    return {
        "agent_id": "research_analyst",
        "agent_name": "Emma (Research Analyst)",
        "execution_id": execution_id,
        "mode": "write_sds",
        "deliverable_type": "sds_document",
        "artifact_id": "SDS-001",
        "content": {
            "document": final_document,
            "sections": sds_sections,
            "project_name": project_name,
            "generated_at": datetime.now().isoformat(),
            "template_used": template.get("template_id", "default"),
            "sources_used": list(sources.keys())
        },
        "metadata": {
            "tokens_used": total_tokens,
            "model": model_used,
            "provider": provider_used,
            "execution_time_seconds": round(execution_time, 2),
            "document_length": len(final_document),
            "sections_count": len(sds_sections),
            "generated_at": datetime.now().isoformat()
        }
    }


# ============================================================================
# MAIN EXECUTION (follows same pattern as other agents)
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Emma Research Analyst Agent')
    parser.add_argument('--input', required=True, help='Input JSON file')
    parser.add_argument('--output', required=True, help='Output JSON file path')
    parser.add_argument('--mode', required=True, choices=['analyze', 'validate', 'write_sds'], 
                        help='Execution mode')
    parser.add_argument('--execution-id', type=int, default=0, help='Execution ID')
    parser.add_argument('--project-id', type=int, default=0, help='Project ID')
    parser.add_argument('--use-rag', action='store_true', help='Enable RAG (optional)')
    
    args = parser.parse_args()
    
    try:
        # Read input
        print(f"📖 Reading input from {args.input}...", file=sys.stderr)
        with open(args.input, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        print(f"🚀 Running Emma in mode: {args.mode}", file=sys.stderr)
        
        # Run appropriate mode
        import asyncio
        
        if args.mode == "analyze":
            result = asyncio.run(run_analyze_mode(input_data, args.execution_id, args))
        elif args.mode == "validate":
            result = asyncio.run(run_validate_mode(input_data, args.execution_id, args))
        elif args.mode == "write_sds":
            result = asyncio.run(run_write_sds_mode(input_data, args.execution_id, args))
        else:
            raise ValueError(f"Unknown mode: {args.mode}")
        
        # Save output
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Output saved to {args.output}", file=sys.stderr)
        
        # Print summary to stdout for agent_executor
        print(json.dumps({
            "success": True,
            "mode": args.mode,
            "deliverable_type": result["deliverable_type"],
            "metadata": result["metadata"]
        }))
        
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
