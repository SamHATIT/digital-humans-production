"""
SDS Section Template — P9 Sectioned Generation

Defines the 11 SDS sections generated sequentially by SDSSectionWriter.
Each section maps to specific agent deliverables and has its own LLM prompt.

Sections:
  1. Executive Summary & Project Overview
  2. Business Requirements Analysis
  3. Use Case Specifications
  4. Current State Assessment (As-Is)
  5. Gap Analysis
  6. Solution Architecture & Design
  7. Work Breakdown Structure (WBS)
  8. Quality Assurance & Test Strategy (Elena)
  9. DevOps & Deployment Strategy (Jordan)
  10. Training & Change Management (Lucas) + Data Migration (Aisha)
  11. Consolidation: Intro, Conclusion, Cross-References, Table of Contents
"""

from typing import Dict, List, Any, Optional


# ============================================================================
# SECTION DEFINITIONS
# ============================================================================

SDS_SECTIONS = [
    {
        "id": "executive_summary",
        "number": 1,
        "title": "Executive Summary & Project Overview",
        "deliverable_keys": ["project_info", "business_requirements"],
        "artifact_keys": [],
        "agent_output_keys": [],
        "description": "High-level project overview, objectives, scope, and stakeholders.",
    },
    {
        "id": "business_requirements",
        "number": 2,
        "title": "Business Requirements Analysis",
        "deliverable_keys": ["business_requirements"],
        "artifact_keys": ["BR"],
        "agent_output_keys": [],
        "description": "Detailed business requirements with priorities and acceptance criteria.",
    },
    {
        "id": "use_cases",
        "number": 3,
        "title": "Use Case Specifications",
        "deliverable_keys": ["use_cases", "uc_digest"],
        "artifact_keys": ["USE_CASES", "UC_DIGEST"],
        "agent_output_keys": [],
        "description": "Detailed use case specifications derived from business requirements.",
    },
    {
        "id": "current_state",
        "number": 4,
        "title": "Current State Assessment (As-Is)",
        "deliverable_keys": [],
        "artifact_keys": ["AS_IS"],
        "agent_output_keys": [],
        "description": "Current Salesforce org analysis: objects, automations, integrations.",
    },
    {
        "id": "gap_analysis",
        "number": 5,
        "title": "Gap Analysis",
        "deliverable_keys": [],
        "artifact_keys": ["GAP", "COVERAGE"],
        "agent_output_keys": [],
        "description": "Gaps between current state and target solution, with coverage analysis.",
    },
    {
        "id": "solution_design",
        "number": 6,
        "title": "Solution Architecture & Design",
        "deliverable_keys": [],
        "artifact_keys": ["ARCHITECTURE"],
        "agent_output_keys": [],
        "description": "Target architecture, data model, integration design, security model.",
    },
    {
        "id": "wbs",
        "number": 7,
        "title": "Work Breakdown Structure",
        "deliverable_keys": [],
        "artifact_keys": ["WBS"],
        "agent_output_keys": [],
        "description": "Implementation phases, tasks, estimates, dependencies, milestones.",
    },
    {
        "id": "qa_strategy",
        "number": 8,
        "title": "Quality Assurance & Test Strategy",
        "deliverable_keys": [],
        "artifact_keys": [],
        "agent_output_keys": ["qa"],
        "description": "Test strategy, test cases, QA approach, UAT plan from Elena.",
    },
    {
        "id": "devops_strategy",
        "number": 9,
        "title": "DevOps & Deployment Strategy",
        "deliverable_keys": [],
        "artifact_keys": [],
        "agent_output_keys": ["devops"],
        "description": "CI/CD pipeline, deployment plan, environment strategy from Jordan.",
    },
    {
        "id": "training_data",
        "number": 10,
        "title": "Training, Change Management & Data Migration",
        "deliverable_keys": [],
        "artifact_keys": [],
        "agent_output_keys": ["trainer", "data"],
        "description": "Training plan from Lucas and data migration strategy from Aisha.",
    },
    {
        "id": "consolidation",
        "number": 11,
        "title": "Document Consolidation",
        "deliverable_keys": [],
        "artifact_keys": [],
        "agent_output_keys": [],
        "description": "Introduction, conclusion, cross-references, and table of contents.",
        "is_consolidation": True,
    },
]


# ============================================================================
# SYSTEM PROMPTS
# ============================================================================

SECTION_SYSTEM_PROMPT = """You are Emma, the Research Analyst for the Digital Humans platform.
You are writing one section of a Solution Design Specification (SDS) document.
Write in professional English. Use Markdown formatting.
Be thorough and precise — include ALL details from the source deliverables.
Do NOT truncate or summarize unless explicitly told to.
Do NOT add information that is not in the source deliverables.
Output ONLY the section content in Markdown (no JSON wrapper)."""

CONSOLIDATION_SYSTEM_PROMPT = """You are Emma, the Research Analyst for the Digital Humans platform.
You are finalizing a Solution Design Specification (SDS) document.
You will receive summaries of all 10 sections already written.
Your task is to produce:
1. A professional **Introduction** (project context, document purpose, audience)
2. A **Table of Contents** referencing all sections
3. Cross-reference notes between related sections
4. A **Conclusion** (key decisions, next steps, recommendations)

Output ONLY in Markdown. Be concise but professional."""


# ============================================================================
# PROMPT BUILDERS
# ============================================================================

def build_section_prompt(
    section: Dict,
    project_info: Dict,
    deliverable_data: Dict[str, Any],
) -> str:
    """
    Build the LLM prompt for a single SDS section.

    Args:
        section: Section definition from SDS_SECTIONS
        project_info: Project name, description, objectives
        deliverable_data: All relevant deliverable content for this section
    """
    parts = []
    parts.append(f"# SDS Section {section['number']}: {section['title']}\n")
    parts.append(f"**Project:** {project_info.get('name', 'N/A')}")
    parts.append(f"**Description:** {project_info.get('description', 'N/A')}\n")
    parts.append(f"## Instructions\n")
    parts.append(f"Write the complete \"{section['title']}\" section of the SDS document.")
    parts.append(f"Section purpose: {section['description']}")
    parts.append(f"Use ALL the source data below — do not truncate or omit anything.\n")

    # Add source data
    parts.append("## Source Data\n")
    for key, value in deliverable_data.items():
        if value:
            content_str = _serialize_content(value)
            if content_str:
                parts.append(f"### {key}\n```\n{content_str}\n```\n")

    return "\n".join(parts)


def build_consolidation_prompt(
    project_info: Dict,
    section_summaries: List[Dict[str, str]],
) -> str:
    """
    Build the LLM prompt for the consolidation section (#11).

    Args:
        project_info: Project name, description, objectives
        section_summaries: List of {number, title, summary} for sections 1-10
    """
    parts = []
    parts.append(f"# SDS Consolidation — Final Assembly\n")
    parts.append(f"**Project:** {project_info.get('name', 'N/A')}")
    parts.append(f"**Description:** {project_info.get('description', 'N/A')}\n")
    parts.append("## Section Summaries (1-10)\n")

    for s in section_summaries:
        parts.append(f"### Section {s['number']}: {s['title']}")
        parts.append(f"{s['summary']}\n")

    parts.append("## Instructions\n")
    parts.append("Produce the following in Markdown:")
    parts.append("1. **Introduction** — project context, document purpose, intended audience")
    parts.append("2. **Table of Contents** — referencing all 10 sections above")
    parts.append("3. **Cross-References** — note relationships between sections")
    parts.append("4. **Conclusion** — key decisions, recommendations, next steps")

    return "\n".join(parts)


# ============================================================================
# HELPERS
# ============================================================================

def _serialize_content(value: Any, max_chars: int = 0) -> str:
    """
    Serialize deliverable content to string for inclusion in prompt.
    max_chars=0 means no limit (P9: zero truncation).
    """
    import json

    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        text = json.dumps(value, indent=2, ensure_ascii=False)
    elif isinstance(value, list):
        text = json.dumps(value, indent=2, ensure_ascii=False)
    else:
        text = str(value)

    if max_chars > 0 and len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated]"
    return text
