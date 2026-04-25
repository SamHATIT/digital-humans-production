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

import re
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

# Note : pricing et display_name viennent désormais directement de
# llm_routing.yaml (sections "pricing" et providers.<p>.models.<m>.display_name).
# Le dict MODEL_PRICING qui était ici dupliquait l'info et a divergé.


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

    # Pricing : section "pricing" du YAML (key = "<provider>/<model_alias>")
    yaml_pricing = raw.get("pricing") or {}
    # Providers : pour récupérer display_name de chaque modèle
    providers = raw.get("providers") or {}

    def _resolve_display(provider_alias: str) -> str:
        """Résoud "anthropic/claude-opus" → display_name depuis le YAML."""
        if "/" not in provider_alias:
            return provider_alias
        prov_name, m_alias = provider_alias.split("/", 1)
        m = (providers.get(prov_name, {}).get("models") or {}).get(m_alias, {})
        return m.get("display_name") or m.get("model_id") or m_alias

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
        pricing = yaml_pricing.get(model_alias, {})
        tiers.append({
            "name": tier_name,
            "model_alias": model_alias,
            "model_display": _resolve_display(model_alias),
            "pricing_in": pricing.get("input"),
            "pricing_out": pricing.get("output"),
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


# --------------------------------------------------------------------------
# 7. Database tables — live PostgreSQL + SSoT YAML rédactionnelle
# --------------------------------------------------------------------------

def _load_db_url() -> str:
    """Lit DATABASE_URL depuis backend/.env. Retourne l'URL ou raise BuildError."""
    env_path = REPO_ROOT / "backend" / ".env"
    if not env_path.exists():
        raise BuildError(f"backend/.env introuvable : {env_path}")
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            if url:
                return url
    raise BuildError("DATABASE_URL absent de backend/.env")


def collect_database_tables() -> dict[str, Any]:
    """Liste les tables Postgres groupées (YAML éditorial) + comptages live.

    Croisement :
      - ``database_tables.yaml`` définit l'ordre, le regroupement et les rôles
      - ``information_schema`` fournit le nombre de colonnes et la liste des colonnes

    Garde-fous :
      - Chaque table du YAML DOIT exister en DB (sinon BuildError)
      - Chaque table live absente du YAML est listée comme "orpheline"

    Returns:
        ``{"groups": [{id, label, tables: [{name, col_count, role, columns: [{name, type}]}]}],
          "total_tables": int, "orphan_tables": [str]}``
    """
    path = DOCS_SOURCES / "database_tables.yaml"
    if not path.exists():
        raise BuildError(f"database_tables.yaml introuvable : {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise BuildError(f"database_tables.yaml invalide : {e}") from e

    yaml_groups = raw.get("groups") or []
    if not yaml_groups:
        raise BuildError("database_tables.yaml : liste 'groups' vide")

    # Live probe via psycopg2 (disponible dans le venv backend)
    try:
        import psycopg2
    except ImportError as e:
        raise BuildError(
            "Module 'psycopg2' indisponible. Activer backend/venv avant build_docs."
        ) from e

    db_url = _load_db_url()
    # psycopg2 n'accepte pas le préfixe postgresql+psycopg2:// (c'est du SQLAlchemy)
    if db_url.startswith("postgresql+psycopg2://"):
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://", 1)

    try:
        conn = psycopg2.connect(db_url)
    except Exception as e:
        raise BuildError(f"Connexion Postgres échouée : {e}") from e

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name,
                       (SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = t.table_name
                          AND table_schema = 'public') AS col_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            live_tables = {row[0]: row[1] for row in cur.fetchall()}

            # Pour chaque table du YAML, on récupère aussi les colonnes (detail row)
            yaml_table_names = {
                tname
                for g in yaml_groups
                for tname in (g.get("tables") or {}).keys()
            }
            columns_by_table: dict[str, list] = {}
            if yaml_table_names:
                cur.execute("""
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = ANY(%s)
                    ORDER BY table_name, ordinal_position
                """, (list(yaml_table_names),))
                for tname, cname, ctype in cur.fetchall():
                    columns_by_table.setdefault(tname, []).append(
                        {"name": cname, "type": ctype}
                    )
    finally:
        conn.close()

    # Build output : pour chaque group, annotation col_count + columns
    groups_out = []
    yaml_all_tables: set[str] = set()
    for g in yaml_groups:
        tables_dict = g.get("tables") or {}
        tables_out = []
        for tname, role in tables_dict.items():
            yaml_all_tables.add(tname)
            if tname not in live_tables:
                raise BuildError(
                    f"Table '{tname}' listée dans database_tables.yaml "
                    f"(group={g.get('id')}) mais absente de la DB."
                )
            tables_out.append({
                "name": tname,
                "col_count": live_tables[tname],
                "role": role,
                "columns": columns_by_table.get(tname, []),
            })
        groups_out.append({
            "id": g.get("id", ""),
            "label": g.get("label", g.get("id", "")),
            "tables": tables_out,
        })

    orphans = sorted(set(live_tables) - yaml_all_tables)

    return {
        "groups": groups_out,
        "total_tables": len(live_tables),
        "orphan_tables": orphans,
    }


# --------------------------------------------------------------------------
# 8. Frontend pages — scan App.tsx + YAML rédactionnelle
# --------------------------------------------------------------------------

def collect_frontend_pages() -> dict[str, Any]:
    """Extrait les routes React de ``frontend/src/App.tsx`` et merge avec YAML.

    Garde-fou : chaque composant mentionné par une Route DOIT avoir une entrée
    dans ``frontend_pages.yaml`` (sinon BuildError). Inversement, les entrées
    YAML non utilisées par une Route sont listées comme "orphelines".

    Returns:
        ``{"pages": [{component, routes: [str], description, access, file}],
          "total_routes": int, "orphan_yaml": [str]}``
    """
    app_tsx = REPO_ROOT / "frontend" / "src" / "App.tsx"
    if not app_tsx.exists():
        raise BuildError(f"frontend/src/App.tsx introuvable : {app_tsx}")
    yaml_path = DOCS_SOURCES / "frontend_pages.yaml"
    if not yaml_path.exists():
        raise BuildError(f"frontend_pages.yaml introuvable : {yaml_path}")
    try:
        yaml_raw = yaml.safe_load(yaml_path.read_text())
    except yaml.YAMLError as e:
        raise BuildError(f"frontend_pages.yaml invalide : {e}") from e
    pages_meta = yaml_raw.get("pages") or {}

    source = app_tsx.read_text()
    # Regex robuste : capture path et le nom du composant (premier <Component ...)
    # Tolère saut de ligne entre path et element grâce à re.DOTALL.
    route_pattern = re.compile(
        r'<Route\s+path="([^"]+)"\s+element=\{\s*<([A-Z][A-Za-z0-9]*)',
        re.DOTALL,
    )
    # Cas multi-ligne où element est un wrapper : <Route ... element={<ProtectedRoute><Page/></ProtectedRoute>}
    # Le regex ci-dessus capture ProtectedRoute. On refait un second pass pour
    # extraire la VRAIE page dans le children.
    routes: list[tuple[str, str]] = []
    for m in re.finditer(
        r'<Route\s+path="([^"]+)"\s+element=\{([^}]+)\}',
        source, re.DOTALL,
    ):
        path_val = m.group(1)
        element = m.group(2)
        # Premier <ComponentName> qui n'est PAS ProtectedRoute ni Navigate
        for cm in re.finditer(r'<([A-Z][A-Za-z0-9]*)', element):
            name = cm.group(1)
            if name not in ("ProtectedRoute", "Navigate"):
                routes.append((path_val, name))
                break
        else:
            # Cas du fallback Navigate — on skippe
            if path_val == "*":
                continue

    # Grouper par composant (un composant peut avoir plusieurs routes)
    by_component: dict[str, list[str]] = {}
    for path_val, comp in routes:
        by_component.setdefault(comp, []).append(path_val)

    # Vérification YAML ↔ code
    components_in_code = set(by_component.keys())
    components_in_yaml = set(pages_meta.keys())
    missing_in_yaml = components_in_code - components_in_yaml
    if missing_in_yaml:
        raise BuildError(
            f"Composants présents dans App.tsx mais absents de frontend_pages.yaml : "
            f"{sorted(missing_in_yaml)}"
        )
    orphan_yaml = sorted(components_in_yaml - components_in_code)

    # Construire output, dans l'ordre du YAML pour la stabilité d'affichage
    pages_out = []
    for comp, meta in pages_meta.items():
        if comp not in by_component:
            continue  # orphelin — on l'a listé séparément
        file_path = f"frontend/src/pages/{comp}.tsx"
        pages_out.append({
            "component": comp,
            "routes": by_component[comp],
            "description": meta.get("description", ""),
            "access": meta.get("access", "protected"),
            "file": file_path,
        })

    return {
        "pages": pages_out,
        "total_routes": len(routes),
        "orphan_yaml": orphan_yaml,
    }


# --------------------------------------------------------------------------
# 9. API endpoints — AST parse des routes FastAPI + mapping prefix
# --------------------------------------------------------------------------

# Groupes éditoriaux pour regrouper les fichiers route sous un label lisible.
# Une route non mappée tombe dans le groupe "other".
API_FILE_GROUPS: dict[str, str] = {
    "projects": "Projets",
    "pm_orchestrator": "Orchestrateur (legacy, à migrer)",
    "orchestrator/project_routes": "Orchestrateur — projets",
    "orchestrator/execution_routes": "Orchestrateur — exécutions SDS",
    "orchestrator/build_routes": "Orchestrateur — phase BUILD",
    "orchestrator/build_executor": "Orchestrateur — exécuteur BUILD",
    "orchestrator/validation_gate_routes": "Orchestrateur — HITL gates",
    "orchestrator/retry_routes": "Orchestrateur — retry",
    "orchestrator/chat_ws_routes": "Orchestrateur — WebSocket chat",
    "hitl_routes": "HITL — chat, métriques, change requests",
    "deliverables": "Deliverables",
    "business_requirements": "Business Requirements",
    "change_requests": "Change Requests",
    "sds_versions": "SDS — versioning",
    "project_chat": "Chat projet",
    "agent_tester": "Agent Tester",
    "audit": "Audit logs",
    "auth": "Authentification",
    "config": "Configuration",
    "analytics": "Analytics",
    "artifacts": "Artifacts",
    "deployment": "Déploiement Salesforce",
    "documents": "Documents",
    "environments": "Environnements Salesforce",
    "leads": "Leads (marketing)",
    "blog": "Blog (marketing)",
    "subscription": "Abonnements",
    "wizard": "Wizard projet",
    "quality_gates": "Quality Gates BUILD",
    "quality_dashboard": "Quality Dashboard",
}

API_ROUTES_DIRS = [
    REPO_ROOT / "backend" / "app" / "api" / "routes",
    REPO_ROOT / "backend" / "app" / "api",  # contient audit.py
]

API_MAIN = REPO_ROOT / "backend" / "app" / "main.py"


def _parse_main_prefixes() -> dict[str, str]:
    """Parse backend/app/main.py pour extraire les prefixes include_router.

    Returns:
        dict {module_name: prefix}. Module = dernier segment d'import
        (ex: 'projects', 'hitl_routes', 'orchestrator').
    """
    if not API_MAIN.exists():
        raise BuildError(f"main.py introuvable : {API_MAIN}")
    source = API_MAIN.read_text()
    prefixes: dict[str, str] = {}
    api_prefix = "/api/v1"  # settings.API_V1_PREFIX — constante connue

    # Pattern : include_router(module.router, prefix=...)
    # prefix peut être settings.API_V1_PREFIX, f"...", "..." ou absent.
    pattern = re.compile(
        r"include_router\(\s*([a-z_]+)\.router"
        r"(?:,\s*prefix\s*=\s*([^,\)]+))?"
        r"[^)]*\)",
        re.DOTALL,
    )
    for m in pattern.finditer(source):
        mod = m.group(1)
        raw_prefix = (m.group(2) or "").strip()
        if not raw_prefix:
            prefix = ""
        elif raw_prefix == "settings.API_V1_PREFIX":
            prefix = api_prefix
        elif raw_prefix.startswith('f"') or raw_prefix.startswith("f'"):
            # f-string : remplace settings.API_V1_PREFIX et les {} simples
            p = raw_prefix[2:-1]  # retire f" ... "
            p = p.replace("{settings.API_V1_PREFIX}", api_prefix)
            prefix = p
        elif raw_prefix.startswith('"') or raw_prefix.startswith("'"):
            prefix = raw_prefix.strip('"').strip("'")
        else:
            prefix = raw_prefix
        prefixes[mod] = prefix
    return prefixes


def _extract_routes_from_file(py_file: Path) -> list[dict]:
    """Parse un fichier .py via AST, retourne la liste des @router.METHOD endpoints.

    Returns:
        list of ``{method, path, fn_name, docstring_first_line}``.
    """
    import ast
    try:
        tree = ast.parse(py_file.read_text())
    except SyntaxError:
        return []

    # Récupérer aussi le prefix local du APIRouter() pour concaténer
    local_prefix = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "router":
                    if (isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Name)
                            and node.value.func.id == "APIRouter"):
                        for kw in node.value.keywords:
                            if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                                local_prefix = kw.value.value or ""
                                break
            break

    HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
    endpoints = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            # Pattern : @router.get("path", ...) ou @router.get("path")
            if not isinstance(dec, ast.Call):
                continue
            if not isinstance(dec.func, ast.Attribute):
                continue
            if not (isinstance(dec.func.value, ast.Name)
                    and dec.func.value.id == "router"):
                continue
            method = dec.func.attr
            if method not in HTTP_METHODS:
                continue
            # Premier arg = path (str constant)
            if not dec.args or not isinstance(dec.args[0], ast.Constant):
                continue
            path_val = dec.args[0].value
            # Docstring ?
            doc = ast.get_docstring(node) or ""
            summary = doc.splitlines()[0].strip() if doc else ""
            endpoints.append({
                "method": method.upper(),
                "path": local_prefix + path_val,
                "fn_name": node.name,
                "summary": summary,
            })
    return endpoints


def collect_api_endpoints() -> dict[str, Any]:
    """Scanne les fichiers routes FastAPI et retourne la liste des endpoints.

    Parsing AST + mapping prefix via main.py. Regroupement éditorial par
    fichier source (``API_FILE_GROUPS``).

    Returns:
        ``{"groups": [{id, label, file, endpoints: [{method, full_path,
          fn_name, summary}]}], "total_endpoints": int, "unmapped_files": [str]}``
    """
    prefixes = _parse_main_prefixes()

    # Collecter tous les fichiers .py ayant un APIRouter
    route_files: list[Path] = []
    for d in API_ROUTES_DIRS:
        if d.exists():
            for p in d.rglob("*.py"):
                if p.name.startswith("_") or p.name == "__init__.py":
                    continue
                route_files.append(p)

    groups_out = []
    total_endpoints = 0
    unmapped: list[str] = []

    # Ordonner par API_FILE_GROUPS (clé = chemin relatif sans .py)
    for file_key, label in API_FILE_GROUPS.items():
        # Chemin relatif potentiel
        candidates = [
            REPO_ROOT / "backend" / "app" / "api" / "routes" / f"{file_key}.py",
            REPO_ROOT / "backend" / "app" / "api" / f"{file_key}.py",
        ]
        py_file = next((c for c in candidates if c.exists()), None)
        if not py_file:
            continue
        # Extraire les endpoints
        endpoints = _extract_routes_from_file(py_file)
        if not endpoints:
            continue

        # Appliquer le prefix global (main.py include_router)
        mod_name = file_key.split("/")[-1]
        global_prefix = prefixes.get(mod_name, "")
        for ep in endpoints:
            ep["full_path"] = global_prefix + ep["path"]
        total_endpoints += len(endpoints)
        groups_out.append({
            "id": file_key.replace("/", "_"),
            "label": label,
            "file": str(py_file.relative_to(REPO_ROOT)),
            "endpoints": endpoints,
        })

    # Fichiers avec @router non mappés dans API_FILE_GROUPS
    mapped_paths = set()
    for g in groups_out:
        mapped_paths.add(REPO_ROOT / g["file"])
    for p in route_files:
        if p not in mapped_paths:
            eps = _extract_routes_from_file(p)
            if eps:
                unmapped.append(str(p.relative_to(REPO_ROOT)))

    return {
        "groups": groups_out,
        "total_endpoints": total_endpoints,
        "unmapped_files": unmapped,
    }
