"""Collectors pour le rendu SDS depuis la DB.

Itération 1 — strict minimum :
- Project / Execution metadata
- Coverage score (depuis research_analyst_coverage_report)
- Liste TOC statique (12 sections, ordre fixe)

Itérations suivantes ajouteront les collectors par section.
"""
from __future__ import annotations

import json
import re
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras


# ─── Connexion DB ──────────────────────────────────────────────────────────
def _db_conn():
    """Retourne une connexion PostgreSQL.
    
    Lit les paramètres depuis backend/.env, ou utilise les défauts de prod.
    """
    # Pour le dev/test on hardcode les valeurs de prod (même DSN que les agents)
    return psycopg2.connect(
        dbname="digital_humans_db",
        user="digital_humans",
        password="DH_SecurePass2025!",
        host="127.0.0.1",
        port=5432,
    )


# ─── 1. Project & Execution metadata ───────────────────────────────────────
def collect_execution_metadata(execution_id: int) -> dict[str, Any]:
    """Récupère les metadata Project + Execution.
    
    Retour:
        {
          "execution": {"id", "status", "started_at", "completed_at", "cost_usd"},
          "project":   {"id", "name", "description", "business_requirements"},
        }
    """
    with _db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT e.id AS exec_id, e.status::text, e.started_at, e.completed_at,
                   e.total_cost AS cost_usd,
                   p.id AS project_id, p.name, p.description, p.business_requirements
            FROM executions e
            JOIN projects p ON p.id = e.project_id
            WHERE e.id = %s
        """, (execution_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Execution #{execution_id} introuvable")
    
    return {
        "execution": {
            "id": row["exec_id"],
            "status": row["status"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "cost_usd": float(row["cost_usd"] or 0),
        },
        "project": {
            "id": row["project_id"],
            "name": row["name"],
            "description": row["description"] or "",
            "business_requirements": row["business_requirements"] or "",
        },
    }


# ─── 2. Coverage score ─────────────────────────────────────────────────────
def collect_coverage(execution_id: int) -> dict[str, Any]:
    """Extrait le score de coverage Emma.
    
    Retour:
        {"score": 95.2, "verdict": "PASS", "by_category": {...}, "critical_gaps": [...]}
    """
    with _db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT content
            FROM agent_deliverables
            WHERE execution_id = %s AND deliverable_type = 'research_analyst_coverage_report'
            LIMIT 1
        """, (execution_id,))
        row = cur.fetchone()
        if not row:
            return {"score": 0, "verdict": "MISSING", "by_category": {}, "critical_gaps": []}
    
    raw = row["content"]
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    # Le content est typiquement {"content": {...payload...}}
    content = parsed.get("content", parsed) if isinstance(parsed, dict) else {}
    
    return {
        "score": content.get("overall_coverage_score", 0),
        "verdict": content.get("verdict", "UNKNOWN"),
        "scoring_method": content.get("scoring_method", ""),
        "by_category": content.get("by_category", {}),
        "critical_gaps": content.get("critical_gaps", []),
    }


# ─── 3. TOC statique (les 12 sections, ordre fixe) ─────────────────────────
TOC_ENTRIES: list[dict[str, str]] = [
    {"num": 1,  "roman": "i",    "title": "Project Overview",        "author": "User brief",       "artifact_id": "initial_brief"},
    {"num": 2,  "roman": "ii",   "title": "Business Requirements",   "author": "Sophie — PM",      "artifact_id": "pm_br_extraction"},
    {"num": 3,  "roman": "iii",  "title": "Use Cases",               "author": "Olivia — BA",      "artifact_id": "ba_use_cases"},
    {"num": 4,  "roman": "iv",   "title": "Use Case Digest",         "author": "Emma — Research",  "artifact_id": "research_uc_digest"},
    {"num": 5,  "roman": "v",    "title": "As-Is Analysis",          "author": "Marcus — Architect", "artifact_id": "architect_as_is"},
    {"num": 6,  "roman": "vi",   "title": "Solution Design",         "author": "Marcus — Architect", "artifact_id": "architect_design"},
    {"num": 7,  "roman": "vii",  "title": "Gap Analysis",            "author": "Marcus — Architect", "artifact_id": "architect_gap"},
    {"num": 8,  "roman": "viii", "title": "Coverage Report",         "author": "Emma — Research",  "artifact_id": "research_coverage"},
    {"num": 9,  "roman": "ix",   "title": "Data Migration Strategy", "author": "Aisha — Data",     "artifact_id": "data_specifications"},
    {"num": 10, "roman": "x",    "title": "Training & Change Mgmt",  "author": "Lucas — Trainer",  "artifact_id": "trainer_specifications"},
    {"num": 11, "roman": "xi",   "title": "Test Strategy & QA",      "author": "Elena — QA",       "artifact_id": "qa_specifications"},
    {"num": 12, "roman": "xii",  "title": "CI/CD & Deployment",      "author": "Jordan — DevOps",  "artifact_id": "devops_specifications"},
]


def collect_toc(execution_id: int, br_count: int = 0, uc_count: int = 0,
                coverage_score: float = 0) -> list[dict[str, str]]:
    """Retourne le TOC enrichi avec les counts dynamiques (BRs / UCs / coverage).
    
    Le HTML de référence affiche par exemple "Use Cases — 58 UCs" et
    "Coverage Report — 95.2%". On reproduit ce pattern à partir de la DB.
    """
    enriched = []
    for entry in TOC_ENTRIES:
        e = dict(entry)
        # Suffixes dynamiques pour reproduire l'original :
        # - "Use Cases — N UCs"
        # - "Coverage Report — XX.X%"
        # (l'original n'a pas de count pour BRs, on s'aligne)
        if e["num"] == 3 and uc_count:
            e["title"] = f"Use Cases — {uc_count} UCs"
        elif e["num"] == 8 and coverage_score:
            e["title"] = f"Coverage Report — {coverage_score}%"
        enriched.append(e)
    return enriched


def _count_business_requirements(execution_id: int) -> int:
    """Compte les BRs en DB. Retourne 0 si la table n'existe pas ou est vide."""
    try:
        with _db_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM business_requirements WHERE execution_id = %s",
                (execution_id,),
            )
            return cur.fetchone()[0] or 0
    except psycopg2.errors.UndefinedTable:
        return 0
    except Exception:
        return 0


def _count_use_cases(execution_id: int) -> int:
    """Compte les UCs en DB (deliverable_items agent_id=ba item_type=use_case)."""
    with _db_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM deliverable_items
            WHERE execution_id = %s AND agent_id = 'ba' AND item_type = 'use_case'
        """, (execution_id,))
        return cur.fetchone()[0] or 0


# ─── 4. Liste agents impliqués + nb deliverables ───────────────────────────
def collect_agents_meta(execution_id: int) -> dict[str, Any]:
    """Liste les agents qui ont produit des deliverables pour cette exec."""
    with _db_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(DISTINCT id) AS deliverable_count,
                   COUNT(DISTINCT agent_id) AS agent_count
            FROM agent_deliverables
            WHERE execution_id = %s
        """, (execution_id,))
        deliv_count, _ = cur.fetchone()
    
    # Ordre canonique des agents impliqués dans le SDS (Sophie → Jordan)
    SDS_AGENTS = ["Sophie", "Olivia", "Emma", "Marcus", "Aisha", "Lucas", "Elena", "Jordan"]
    return {
        "involved": SDS_AGENTS,
        "deliverable_count": deliv_count,
    }



# ─── 6. Solution Design (section 6 du SDS) ─────────────────────────────────
def collect_solution_design(execution_id: int) -> dict[str, Any]:
    """Récupère le deliverable architect_solution_design et le retourne brut.
    
    Le content JSON contient (clés L1) : data_model, security_model, queues,
    reporting, automation_design, integration_points, ui_components,
    uc_traceability, technical_considerations, risks.
    
    Itération 2A.1 — utilise seulement queues, technical_considerations, risks.
    Les autres clés sont retournées telles quelles, le partial les ignore et
    affiche le bloc HTML en dur copié de la référence pour l'instant.
    """
    with _db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT content
            FROM agent_deliverables
            WHERE execution_id = %s AND deliverable_type = 'architect_solution_design'
            LIMIT 1
        """, (execution_id,))
        row = cur.fetchone()
        if not row:
            return {
                "data_model": {}, "security_model": {}, "queues": [],
                "reporting": {}, "automation_design": {}, "integration_points": [],
                "ui_components": {}, "uc_traceability": {},
                "technical_considerations": [], "risks": [],
            }
    
    raw = row["content"]
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    content = parsed.get("content", parsed) if isinstance(parsed, dict) else {}
    
    return {
        "data_model": content.get("data_model", {}),
        "security_model": content.get("security_model", {}),
        "queues": content.get("queues", []),
        "reporting": content.get("reporting", {}),
        "automation_design": content.get("automation_design", {}),
        "integration_points": content.get("integration_points", []),
        "ui_components": content.get("ui_components", {}),
        "uc_traceability": content.get("uc_traceability", {}),
        "technical_considerations": content.get("technical_considerations", []),
        "risks": content.get("risks", []),
    }




# ─── Loader générique deliverable ──────────────────────────────────────────
def _load_deliverable(execution_id: int, deliverable_type: str) -> dict[str, Any]:
    """Charge un deliverable et retourne son content parsé.
    
    Convention : les deliverables sont stockés en {"content": {...}} ou directement le payload.
    On gère les deux cas.
    """
    with _db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT content
            FROM agent_deliverables
            WHERE execution_id = %s AND deliverable_type = %s
            ORDER BY id DESC LIMIT 1
        """, (execution_id, deliverable_type))
        row = cur.fetchone()
        if not row:
            return {}
    raw = row["content"]
    parsed = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(parsed, dict):
        return parsed.get("content", parsed) or {}
    return {}


# ─── 1. Project Overview (sec-1) ───────────────────────────────────────────
def _parse_initial_needs(business_requirements_text: str) -> list[str]:
    """Parse le brief utilisateur (texte libre avec bullets) en liste de needs.
    
    Format typique : "Besoins :\n- need 1\n- need 2\n..."
    """
    if not business_requirements_text:
        return []
    needs = []
    for line in business_requirements_text.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ", "• ")):
            needs.append(line[2:].strip())
        elif line.startswith("-"):
            needs.append(line[1:].strip())
    return needs


# ─── 2. Business Requirements (sec-2) ──────────────────────────────────────
def collect_business_requirements(execution_id: int) -> dict[str, Any]:
    """Récupère le deliverable pm_br_extraction (Sophie).
    
    Retour:
        {
          "project_summary": str,
          "business_requirements": [{id, title, description, category, priority, stakeholder, metadata{...}}],
          "constraints": [...],
          "assumptions": [...],
        }
    """
    content = _load_deliverable(execution_id, "pm_br_extraction")
    return {
        "project_summary": content.get("project_summary", ""),
        "business_requirements": content.get("business_requirements", []),
        "constraints": content.get("constraints", []),
        "assumptions": content.get("assumptions", []),
    }


# ─── 3. Use Cases (sec-3) ──────────────────────────────────────────────────
def collect_use_cases(execution_id: int) -> dict[str, Any]:
    """Récupère les Use Cases d'Olivia depuis deliverable_items.
    
    Les UCs sont stockés un-par-row dans deliverable_items (agent_id='ba',
    item_type='use_case'), avec content JSON par UC.
    
    Retour:
        {"use_cases": [{id, title, br_refs, ...}], "by_br": {br_id: [uc, ...]}}
    """
    use_cases = []
    with _db_conn() as conn, conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""
            SELECT content_parsed, content_raw, item_id
            FROM deliverable_items
            WHERE execution_id = %s AND agent_id = 'ba' AND item_type = 'use_case'
            ORDER BY id
        """, (execution_id,))
        for row in cur.fetchall():
            parsed = row["content_parsed"]
            if parsed is None and row["content_raw"]:
                try:
                    parsed = json.loads(row["content_raw"])
                except json.JSONDecodeError:
                    continue
            if isinstance(parsed, dict):
                # Le content peut être nested sous "content"
                uc = parsed.get("content", parsed)
                if isinstance(uc, dict):
                    # S'assurer que l'item_id de la table est présent comme id
                    uc.setdefault("id", row["item_id"])
                    use_cases.append(uc)
    
    # Index par BR pour le rendu "Use Case Index by Business Requirement".
    # Olivia produit la cle 'parent_br' (string). On supporte aussi 'br_refs' (liste)
    # et 'br_id' (string) en fallback defensif si le format evolue.
    by_br: dict[str, list] = {}
    for uc in use_cases:
        br_refs = uc.get("br_refs") or []
        if not br_refs:
            single = uc.get("parent_br") or uc.get("br_id")
            if single:
                br_refs = [single]
        for br_id in br_refs:
            by_br.setdefault(br_id, []).append(uc)
    
    return {"use_cases": use_cases, "by_br": by_br}


# ─── 4. Use Case Digest (sec-4) ────────────────────────────────────────────
def collect_uc_digest(execution_id: int) -> dict[str, Any]:
    """Recupere research_analyst_uc_digest (Emma).
    
    Le payload Emma contient :
    - by_requirement : dict {BR-id: {title, uc_count, sf_objects, sf_fields,
                                      automations, ui_components, key_acceptance_criteria}}
    - cross_cutting_concerns : dict {shared_objects[], integration_points[], security_requirements[]}
    - recommendations : list[str]
    - data_volume_estimates : dict {ObjectName: "X-Y records (notes)"}
    
    On expose 'synthesis_by_br' comme une LISTE ordonnee par BR-id (BR-001, BR-002, ...)
    chaque item etant {br_id, title, uc_count, sf_objects, sf_fields, automations,
    ui_components, key_acceptance_criteria}. Jinja2 itere proprement sans dependre
    de l'ordre JSONB PostgreSQL.
    """
    content = _load_deliverable(execution_id, "research_analyst_uc_digest")
    
    # by_requirement : dict -> liste ordonnee
    by_req_dict = content.get("by_requirement", {}) or {}
    def _br_sort_key(br_id: str):
        # 'BR-001' -> (0, 1) ; clefs non standard -> (1, br_id)
        m = re.match(r"BR-(\d+)", br_id)
        return (0, int(m.group(1))) if m else (1, br_id)
    synthesis_list = []
    for br_id in sorted(by_req_dict.keys(), key=_br_sort_key):
        item = {"br_id": br_id, **by_req_dict[br_id]}
        synthesis_list.append(item)
    
    return {
        "synthesis_by_br": synthesis_list,
        "cross_cutting_concerns": content.get("cross_cutting_concerns", {}),
        "recommendations": content.get("recommendations", []),
        "data_volume_estimates": content.get("data_volume_estimates", {}),
        "total_use_cases_analyzed": content.get("total_use_cases_analyzed", 0),
    }


# ─── 5. As-Is Analysis (sec-5) ─────────────────────────────────────────────
def collect_as_is(execution_id: int) -> dict[str, Any]:
    """Recupere architect_as_is (Marcus).
    
    Retour:
        {
          "organization": {edition, api_version, release, custom_objects, ...,
                           permission_sets_standard[], profiles_standard[]},
          "standard_objects": [{name, label, standard_fields_count,
                                custom_fields_count, record_types_custom, description}]
        }
    """
    content = _load_deliverable(execution_id, "architect_as_is")
    return {
        "organization": content.get("organization", {}),
        "standard_objects": content.get("standard_objects", []),
    }


# ─── 7. Gap Analysis (sec-7) ───────────────────────────────────────────────
def collect_gap_analysis(execution_id: int) -> dict[str, Any]:
    """Recupere architect_gap_analysis (Marcus).
    
    Retour:
        {
          "summary": {total_gaps, by_category{}, by_complexity{}, by_agent{},
                      total_effort_days},
          "gaps": [{id, category, complexity, effort_days, gap_description,
                    current_state, target_state, assigned_agent, uc_refs[],
                    dependencies[]}],
          "migration_considerations": [str, ...],  # 7 strings
          "risk_areas": [str, ...],                # 8 strings
        }
    """
    content = _load_deliverable(execution_id, "architect_gap_analysis")
    return {
        "summary": content.get("summary", {}),
        "gaps": content.get("gaps", []),
        "migration_considerations": content.get("migration_considerations", []),
        "risk_areas": content.get("risk_areas", []),
    }


# ─── Parser JSON tolerant pour les deliverables wrapped en raw_markdown ───
def _parse_raw_markdown_json(md: str) -> tuple[dict, str | None]:
    """Parse un JSON entoure de fences ```json...``` avec recuperation tolerante.
    
    Strategy : (1) strip fences, (2) strict json, (3) strict=False (autorise
    control chars), (4) drop des lignes parasites '```' (LLM glitch), (5) tronque
    au point d'erreur et ferme les structures ouvertes.
    
    Retourne : (data_dict, error_message_or_None).
    """
    if not md:
        return {}, "empty"
    md = md.strip()
    if md.startswith('```'):
        nl = md.index('\n')
        md = md[nl+1:]
    if md.endswith('```'):
        md = md[:-3].rstrip()
    
    # 1. Strict
    try:
        return json.loads(md), None
    except json.JSONDecodeError:
        pass
    # 2. strict=False
    try:
        return json.loads(md, strict=False), None
    except json.JSONDecodeError:
        pass
    # 3. Drop lignes ```...```
    cleaned = '\n'.join(l for l in md.split('\n') if not l.strip().startswith('```'))
    try:
        return json.loads(cleaned, strict=False), None
    except json.JSONDecodeError as e:
        last_err = e
    # 4. Tronque au point d'erreur + ferme les structures
    try:
        truncated = cleaned[:last_err.pos]
        last_safe = max(truncated.rfind(','), truncated.rfind('}'), truncated.rfind(']'))
        if last_safe > 0:
            truncated = truncated[:last_safe]
        # Compter struct ouvertes
        opens_brace = opens_bracket = 0
        in_str = False
        esc = False
        for c in truncated:
            if esc:
                esc = False; continue
            if c == '\\':
                esc = True; continue
            if c == '"':
                in_str = not in_str
            elif not in_str:
                if c == '[': opens_bracket += 1
                elif c == ']': opens_bracket -= 1
                elif c == '{': opens_brace += 1
                elif c == '}': opens_brace -= 1
        truncated = truncated.rstrip().rstrip(',')
        # Heuristique : refermer brackets puis braces (assume nested order)
        candidate = truncated + (']' * opens_bracket) + ('}' * opens_brace)
        try:
            return json.loads(candidate, strict=False), f"partial-recovery: truncated at pos {last_err.pos}"
        except Exception:
            pass
    except Exception:
        pass
    return {}, "unrecoverable"


# ─── 9. Data Migration (sec-9) ─────────────────────────────────────────────
def collect_data_migration(execution_id: int) -> dict[str, Any]:
    """Recupere data_data_specifications (Aisha).
    
    Le payload Aisha est wrappe en {"raw_markdown": "```json\\n{...}\\n```"}.
    Le JSON interne peut etre corrompu (LLM glitch a observe sur exec 146).
    On utilise un parser tolerant.
    
    Retour:
        {
          "data_assessment": {source_systems[], target_objects[]},
          "migration_strategy": {approach, phases, tool},
          "field_mapping": [...],
          "data_cleansing_rules": [...],
          "validation_plan": {pre_migration, post_migration},
          "rollback_strategy": {approach, steps, ...},
          "integration_specs": [...],   # peut etre absent si parsing partiel
          "_parse_error": str | None,
        }
    """
    payload = _load_deliverable(execution_id, "data_data_specifications")
    md = payload.get("raw_markdown", "") if isinstance(payload, dict) else ""
    data, err = _parse_raw_markdown_json(md)
    return {
        "data_assessment": data.get("data_assessment", {}) or {},
        "migration_strategy": data.get("migration_strategy", {}) or {},
        "field_mapping": data.get("field_mapping", []) or [],
        "data_cleansing_rules": data.get("data_cleansing_rules", []) or [],
        "validation_plan": data.get("validation_plan", {}) or {},
        "rollback_strategy": data.get("rollback_strategy", {}) or {},
        "integration_specs": data.get("integration_specs", []) or [],
        "_parse_error": err,
    }


# ─── 10. Training & Adoption (sec-10) ──────────────────────────────────────
def collect_training(execution_id: int) -> dict[str, Any]:
    """Recupere trainer_trainer_specifications (Lucas).
    
    Retour:
        {
          "audience_analysis": {total_users_estimate, user_personas[]},
          "curriculum": [list[11] avec module_id, title, audience, duration_hours,
                          objectives[], topics[], prerequisites[]],
          "training_approach": {methodology, delivery_methods, phasing},
          "adoption_plan": {champions_program, communication_plan, kpis, success_criteria},
          "resource_requirements": {trainers, environments, materials_to_produce},
          "timeline": {aligned_to_wbs, phases},
          "risks": [list[8] avec risk, impact, mitigation],
        }
    """
    content = _load_deliverable(execution_id, "trainer_trainer_specifications")
    return {
        "audience_analysis": content.get("audience_analysis", {}) or {},
        "curriculum": content.get("curriculum", []) or [],
        "training_approach": content.get("training_approach", {}) or {},
        "adoption_plan": content.get("adoption_plan", {}) or {},
        "resource_requirements": content.get("resource_requirements", {}) or {},
        "timeline": content.get("timeline", {}) or {},
        "risks": content.get("risks", []) or [],
    }


# ─── 5. Build context — assemble tout pour le rendu Jinja2 ─────────────────
def build_render_context(execution_id: int) -> dict[str, Any]:
    """Assemble le dict complet à passer à Jinja2."""
    meta = collect_execution_metadata(execution_id)
    cov = collect_coverage(execution_id)
    agents = collect_agents_meta(execution_id)
    br_count = _count_business_requirements(execution_id)
    uc_count = _count_use_cases(execution_id)
    toc = collect_toc(execution_id, br_count=br_count, uc_count=uc_count,
                     coverage_score=cov.get("score", 0))
    sd = collect_solution_design(execution_id)
    
    # Lot A — sections 1-4 (sec-1 utilise meta + project, sec-2/3/4 ont leurs deliverables)
    brs = collect_business_requirements(execution_id)
    ucs = collect_use_cases(execution_id)
    digest = collect_uc_digest(execution_id)
    initial_needs = _parse_initial_needs(meta["project"]["business_requirements"])
    
    # Lot B — sections 5, 7, 8
    as_is = collect_as_is(execution_id)
    gap = collect_gap_analysis(execution_id)
    # sec-8 utilise 'coverage' deja collecte ci-dessus
    
    # Lot C — sections 9, 10
    data_mig = collect_data_migration(execution_id)
    training = collect_training(execution_id)
    
    # Status mapping → label + CSS class. La couleur indique le degré de finition
    # (brass = approved/complete, sage = build done, ochre = in progress, terra = failed).
    status_raw = (meta["execution"]["status"] or "").upper()
    status_map = {
        "DRAFT":                  ("DRAFT",        ""),
        "PENDING":                ("PENDING",      "ochre"),
        "RUNNING":                ("RUNNING",      "ochre"),
        "WAITING_SDS_VALIDATION": ("IN REVIEW",    "ochre"),
        "SDS_COMPLETE":           ("APPROVED",     "brass"),
        "COMPLETED":              ("APPROVED",     "brass"),
        "BUILD_COMPLETE":         ("BUILD DONE",   "sage"),
        "FAILED":                 ("FAILED",       "terra"),
    }
    label, css = status_map.get(status_raw, (status_raw, ""))
    
    # Hero rédactionnel — pour itération 1, valeurs minimales en dur.
    # Plus tard : titre + subtitle générés par Emma ou un YAML par projet.
    project_name = meta["project"]["name"] or f"Execution #{execution_id}"
    hero = {
        "title_html": f"{project_name},<br><em>structured</em><br>as a single brief.",
        "subtitle": (meta["project"]["description"]
                     or f"This document consolidates the deliverables of eight specialised "
                        f"agents — from Sophie's business requirements to Jordan's deployment "
                        f"pipeline — into a single, structured specification."),
    }
    
    # Build metadata
    now = datetime.now(timezone.utc)
    build = {
        "timestamp_human": now.strftime("%Y-%m-%d · %H:%M UTC"),
        "timestamp_iso": now.isoformat(),
    }
    
    return {
        "execution": meta["execution"],
        "project": meta["project"],
        "coverage": cov,
        # Solution Design : sous-clés exposées au top-level pour le partial
        "data_model": sd["data_model"],
        "security_model": sd["security_model"],
        "queues": sd["queues"],
        "reporting": sd["reporting"],
        "automation_design": sd["automation_design"],
        "integration_points": sd["integration_points"],
        "ui_components": sd["ui_components"],
        "uc_traceability": sd["uc_traceability"],
        "technical_considerations": sd["technical_considerations"],
        "risks": sd["risks"],
        "agents": agents,
        "deliverables": {"count": agents["deliverable_count"]},
        "toc": toc,
        "status": {"label": label, "css_class": css},
        "hero": hero,
        "build": build,
        # Lot A — sections 1-4
        "initial_needs": initial_needs,
        "br_data": brs,           # sec-2 : project_summary, business_requirements, constraints, assumptions
        "uc_data": ucs,           # sec-3 : use_cases, by_br
        "uc_digest": digest,      # sec-4 : synthesis_by_br, cross_cutting_concerns, recommendations, data_volume_estimates
        # Lot B — sections 5, 7, 8
        "as_is": as_is,           # sec-5 : organization, standard_objects
        "gap": gap,               # sec-7 : summary, gaps, migration_considerations, risk_areas
        # sec-8 reuse 'coverage' (deja expose)
        # Lot C — sections 9, 10
        "data_mig": data_mig,     # sec-9 : data_assessment, migration_strategy, field_mapping,
                                   #         data_cleansing_rules, validation_plan, rollback_strategy
        "training": training,     # sec-10 : audience_analysis, curriculum, training_approach,
                                   #          adoption_plan, resource_requirements, timeline, risks
    }
