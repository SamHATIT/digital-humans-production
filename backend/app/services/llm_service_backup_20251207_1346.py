#!/usr/bin/env python3
"""
LLM Service - Multi-Provider Support with Model Stratification
Supports OpenAI (GPT-4) and Anthropic (Claude) models

Strategy:
- ORCHESTRATOR (PM): Claude Opus 4.5 - Best reasoning, context handling
- ANALYST (BA, Architect): Claude Sonnet 4.5 - Balanced performance/cost
- WORKER (Apex, LWC, Admin, QA, etc.): Claude Haiku 4.5 - Fast, economical

Author: Digital Humans Team
Date: November 27, 2025
"""

import os
import sys
from typing import Optional, Dict, Any, Literal
from enum import Enum
from dataclasses import dataclass

# Provider imports - handled gracefully
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    Anthropic = None


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class AgentTier(str, Enum):
    """Agent tiers for model selection"""
    ORCHESTRATOR = "orchestrator"  # PM - needs best reasoning
    ANALYST = "analyst"            # BA, Architect - needs good analysis
    WORKER = "worker"              # Developers, QA, etc. - execution focused


@dataclass
class LLMConfig:
    """Configuration for LLM calls"""
    provider: LLMProvider
    model: str
    max_tokens: int = 16000
    temperature: float = 0.7
    system_prompt: Optional[str] = None


# Model mappings per tier
ANTHROPIC_MODELS = {
    AgentTier.ORCHESTRATOR: "claude-opus-4-5-20251101",      # Best reasoning
    AgentTier.ANALYST: "claude-sonnet-4-5-20250929",         # Balanced
    AgentTier.WORKER: "claude-haiku-4-5-20251001",           # Fast & economical
}

OPENAI_MODELS = {
    AgentTier.ORCHESTRATOR: "gpt-4o",
    AgentTier.ANALYST: "gpt-4o-mini",
    AgentTier.WORKER: "gpt-4o-mini",
}

# Agent to tier mapping
AGENT_TIER_MAP = {
    # Orchestrator tier
    "pm": AgentTier.ORCHESTRATOR,
    "pm_orchestrator": AgentTier.ORCHESTRATOR,
    "sophie": AgentTier.ORCHESTRATOR,
    
    # Analyst tier
    "ba": AgentTier.ANALYST,
    "business_analyst": AgentTier.ANALYST,
    "olivia": AgentTier.ANALYST,
    "architect": AgentTier.ANALYST,
    "solution_architect": AgentTier.ANALYST,
    "marcus": AgentTier.ANALYST,
    
    # Worker tier
    "apex": AgentTier.WORKER,
    "apex_developer": AgentTier.WORKER,
    "diego": AgentTier.WORKER,
    "lwc": AgentTier.WORKER,
    "lwc_developer": AgentTier.WORKER,
    "zara": AgentTier.WORKER,
    "admin": AgentTier.WORKER,
    "sf_admin": AgentTier.WORKER,
    "raj": AgentTier.WORKER,
    "qa": AgentTier.WORKER,
    "qa_tester": AgentTier.WORKER,
    "elena": AgentTier.WORKER,
    "devops": AgentTier.WORKER,
    "jordan": AgentTier.WORKER,
    "data_migration": AgentTier.WORKER,
    "aisha": AgentTier.WORKER,
    "trainer": AgentTier.WORKER,
    "lucas": AgentTier.WORKER,
}


class LLMService:
    """
    Unified LLM service supporting multiple providers and model stratification.
    
    Usage:
        service = LLMService()
        response = service.generate(
            prompt="Analyze these requirements...",
            agent_type="ba",
            system_prompt="You are a Salesforce Business Analyst..."
        )
    """
    
    def __init__(
        self,
        default_provider: LLMProvider = LLMProvider.ANTHROPIC,
        fallback_to_openai: bool = True
    ):
        """
        Initialize the LLM service.
        
        Args:
            default_provider: Primary provider to use
            fallback_to_openai: If True, falls back to OpenAI if Anthropic fails
        """
        self.default_provider = default_provider
        self.fallback_to_openai = fallback_to_openai
        
        # Initialize clients
        self._openai_client = None
        self._anthropic_client = None
        
        self._init_clients()
    
    def _init_clients(self):
        """Initialize API clients based on available keys"""
        # Anthropic client
        if ANTHROPIC_AVAILABLE:
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if api_key:
                self._anthropic_client = Anthropic(api_key=api_key)
                print("✅ Anthropic client initialized", file=sys.stderr)
            else:
                print("⚠️ ANTHROPIC_API_KEY not set", file=sys.stderr)
        else:
            print("⚠️ anthropic package not installed", file=sys.stderr)
        
        # OpenAI client (fallback)
        if OPENAI_AVAILABLE:
            api_key = os.environ.get('OPENAI_API_KEY')
            if api_key:
                self._openai_client = OpenAI(api_key=api_key)
                print("✅ OpenAI client initialized (fallback)", file=sys.stderr)
    
    def get_tier_for_agent(self, agent_type: str) -> AgentTier:
        """Get the tier for a given agent type"""
        normalized = agent_type.lower().replace("-", "_").replace(" ", "_")
        return AGENT_TIER_MAP.get(normalized, AgentTier.WORKER)
    
    def get_model_for_agent(
        self, 
        agent_type: str, 
        provider: Optional[LLMProvider] = None
    ) -> str:
        """Get the appropriate model for an agent type"""
        provider = provider or self.default_provider
        tier = self.get_tier_for_agent(agent_type)
        
        if provider == LLMProvider.ANTHROPIC:
            return ANTHROPIC_MODELS[tier]
        else:
            return OPENAI_MODELS[tier]
    
    def generate(
        self,
        prompt: str,
        agent_type: str = "worker",
        system_prompt: Optional[str] = None,
        max_tokens: int = 16000,
        temperature: float = 0.7,
        provider: Optional[LLMProvider] = None,
        model_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The user prompt
            agent_type: Type of agent (determines model tier)
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            provider: Override default provider
            model_override: Override automatic model selection
            
        Returns:
            Dict with 'content', 'model', 'provider', 'tokens_used'
        """
        provider = provider or self.default_provider
        model = model_override or self.get_model_for_agent(agent_type, provider)
        tier = self.get_tier_for_agent(agent_type)
        
        print(f"🤖 LLM Request: agent={agent_type}, tier={tier.value}, provider={provider.value}, model={model}", file=sys.stderr)
        
        # Try primary provider
        try:
            if provider == LLMProvider.ANTHROPIC and self._anthropic_client:
                return self._call_anthropic(prompt, system_prompt, model, max_tokens, temperature)
            elif provider == LLMProvider.OPENAI and self._openai_client:
                return self._call_openai(prompt, system_prompt, model, max_tokens, temperature)
            else:
                raise ValueError(f"Provider {provider.value} not available")
                
        except Exception as e:
            print(f"❌ {provider.value} failed: {e}", file=sys.stderr)
            
            # Fallback to OpenAI if enabled
            if self.fallback_to_openai and provider != LLMProvider.OPENAI and self._openai_client:
                print("🔄 Falling back to OpenAI...", file=sys.stderr)
                fallback_model = self.get_model_for_agent(agent_type, LLMProvider.OPENAI)
                return self._call_openai(prompt, system_prompt, fallback_model, max_tokens, temperature)
            
            raise
    
    def _call_anthropic(
        self,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Call Anthropic Claude API"""
        print(f"📤 Calling Anthropic API ({model})...", file=sys.stderr)
        
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        # Add system prompt if provided (Claude uses top-level system parameter)
        if system_prompt:
            kwargs["system"] = system_prompt
        
        # Note: Claude doesn't support temperature > 1, clamp if needed
        if temperature <= 1.0:
            kwargs["temperature"] = temperature
        
        response = self._anthropic_client.messages.create(**kwargs)
        
        content = response.content[0].text
        tokens_used = response.usage.input_tokens + response.usage.output_tokens
        
        print(f"✅ Anthropic response: {len(content)} chars, {tokens_used} tokens", file=sys.stderr)
        
        return {
            "content": content,
            "model": model,
            "provider": LLMProvider.ANTHROPIC.value,
            "tokens_used": tokens_used,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    
    def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        model: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Call OpenAI GPT API"""
        print(f"📤 Calling OpenAI API ({model})...", file=sys.stderr)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = self._openai_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        content = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        
        print(f"✅ OpenAI response: {len(content)} chars, {tokens_used} tokens", file=sys.stderr)
        
        return {
            "content": content,
            "model": model,
            "provider": LLMProvider.OPENAI.value,
            "tokens_used": tokens_used,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens
        }
    
    def is_anthropic_available(self) -> bool:
        """Check if Anthropic is available"""
        return self._anthropic_client is not None
    
    def is_openai_available(self) -> bool:
        """Check if OpenAI is available"""
        return self._openai_client is not None
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "anthropic_available": self.is_anthropic_available(),
            "openai_available": self.is_openai_available(),
            "default_provider": self.default_provider.value,
            "fallback_enabled": self.fallback_to_openai,
            "tier_models": {
                "anthropic": {tier.value: model for tier, model in ANTHROPIC_MODELS.items()},
                "openai": {tier.value: model for tier, model in OPENAI_MODELS.items()}
            }
        }


# Singleton instance for easy import
_llm_service: Optional[LLMService] = None

def get_llm_service() -> LLMService:
    """Get or create the singleton LLM service instance"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


# Convenience function for direct usage
def generate_llm_response(
    prompt: str,
    agent_type: str = "worker",
    system_prompt: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to generate LLM response.
    
    Example:
        response = generate_llm_response(
            prompt="Analyze these requirements...",
            agent_type="ba",
            system_prompt="You are a Salesforce BA..."
        )
        content = response["content"]
    """
    return get_llm_service().generate(
        prompt=prompt,
        agent_type=agent_type,
        system_prompt=system_prompt,
        **kwargs
    )


if __name__ == "__main__":
    # Test the service
    print("🧪 Testing LLM Service...")
    
    service = LLMService()
    print(f"\n📊 Service Status: {service.get_status()}")
    
    # Test tier mapping
    test_agents = ["pm", "ba", "architect", "apex", "qa", "trainer"]
    print("\n📋 Agent Tier Mapping:")
    for agent in test_agents:
        tier = service.get_tier_for_agent(agent)
        model = service.get_model_for_agent(agent)
        print(f"  {agent}: tier={tier.value}, model={model}")
