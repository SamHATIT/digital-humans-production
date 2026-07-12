"""
Platform State directive injection (Gate 0bis - GUIDELINE_RAG_VEILLE_SF.md, layer 2).

Loads backend/config/platform_state.yaml (single source of truth) and builds
an agent-scoped PLATFORM STATE block appended to system prompts, mirroring
the FEAT-LANG-001 language-directive pattern in llm_service.

Scopes:
  full   -> code-gen/deploy agents: all directives + naming + retirements
  review -> QA reviewer: directives reformulated as a release-aware checklist
  short  -> architecture/analysis agents: naming + retirements only
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_YAML_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "platform_state.yaml",
)


@lru_cache(maxsize=1)
def _load_state() -> dict:
    try:
        with open(_YAML_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f).get("platform_state", {})
    except Exception as exc:  # never break an LLM call because of this file
        logger.error("platform_state.yaml unreadable (%s) - injection disabled", exc)
        return {}


def _scope_for(agent_type: str, state: dict) -> Optional[str]:
    scope = state.get("scope", {})
    at = (agent_type or "").lower()
    for name in ("full", "review", "short"):
        if at in [s.lower() for s in scope.get(name, [])]:
            return name
    return None


@lru_cache(maxsize=32)
def _build_block(scope_name: str) -> str:
    state = _load_state()
    release = state.get("reference_release", "?")
    api = state.get("api_version", "?")
    header = f"PLATFORM STATE (reference: Salesforce {release}, API {api}):"
    lines = []

    if scope_name == "full":
        lines += [f"- {d}" for d in state.get("directives", [])]
        lines += [f"- {n}" for n in state.get("naming", [])]
    elif scope_name == "review":
        lines.append("RELEASE-AWARE REVIEW CHECKLIST - flag as an issue any of the following in reviewed code:")
        lines.append("- Any without sharing class lacking a documented justification (with sharing is the default since Summer 26).")
        lines.append("- Redundant manual FLS/CRUD checks duplicating what user-mode DML already enforces, or unjustified AccessLevel.SYSTEM_MODE.")
        lines.append("- Any integration using SOAP login() or the Username-Password OAuth Flow (both retiring).")
        lines.append("- File downloads generated via data: URIs (blocked by Lightning Web Security).")
        lines.append("- Metadata/code targeting an API version below 67.0 without a declared project target_api_version.")
    elif scope_name == "short":
        lines += [f"- {n}" for n in state.get("naming", [])]

    rets = state.get("scheduled_retirements", [])
    if rets and scope_name in ("full", "short"):
        parts = [r.get("feature", "?") + " (" + r.get("release", "?") + ")" for r in rets]
        lines.append("Scheduled retirements to design around: " + "; ".join(parts))

    return header + "\n" + "\n".join(lines) if lines else ""


def apply_platform_state(system_prompt: Optional[str], agent_type: Optional[str]) -> Optional[str]:
    """Append the scoped PLATFORM STATE block to a system prompt. No-op if agent out of scope."""
    state = _load_state()
    if not state:
        return system_prompt
    scope_name = _scope_for(agent_type or "", state)
    if not scope_name:
        return system_prompt
    block = _build_block(scope_name)
    if not block:
        return system_prompt
    if system_prompt and "PLATFORM STATE (reference:" in system_prompt:
        return system_prompt  # idempotent - never inject twice
    return f"{system_prompt}\n\n{block}" if system_prompt else block
