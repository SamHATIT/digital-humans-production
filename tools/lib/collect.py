"""Collecte des données dynamiques consommées par les partials Jinja2.

6 fonctions publiques, une par partial. Contrat commun :

- Chacune retourne un ``dict`` (ou ``list``) sérialisable dont la forme est
  documentée dans sa docstring.
- En cas d'indisponibilité (fichier manquant, service down, import échoué),
  chacune lève ``BuildError`` avec un message explicite — on préfère un build
  qui échoue fort à un HTML silencieusement faux.
- Aucune fonction ne déclenche d'effet de bord (pas d'écriture, pas de commit).

Sources de vérité consommées :

- ``backend/config/agents_registry.yaml``       → ``collect_agents``
- ``backend/config/llm_routing.yaml``           → ``collect_llm_profiles``
- ChromaDB ``PersistentClient``                 → ``collect_rag_stats``
- ``systemctl list-units``                      → ``collect_services``
- ``docs/refonte/sources/problems.yaml``        → ``collect_problems``
- ``docs/refonte/sources/timeline.yaml``        → ``collect_timeline``
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_CONFIG = REPO_ROOT / "backend" / "config"
DOCS_SOURCES = REPO_ROOT / "docs" / "refonte" / "sources"
CHROMA_PATH = Path("/opt/digital-humans/rag/chromadb_data")


class BuildError(RuntimeError):
    """Échec non récupérable de la collecte — stoppe le build."""


# --------------------------------------------------------------------------
# 1. Agents — depuis backend/config/agents_registry.yaml
# --------------------------------------------------------------------------

# Métadonnées rédactionnelles pour les tableaux doc (pas dans le registry
# backend : ce sont des informations documentaires, pas runtime).
# Ordre = ordre d'affichage dans le tableau.
AGENT_DOC_META: list[dict[str, str]] = [
    {"id": "sophie",  "phase_sds": "1 — BR extraction",     "phase_build": "—"},
    {"id": "olivia",  "phase_sds": "2 — Use Cases",         "phase_build": "—"},
    {"id": "emma",    "phase_sds": "2.5 / 3.3 / 4.5 / 5",   "phase_build": "—"},
    {"id": "marcus",  "phase_sds": "3 — Architecture",      "phase_build": "—"},
    {"id": "elena",   "phase_sds": "4 — Test specs",        "phase_build": "—"},
    {"id": "jordan",  "phase_sds": "4 — DevOps specs",      "phase_build": "Deploy (toutes phases)"},
    {"id": "raj",     "phase_sds": "—",                     "phase_build": "1,4,5 — Model/Auto/Security"},
    {"id": "diego",   "phase_sds": "—",                     "phase_build": "2 — Business logic"},
    {"id": "zara",    "phase_sds": "—",                     "phase_build": "3 — UI components"},
    {"id": "aisha",   "phase_sds": "4 — Data specs",        "phase_build": "6 — Migration scripts"},
    {"id": "lucas",   "phase_sds": "4 — Training specs",    "phase_build": "—"},
]


def collect_agents() -> dict[str, Any]:
    """Charge ``agents_registry.yaml`` et l'enrichit avec ``AGENT_DOC_META``.

    Returns:
        ``{"agents": [{id, name, role, agent_type, tier, color, cost_estimate_usd,
        rag_collections, aliases, phase_sds, phase_build}, ...]}``
        dans l'ordre d'``AGENT_DOC_META`` (ordre d'affichage doc).

    Raises:
        BuildError: si le YAML est introuvable, mal formé, ou référence un agent
            inconnu de ``AGENT_DOC_META`` (garde-fou : si on ajoute un agent
            dans le registry, on doit aussi l'ajouter ici, sinon il sort du tableau doc).
    """
    path = BACKEND_CONFIG / "agents_registry.yaml"
    if not path.exists():
        raise BuildError(f"agents_registry introuvable : {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise BuildError(f"agents_registry YAML invalide : {e}") from e

    registry = raw.get("agents") or {}
    if not registry:
        raise BuildError("agents_registry.yaml : clé 'agents' vide ou absente")

    result = []
    for meta in AGENT_DOC_META:
        aid = meta["id"]
        if aid not in registry:
            raise BuildError(
                f"Agent '{aid}' listé dans AGENT_DOC_META mais absent du registry"
            )
        entry = registry[aid]
        result.append({
            "id": aid,
            "name": entry.get("name", aid.capitalize()),
            "role": entry.get("role", ""),
            "role_fr": entry.get("role_fr", entry.get("role", "")),
            "agent_type": entry.get("agent_type", ""),
            "tier": entry.get("tier", ""),
            "complexity": entry.get("complexity", ""),
            "color": entry.get("color", "blue"),
            "cost_estimate_usd": entry.get("cost_estimate_usd", 0.0),
            "rag_collections": entry.get("rag_collections", []) or [],
            "aliases": entry.get("aliases", []) or [],
            "phase_sds": meta["phase_sds"],
            "phase_build": meta["phase_build"],
        })
    return {"agents": result}


# --------------------------------------------------------------------------
# 2. LLM profiles — depuis backend/config/llm_routing.yaml
# --------------------------------------------------------------------------

# Prix par modèle (USD per M tokens, input/output) — miroir de budget_service.
# Conservé ici plutôt que dans le YAML routing pour isoler la donnée "doc".
MODEL_PRICING: dict[str, dict[str, float]] = {
    "anthropic/claude-opus":    {"in": 15.0, "out": 75.0, "display": "Claude Opus 4.6"},
    "anthropic/claude-sonnet":  {"in":  3.0, "out": 15.0, "display": "Claude Sonnet 4.5"},
    "anthropic/claude-haiku":   {"in":  1.0, "out":  5.0, "display": "Claude Haiku"},
    "local/mixtral":            {"in":  0.0, "out":  0.0, "display": "Mixtral 8x7B (local)"},
    "local/mistral":            {"in":  0.0, "out":  0.0, "display": "Mistral 7B (local)"},
    "openai/gpt-4o-mini":       {"in":  0.15,"out":  0.60,"display": "GPT-4o mini"},
}


def collect_llm_profiles() -> dict[str, Any]:
    """Charge ``llm_routing.yaml`` et reconstruit la vue par tier pour le profile actif.

    Note: on considère ``active_profile = default_profile`` si la var d'env
    ``DH_DEPLOYMENT_PROFILE`` n'est pas résolue dans le fichier (``${...}`` non
    substitué). Pour la doc, c'est toujours le ``default_profile`` qui compte.

    Returns:
        ``{"active_profile": "cloud", "build_enabled": True, "tiers": [
            {"name": "orchestrator", "model_alias": "...", "model_display": "...",
             "pricing_in": float, "pricing_out": float,
             "agent_types": ["pm", "architect", ...]},
             ...
        ]}``
    """
    path = BACKEND_CONFIG / "llm_routing.yaml"
    if not path.exists():
        raise BuildError(f"llm_routing introuvable : {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise BuildError(f"llm_routing YAML invalide : {e}") from e

    default_profile = raw.get("default_profile", "cloud")
    profiles = raw.get("profiles") or {}
    if default_profile not in profiles:
        raise BuildError(
            f"Profile '{default_profile}' absent de profiles. "
            f"Disponibles : {list(profiles.keys())}"
        )
    profile = profiles[default_profile]
    tier_map = raw.get("agent_tier_map") or {}

    # Grouper agent_types par tier
    per_tier: dict[str, list[str]] = {}
    for agent_type, tier_name in tier_map.items():
        per_tier.setdefault(tier_name, []).append(agent_type)

    tiers = []
    # Ordre stable : orchestrator, worker, puis tout le reste
    ordered = ["orchestrator", "worker"] + [
        t for t in per_tier if t not in ("orchestrator", "worker")
    ]
    for tier_name in ordered:
        model_alias = profile.get(tier_name)
        if not model_alias:
            # Tier présent dans agent_tier_map mais pas dans le profile → skip
            continue
        pricing = MODEL_PRICING.get(model_alias, {})
        tiers.append({
            "name": tier_name,
            "model_alias": model_alias,
            "model_display": pricing.get("display", model_alias),
            "pricing_in": pricing.get("in"),
            "pricing_out": pricing.get("out"),
            "agent_types": sorted(set(per_tier.get(tier_name, []))),
        })

    return {
        "active_profile": default_profile,
        "build_enabled": bool(profile.get("build_enabled", True)),
        "tiers": tiers,
    }


# --------------------------------------------------------------------------
# 3. RAG stats — probe live ChromaDB
# --------------------------------------------------------------------------

# Mapping editorial collection → embedding type et agents consommateurs.
# Ne vient pas de ChromaDB : c'est une vue documentaire qu'on maintient ici.
RAG_COLLECTION_META: dict[str, dict[str, Any]] = {
    "technical_collection":  {"embedding": "OpenAI", "agents": ["Marcus", "Jordan", "Raj", "Elena", "Aisha", "Diego", "Zara"]},
    "operations_collection": {"embedding": "OpenAI", "agents": ["Marcus", "Olivia", "Jordan", "Raj", "Elena", "Aisha", "Lucas"]},
    "business_collection":   {"embedding": "OpenAI", "agents": ["Marcus", "Olivia", "Sophie", "Lucas"]},
    "apex_collection":       {"embedding": "Nomic",  "agents": ["Diego", "Elena"]},
    "lwc_collection":        {"embedding": "Nomic",  "agents": ["Zara"]},
    "china_collection":      {"embedding": "OpenAI", "agents": ["Marcus", "Olivia"], "note": "projets region=cn"},
}


def collect_rag_stats() -> dict[str, Any]:
    """Probe ChromaDB et retourne les comptages live par collection.

    Returns:
        ``{"collections": [{"name", "count", "embedding", "agents", "note"}],
           "total_chunks": int, "probe_ok": True}``

    Raises:
        BuildError: si ChromaDB n'est pas accessible ou renvoie une erreur.
            La doc DOIT refléter l'état réel — un RAG down est une info, pas
            une raison de générer un comptage obsolète silencieusement.
    """
    try:
        import chromadb
    except ImportError as e:
        raise BuildError(
            "Module 'chromadb' indisponible dans cet environnement Python. "
            "Activer backend/venv avant de lancer build_docs."
        ) from e

    if not CHROMA_PATH.exists():
        raise BuildError(f"CHROMA_PATH inexistant : {CHROMA_PATH}")

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        live_collections = client.list_collections()
    except Exception as e:
        raise BuildError(f"ChromaDB probe échoué : {e}") from e

    collections = []
    total = 0
    # Itérer sur RAG_COLLECTION_META pour garder un ordre stable ; mentionner
    # séparément les collections "orphelines" (live mais sans entrée meta).
    live_by_name = {c.name: c for c in live_collections}
    seen_live: set[str] = set()

    for name, meta in RAG_COLLECTION_META.items():
        entry = {
            "name": name,
            "embedding": meta["embedding"],
            "agents": meta["agents"],
            "note": meta.get("note", ""),
            "count": None,
            "present": False,
        }
        if name in live_by_name:
            try:
                entry["count"] = live_by_name[name].count()
                entry["present"] = True
                total += entry["count"]
                seen_live.add(name)
            except Exception as e:
                entry["count"] = None
                entry["note"] = f"erreur count() : {e}"
        collections.append(entry)

    orphans = [c.name for c in live_collections if c.name not in seen_live]

    return {
        "collections": collections,
        "total_chunks": total,
        "orphan_collections": orphans,
        "probe_ok": True,
    }


# --------------------------------------------------------------------------
# 4. Services — systemctl list-units + mapping editorial
# --------------------------------------------------------------------------

# Services à afficher dans le tableau infra, dans cet ordre. ``unit`` correspond
# au nom systemd (sans ``.service``). ``kind=docker`` pour les containers qu'on
# interroge via ``docker inspect`` plutôt que systemctl.
INFRA_SERVICES: list[dict[str, str]] = [
    {"label": "Backend API",  "unit": "digital-humans-backend",  "port": "8002",    "kind": "systemd"},
    {"label": "ARQ Worker",   "unit": "digital-humans-worker",   "port": "—",       "kind": "systemd"},
    {"label": "Frontend",     "unit": "digital-humans-frontend", "port": "3000",    "kind": "systemd"},
    {"label": "PostgreSQL",   "unit": "postgresql",              "port": "5432",    "kind": "systemd"},
    {"label": "Redis",        "unit": "redis-server",            "port": "6379",    "kind": "systemd"},
    {"label": "ChromaDB",     "unit": "",                        "port": "—",       "kind": "embedded", "note": "PersistentClient"},
    {"label": "Ollama",       "unit": "ollama",                  "port": "11434",   "kind": "systemd"},
    {"label": "Nginx",        "unit": "nginx",                   "port": "80/443",  "kind": "systemd"},
    {"label": "Ghost CMS",    "unit": "ghost-blog",              "port": "2368",    "kind": "docker"},
    {"label": "N8N",          "unit": "n8n",                     "port": "5678",    "kind": "systemd"},
    {"label": "Open WebUI",   "unit": "open-webui",              "port": "3200→8080","kind": "docker"},
]


def _systemctl_is_active(unit: str) -> str:
    """Retourne ``active`` / ``inactive`` / ``failed`` / ``unknown``."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", unit],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def _docker_is_running(container: str) -> str:
    """Retourne ``active`` / ``stopped`` / ``missing`` / ``unknown``."""
    try:
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return "missing"
        return "active" if r.stdout.strip() == "true" else "stopped"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def collect_services() -> dict[str, Any]:
    """Probe l'état live de chaque service de ``INFRA_SERVICES``.

    Returns:
        ``{"services": [{"label", "unit", "port", "kind", "status", "note"}, ...]}``

        ``status`` ∈ {"active", "inactive", "failed", "stopped", "missing",
        "unknown", "embedded"}. Le template se charge du mapping vers un tag visuel.
    """
    services = []
    for svc in INFRA_SERVICES:
        status = "unknown"
        if svc["kind"] == "systemd":
            status = _systemctl_is_active(svc["unit"])
        elif svc["kind"] == "docker":
            status = _docker_is_running(svc["unit"])
        elif svc["kind"] == "embedded":
            status = "embedded"
        services.append({
            "label": svc["label"],
            "unit": svc["unit"],
            "port": svc["port"],
            "kind": svc["kind"],
            "status": status,
            "note": svc.get("note", ""),
        })
    return {"services": services}


# --------------------------------------------------------------------------
# 5. Problems — depuis docs/refonte/sources/problems.yaml
# --------------------------------------------------------------------------

def collect_problems() -> dict[str, Any]:
    """Charge ``problems.yaml`` et calcule les compteurs par statut.

    Returns:
        ``{"problems": [...], "stats": {"total", "fixed", "partial", "planned"},
           "by_status": {"fixed": [...], "partial": [...], "planned": [...]}}``
        Chaque problème conserve sa structure d'origine (id, title, status, severity,
        fixed_in[], remaining, description).
    """
    path = DOCS_SOURCES / "problems.yaml"
    if not path.exists():
        raise BuildError(f"problems.yaml introuvable : {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise BuildError(f"problems.yaml invalide : {e}") from e

    problems = raw.get("problems") or []
    if not problems:
        raise BuildError("problems.yaml : liste 'problems' vide")

    by_status: dict[str, list] = {"fixed": [], "partial": [], "planned": []}
    for p in problems:
        st = p.get("status", "planned")
        if st not in by_status:
            raise BuildError(f"{p.get('id')}: statut inconnu '{st}'")
        by_status[st].append(p)

    stats = {
        "total": len(problems),
        "fixed": len(by_status["fixed"]),
        "partial": len(by_status["partial"]),
        "planned": len(by_status["planned"]),
    }

    return {
        "problems": problems,
        "stats": stats,
        "by_status": by_status,
    }


# --------------------------------------------------------------------------
# 6. Timeline — depuis docs/refonte/sources/timeline.yaml
# --------------------------------------------------------------------------

def collect_timeline() -> dict[str, Any]:
    """Charge ``timeline.yaml`` — SSoT rédactionnelle pour le journal.

    Le YAML contient des entrées éditoriales (synthèses condensées, emojis,
    HTML inline dans ``description``). Ce n'est pas un dérivé automatique du
    CHANGELOG car le ton et le regroupement sont rédactionnels.

    Returns:
        ``{"entries": [{"label", "date", "status", "title", "description"}, ...]}``
        dans l'ordre du YAML (chronologique ascendant).
    """
    path = DOCS_SOURCES / "timeline.yaml"
    if not path.exists():
        raise BuildError(f"timeline.yaml introuvable : {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise BuildError(f"timeline.yaml invalide : {e}") from e

    entries = raw.get("entries") or []
    if not entries:
        raise BuildError("timeline.yaml : liste 'entries' vide")

    valid_status = {"done", "active", "planned"}
    for i, e in enumerate(entries):
        st = e.get("status")
        if st not in valid_status:
            raise BuildError(
                f"timeline.yaml entry #{i}: status '{st}' invalide (attendu : {valid_status})"
            )
    return {"entries": entries}
