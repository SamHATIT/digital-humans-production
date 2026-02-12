"""
Prompt Service — loads and renders agent prompts from YAML files.

Usage:
    from prompts.prompt_service import PromptService

    ps = PromptService()
    prompt = ps.render("marcus_architect", "design", {
        "project_summary": "...",
        "uc_text": "...",
        "rag_section": "..."
    })
"""
import yaml
from pathlib import Path
from string import Template
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "agents"


class PromptService:
    """Loads YAML prompt files and renders them with variables."""

    _cache: Dict[str, dict] = {}
    _instance = None

    def __new__(cls):
        """Singleton — one instance, one cache."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, agent_name: str) -> dict:
        """Load and cache a YAML prompt file."""
        if agent_name not in self._cache:
            path = PROMPTS_DIR / f"{agent_name}.yaml"
            if not path.exists():
                raise FileNotFoundError(f"Prompt file not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                self._cache[agent_name] = yaml.safe_load(f)
            logger.info(f"Loaded prompts for {agent_name}")
        return self._cache[agent_name]

    def render(self, agent_name: str, mode: str, variables: Dict[str, Any]) -> str:
        """Render a prompt template with variables."""
        prompts = self.load(agent_name)

        modes = prompts.get("modes", {})
        if mode not in modes:
            raise ValueError(f"Unknown mode '{mode}' for {agent_name}. Available: {list(modes.keys())}")

        template_str = modes[mode].get("prompt", "")

        # Use safe_substitute to avoid KeyError on missing variables
        template = Template(template_str)
        return template.safe_substitute(variables)

    def get_system_prompt(self, agent_name: str, mode: str = None) -> str:
        """Get system prompt for an agent (global or mode-specific)."""
        prompts = self.load(agent_name)

        if mode:
            mode_system = prompts.get("modes", {}).get(mode, {}).get("system_prompt")
            if mode_system:
                return mode_system

        return prompts.get("system_prompt", "")

    def get_config(self, agent_name: str, mode: str) -> dict:
        """Get mode config (max_tokens, temperature, etc.)."""
        prompts = self.load(agent_name)
        return prompts.get("modes", {}).get(mode, {}).get("config", {})

    def reload(self, agent_name: str = None):
        """Clear cache — forces reload on next access."""
        if agent_name:
            self._cache.pop(agent_name, None)
        else:
            self._cache.clear()
        logger.info(f"Prompt cache cleared: {agent_name or 'all'}")
