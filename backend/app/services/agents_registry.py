"""Single source of truth for the 11 Digital Humans agents.

This module replaces 6 legacy dicts that described agents with diverging
conventions (AGENT_CONFIG, AGENT_COLLECTIONS, CATEGORY_AGENT_MAP,
agent_artifact_needs, AGENT_CHAT_PROFILES, AGENT_COSTS).

All agent metadata lives in ``backend/config/agents_registry.yaml``. This
module exposes typed accessors over that YAML so consumers never need to
know the file format.

Canonical agent IDs are character first names (``sophie``, ``olivia``,
``marcus`` ...). Any legacy code (``pm``, ``ba``, ``apex_developer``,
``qa_tester`` ...) is declared as an alias and normalised via
:func:`resolve_agent_id`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.config import settings

REGISTRY_PATH: Path = settings.BACKEND_ROOT / "config" / "agents_registry.yaml"


class AgentNotFoundError(KeyError):
    """Raised when an agent id/alias cannot be resolved."""


def _load_registry() -> Dict[str, Any]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Agents registry not found: {REGISTRY_PATH}")
    with REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    agents = data.get("agents") or {}
    if not isinstance(agents, dict) or not agents:
        raise ValueError("agents_registry.yaml is missing the `agents` section")
    return data


@lru_cache(maxsize=1)
def _registry() -> Dict[str, Any]:
    return _load_registry()


@lru_cache(maxsize=1)
def _alias_index() -> Dict[str, str]:
    """Map every known alias (and canonical id) to its canonical id."""
    index: Dict[str, str] = {}
    for agent_id, agent in _registry()["agents"].items():
        index[agent_id] = agent_id
        for alias in agent.get("aliases", []) or []:
            index[str(alias).lower()] = agent_id
        agent_type = agent.get("agent_type")
        if agent_type:
            index.setdefault(str(agent_type).lower(), agent_id)
        name = agent.get("name")
        if name:
            index.setdefault(str(name).lower(), agent_id)
    return index


def reload() -> None:
    """Invalidate caches. Useful for tests or hot reload."""
    _registry.cache_clear()
    _alias_index.cache_clear()


def resolve_agent_id(agent_id_or_alias: str) -> str:
    """Return canonical id for any alias/name. Raises :class:`AgentNotFoundError`."""
    if not agent_id_or_alias:
        raise AgentNotFoundError("empty agent id")
    key = str(agent_id_or_alias).lower()
    index = _alias_index()
    if key not in index:
        raise AgentNotFoundError(f"Unknown agent id or alias: {agent_id_or_alias!r}")
    return index[key]


def try_resolve_agent_id(agent_id_or_alias: Optional[str]) -> Optional[str]:
    """Non-raising variant — returns None when the alias is unknown."""
    if not agent_id_or_alias:
        return None
    try:
        return resolve_agent_id(agent_id_or_alias)
    except AgentNotFoundError:
        return None


def get_agent(agent_id_or_alias: str) -> Dict[str, Any]:
    """Return the full agent record (incl. canonical ``id``)."""
    canonical = resolve_agent_id(agent_id_or_alias)
    record = dict(_registry()["agents"][canonical])
    record["id"] = canonical
    return record


def list_agents() -> List[Dict[str, Any]]:
    """Return all agents in registry order, each enriched with its ``id``."""
    agents = []
    for agent_id, agent in _registry()["agents"].items():
        record = dict(agent)
        record["id"] = agent_id
        agents.append(record)
    return agents


def list_agent_ids() -> List[str]:
    return list(_registry()["agents"].keys())


# ---------------------------------------------------------------------------
# RAG collections — replaces rag_service.AGENT_COLLECTIONS
# ---------------------------------------------------------------------------

def get_rag_collections(agent_id_or_alias: Optional[str]) -> List[str]:
    """Return the RAG collections for an agent (default fallback for unknown)."""
    canonical = try_resolve_agent_id(agent_id_or_alias)
    if canonical is None:
        return list(_registry().get("default_rag_collections") or [])
    collections = _registry()["agents"][canonical].get("rag_collections")
    if not collections:
        return list(_registry().get("default_rag_collections") or [])
    return list(collections)


# ---------------------------------------------------------------------------
# Change-Request category map — replaces CATEGORY_AGENT_MAP
# ---------------------------------------------------------------------------

def get_agents_for_cr_category(category: str) -> List[str]:
    """Return the legacy agent codes (``ba``, ``architect`` ...) impacted by a CR category.

    Values returned are the ``agent_type`` of each impacted agent so callers
    stay compatible with existing CR code that expects short codes.
    """
    if not category:
        return []
    cat = str(category).lower()
    overrides = _registry().get("cr_category_overrides") or {}
    if cat in overrides:
        canonicals = overrides[cat]
    else:
        canonicals = [
            agent_id
            for agent_id, agent in _registry()["agents"].items()
            if cat in (agent.get("cr_categories") or [])
        ]
    out: List[str] = []
    for cid in canonicals:
        agent = _registry()["agents"].get(cid)
        if not agent:
            continue
        code = agent.get("agent_type") or cid
        if code not in out:
            out.append(code)
    return out


def get_cost_estimate(agent_id_or_alias: str) -> float:
    """Return the typical USD cost estimate for one run of an agent (fallback 0.0)."""
    canonical = try_resolve_agent_id(agent_id_or_alias)
    if canonical is None:
        return 0.0
    return float(_registry()["agents"][canonical].get("cost_estimate_usd") or 0.0)


# ---------------------------------------------------------------------------
# Artifact needs — replaces artifact_service.agent_artifact_needs
# ---------------------------------------------------------------------------

def get_artifact_needs(agent_id_or_alias: str) -> List[str]:
    """Return the artifact types an agent needs as context (may be empty)."""
    canonical = try_resolve_agent_id(agent_id_or_alias)
    if canonical is None:
        return []
    return list(_registry()["agents"][canonical].get("artifact_needs") or [])


# ---------------------------------------------------------------------------
# HITL chat profiles — replaces AGENT_CHAT_PROFILES
# ---------------------------------------------------------------------------

def get_chat_profile(agent_id_or_alias: str) -> Dict[str, Any]:
    """Return a HITL chat profile (name/role/color/system_prompt/...).

    The returned dict is safe to mutate — it is a fresh copy on each call.
    """
    agent = get_agent(agent_id_or_alias)
    chat = dict(agent.get("chat") or {})
    profile: Dict[str, Any] = {
        "agent_id": agent["id"],
        "name": agent.get("name", agent["id"].title()),
        "role": agent.get("role", ""),
        "agent_type": agent.get("agent_type", agent["id"]),
        "color": agent.get("color", "slate"),
        "deliverable_types": list(agent.get("deliverable_types") or []),
        "system_prompt": chat.get("system_prompt", "").strip(),
        "enabled": bool(chat.get("enabled", True)),
        "always_available": bool(chat.get("always_available", False)),
    }
    return profile


def iter_chat_profiles() -> List[Dict[str, Any]]:
    """Return chat profiles for every enabled agent."""
    profiles = []
    for agent_id in list_agent_ids():
        profile = get_chat_profile(agent_id)
        if profile["enabled"]:
            profiles.append(profile)
    return profiles


# ---------------------------------------------------------------------------
# AGENT_CONFIG replacement — display / script / tier metadata
# ---------------------------------------------------------------------------

def get_script_name(agent_id_or_alias: str) -> str:
    return get_agent(agent_id_or_alias).get("script", "")


def get_display_name(agent_id_or_alias: str) -> str:
    agent = get_agent(agent_id_or_alias)
    name = agent.get("name", agent["id"].title())
    role = agent.get("role_fr") or agent.get("role") or ""
    return f"{name} ({role})" if role else name


def get_tier(agent_id_or_alias: str) -> str:
    return get_agent(agent_id_or_alias).get("tier", "worker")


def get_complexity(agent_id_or_alias: str) -> str:
    return get_agent(agent_id_or_alias).get("complexity", "complex")
