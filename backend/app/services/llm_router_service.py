#!/usr/bin/env python3
"""
LLM Router Service — Centralized LLM Management with Multi-Profile Support.

Features:
- 3 deployment profiles : cloud / on-premise / freemium (source YAML).
- 2 logical tiers        : orchestrator / worker (per-profile mapping).
- Profile-aware fallback chain (on-premise ne fallback jamais vers cloud).
- Cost tracking via budget_service (pricing read from YAML).
- Continuation automatique sur stop_reason="max_tokens" (CRIT-02 ported from V1).

Env var : DH_DEPLOYMENT_PROFILE = cloud | on-premise | freemium (default: cloud).

Version: 2.0.0 (session3 — Agent C)
"""

import os
import time
import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

import yaml
import httpx
from app.config import settings

try:
    from anthropic import Anthropic, AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None
    AsyncAnthropic = None

try:
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
    AsyncOpenAI = None


logger = logging.getLogger(__name__)


class AgentTier(str, Enum):
    """Logical tiers for agent routing (2 tiers only — was 4 before session3)."""
    ORCHESTRATOR = "orchestrator"   # PM, BA, Architect, Research — raisonnement
    WORKER = "worker"               # Apex, LWC, Admin, QA, DevOps, Data, Trainer


class ProviderType(str, Enum):
    LOCAL = "local"        # Ollama
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


# Backward-compat alias for callers still using TaskComplexity
class TaskComplexity(str, Enum):
    """Deprecated — kept for backward compatibility. Use AgentTier instead."""
    SIMPLE = "worker"
    MEDIUM = "worker"
    COMPLEX = "orchestrator"
    CRITICAL = "orchestrator"


@dataclass
class LLMRequest:
    """Request object for LLM calls."""
    prompt: str
    task_type: Any = None                           # Deprecated — kept for legacy callers
    system_prompt: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.3
    force_provider: Optional[str] = None            # e.g., "anthropic/claude-sonnet"
    agent_type: Optional[str] = None                # Preferred : routing via agent_tier_map
    project_id: Optional[int] = None
    execution_id: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str
    provider: str
    model_id: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    success: bool
    error: Optional[str] = None
    stop_reason: Optional[str] = None
    continuations: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMRouterService:
    """
    Multi-profile LLM Router.

    Usage:
        router = get_llm_router()
        response = await router.complete(LLMRequest(
            prompt="...", agent_type="marcus"
        ))

    Profile is selected at init time from DH_DEPLOYMENT_PROFILE env var.
    Re-init (or call reload_config()) to switch profile at runtime.
    """

    # Max continuations for max_tokens stop_reason (CRIT-02 port)
    MAX_CONTINUATIONS = 3

    def __init__(self, config_path: Optional[str] = None, profile: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()

        # Profile resolution : explicit arg > env var > YAML default
        self.profile = profile or self._resolve_active_profile()
        self._validate_profile()

        self.providers: Dict[str, Any] = {}
        self.async_providers: Dict[str, Any] = {}

        self.usage_log: List[Dict[str, Any]] = []
        self.session_cost_usd: float = 0.0

        self._init_providers()

        logger.info(
            "LLM Router initialized : profile=%s, build_enabled=%s, config=%s",
            self.profile, self.is_build_enabled(), self.config_path,
        )

    # ----------------------------------------------------------------------
    # Config loading
    # ----------------------------------------------------------------------

    def _get_default_config_path(self) -> str:
        candidates = [
            Path(__file__).parent.parent.parent / "config" / "llm_routing.yaml",
            settings.LLM_CONFIG_PATH,
            Path("config/llm_routing.yaml"),
        ]
        for path in candidates:
            if path.exists():
                return str(path)
        raise FileNotFoundError(f"LLM routing config not found. Tried: {candidates}")

    def _load_config(self) -> Dict[str, Any]:
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        return self._expand_env_vars(config)

    def _expand_env_vars(self, obj: Any) -> Any:
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                val = os.environ.get(var_name)
                return val if val else None
            return obj
        if isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        return obj

    def _resolve_active_profile(self) -> str:
        """Profile selection : DH_DEPLOYMENT_PROFILE env > YAML active_profile > YAML default."""
        active = self.config.get("active_profile")
        if active:
            return active
        return self.config.get("default_profile", "cloud")

    def _validate_profile(self):
        profiles = self.config.get("profiles", {})
        if self.profile not in profiles:
            available = list(profiles.keys())
            raise ValueError(
                f"Profile '{self.profile}' not found in YAML. Available: {available}"
            )
        required_tiers = {"orchestrator", "worker"}
        missing = required_tiers - set(profiles[self.profile].keys())
        if missing:
            raise ValueError(
                f"Profile '{self.profile}' is missing required tiers: {missing}"
            )

    def reload_config(self, profile: Optional[str] = None):
        """Reload YAML + re-init providers. Useful for tests and profile switching."""
        self.config = self._load_config()
        if profile:
            self.profile = profile
        else:
            self.profile = self._resolve_active_profile()
        self._validate_profile()
        self.providers = {}
        self.async_providers = {}
        self._init_providers()

    # ----------------------------------------------------------------------
    # Provider initialization
    # ----------------------------------------------------------------------

    def _init_providers(self):
        providers_config = self.config.get("providers", {})

        if providers_config.get("ollama", {}).get("enabled", False):
            ollama_cfg = providers_config["ollama"]
            self.providers["local"] = {
                "type": ProviderType.LOCAL,
                "base_url": ollama_cfg.get("base_url", "http://localhost:11434"),
                "timeout": ollama_cfg.get("timeout_seconds", 300),
                "models": ollama_cfg.get("models", {}),
            }
            logger.info("Ollama provider configured")

        if providers_config.get("anthropic", {}).get("enabled", False) and ANTHROPIC_AVAILABLE:
            api_key_env = providers_config["anthropic"].get("api_key_env", "ANTHROPIC_API_KEY")
            api_key = os.environ.get(api_key_env)
            if api_key:
                timeout = providers_config["anthropic"].get("timeout_seconds", 600)
                self.providers["anthropic"] = {
                    "type": ProviderType.ANTHROPIC,
                    "client": Anthropic(api_key=api_key, timeout=float(timeout)),
                    "models": providers_config["anthropic"].get("models", {}),
                }
                self.async_providers["anthropic"] = {
                    "type": ProviderType.ANTHROPIC,
                    "client": AsyncAnthropic(api_key=api_key, timeout=float(timeout)),
                    "models": providers_config["anthropic"].get("models", {}),
                }
                logger.info("Anthropic provider initialized")
            else:
                logger.warning("%s not set, Anthropic disabled", api_key_env)

        if providers_config.get("openai", {}).get("enabled", False) and OPENAI_AVAILABLE:
            api_key_env = providers_config["openai"].get("api_key_env", "OPENAI_API_KEY")
            api_key = os.environ.get(api_key_env)
            if api_key:
                self.providers["openai"] = {
                    "type": ProviderType.OPENAI,
                    "client": OpenAI(api_key=api_key),
                    "models": providers_config["openai"].get("models", {}),
                }
                self.async_providers["openai"] = {
                    "type": ProviderType.OPENAI,
                    "client": AsyncOpenAI(api_key=api_key),
                    "models": providers_config["openai"].get("models", {}),
                }
                logger.info("OpenAI provider initialized")
            else:
                logger.warning("%s not set, OpenAI disabled", api_key_env)

    # ----------------------------------------------------------------------
    # Public accessors
    # ----------------------------------------------------------------------

    def get_active_profile(self) -> str:
        return self.profile

    def is_build_enabled(self) -> bool:
        return bool(self.config["profiles"][self.profile].get("build_enabled", True))

    def get_tier_for_agent(self, agent_type: str) -> AgentTier:
        """Map agent_type → tier via YAML. Unknown agents default to WORKER."""
        normalized = (agent_type or "").lower().replace("-", "_").replace(" ", "_")
        tier_map = self.config.get("agent_tier_map", {})
        tier_str = tier_map.get(normalized, "worker")
        try:
            return AgentTier(tier_str)
        except ValueError:
            logger.warning("Unknown tier '%s' for agent '%s', defaulting to worker", tier_str, agent_type)
            return AgentTier.WORKER

    # ----------------------------------------------------------------------
    # Routing
    # ----------------------------------------------------------------------

    def _select_provider(self, request: LLMRequest) -> str:
        """
        Select provider/model for a request based on the active profile.

        Returns e.g. "anthropic/claude-opus" or "local/mixtral".
        """
        if request.force_provider:
            return request.force_provider

        tier = AgentTier.WORKER
        if request.agent_type:
            tier = self.get_tier_for_agent(request.agent_type)
        elif request.task_type is not None:
            # Legacy TaskComplexity fallback
            try:
                legacy = request.task_type.value if hasattr(request.task_type, "value") else str(request.task_type)
                if legacy in ("complex", "critical", "orchestrator"):
                    tier = AgentTier.ORCHESTRATOR
            except Exception:
                pass

        profile_cfg = self.config["profiles"][self.profile]
        provider = profile_cfg.get(tier.value)
        if not provider:
            raise RuntimeError(
                f"Profile '{self.profile}' is missing tier '{tier.value}' mapping"
            )
        return provider

    def _fallback_for(self, provider_str: str) -> Optional[str]:
        """Get the fallback provider for a given provider, scoped to the active profile."""
        chain = self.config["profiles"][self.profile].get("fallback_chain", {}) or {}
        return chain.get(provider_str)

    def _get_model_id(self, provider_str: str) -> str:
        provider_name, model_name = provider_str.split("/", 1)
        if provider_name == "local":
            return model_name
        provider_config = self.providers.get(provider_name, {})
        models = provider_config.get("models", {})
        model_config = models.get(model_name, {})
        return model_config.get("model_id", model_name)

    def _calculate_cost(self, provider_str: str, tokens_in: int, tokens_out: int) -> float:
        pricing = self.config.get("pricing", {}).get(provider_str, {})
        cost_in = (tokens_in / 1_000_000) * pricing.get("input", 0)
        cost_out = (tokens_out / 1_000_000) * pricing.get("output", 0)
        return round(cost_in + cost_out, 6)

    # ----------------------------------------------------------------------
    # Provider calls
    # ----------------------------------------------------------------------

    async def _call_ollama(self, request: LLMRequest, model: str) -> LLMResponse:
        start_time = time.time()
        ollama_cfg = self.providers.get("local", {})
        if not ollama_cfg:
            return LLMResponse(
                content="", provider=f"local/{model}", model_id=model,
                tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=0,
                success=False, error="Ollama provider not initialized",
            )

        base_url = ollama_cfg.get("base_url", "http://localhost:11434")
        timeout = ollama_cfg.get("timeout", 300)

        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()

            content = data.get("response", "")
            tokens_out = data.get("eval_count", len(content) // 4)
            tokens_in = data.get("prompt_eval_count", len(request.prompt) // 4)
            latency_ms = int((time.time() - start_time) * 1000)

            return LLMResponse(
                content=content, provider=f"local/{model}", model_id=model,
                tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=0.0,
                latency_ms=latency_ms, success=True,
                stop_reason=data.get("done_reason", "stop"),
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("Ollama call failed: %s", e)
            return LLMResponse(
                content="", provider=f"local/{model}", model_id=model,
                tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=latency_ms,
                success=False, error=str(e),
            )

    async def _call_anthropic(self, request: LLMRequest, model_id: str, provider_str: str) -> LLMResponse:
        """Call Anthropic Claude API with automatic continuation on max_tokens (CRIT-02 port)."""
        start_time = time.time()

        async_client = self.async_providers.get("anthropic", {}).get("client")
        if not async_client:
            return LLMResponse(
                content="", provider=provider_str, model_id=model_id,
                tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=0,
                success=False, error="Anthropic client not initialized",
            )

        def _build_kwargs(messages: List[Dict[str, str]]) -> Dict[str, Any]:
            kw = {"model": model_id, "max_tokens": request.max_tokens, "messages": messages}
            if request.system_prompt:
                kw["system"] = request.system_prompt
            if request.temperature <= 1.0:
                kw["temperature"] = request.temperature
            return kw

        try:
            messages = [{"role": "user", "content": request.prompt}]
            response = await async_client.messages.create(**_build_kwargs(messages))

            content = response.content[0].text
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            stop_reason = response.stop_reason

            # CRIT-02 port : auto-continue if truncated
            continuations = 0
            while stop_reason == "max_tokens" and continuations < self.MAX_CONTINUATIONS:
                continuations += 1
                logger.warning(
                    "Response truncated, continuing (%d/%d) — model=%s",
                    continuations, self.MAX_CONTINUATIONS, model_id,
                )
                cont_messages = [
                    {"role": "user", "content": request.prompt},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": "Continue from where you left off. Do not repeat what you already wrote."},
                ]
                try:
                    cont_resp = await async_client.messages.create(**_build_kwargs(cont_messages))
                    cont_text = cont_resp.content[0].text
                    stop_reason = cont_resp.stop_reason
                    content += "\n" + cont_text
                    tokens_in += cont_resp.usage.input_tokens
                    tokens_out += cont_resp.usage.output_tokens
                except Exception as cont_err:
                    logger.error("Continuation %d failed: %s", continuations, cont_err)
                    break

            latency_ms = int((time.time() - start_time) * 1000)
            cost_usd = self._calculate_cost(provider_str, tokens_in, tokens_out)

            return LLMResponse(
                content=content, provider=provider_str, model_id=model_id,
                tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd,
                latency_ms=latency_ms, success=True, stop_reason=stop_reason,
                continuations=continuations,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("Anthropic call failed: %s", e)
            return LLMResponse(
                content="", provider=provider_str, model_id=model_id,
                tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=latency_ms,
                success=False, error=str(e),
            )

    async def _call_openai(self, request: LLMRequest, model_id: str, provider_str: str) -> LLMResponse:
        start_time = time.time()
        async_client = self.async_providers.get("openai", {}).get("client")
        if not async_client:
            return LLMResponse(
                content="", provider=provider_str, model_id=model_id,
                tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=0,
                success=False, error="OpenAI client not initialized",
            )

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        try:
            response = await async_client.chat.completions.create(
                model=model_id, messages=messages,
                max_tokens=request.max_tokens, temperature=request.temperature,
            )
            content = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            latency_ms = int((time.time() - start_time) * 1000)
            cost_usd = self._calculate_cost(provider_str, tokens_in, tokens_out)
            return LLMResponse(
                content=content, provider=provider_str, model_id=model_id,
                tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost_usd,
                latency_ms=latency_ms, success=True,
                stop_reason=response.choices[0].finish_reason,
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("OpenAI call failed: %s", e)
            return LLMResponse(
                content="", provider=provider_str, model_id=model_id,
                tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=latency_ms,
                success=False, error=str(e),
            )

    # ----------------------------------------------------------------------
    # Entry points
    # ----------------------------------------------------------------------

    async def complete(self, request: LLMRequest) -> LLMResponse:
        provider_str = self._select_provider(request)
        logger.info(
            "LLM Request: agent=%s, profile=%s, provider=%s",
            request.agent_type, self.profile, provider_str,
        )

        response = await self._call_provider(request, provider_str)

        # Fallback chain scoped to profile
        if not response.success:
            fallback = self._fallback_for(provider_str)
            if fallback and fallback != provider_str:
                logger.warning("Falling back from %s to %s (profile=%s)", provider_str, fallback, self.profile)
                response = await self._call_provider(request, fallback)
            elif fallback == provider_str:
                logger.info("No-op fallback for %s in profile %s", provider_str, self.profile)
            else:
                logger.warning(
                    "No fallback configured for %s in profile %s — error surfaced as-is",
                    provider_str, self.profile,
                )

        self._track_usage(request, response)
        return response

    async def _call_provider(self, request: LLMRequest, provider_str: str) -> LLMResponse:
        provider_name, model_name = provider_str.split("/", 1)
        model_id = self._get_model_id(provider_str)

        if provider_name == "local":
            return await self._call_ollama(request, model_name)
        if provider_name == "anthropic":
            return await self._call_anthropic(request, model_id, provider_str)
        if provider_name == "openai":
            return await self._call_openai(request, model_id, provider_str)

        return LLMResponse(
            content="", provider=provider_str, model_id=model_id,
            tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=0,
            success=False, error=f"Unknown provider: {provider_name}",
        )

    def _track_usage(self, request: LLMRequest, response: LLMResponse):
        self.session_cost_usd += response.cost_usd
        self.usage_log.append({
            "timestamp": datetime.now().isoformat(),
            "provider": response.provider,
            "model_id": response.model_id,
            "agent_type": request.agent_type,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
            "success": response.success,
            "project_id": request.project_id,
            "execution_id": request.execution_id,
        })
        if response.cost_usd > 0:
            logger.info(
                "Cost: $%.4f | session total: $%.4f",
                response.cost_usd, self.session_cost_usd,
            )

    def get_session_stats(self) -> Dict[str, Any]:
        if not self.usage_log:
            return {"total_requests": 0, "total_cost_usd": 0.0, "by_provider": {}}
        by_provider: Dict[str, Dict] = {}
        for entry in self.usage_log:
            p = entry["provider"]
            if p not in by_provider:
                by_provider[p] = {"requests": 0, "cost_usd": 0.0, "tokens": 0}
            by_provider[p]["requests"] += 1
            by_provider[p]["cost_usd"] += entry["cost_usd"]
            by_provider[p]["tokens"] += entry["tokens_in"] + entry["tokens_out"]
        return {
            "total_requests": len(self.usage_log),
            "total_cost_usd": round(self.session_cost_usd, 4),
            "by_provider": by_provider,
        }

    def get_available_providers(self) -> Dict[str, bool]:
        return {
            "local/ollama": "local" in self.providers,
            "anthropic": "anthropic" in self.providers,
            "openai": "openai" in self.providers,
        }

    # ----------------------------------------------------------------------
    # Sync + legacy wrappers
    # ----------------------------------------------------------------------

    def complete_sync(self, request: LLMRequest) -> LLMResponse:
        """Sync wrapper for complete() — handles being inside an async context."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.complete(request))
                return future.result(timeout=600)
        return asyncio.run(self.complete(request))

    def generate(
        self,
        prompt: str,
        agent_type: str = "worker",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs,
    ) -> Dict[str, Any]:
        """Sync convenience method matching the legacy LLMService interface."""
        request = LLMRequest(
            prompt=prompt, agent_type=agent_type, system_prompt=system_prompt,
            max_tokens=max_tokens, temperature=temperature,
            project_id=kwargs.get("project_id"),
            execution_id=kwargs.get("execution_id"),
        )
        response = self.complete_sync(request)
        return _response_to_dict(response)

    async def generate_async(
        self,
        prompt: str,
        agent_type: str = "worker",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs,
    ) -> Dict[str, Any]:
        """Async convenience method matching the legacy LLMService interface."""
        request = LLMRequest(
            prompt=prompt, agent_type=agent_type, system_prompt=system_prompt,
            max_tokens=max_tokens, temperature=temperature,
            project_id=kwargs.get("project_id"),
            execution_id=kwargs.get("execution_id"),
        )
        response = await self.complete(request)
        return _response_to_dict(response)


def _response_to_dict(response: LLMResponse) -> Dict[str, Any]:
    return {
        "content": response.content,
        "model": response.model_id,
        "provider": response.provider,
        "tokens_used": response.tokens_in + response.tokens_out,
        "input_tokens": response.tokens_in,
        "output_tokens": response.tokens_out,
        "cost_usd": response.cost_usd,
        "latency_ms": response.latency_ms,
        "success": response.success,
        "error": response.error,
        "stop_reason": response.stop_reason,
        "continuations": response.continuations,
    }


# Singleton
_router_instance: Optional[LLMRouterService] = None


def get_llm_router() -> LLMRouterService:
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouterService()
    return _router_instance


def reset_llm_router():
    """Reset the singleton — used by tests to switch profile via env var."""
    global _router_instance
    _router_instance = None


async def route_llm_request(
    prompt: str,
    agent_type: Optional[str] = None,
    system_prompt: Optional[str] = None,
    **kwargs,
) -> LLMResponse:
    router = get_llm_router()
    request = LLMRequest(
        prompt=prompt, agent_type=agent_type, system_prompt=system_prompt, **kwargs,
    )
    return await router.complete(request)


if __name__ == "__main__":
    async def _test():
        router = LLMRouterService()
        print(f"Profile: {router.get_active_profile()}")
        print(f"Build enabled: {router.is_build_enabled()}")
        print(f"Providers: {router.get_available_providers()}")
        provider = router._select_provider(LLMRequest(prompt="", agent_type="marcus"))
        print(f"Marcus → {provider}")
        provider = router._select_provider(LLMRequest(prompt="", agent_type="diego"))
        print(f"Diego  → {provider}")
    asyncio.run(_test())
