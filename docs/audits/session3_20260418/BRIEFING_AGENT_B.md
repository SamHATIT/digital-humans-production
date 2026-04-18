# BRIEFING AGENT B — Contracts inter-agents

**Date** : 18 avril 2026
**Basé sur** : `AUDIT_REPORT_20260418_v3.md`
**Branches Claude Code** : `refactor/agent-b-contracts`

---

## 1. Mission

Consolider les **contrats entre agents et modules** en éliminant les duplications de référentiels et en formalisant les interfaces. Aujourd'hui, répondre à la question "qui est Marcus ?" nécessite de lire **6 dicts Python différents** dans 6 fichiers — avec des conventions de nommage divergentes.

**Objectif concret** : après ce chantier :
- **1 seul fichier source** (`agents_registry.yaml`) décrit tous les agents (nom, rôle, tier LLM, collections RAG, deliverable types, chat profile, etc.)
- Les 6 dicts Python deviennent des accesseurs qui lisent ce fichier au boot
- L'alias agent utilisé dans le code est **unique et stable** (ex: `"marcus"`, pas `"architect"` ni `"solution_architect"`)
- Les 3 YAML prompt stubs (Diego, Zara, Raj) sont remplis pour éliminer P9
- Les bugs de contrat HITL (N91, N92, N93) sont corrigés

**NON-objectif** : refactor des agents eux-mêmes (BaseAgent → briefing futur). Ici on consolide **les métadonnées** qui décrivent les agents.

---

## 2. Périmètre

### Les 6 dicts à consolider

| Dict | Fichier | Contenu |
|------|---------|---------|
| `AGENT_TIER_MAP` | `app/services/llm_service.py` L104-137 | alias → ORCHESTRATOR/ANALYST/WORKER |
| `agent_complexity_map` | `config/llm_routing.yaml` | alias → simple/medium/complex/critical |
| `AGENT_COLLECTIONS` | `app/services/rag_service.py` L58-70 | alias → [collections RAG] |
| `CATEGORY_AGENT_MAP` | `app/services/change_request_service.py` L36-44 | catégorie CR → [alias agents à rerun] |
| `agent_artifact_needs` | `app/services/artifact_service.py` L148-157 | alias → [artifact_types requis] |
| `AGENT_CHAT_PROFILES` | `app/api/routes/hitl_routes.py` L80-180 | alias → {name, role, color, system_prompt, deliverable_types} |

**Note** : les deux premiers dicts sont consolidés par le **briefing C** (LLM Modernization) en `agent_complexity_map` YAML unique. Ce briefing B s'occupe des 4 autres + ajoute ce que le briefing C produit pour former **1 seul registry global**.

### Les 3 YAML prompt stubs à remplir (P9)

- `backend/prompts/agents/diego_apex.yaml` (15 L actuellement)
- `backend/prompts/agents/zara_lwc.yaml` (15 L actuellement)
- `backend/prompts/agents/raj_admin.yaml` (15 L actuellement)

### Les bugs de contrat HITL à corriger

- **N91** : `deliverable_id` param ambigu (2 sémantiques selon l'endpoint)
- **N92** : `get_agent_chat_history` retourne toujours vide (agent_id jamais sauvé)
- **N93** : system_prompt Sophie dupliqué inline vs `AGENT_CHAT_PROFILES`

---

## 3. Structure `agents_registry.yaml` cible

**Nouveau fichier** : `backend/config/agents_registry.yaml`

```yaml
# Digital Humans Agent Registry — single source of truth
# All 6 previous Python dicts are derived from this file at boot time.

version: "1.0"
last_updated: "2026-04-18"

agents:
  # ═════════════════════════════════════════════════════════════
  # ORCHESTRATOR tier (SDS pipeline critique)
  # ═════════════════════════════════════════════════════════════
  sophie:
    # Identity
    name: "Sophie"
    role: "Project Manager"
    emoji: "👩‍💼"
    color: "purple"

    # LLM routing (read by llm_router_service)
    tier: "orchestrator"

    # Agent type aliases (for backward compat — all strings map to this agent)
    aliases: ["pm", "pm_orchestrator", "sophie"]

    # RAG collections (read by rag_service)
    rag_collections: ["business", "operations", "technical"]

    # Deliverables produced
    deliverable_types: ["pm_br_extraction"]

    # Chat profile (read by hitl_routes)
    chat:
      enabled: true
      system_prompt: |
        Tu es Sophie, Project Manager senior chez Digital Humans, spécialisée
        en implémentation Salesforce. Tu es en charge du projet "{project_name}".
        Réponds aux questions du client sur le projet et ses livrables.
        Explique les choix faits. Si le client demande une modification,
        propose de créer un Change Request.
        Réponds en français, de manière concise et professionnelle.

    # Change Request categories that trigger this agent to rerun
    cr_categories: ["process", "business_rule", "other"]

    # Artifact types this agent needs as input
    artifact_needs: ["requirement", "business_req", "use_case", "adr", "spec"]

  olivia:
    name: "Olivia"
    role: "Business Analyst"
    emoji: "👩‍🎓"
    color: "green"
    tier: "orchestrator"
    aliases: ["ba", "business_analyst", "olivia"]
    rag_collections: ["business", "operations"]
    deliverable_types: ["ba_use_cases"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Olivia, Business Analyst senior spécialisée Salesforce.
        Tu as rédigé les Use Cases du projet "{project_name}".
        Tu peux expliquer la logique métier, les scénarios, et les critères
        d'acceptation. Réponds en français, de manière claire et orientée métier.
    cr_categories: ["business_rule", "process"]
    artifact_needs: ["requirement", "business_req"]

  marcus:
    name: "Marcus"
    role: "Solution Architect"
    emoji: "👨‍🔧"
    color: "blue"
    tier: "orchestrator"
    aliases: ["architect", "solution_architect", "marcus"]
    rag_collections: ["technical", "operations", "business"]
    deliverable_types: ["architect_solution_design", "architect_gap_analysis", "architect_wbs"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Marcus, Salesforce Certified Technical Architect (CTA).
        Tu as conçu l'architecture du projet "{project_name}".
        Tu peux expliquer tes choix de data model, flows, security, et répondre
        aux questions techniques. Si le client propose une modification
        architecturale, explique l'impact et les dépendances.
        Réponds en français, en étant précis et technique.
    cr_categories: ["data_model", "integration", "security", "process"]
    artifact_needs: ["requirement", "business_req", "use_case"]

  emma:
    name: "Emma"
    role: "Research Analyst"
    emoji: "🔬"
    color: "cyan"
    tier: "orchestrator"
    aliases: ["research", "research_analyst", "emma"]
    rag_collections: ["technical", "operations", "business"]
    deliverable_types:
      - "research_analyst_uc_digest"
      - "research_analyst_coverage_report"
      - "research_analyst_sds_document"
    chat:
      enabled: true
      system_prompt: |
        Tu es Emma, Research Analyst senior. Tu as validé la couverture de
        l'architecture et rédigé le SDS du projet "{project_name}".
        Tu peux expliquer les gaps identifiés, le score de couverture, et la
        structure du SDS. Réponds en français, de manière analytique et précise.
    cr_categories: []
    artifact_needs: ["business_req", "use_case", "adr", "spec"]

  # ═════════════════════════════════════════════════════════════
  # WORKER tier (experts)
  # ═════════════════════════════════════════════════════════════
  diego:
    name: "Diego"
    role: "Apex Developer"
    emoji: "👨‍💻"
    color: "red"
    tier: "worker"
    aliases: ["apex", "apex_developer", "developer_apex", "diego"]
    rag_collections: ["apex", "technical"]
    deliverable_types: ["apex_classes", "apex_triggers", "apex_tests"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Diego, Apex Developer senior spécialisé Salesforce.
        Tu as généré les classes Apex du projet "{project_name}".
        Tu peux expliquer tes choix d'implémentation, bulkification, gestion
        d'erreur, et couverture de test.
        Réponds en français, techniquement et précisément.
    cr_categories: ["business_rule", "integration"]
    artifact_needs: ["spec", "adr", "use_case", "business_req"]

  zara:
    name: "Zara"
    role: "LWC Developer"
    emoji: "👩‍💻"
    color: "pink"
    tier: "worker"
    aliases: ["lwc", "lwc_developer", "developer_lwc", "zara"]
    rag_collections: ["lwc", "technical"]
    deliverable_types: ["lwc_components", "aura_components"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Zara, Lightning Web Components Developer senior.
        Tu as conçu les composants UI du projet "{project_name}".
        Tu peux expliquer tes choix de décorateurs, @wire vs imperatif,
        et la structure des composants.
        Réponds en français, techniquement et visuellement.
    cr_categories: ["ui_ux"]
    artifact_needs: ["spec", "adr", "use_case", "business_req"]

  raj:
    name: "Raj"
    role: "Salesforce Admin"
    emoji: "👨‍🔧"
    color: "indigo"
    tier: "worker"
    aliases: ["admin", "sf_admin", "raj"]
    rag_collections: ["operations", "technical"]
    deliverable_types:
      - "admin_objects"
      - "admin_fields"
      - "admin_permission_sets"
      - "admin_page_layouts"
      - "admin_validation_rules"
    chat:
      enabled: true
      system_prompt: |
        Tu es Raj, Salesforce Admin senior. Tu as planifié la configuration
        du projet "{project_name}". Tu peux expliquer les choix de configuration,
        permissions, page layouts et record types.
        Réponds en français, de manière pratique et orientée solution.
    cr_categories: ["data_model", "security"]
    artifact_needs: ["spec", "adr", "use_case", "business_req"]

  elena:
    name: "Elena"
    role: "QA Engineer"
    emoji: "🧪"
    color: "violet"
    tier: "worker"
    aliases: ["qa", "qa_tester", "qa_engineer", "elena"]
    rag_collections: ["apex", "technical", "operations"]
    deliverable_types: ["qa_specifications", "qa_test_cases"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Elena, QA Engineer senior spécialisée Salesforce.
        Tu as conçu la stratégie de test du projet "{project_name}".
        Tu peux expliquer les scénarios de test, la couverture, et les risques.
        Réponds en français, de manière rigoureuse et méthodique.
    cr_categories: []
    artifact_needs: ["spec", "code", "config"]

  aisha:
    name: "Aisha"
    role: "Data Migration Specialist"
    emoji: "📊"
    color: "orange"
    tier: "worker"
    aliases: ["data", "data_migration", "aisha"]
    rag_collections: ["technical", "operations"]
    deliverable_types: ["data_specifications", "data_mappings", "data_validation"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Aisha, Data Migration Specialist senior.
        Tu as conçu le plan de migration de données du projet "{project_name}".
        Tu peux expliquer les mappings, les stratégies de migration,
        et les validations.
        Réponds en français, de manière structurée et rigoureuse.
    cr_categories: ["data_model", "integration"]
    artifact_needs: ["spec", "business_req"]

  jordan:
    name: "Jordan"
    role: "DevOps Engineer"
    emoji: "🚀"
    color: "yellow"
    tier: "worker"
    aliases: ["devops", "jordan"]
    rag_collections: ["technical", "operations"]
    deliverable_types: ["devops_specifications", "devops_pipeline", "devops_scripts"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Jordan, DevOps Engineer senior spécialisé Salesforce.
        Tu as planifié le pipeline CI/CD et la stratégie de déploiement du
        projet "{project_name}". Tu peux expliquer la stratégie de déploiement,
        les environnements, et les pipelines CI/CD.
        Réponds en français, de manière technique et concrète.
    cr_categories: ["integration"]
    artifact_needs: ["code", "config", "test"]

  lucas:
    name: "Lucas"
    role: "Trainer"
    emoji: "🎓"
    color: "teal"
    tier: "worker"
    aliases: ["trainer", "lucas"]
    rag_collections: ["business", "operations"]
    deliverable_types: ["trainer_specifications", "trainer_materials"]
    chat:
      enabled: true
      system_prompt: |
        Tu es Lucas, Trainer senior spécialisé Salesforce.
        Tu as conçu le plan de formation du projet "{project_name}".
        Tu peux expliquer les modules, les audiences cibles, et les approches
        pédagogiques. Réponds en français, de manière pédagogique et engageante.
    cr_categories: []
    artifact_needs: ["use_case", "business_req", "doc"]
```

---

## 4. Accesseurs Python (remplacent les 6 dicts)

**Nouveau fichier** : `backend/app/services/agents_registry.py`

```python
"""
Agent registry loader and accessors.

Loads config/agents_registry.yaml once at import time and provides
typed accessors for LLM tier, RAG collections, chat profile, etc.

This module replaces:
- AGENT_TIER_MAP (llm_service.py) — now in config/llm_routing.yaml via briefing C
- AGENT_COLLECTIONS (rag_service.py)
- CATEGORY_AGENT_MAP (change_request_service.py)
- agent_artifact_needs (artifact_service.py)
- AGENT_CHAT_PROFILES (hitl_routes.py)
"""
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)


def _get_registry_path() -> Path:
    return Path(__file__).parent.parent.parent / "config" / "agents_registry.yaml"


@lru_cache(maxsize=1)
def _load_registry() -> Dict[str, Any]:
    """Load the agent registry YAML at first call, cached thereafter."""
    path = _get_registry_path()
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        logger.info(f"Agent registry loaded from {path} — {len(data.get('agents', {}))} agents")
        return data
    except Exception as e:
        logger.error(f"Failed to load agent registry: {e}")
        return {"agents": {}}


def _build_alias_index() -> Dict[str, str]:
    """Build a dict mapping every alias → canonical agent_id."""
    registry = _load_registry()
    index = {}
    for canonical_id, agent in registry.get("agents", {}).items():
        for alias in agent.get("aliases", [canonical_id]):
            index[alias.lower()] = canonical_id
    return index


@lru_cache(maxsize=1)
def _alias_index() -> Dict[str, str]:
    return _build_alias_index()


def resolve_agent_id(alias: str) -> Optional[str]:
    """Resolve any agent alias to the canonical agent_id.

    Examples:
        resolve_agent_id('ba') → 'olivia'
        resolve_agent_id('qa_tester') → 'elena'
        resolve_agent_id('sophie') → 'sophie'
        resolve_agent_id('unknown') → None
    """
    return _alias_index().get(alias.lower())


def get_agent(alias: str) -> Optional[Dict[str, Any]]:
    """Get agent config by alias (returns None if not found)."""
    canonical = resolve_agent_id(alias)
    if not canonical:
        return None
    return _load_registry().get("agents", {}).get(canonical)


def list_agents() -> Dict[str, Dict[str, Any]]:
    """Return all agents keyed by canonical id."""
    return _load_registry().get("agents", {})


# ═════════════════════════════════════════════════════════
# Accessors replacing the 6 legacy dicts
# ═════════════════════════════════════════════════════════

def get_rag_collections(alias: str) -> List[str]:
    """Replaces AGENT_COLLECTIONS[alias]."""
    agent = get_agent(alias)
    return agent.get("rag_collections", ["technical", "operations", "business"]) if agent else []


def get_agents_for_cr_category(category: str) -> List[str]:
    """Replaces CATEGORY_AGENT_MAP[category]. Returns canonical agent_ids."""
    category = category.lower()
    result = []
    for agent_id, agent in list_agents().items():
        if category in agent.get("cr_categories", []):
            result.append(agent_id)
    return result


def get_artifact_needs(alias: str) -> List[str]:
    """Replaces agent_artifact_needs[alias]."""
    agent = get_agent(alias)
    return agent.get("artifact_needs", []) if agent else []


def get_chat_profile(alias: str) -> Optional[Dict[str, Any]]:
    """Replaces AGENT_CHAT_PROFILES[alias]. Returns dict with name, role, color, system_prompt."""
    agent = get_agent(alias)
    if not agent:
        return None
    return {
        "agent_id": resolve_agent_id(alias),
        "name": agent["name"],
        "role": agent["role"],
        "color": agent.get("color", "slate"),
        "emoji": agent.get("emoji", "🤖"),
        "system_prompt": agent.get("chat", {}).get("system_prompt", ""),
        "deliverable_types": agent.get("deliverable_types", []),
        "chat_enabled": agent.get("chat", {}).get("enabled", True),
    }


def get_deliverable_types(alias: str) -> List[str]:
    """Return deliverable types produced by this agent."""
    agent = get_agent(alias)
    return agent.get("deliverable_types", []) if agent else []


def get_tier(alias: str) -> str:
    """Return 'orchestrator' or 'worker'. Used by llm_router cross-check."""
    agent = get_agent(alias)
    return agent.get("tier", "worker") if agent else "worker"
```

---

## 5. Migration des 6 dicts — patches à appliquer

### 5.1 `rag_service.py` — AGENT_COLLECTIONS

```python
# AVANT
AGENT_COLLECTIONS = {
    "business_analyst": ["business", "operations"],
    # ... 11 entries
}

# ...
collection_keys = AGENT_COLLECTIONS.get(agent_type, AGENT_COLLECTIONS["default"])

# APRÈS — supprimer le dict, utiliser l'accessor
from app.services.agents_registry import get_rag_collections
# ...
collection_keys = get_rag_collections(agent_type) or ["technical", "operations", "business"]
```

### 5.2 `change_request_service.py` — CATEGORY_AGENT_MAP

```python
# AVANT
CATEGORY_AGENT_MAP = {
    "business_rule": ["ba", "architect", "apex", "admin", "qa"],
    # ...
}

# ...
agents = CATEGORY_AGENT_MAP.get(cr.category, ["ba", "architect"])

# APRÈS
from app.services.agents_registry import get_agents_for_cr_category, resolve_agent_id
# ...
agents = get_agents_for_cr_category(cr.category)
if not agents:
    agents = ["olivia", "marcus"]  # canonical IDs fallback
```

### 5.3 `artifact_service.py` — agent_artifact_needs

```python
# AVANT
agent_artifact_needs = {
    "ba": ["requirement"],
    # ... 10 entries with SHORT aliases
}
needed_types = agent_artifact_needs.get(agent_id, [])

# APRÈS — accepte tous les alias (short et long)
from app.services.agents_registry import get_artifact_needs, resolve_agent_id
needed_types = get_artifact_needs(agent_id)
```

**Fix bonus** : N80 résolu — `get_context_for_agent("business_analyst")` fonctionne maintenant (avant retournait `[]`).

### 5.4 `hitl_routes.py` — AGENT_CHAT_PROFILES

```python
# AVANT (L80-180) — 120 lignes de dict
AGENT_CHAT_PROFILES = {
    "sophie": {...},
    # ... 9 entries
}

# APRÈS — supprimer le dict, remplacer tous les usages
from app.services.agents_registry import get_chat_profile, list_agents

# L680-710 (list_available_agents) : itérer list_agents() au lieu de AGENT_CHAT_PROFILES
agents = []
for agent_id, agent_data in list_agents().items():
    profile = get_chat_profile(agent_id)
    if not profile or not profile["chat_enabled"]:
        continue
    # ... logic pour has_deliverables ...

# L250-260 (chat_with_sophie_contextual system_prompt) : supprimer le inline rewrite
# REMPLACER par :
from app.services.agents_registry import get_chat_profile
profile = get_chat_profile("sophie")
system_prompt = profile["system_prompt"].format(project_name=project.name)
```

**Fix bonus N93** : résolu — `system_prompt` vient d'une source unique.

---

## 6. Remplir les 3 YAML stubs (P9)

### 6.1 `prompts/agents/diego_apex.yaml`

Utiliser la structure des YAML déjà remplis (Sophie, Olivia, Marcus) comme template. Contenu minimal à produire :

```yaml
# diego_apex.yaml — Diego (Apex Developer) prompts
agent_id: apex
agent_name: "Diego (Apex Developer)"
role: "Salesforce Apex Developer"

prompts:
  build:
    system: |
      You are Diego, a senior Salesforce Apex Developer (15+ years).
      Generate production-quality Apex code for the requested task.

      MANDATORY RULES:
      - All SOQL/DML must be bulkified
      - Every class ends with @isTest class + min 85% coverage target
      - Use AuraHandledException for all user-facing errors
      - Annotations @InvocableMethod / @AuraEnabled where needed
      - Sharing model: `with sharing` by default unless spec says otherwise
      - File pattern output: use markdown code blocks prefixed by `// FILE: <path>`

    user_template: |
      ## TASK
      {task_description}

      ## ARCHITECTURE CONTEXT
      {architecture_context}

      ## RAG BEST PRACTICES
      {rag_context}

      {correction_context}

      Generate production-ready Apex artifacts now.
```

Faire de même pour Zara (LWC) et Raj (Admin) en adaptant les règles métier (composants LWC pour Zara, metadata XML pour Raj).

**DoD P9** :
- Les 3 YAML stubs passent de 15 à 100+ lignes (volume similaire aux 8 autres remplis)
- Les fonctions `generate_build` de Diego/Zara/Raj utilisent `PROMPT_SERVICE.render()` au lieu du prompt hardcodé inline dans le .py
- Vérification : `wc -l prompts/agents/*.yaml | sort` — plus de stubs < 30 lignes

---

## 7. Fix N91 — `deliverable_id` ambigu

**Fichier** : `backend/app/api/routes/hitl_routes.py`

**Problème** : le param `deliverable_id` pointe vers `AgentDeliverable.id` dans `/chat` mais vers `ExecutionArtifact.id` dans `/versions` et `/diff` — 2 tables différentes, même nom de param.

**Solution** : renommer explicitement les params dans les signatures.

```python
# AVANT
@router.get("/deliverables/{deliverable_id}/versions")
def list_deliverable_versions(deliverable_id: int, ...):
    artifact = db.query(ExecutionArtifact).filter(ExecutionArtifact.id == deliverable_id).first()

# APRÈS
@router.get("/artifacts/{artifact_id}/versions")   # ← route path changée
def list_artifact_versions(artifact_id: int, ...):  # ← param renommé
    artifact = db.query(ExecutionArtifact).filter(ExecutionArtifact.id == artifact_id).first()
```

**Backward compat** : garder l'ancienne route `/deliverables/{deliverable_id}/versions` avec `DeprecationWarning` + redirect vers la nouvelle pendant 1 release.

**Frontend** : mettre à jour `frontend/src/services/api.ts` pour utiliser les nouvelles routes.

---

## 8. Fix N92 — chat history vide

**Fichier** : `backend/app/api/routes/hitl_routes.py` L295-304 + modèle `ProjectConversation`

**Problème** : `chat_with_sophie_contextual` sauve les messages **sans** `agent_id`. `get_agent_chat_history` filtre **sur** `agent_id`. Résultat : historique toujours vide.

**Solution** :

```python
# L295-304 — AJOUTER agent_id dans le save
agent_id = body.agent_id or "sophie"  # from ChatRequest, default sophie

for role, text, tokens in [
    ("user", body.message, 0),
    ("assistant", assistant_message, tokens_used),
]:
    db.add(ProjectConversation(
        project_id=project.id,
        execution_id=execution_id,
        agent_id=agent_id,          # ← NEW
        role=role,
        message=text,
        tokens_used=tokens,
        model_used=model_used,
    ))
db.commit()
```

**Migration SQL** : les anciens messages ont `agent_id=NULL`. Migration de nettoyage :
```sql
UPDATE project_conversations
SET agent_id = 'sophie'
WHERE agent_id IS NULL;
```

**Modèle** : s'assurer que `ProjectConversation.agent_id` a une valeur par défaut `'sophie'` au niveau de la colonne (et non-nullable après migration).

---

## 9. Plan d'exécution

### Sprint 1 — Agents registry (jour 1)
- Créer `config/agents_registry.yaml` (section 3)
- Créer `app/services/agents_registry.py` (section 4)
- Tests unitaires des accesseurs

### Sprint 2 — Migrations services (jour 1-2)
- Migration `rag_service.py` (AGENT_COLLECTIONS)
- Migration `change_request_service.py` (CATEGORY_AGENT_MAP)
- Migration `artifact_service.py` (agent_artifact_needs) + fix N80
- Migration `hitl_routes.py` (AGENT_CHAT_PROFILES) + fix N93

### Sprint 3 — YAML prompts (jour 2)
- Remplir `diego_apex.yaml`, `zara_lwc.yaml`, `raj_admin.yaml`
- Adapter `salesforce_developer_apex.py`, `salesforce_developer_lwc.py`, `salesforce_admin.py` pour utiliser `PROMPT_SERVICE.render()` au lieu des prompts inline

### Sprint 4 — Fix contrats HITL (jour 3)
- Fix N91 : rename `deliverable_id` → `artifact_id` dans les routes versions/diff
- Fix N92 : sauver `agent_id` dans chat + migration SQL
- Frontend : mise à jour api.ts

---

## 10. DoD — Definition of Done

```bash
# 1. 1 seul registry chargé
python -c "
from app.services.agents_registry import list_agents, resolve_agent_id
agents = list_agents()
assert len(agents) == 11, f'expected 11, got {len(agents)}'
# Alias resolution fonctionne
assert resolve_agent_id('ba') == 'olivia'
assert resolve_agent_id('qa_tester') == 'elena'
assert resolve_agent_id('apex_developer') == 'diego'
print('✅ Registry loaded + aliases resolve')
"

# 2. Dicts legacy disparus
for pattern in 'AGENT_COLLECTIONS' 'CATEGORY_AGENT_MAP' 'agent_artifact_needs' 'AGENT_CHAT_PROFILES'; do
  grep -rn "^$pattern = {" backend/app --include="*.py" | grep -v "agents_registry" && echo "❌ still present: $pattern" || echo "✅ removed: $pattern"
done

# 3. YAML stubs remplis
for f in diego_apex zara_lwc raj_admin; do
  lines=$(wc -l < backend/prompts/agents/${f}.yaml)
  [ "$lines" -gt 50 ] && echo "✅ ${f}.yaml: $lines lines" || echo "❌ still stub: $f ($lines lines)"
done

# 4. Chat history test (N92)
python -c "
# Simulated: post a chat message then fetch history
# Should return the message (not empty array)
"

# 5. Route artifact_id renamed
curl -s http://localhost:8002/api/pm-orchestrator/artifacts/1/versions 
# Should 200 or 404 (not 422 "deliverable_id required")
```

---

## 11. Risques & points d'attention

1. **Backward compat des alias** : les agents utilisent historiquement les alias courts (`"ba"`, `"qa_tester"`) dans les appels `generate_llm_response`. `resolve_agent_id` doit accepter TOUS les alias historiques. À tester exhaustivement.

2. **Migration ordered** : la migration `rag_service.py` dépend de `agents_registry.py`. S'assurer que le nouveau service est mergé avant.

3. **Fix N93 système prompt inline** : peut impacter la qualité des réponses Sophie chat. Tester manuellement quelques échanges après migration pour valider que le ton/contenu ne régresse pas.

4. **YAML stubs Diego/Zara/Raj** : les prompts inline dans le .py actuellement **fonctionnent** (malgré les F821 qui font crasher avant utilisation). Extraire en YAML ne doit pas dégrader la qualité. Prévoir un E2E comparatif avant/après.

5. **Fix N92 migration SQL** : attention à ne pas lancer la migration sur un projet avec des milliers de messages sans index sur `agent_id`. Ajouter l'index AVANT la mass update.

---

## 12. Livrables attendus

- `backend/config/agents_registry.yaml` (nouveau)
- `backend/app/services/agents_registry.py` (nouveau)
- `backend/prompts/agents/diego_apex.yaml` (rempli)
- `backend/prompts/agents/zara_lwc.yaml` (rempli)
- `backend/prompts/agents/raj_admin.yaml` (rempli)
- Migrations des 4 services cités
- Migration DB `add_agent_id_to_conversations.py`
- Tests unitaires `test_agents_registry.py`
- CHANGELOG.md + docs/agents.md (doc utilisateur listant tous les agents)

*Fin briefing Agent B*
