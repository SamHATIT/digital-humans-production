# BRIEFING AGENT C — LLM Modernization (multi-profile)

**Date** : 18 avril 2026
**Basé sur** : `AUDIT_REPORT_20260418_v3.md` + directive Sam "2 tiers Opus/Sonnet, multi-profile cloud/on-premise/freemium"
**Branches Claude Code** : `feat/agent-c-llm-unified`

---

## 1. Mission

Consolider l'architecture LLM autour de **2 tiers logiques** (`orchestrator` / `worker`) et **3 deployment profiles** (`cloud`, `on-premise`, `freemium`), avec **un seul fichier YAML comme source de vérité**.

**Objectif concret** : après ce chantier, changer de modèle Opus → Opus 4.8 → Opus 5 se résume à **modifier 1 ligne dans un YAML**, sans toucher au code Python ni aux 11 agents. La capacité multi-provider (Anthropic cloud / Ollama local) reste préservée pour les cas d'usage L'Oréal / LVMH / freemium.

**Bénéfice mécanique** : **12 findings supprimés** avant même d'être traités (N21, N22, N23, N28, N31, N33, N35, N41, N42, N43, N45, N86).

---

## 2. Stratégie cible

### 2.1 Les 2 tiers logiques

| Tier | Agents | Raison |
|------|--------|--------|
| **orchestrator** | Sophie, Olivia, Marcus, Emma | Pipeline SDS critique — raisonnement, architecture, analyse, validation couverture |
| **worker** | Diego, Zara, Raj, Elena, Aisha, Jordan, Lucas | Agents experts produisant code/config/tests selon spec fournie par l'orchestrator |

**Plus de tier `worker` = Haiku**. Plus de tier `analyst` intermédiaire. Plus de `CRIT-02 Upgraded` incohérent. **2 tiers, point**.

### 2.2 Les 3 deployment profiles

| Profile | orchestrator | worker | build_enabled | Cas d'usage |
|---------|--------------|--------|---------------|-------------|
| **`cloud`** (défaut SaaS) | `anthropic/opus-latest` | `anthropic/sonnet-latest` | ✅ | Clients standards sur app.samhatit.cloud |
| **`on-premise`** | `local/llama-3.3-70b` | `local/llama-3.1-8b` ou `local/mistral-large` | ✅ | L'Oréal, LVMH — data souveraine |
| **`freemium`** | `local/mistral-7b` | `local/mistral-7b` | ❌ SDS only | Lead capture, trial gratuit |

**Activation** : variable d'environnement `DH_DEPLOYMENT_PROFILE=cloud|on-premise|freemium`. Le Router V3 lit au boot, active les bons providers, applique les feature flags.

### 2.3 Structure YAML cible

```yaml
# config/llm_routing.yaml — version refondue multi-profile

# Active profile (overridable via DH_DEPLOYMENT_PROFILE env var)
deployment_profile: cloud

# Profile definitions
profiles:
  cloud:
    description: "SaaS default — Anthropic API, full BUILD pipeline"
    orchestrator: anthropic/opus-latest
    worker:       anthropic/sonnet-latest
    build_enabled: true
    fallback_allowed: cloud    # can fallback to another cloud provider (none configured yet)

  on-premise:
    description: "Client-hosted — Ollama local only, data sovereignty"
    orchestrator: local/llama-3.3-70b
    worker:       local/llama-3.1-8b   # or mistral-large-7b if hardware permits
    build_enabled: true
    fallback_allowed: none     # NEVER fallback to cloud

  freemium:
    description: "Free trial — SDS-only, local LLM, rate-limited"
    orchestrator: local/mistral-7b
    worker:       local/mistral-7b      # same model, tier distinction kept for consistency
    build_enabled: false
    fallback_allowed: none

# Provider configurations
providers:
  anthropic:
    enabled: true
    api_key_env: "ANTHROPIC_API_KEY"
    timeout_seconds: 600
    models:
      opus-latest:
        model_id: "claude-opus-4-7-XXXXXXXX"   # UPDATE THIS when new version released
      sonnet-latest:
        model_id: "claude-sonnet-4-6-XXXXXXXX"

  local:
    enabled: true
    base_url: "http://localhost:11434"
    timeout_seconds: 900     # longer for local LLMs
    models:
      llama-3.3-70b:
        context_length: 128000
      llama-3.1-8b:
        context_length: 128000
      mistral-large:
        context_length: 128000
      mistral-7b:
        context_length: 32768

  openai:
    enabled: false    # KEPT for future but disabled by default

# Agent → tier mapping (profile-agnostic)
agent_complexity_map:
  # Orchestrator tier
  sophie: orchestrator
  pm: orchestrator
  pm_orchestrator: orchestrator
  olivia: orchestrator
  business_analyst: orchestrator
  ba: orchestrator
  marcus: orchestrator
  architect: orchestrator
  solution_architect: orchestrator
  emma: orchestrator
  research: orchestrator
  research_analyst: orchestrator

  # Worker tier
  diego: worker
  apex_developer: worker
  apex: worker
  zara: worker
  lwc_developer: worker
  lwc: worker
  raj: worker
  admin: worker
  sf_admin: worker
  elena: worker
  qa: worker
  qa_tester: worker
  aisha: worker
  data: worker
  data_migration: worker
  jordan: worker
  devops: worker
  lucas: worker
  trainer: worker

# Pricing (used by budget_service via programmatic YAML read)
# USD per 1M tokens
pricing:
  anthropic/opus-latest:
    input: 15.0      # ← VERIFY current Anthropic pricing
    output: 75.0
  anthropic/sonnet-latest:
    input: 3.0
    output: 15.0
  local/llama-3.3-70b:
    input: 0.0       # local = free (compute cost not tracked here)
    output: 0.0
  local/llama-3.1-8b:
    input: 0.0
    output: 0.0
  local/mistral-large:
    input: 0.0
    output: 0.0
  local/mistral-7b:
    input: 0.0
    output: 0.0
```

---

## 3. Périmètre — fichiers concernés

### À modifier
- `backend/config/llm_routing.yaml` — refonte complète (format ci-dessus)
- `backend/app/services/llm_router_service.py` — profile-aware logic
- `backend/app/services/llm_service.py` — **SIMPLIFICATION MASSIVE** : devient un wrapper mince
- `backend/app/services/budget_service.py` — pricing lu depuis YAML au boot
- `backend/app/services/change_request_service.py` — retrait `self.llm_service = LLMService()`, utilise `generate_llm_response`
- `backend/app/api/routes/hitl_routes.py` — retrait `LLMService()` direct

### À supprimer (ou marquer deprecated puis supprimer au sprint suivant)
- `ANTHROPIC_MODELS`, `OPENAI_MODELS`, `AGENT_TIER_MAP` dans llm_service.py
- Classe `LLMService` (entière)
- Enum `AgentTier`
- Fallback OpenAI path dans `_call_openai` / `_init_clients`

### À créer
- `backend/app/middleware/build_enabled.py` — middleware FastAPI qui bloque `/execute/*/build*` en mode freemium
- `backend/app/api/routes/config.py` — endpoint `GET /api/config/capabilities` pour que le frontend lise `build_enabled` et grise le bouton BUILD

---

## 4. Chantiers LLM-0 à LLM-5

### LLM-0 — Suppression LLMService V1 + bridge dual-path

**Objectif** : Router V3 devient le **seul path** LLM.

**Fichier** : `backend/app/services/llm_service.py`

**Avant** (752 LOC) : classe `LLMService` + dicts `ANTHROPIC_MODELS`/`OPENAI_MODELS`/`AGENT_TIER_MAP` + bridge V3 + fallback OpenAI

**Après** (~150 LOC) : juste les wrappers `generate_llm_response()` et `generate_llm_response_async()` qui délèguent au Router V3.

**Nouveau contenu** (squelette) :

```python
"""
LLM Service - Thin wrapper delegating to LLMRouterService (V3).

This module exists for backward compatibility with agents calling
generate_llm_response(). All routing, pricing and provider logic
is handled by llm_router_service.py reading config/llm_routing.yaml.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def generate_llm_response(
    prompt: str,
    agent_type: str = "worker",
    system_prompt: Optional[str] = None,
    max_tokens: int = 16000,
    temperature: float = 0.7,
    execution_id: Optional[int] = None,
    project_id: Optional[int] = None,
    **kwargs,  # backward compat: swallow 'provider', 'model', 'model_override' if passed
) -> Dict[str, Any]:
    """
    Generate LLM response via the central router.

    All historical kwargs (provider, model, model_override, fallback_to_openai)
    are ignored — routing is now YAML-driven per deployment_profile.
    """
    from app.services.llm_router_service import get_llm_router
    router = get_llm_router()
    return router.generate(
        prompt=prompt,
        agent_type=agent_type,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        execution_id=execution_id,
        project_id=project_id,
    )


async def generate_llm_response_async(
    prompt: str,
    agent_type: str = "worker",
    system_prompt: Optional[str] = None,
    max_tokens: int = 16000,
    temperature: float = 0.7,
    execution_id: Optional[int] = None,
    project_id: Optional[int] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Async version using router.generate_async()."""
    from app.services.llm_router_service import get_llm_router
    router = get_llm_router()
    return await router.generate_async(
        prompt=prompt,
        agent_type=agent_type,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        execution_id=execution_id,
        project_id=project_id,
    )


# JSON helper kept as is (doesn't touch routing)
def generate_json_response(prompt, agent_type="worker", **kwargs):
    from app.utils.json_cleaner import clean_llm_json_response
    response = generate_llm_response(prompt=prompt, agent_type=agent_type, **kwargs)
    raw = response.get("content", "")
    parsed, error = clean_llm_json_response(raw)
    if parsed is not None:
        response["content"] = parsed
        response["content_raw"] = raw
        response["json_parsed"] = True
    else:
        response["content"] = {"raw": raw, "parse_error": error}
        response["json_parsed"] = False
    return response
```

**Gains** :
- -500 LOC de code dead / dupliqué
- N21 (hardcoded models) supprimé
- N22 (AGENT_TIER_MAP dup) supprimé
- N23 (Elena incohérence qa_tester/elena) supprimé — plus de tier distinction Haiku/Sonnet
- N24, N25, N26, N27, N30 supprimés
- N45, N86 (bypass V3) : plus possible puisque `LLMService` n'existe plus

---

### LLM-1 — Profile-aware router

**Fichier** : `backend/app/services/llm_router_service.py`

**Patch `_select_provider`** (L228-246) :

```python
def _select_provider(self, request: LLMRequest) -> str:
    """Select provider based on current deployment profile + agent tier."""
    # force_provider still wins for explicit overrides
    if request.force_provider:
        return request.force_provider

    # Get active profile
    active_profile_name = os.environ.get(
        "DH_DEPLOYMENT_PROFILE",
        self.config.get("deployment_profile", "cloud")
    )
    profiles = self.config.get("profiles", {})
    profile = profiles.get(active_profile_name)
    if not profile:
        logger.error(f"Unknown profile '{active_profile_name}', falling back to cloud")
        profile = profiles.get("cloud", {})

    # Get agent tier
    agent_map = self.config.get("agent_complexity_map", {})
    tier = agent_map.get((request.agent_type or "worker").lower(), "worker")

    # Get provider for (profile, tier)
    return profile.get(tier, profile.get("worker", "anthropic/sonnet-latest"))
```

**Gains** :
- N42 (alias prénom → Ollama) : résolu — plus de `default_routing` tombant sur Ollama, le profile décide
- N31, N28 : YAML source unique confirmée
- Multi-profile : cloud/on-premise/freemium supportés nativement

**Ajout `build_enabled` accessor** :

```python
def is_build_enabled(self) -> bool:
    """Check if current profile allows BUILD endpoints."""
    active_profile_name = os.environ.get(
        "DH_DEPLOYMENT_PROFILE",
        self.config.get("deployment_profile", "cloud")
    )
    profiles = self.config.get("profiles", {})
    return profiles.get(active_profile_name, {}).get("build_enabled", True)

def get_active_profile(self) -> dict:
    """Return active profile config (for health checks, capabilities endpoint)."""
    active_profile_name = os.environ.get(
        "DH_DEPLOYMENT_PROFILE",
        self.config.get("deployment_profile", "cloud")
    )
    return {
        "name": active_profile_name,
        **self.config.get("profiles", {}).get(active_profile_name, {})
    }
```

---

### LLM-2 — Fallback chain profile-aware (N42)

**Fichier** : même

**Patch `complete()`** (L478-506) :

```python
async def complete(self, request: LLMRequest) -> LLMResponse:
    provider_str = self._select_provider(request)
    logger.info(f"🤖 LLM Request: agent={request.agent_type}, provider={provider_str}")

    response = await self._call_provider(request, provider_str)

    # Profile-aware fallback
    if not response.success:
        active_profile = self.get_active_profile()
        fallback_allowed = active_profile.get("fallback_allowed", "none")

        if fallback_allowed == "cloud" and not provider_str.startswith("local/"):
            # Cloud-to-cloud fallback (not yet configured but structure ready)
            fallback = self.config.get("fallback_chain", {}).get(provider_str)
            if fallback:
                logger.warning(f"🔄 Fallback {provider_str} → {fallback}")
                response = await self._call_provider(request, fallback)

        elif fallback_allowed == "none":
            # On-premise or freemium: NEVER fallback to cloud
            logger.error(
                f"❌ LLM call failed in profile '{active_profile['name']}' "
                f"and fallback is disabled. Returning failure to caller."
            )
            # response stays as failure — caller sees it

    self._track_usage(request, response)
    return response
```

**Gains** :
- **L'Oréal/LVMH protégés** : une panne Ollama locale ne déclenchera **jamais** un call cloud qui violerait la contrainte data souveraine
- **Freemium contained** : erreur visible au lieu d'exploser les coûts Anthropic

---

### LLM-3 — Continuation CRIT-02 dans Router V3 (N33)

**Fichier** : `backend/app/services/llm_router_service.py` — `_call_anthropic` L332-404

**Régression à corriger** : V1 avait l'auto-continuation si `stop_reason == "max_tokens"`, V3 ne l'a pas.

**Patch** : ajouter la logique de continuation dans `_call_anthropic` (et équivalent `_call_ollama` si pertinent pour Llama qui fait aussi du truncation) :

```python
async def _call_anthropic(self, request, model_id, provider_str):
    start_time = time.time()
    async_client = self.async_providers.get("anthropic", {}).get("client")
    if not async_client:
        raise ValueError("Anthropic client not initialized")

    kwargs = {
        "model": model_id,
        "max_tokens": request.max_tokens,
        "messages": [{"role": "user", "content": request.prompt}]
    }
    if request.system_prompt:
        kwargs["system"] = request.system_prompt
    if request.temperature <= 1.0:
        kwargs["temperature"] = request.temperature

    try:
        response = await async_client.messages.create(**kwargs)
        content = response.content[0].text
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        stop_reason = response.stop_reason

        # === CRIT-02 AUTO-CONTINUATION (ported from V1) ===
        continuation_count = 0
        max_continuations = 3

        while stop_reason == "max_tokens" and continuation_count < max_continuations:
            continuation_count += 1
            logger.warning(f"V3 Response truncated, continuing ({continuation_count}/{max_continuations})")

            cont_kwargs = dict(kwargs)
            cont_kwargs["messages"] = [
                {"role": "user", "content": request.prompt},
                {"role": "assistant", "content": content},
                {"role": "user", "content": "Continue from where you left off. Do not repeat what you already wrote."}
            ]
            try:
                cont_response = await async_client.messages.create(**cont_kwargs)
                content += "\n" + cont_response.content[0].text
                tokens_in += cont_response.usage.input_tokens
                tokens_out += cont_response.usage.output_tokens
                stop_reason = cont_response.stop_reason
            except Exception as e:
                logger.error(f"Continuation failed: {e}")
                break

        latency_ms = int((time.time() - start_time) * 1000)
        cost_usd = self._calculate_cost(provider_str, tokens_in, tokens_out)

        return LLMResponse(
            content=content, provider=provider_str, model_id=model_id,
            tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd,
            latency_ms=latency_ms, success=True, stop_reason=stop_reason,
            metadata={"continuations": continuation_count}
        )
    except Exception as e:
        # ... (existing error handling)
```

**Gains** :
- N33 résolu — retour à la parité V1/V3
- Marcus / Emma peuvent revenir à `max_tokens` raisonnables (16K au lieu de 32K) sans truncation
- Commit `3cf7dd1` "Emma max_tokens 16K→32K" devient obsolète, peut être reverted

---

### LLM-4 — Middleware `build_enabled` (freemium)

**Nouveau fichier** : `backend/app/middleware/build_enabled.py`

```python
"""
Middleware that enforces build_enabled flag from active deployment profile.

In freemium profile, BUILD endpoints return 403 with a clear upgrade prompt.
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
import re

logger = logging.getLogger(__name__)

# URLs patterns that require build_enabled=true
BUILD_URL_PATTERNS = [
    re.compile(r"^/api/pm-orchestrator/execute/\d+/build"),
    re.compile(r"^/api/pm-orchestrator/execute/\d+/deploy"),
    re.compile(r"^/api/build/"),
    # Add more as needed
]

class BuildEnabledMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Check if this is a BUILD endpoint
        is_build_endpoint = any(p.match(path) for p in BUILD_URL_PATTERNS)
        if not is_build_endpoint:
            return await call_next(request)

        # Check if BUILD is enabled in current profile
        from app.services.llm_router_service import get_llm_router
        router = get_llm_router()
        if not router.is_build_enabled():
            profile = router.get_active_profile()
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "build_disabled",
                    "message": (
                        f"BUILD features are not available in the '{profile['name']}' tier. "
                        f"Upgrade to unlock code generation, deployment, and QA automation."
                    ),
                    "profile": profile["name"],
                    "upgrade_url": "/pricing",
                }
            )

        return await call_next(request)
```

**Registration** dans `backend/app/main.py` :
```python
from app.middleware.build_enabled import BuildEnabledMiddleware

app.add_middleware(BuildEnabledMiddleware)
```

**Endpoint companion** `backend/app/api/routes/config.py` :
```python
from fastapi import APIRouter
from app.services.llm_router_service import get_llm_router

router = APIRouter(prefix="/api/config", tags=["config"])

@router.get("/capabilities")
def get_capabilities():
    """
    Return capabilities for the frontend to adapt UI.
    Used to grey out BUILD button in freemium tier.
    """
    llm_router = get_llm_router()
    profile = llm_router.get_active_profile()
    return {
        "profile": profile["name"],
        "build_enabled": profile.get("build_enabled", True),
        "description": profile.get("description", ""),
    }
```

**Frontend usage** (suggestion) : au boot de l'app, `GET /api/config/capabilities` → store dans Redux/Zustand → `<BuildButton disabled={!capabilities.build_enabled} />`

---

### LLM-5 — Pricing unifié depuis YAML

**Fichier** : `backend/app/services/budget_service.py`

**Avant** (L17-31) :
```python
MODEL_PRICING = {
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
    # ... 10 entries hardcoded
}
```

**Après** :
```python
def _load_pricing_from_config() -> dict:
    """Load pricing from llm_routing.yaml at module import time."""
    try:
        from app.services.llm_router_service import get_llm_router
        router = get_llm_router()
        return router.config.get("pricing", {})
    except Exception as e:
        logger.error(f"Failed to load pricing from config: {e}")
        return {}

# Loaded at import, indexed by provider_str (e.g. "anthropic/opus-latest")
MODEL_PRICING = _load_pricing_from_config()

def estimate_cost_from_provider(provider_str: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost using provider string (e.g. 'anthropic/opus-latest')."""
    pricing = MODEL_PRICING.get(provider_str, {"input": 3.0, "output": 15.0})  # Sonnet fallback
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return round(cost, 6)
```

**Caller adaptation** : les callers passent maintenant `provider_str` (retourné dans la response LLM), pas `model` :

```python
# Avant
budget_service.record_cost(execution_id, response["model"], input_tokens, output_tokens)

# Après
budget_service.record_cost(execution_id, response["provider"], input_tokens, output_tokens)
```

**Gains** :
- N35 (pricing dup) résolu — source unique
- N41 (opus-4-6 vs opus-4-6-20260201) résolu — on track par `provider_str` stable (`anthropic/opus-latest`), pas par l'ID model retourné

---

## 5. Migration chart — avant / après

| Avant | Après |
|-------|-------|
| `generate_llm_response(agent_type="sophie")` | idem — inchangé pour les agents |
| `LLMService()` instancié direct (bypass V3) | **interdit** — classe supprimée |
| `AGENT_TIER_MAP["sophie"]` → `ORCHESTRATOR` → `claude-opus-4-5-20251101` (hardcoded Python) | `agent_complexity_map["sophie"]` → `orchestrator` → `profiles.cloud.orchestrator` → `anthropic/opus-latest` → `providers.anthropic.models.opus-latest.model_id` → Claude Opus dernière version |
| 3 tiers `ORCHESTRATOR/ANALYST/WORKER` + subdivisions YAML `simple/medium/complex/critical` | 2 tiers `orchestrator/worker` — 1 source |
| OpenAI fallback silencieux | Pas de fallback cross-provider (sauf profile `cloud` explicite dans le futur) |
| Ollama déclenché si agent_type non mappé | Profile-driven : Ollama uniquement en `on-premise` ou `freemium` |
| Pricing dans `budget_service.MODEL_PRICING` + YAML `pricing` | YAML `pricing` unique, lu au boot |
| `ANTHROPIC_MODELS[ORCHESTRATOR] = "claude-opus-4-5-20251101"` | `providers.anthropic.models.opus-latest.model_id = "claude-opus-4-7-XXX"` |
| Changer Opus = éditer 4 fichiers Python | Changer Opus = éditer 1 ligne YAML |

---

## 6. Plan d'exécution

### Sprint 1 — YAML refonte + Router adapt (jour 1)
- LLM-1 : patch `_select_provider` + ajout `is_build_enabled` / `get_active_profile`
- Nouveau YAML `config/llm_routing.yaml`
- Vérifier que 1 profile = valide + tests smoke

### Sprint 2 — Suppression V1 (jour 1-2)
- LLM-0 : réécriture `llm_service.py` en wrapper mince
- Callers qui instanciaient `LLMService()` directement : migrés
  - `change_request_service.py` L54
  - `hitl_routes.py` L266
- Retrait OpenAI path

### Sprint 3 — Continuation CRIT-02 + pricing (jour 2)
- LLM-3 : port continuation dans Router V3 `_call_anthropic`
- LLM-5 : `budget_service` refactor pricing

### Sprint 4 — Middleware + endpoint capabilities (jour 3)
- LLM-4 : `BuildEnabledMiddleware` + `/api/config/capabilities`
- Integration tests : `DH_DEPLOYMENT_PROFILE=freemium` → `POST /execute/1/build` retourne 403

### Sprint 5 — Validation multi-profile (jour 3-4)
- Test complet en mode `cloud` (default)
- Test en mode `on-premise` (ollama local requis — peut être mocké)
- Test en mode `freemium` avec build_enabled=false

---

## 7. DoD — Definition of Done

```bash
# 1. V1 LLMService supprimée
grep -n "class LLMService" backend/app/services/llm_service.py && echo "❌ still present" || echo "✅ removed"

# 2. Bypass direct introuvable
grep -rn "LLMService()" backend/app --include="*.py" | grep -v "llm_router" | grep -v "# deprecated"
# Should return 0 lines

# 3. YAML charge 3 profiles
python -c "
from app.services.llm_router_service import get_llm_router
r = get_llm_router()
assert 'cloud' in r.config['profiles']
assert 'on-premise' in r.config['profiles']
assert 'freemium' in r.config['profiles']
print('✅ 3 profiles loaded')
"

# 4. Routing test cloud
DH_DEPLOYMENT_PROFILE=cloud python -c "
from app.services.llm_router_service import get_llm_router, LLMRequest
r = get_llm_router()
provider = r._select_provider(LLMRequest(prompt='', agent_type='sophie'))
assert provider == 'anthropic/opus-latest', f'got {provider}'
print('✅ cloud/sophie → opus')
"

# 5. Routing test freemium blocks build
DH_DEPLOYMENT_PROFILE=freemium curl -X POST http://localhost:8002/api/pm-orchestrator/execute/1/build
# Should return 403 with build_disabled

# 6. Continuation works
python -c "
# Test that a long response gets auto-continued
# (requires mock or live API)
"

# 7. Pricing cohérent
python -c "
from app.services.budget_service import MODEL_PRICING
assert 'anthropic/opus-latest' in MODEL_PRICING
print('✅ pricing loaded from YAML')
"
```

---

## 8. Risques & points d'attention

1. **Régression pendant suppression V1** : s'assurer que tous les callers de `LLMService()` sont migrés AVANT la suppression de la classe. Utiliser `grep -rn "LLMService()"` exhaustivement.

2. **Alias Anthropic réels** : à vérifier au moment du chantier si Anthropic supporte des alias type `claude-opus-latest`. Si non, `opus-latest` reste un alias **local** mappé vers la version datée dans le YAML (pattern déjà proposé).

3. **Cost tracking migration** : après LLM-5, les anciennes lignes DB `executions.total_cost` tracées avec l'ancien pricing peuvent avoir des valeurs sous-estimées. Prévoir soit :
   - Script de re-calcul rétroactif depuis les tokens
   - Flag dans l'UI "coûts pré-v3 approximatifs"

4. **Tests multi-profile** : nécessitent un environnement Ollama pour `on-premise` / `freemium`. Utiliser des mocks au lieu d'un Ollama réel pour les tests CI.

5. **Frontend adaptation** : le middleware `build_enabled` retournera des 403 sur les endpoints build si mal utilisé. Le frontend doit lire `/api/config/capabilities` au boot et adapter son UI. Sinon l'utilisateur voit des erreurs techniques.

6. **Durée de migration client L'Oréal/LVMH** : le profile `on-premise` n'a pas été testé réellement (Ollama OFF en dev). Prévoir une phase de POC avec un Ollama local avant de lancer chez un vrai client.

---

## 9. Livrables attendus

- `backend/config/llm_routing.yaml` refondu (format section 2.3)
- `backend/app/services/llm_service.py` réécrit (~150 LOC)
- `backend/app/services/llm_router_service.py` patchée (profile-aware + continuation)
- `backend/app/services/budget_service.py` pricing from YAML
- `backend/app/middleware/build_enabled.py` nouveau
- `backend/app/api/routes/config.py` nouveau
- `docs/ADR-001-llm-strategy.md` nouveau — décision architecturale
- Tests unitaires pour les 3 profiles + fallback behavior
- CHANGELOG.md mis à jour

---

## 10. Documentation utilisateur

Au moment de déployer, ajouter dans `docs/deployment.md` :

```markdown
## Deployment profiles

Digital Humans supports three deployment profiles via the
`DH_DEPLOYMENT_PROFILE` environment variable:

- `cloud` (default) — Anthropic API, full BUILD pipeline
- `on-premise` — Ollama local only, data sovereignty, full BUILD
- `freemium` — Ollama local, SDS-only, BUILD disabled

Set via:
```bash
export DH_DEPLOYMENT_PROFILE=cloud
# or in systemd unit: Environment="DH_DEPLOYMENT_PROFILE=cloud"
```

Current profile capabilities can be queried at:
```
GET /api/config/capabilities
```
```

*Fin briefing Agent C*
