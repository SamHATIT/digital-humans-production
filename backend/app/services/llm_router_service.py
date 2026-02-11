#!/usr/bin/env python3
"""
LLM Router Service - Centralized LLM Management with Cost Optimization

Features:
- Multi-provider support (Ollama local, Anthropic, OpenAI, Custom)
- Task complexity-based routing
- Cost tracking and reporting
- Automatic fallback chain
- YAML-based configuration

Version: 1.0.0
Created: 2026-01-26
Author: Digital Humans Team
"""

import os
import sys
import time
import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from datetime import datetime

import yaml
import httpx
from app.config import settings

# Provider imports - handled gracefully
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


# Configure logging
logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels for routing decisions"""
    SIMPLE = "simple"      # CRUD, extraction, UC analysis
    MEDIUM = "medium"      # Analysis, transformation
    COMPLEX = "complex"    # Synthesis, architecture
    CRITICAL = "critical"  # Final documents, validation


class ProviderType(str, Enum):
    """Supported LLM provider types"""
    LOCAL = "local"        # Ollama
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    MISTRAL = "mistral"
    CUSTOM = "custom"


@dataclass
class LLMRequest:
    """Request object for LLM calls"""
    prompt: str
    task_type: TaskComplexity = TaskComplexity.SIMPLE
    system_prompt: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.3
    force_provider: Optional[str] = None  # e.g., "anthropic/claude-sonnet"
    agent_type: Optional[str] = None      # For backward compatibility
    project_id: Optional[int] = None      # For cost tracking
    execution_id: Optional[int] = None    # For cost tracking
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response object from LLM calls"""
    content: str
    provider: str              # e.g., "anthropic/claude-sonnet"
    model_id: str             # Actual model ID used
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    success: bool
    error: Optional[str] = None
    stop_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMRouterService:
    """
    Centralized LLM Router with multi-provider support.
    
    Usage:
        router = LLMRouterService()
        
        # Simple call
        response = await router.complete(LLMRequest(
            prompt="Analyze this UC...",
            task_type=TaskComplexity.SIMPLE
        ))
        
        # Force specific provider
        response = await router.complete(LLMRequest(
            prompt="Synthesize SDS...",
            task_type=TaskComplexity.COMPLEX,
            force_provider="anthropic/claude-sonnet"
        ))
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the router.
        
        Args:
            config_path: Path to YAML config file. If None, uses default location.
        """
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        self.providers: Dict[str, Any] = {}
        self.async_providers: Dict[str, Any] = {}
        
        # Usage tracking
        self.usage_log: List[Dict[str, Any]] = []
        self.session_cost_usd: float = 0.0
        
        self._init_providers()
        
        logger.info(f"✅ LLM Router initialized with config from {self.config_path}")
    
    def _get_default_config_path(self) -> str:
        """Get default config file path"""
        # Try multiple locations
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
        """Load and parse YAML configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Expand environment variables in config
            config = self._expand_env_vars(config)
            
            return config
        except Exception as e:
            logger.error(f"Failed to load config from {self.config_path}: {e}")
            raise
    
    def _expand_env_vars(self, obj: Any) -> Any:
        """Recursively expand ${VAR} patterns in config"""
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.environ.get(var_name, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        return obj
    
    def _init_providers(self):
        """Initialize all configured providers"""
        providers_config = self.config.get("providers", {})
        
        # Initialize Ollama (local)
        if providers_config.get("ollama", {}).get("enabled", False):
            ollama_config = providers_config["ollama"]
            self.providers["local"] = {
                "type": ProviderType.LOCAL,
                "base_url": ollama_config.get("base_url", "http://localhost:11434"),
                "timeout": ollama_config.get("timeout_seconds", 300),
                "models": ollama_config.get("models", {})
            }
            logger.info("✅ Ollama provider configured")
        
        # Initialize Anthropic
        if providers_config.get("anthropic", {}).get("enabled", False) and ANTHROPIC_AVAILABLE:
            api_key_env = providers_config["anthropic"].get("api_key_env", "ANTHROPIC_API_KEY")
            api_key = os.environ.get(api_key_env)
            
            if api_key:
                timeout = providers_config["anthropic"].get("timeout_seconds", 600)
                self.providers["anthropic"] = {
                    "type": ProviderType.ANTHROPIC,
                    "client": Anthropic(api_key=api_key, timeout=float(timeout)),
                    "models": providers_config["anthropic"].get("models", {})
                }
                self.async_providers["anthropic"] = {
                    "type": ProviderType.ANTHROPIC,
                    "client": AsyncAnthropic(api_key=api_key, timeout=float(timeout)),
                    "models": providers_config["anthropic"].get("models", {})
                }
                logger.info("✅ Anthropic provider initialized")
            else:
                logger.warning(f"⚠️ {api_key_env} not set, Anthropic disabled")
        
        # Initialize OpenAI
        if providers_config.get("openai", {}).get("enabled", False) and OPENAI_AVAILABLE:
            api_key_env = providers_config["openai"].get("api_key_env", "OPENAI_API_KEY")
            api_key = os.environ.get(api_key_env)
            
            if api_key:
                self.providers["openai"] = {
                    "type": ProviderType.OPENAI,
                    "client": OpenAI(api_key=api_key),
                    "models": providers_config["openai"].get("models", {})
                }
                self.async_providers["openai"] = {
                    "type": ProviderType.OPENAI,
                    "client": AsyncOpenAI(api_key=api_key),
                    "models": providers_config["openai"].get("models", {})
                }
                logger.info("✅ OpenAI provider initialized")
            else:
                logger.warning(f"⚠️ {api_key_env} not set, OpenAI disabled")
    
    def _select_provider(self, request: LLMRequest) -> str:
        """
        Select the best provider for a request.
        
        Returns:
            Provider string like "local/mistral-nemo" or "anthropic/claude-sonnet"
        """
        # If force_provider is set, use it
        if request.force_provider:
            return request.force_provider
        
        # Map agent_type to complexity if provided (backward compatibility)
        if request.agent_type:
            agent_map = self.config.get("agent_complexity_map", {})
            complexity_str = agent_map.get(request.agent_type.lower(), "simple")
            request.task_type = TaskComplexity(complexity_str)
        
        # Get routing from config
        routing = self.config.get("default_routing", {})
        return routing.get(request.task_type.value, "anthropic/claude-haiku")
    
    def _get_model_id(self, provider_str: str) -> str:
        """Get the actual model ID for API calls"""
        provider_name, model_name = provider_str.split("/", 1)
        
        if provider_name == "local":
            # Ollama uses model name directly
            return model_name
        
        provider_config = self.providers.get(provider_name, {})
        models = provider_config.get("models", {})
        model_config = models.get(model_name, {})
        
        return model_config.get("model_id", model_name)
    
    def _calculate_cost(self, provider_str: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost in USD for a request"""
        pricing = self.config.get("pricing", {}).get(provider_str, {})
        
        cost_in = (tokens_in / 1_000_000) * pricing.get("input", 0)
        cost_out = (tokens_out / 1_000_000) * pricing.get("output", 0)
        
        return round(cost_in + cost_out, 6)
    
    async def _call_ollama(
        self,
        request: LLMRequest,
        model: str
    ) -> LLMResponse:
        """Call Ollama local API"""
        start_time = time.time()
        
        ollama_config = self.providers.get("local", {})
        base_url = ollama_config.get("base_url", "http://localhost:11434")
        timeout = ollama_config.get("timeout", 300)
        
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens
            }
        }
        
        if request.system_prompt:
            payload["system"] = request.system_prompt
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
            
            content = data.get("response", "")
            # Ollama provides eval_count (output) and prompt_eval_count (input)
            tokens_out = data.get("eval_count", len(content) // 4)
            tokens_in = data.get("prompt_eval_count", len(request.prompt) // 4)
            
            latency_ms = int((time.time() - start_time) * 1000)
            provider_str = f"local/{model}"
            
            return LLMResponse(
                content=content,
                provider=provider_str,
                model_id=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=0.0,  # Local is free
                latency_ms=latency_ms,
                success=True,
                stop_reason=data.get("done_reason", "stop"),
                metadata={"ollama_stats": data.get("context", None)}
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Ollama call failed: {e}")
            return LLMResponse(
                content="",
                provider=f"local/{model}",
                model_id=model,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    async def _call_anthropic(
        self,
        request: LLMRequest,
        model_id: str,
        provider_str: str
    ) -> LLMResponse:
        """Call Anthropic Claude API"""
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
            
            latency_ms = int((time.time() - start_time) * 1000)
            cost_usd = self._calculate_cost(provider_str, tokens_in, tokens_out)
            
            return LLMResponse(
                content=content,
                provider=provider_str,
                model_id=model_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=True,
                stop_reason=stop_reason
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Anthropic call failed: {e}")
            return LLMResponse(
                content="",
                provider=provider_str,
                model_id=model_id,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    async def _call_openai(
        self,
        request: LLMRequest,
        model_id: str,
        provider_str: str
    ) -> LLMResponse:
        """Call OpenAI API"""
        start_time = time.time()
        
        async_client = self.async_providers.get("openai", {}).get("client")
        if not async_client:
            raise ValueError("OpenAI client not initialized")
        
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        
        try:
            response = await async_client.chat.completions.create(
                model=model_id,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            content = response.choices[0].message.content
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            
            latency_ms = int((time.time() - start_time) * 1000)
            cost_usd = self._calculate_cost(provider_str, tokens_in, tokens_out)
            
            return LLMResponse(
                content=content,
                provider=provider_str,
                model_id=model_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                success=True,
                stop_reason=response.choices[0].finish_reason
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"OpenAI call failed: {e}")
            return LLMResponse(
                content="",
                provider=provider_str,
                model_id=model_id,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=latency_ms,
                success=False,
                error=str(e)
            )
    
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Main entry point for LLM completion.
        
        Handles provider selection, fallback, and cost tracking.
        """
        provider_str = self._select_provider(request)
        
        logger.info(f"🤖 LLM Request: task={request.task_type.value}, provider={provider_str}")
        
        # Try primary provider
        response = await self._call_provider(request, provider_str)
        
        # If failed, try fallback chain
        if not response.success:
            fallback_chain = self.config.get("fallback_chain", {})
            fallback_provider = fallback_chain.get(provider_str)
            
            if fallback_provider:
                logger.warning(f"🔄 Falling back from {provider_str} to {fallback_provider}")
                response = await self._call_provider(request, fallback_provider)
        
        # Track usage
        self._track_usage(request, response)
        
        return response
    
    async def _call_provider(self, request: LLMRequest, provider_str: str) -> LLMResponse:
        """Route call to appropriate provider"""
        provider_name, model_name = provider_str.split("/", 1)
        model_id = self._get_model_id(provider_str)
        
        if provider_name == "local":
            return await self._call_ollama(request, model_name)
        elif provider_name == "anthropic":
            return await self._call_anthropic(request, model_id, provider_str)
        elif provider_name == "openai":
            return await self._call_openai(request, model_id, provider_str)
        else:
            return LLMResponse(
                content="",
                provider=provider_str,
                model_id=model_id,
                tokens_in=0,
                tokens_out=0,
                cost_usd=0.0,
                latency_ms=0,
                success=False,
                error=f"Unknown provider: {provider_name}"
            )
    
    def _track_usage(self, request: LLMRequest, response: LLMResponse):
        """Track usage for cost reporting"""
        self.session_cost_usd += response.cost_usd
        
        usage_entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": response.provider,
            "model_id": response.model_id,
            "task_type": request.task_type.value,
            "tokens_in": response.tokens_in,
            "tokens_out": response.tokens_out,
            "cost_usd": response.cost_usd,
            "latency_ms": response.latency_ms,
            "success": response.success,
            "project_id": request.project_id,
            "execution_id": request.execution_id
        }
        
        self.usage_log.append(usage_entry)
        
        # Log cost
        if response.cost_usd > 0:
            logger.info(f"💰 Cost: ${response.cost_usd:.4f} | Session total: ${self.session_cost_usd:.4f}")
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for current session"""
        if not self.usage_log:
            return {
                "total_requests": 0,
                "total_cost_usd": 0.0,
                "by_provider": {},
                "by_task_type": {}
            }
        
        by_provider: Dict[str, Dict] = {}
        by_task_type: Dict[str, Dict] = {}
        
        for entry in self.usage_log:
            # By provider
            provider = entry["provider"]
            if provider not in by_provider:
                by_provider[provider] = {"requests": 0, "cost_usd": 0.0, "tokens": 0}
            by_provider[provider]["requests"] += 1
            by_provider[provider]["cost_usd"] += entry["cost_usd"]
            by_provider[provider]["tokens"] += entry["tokens_in"] + entry["tokens_out"]
            
            # By task type
            task_type = entry["task_type"]
            if task_type not in by_task_type:
                by_task_type[task_type] = {"requests": 0, "cost_usd": 0.0}
            by_task_type[task_type]["requests"] += 1
            by_task_type[task_type]["cost_usd"] += entry["cost_usd"]
        
        return {
            "total_requests": len(self.usage_log),
            "total_cost_usd": round(self.session_cost_usd, 4),
            "by_provider": by_provider,
            "by_task_type": by_task_type
        }
    
    def get_available_providers(self) -> Dict[str, bool]:
        """Get status of all providers"""
        return {
            "local/ollama": "local" in self.providers,
            "anthropic": "anthropic" in self.providers,
            "openai": "openai" in self.providers
        }
    
    # Synchronous wrapper for backward compatibility
    def complete_sync(self, request: LLMRequest) -> LLMResponse:
        """Synchronous wrapper for complete()"""
        return asyncio.run(self.complete(request))
    
    # Convenience method matching old LLMService interface
    def generate(
        self,
        prompt: str,
        agent_type: str = "worker",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Backward-compatible generate method.
        
        Returns dict matching old LLMService interface.
        """
        request = LLMRequest(
            prompt=prompt,
            agent_type=agent_type,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            project_id=kwargs.get("project_id"),
            execution_id=kwargs.get("execution_id")
        )
        
        response = self.complete_sync(request)
        
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
            "error": response.error
        }

    # BUG-012 fix: Async version of generate() for callers already in async context
    async def generate_async(
        self,
        prompt: str,
        agent_type: str = "worker",
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Async version of generate(). Calls self.complete() directly with await.
        Use this from async contexts to avoid asyncio.run() crash (BUG-012).
        """
        request = LLMRequest(
            prompt=prompt,
            agent_type=agent_type,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            project_id=kwargs.get("project_id"),
            execution_id=kwargs.get("execution_id")
        )

        response = await self.complete(request)

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
            "error": response.error
        }


# Singleton instance
_router_instance: Optional[LLMRouterService] = None


def get_llm_router() -> LLMRouterService:
    """Get or create the singleton router instance"""
    global _router_instance
    if _router_instance is None:
        _router_instance = LLMRouterService()
    return _router_instance


# Convenience async function
async def route_llm_request(
    prompt: str,
    task_type: TaskComplexity = TaskComplexity.SIMPLE,
    system_prompt: Optional[str] = None,
    **kwargs
) -> LLMResponse:
    """
    Convenience function for async LLM routing.
    
    Example:
        response = await route_llm_request(
            prompt="Analyze this UC...",
            task_type=TaskComplexity.SIMPLE
        )
    """
    router = get_llm_router()
    request = LLMRequest(
        prompt=prompt,
        task_type=task_type,
        system_prompt=system_prompt,
        **kwargs
    )
    return await router.complete(request)


if __name__ == "__main__":
    # Test the router
    import asyncio
    
    async def test_router():
        print("🧪 Testing LLM Router Service...")
        
        router = LLMRouterService()
        print(f"\n📊 Available providers: {router.get_available_providers()}")
        
        # Test simple task (should use Nemo)
        print("\n--- Test 1: Simple task (UC analysis) ---")
        response = await router.complete(LLMRequest(
            prompt="List 3 Salesforce standard objects.",
            task_type=TaskComplexity.SIMPLE,
            max_tokens=200
        ))
        print(f"Provider: {response.provider}")
        print(f"Success: {response.success}")
        print(f"Latency: {response.latency_ms}ms")
        print(f"Cost: ${response.cost_usd}")
        if response.content:
            print(f"Response: {response.content[:200]}...")
        
        # Test complex task (should use Sonnet)
        print("\n--- Test 2: Complex task (SDS synthesis) ---")
        response = await router.complete(LLMRequest(
            prompt="What are the key components of a Salesforce SDS document?",
            task_type=TaskComplexity.COMPLEX,
            max_tokens=200
        ))
        print(f"Provider: {response.provider}")
        print(f"Success: {response.success}")
        print(f"Cost: ${response.cost_usd}")
        
        # Show stats
        print(f"\n📈 Session stats: {router.get_session_stats()}")
    
    asyncio.run(test_router())
