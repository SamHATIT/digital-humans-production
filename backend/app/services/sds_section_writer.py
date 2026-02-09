"""
SDS Section Writer - Sectioned SDS generation with agent list enforcement.

Provides the DIGITAL_HUMANS_AGENTS constant and UC sub-batching for Phase 5.
Used by pm_orchestrator_service_v2.py for SDS generation.
"""

import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# AGENT LIST CONSTANT — Source of truth for all SDS generation prompts
# ============================================================================

DIGITAL_HUMANS_AGENTS = """
The Digital Humans platform has exactly 11 specialized agents:
- Sophie (PM/Project Manager) — orchestration, project management
- Olivia (BA/Business Analyst) — use cases, requirements analysis
- Emma (Research Analyst) — coverage validation, research
- Marcus (Architect/Solution Architect) — architecture, data model, WBS
- Diego (Apex Developer) — Apex code, triggers, batch jobs
- Zara (LWC Developer) — Lightning Web Components, UI
- Jordan (DevOps Engineer) — CI/CD, deployment, environments
- Elena (QA Specialist) — test strategy, test cases, quality
- Raj (Admin/Salesforce Admin) — configuration, permissions, security
- Aisha (Data Specialist) — data migration, data model, ETL
- Lucas (Trainer) — training, documentation, change management

IMPORTANT: Only reference these 11 agents by their exact names. Never invent other agent names.
"""

# Sub-batch size for Section 3 (Use Case Specifications)
UC_BATCH_SIZE = 35  # ~35 UCs ~ 50K tokens of context


def get_section_system_prompt(section_name: str = "") -> str:
    """Build a system prompt that includes the agent list for any SDS section."""
    return f"""You are a senior Salesforce consultant writing a professional SDS (Solution Design Specification).

{DIGITAL_HUMANS_AGENTS}

Write in a clear, professional tone. Be specific and actionable.
Only reference the 11 agents listed above — never invent agent names.
{"Section: " + section_name if section_name else ""}"""
