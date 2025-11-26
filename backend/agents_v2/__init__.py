"""
V2 Agents - Artifact-based Multi-Agent System
Each agent produces structured artifacts instead of free text
"""
from .base_agent import BaseAgentV2
from .ba_agent import BusinessAnalystAgent
from .architect_agent import ArchitectAgent
from .orchestrator import OrchestratorV2

__all__ = [
    "BaseAgentV2",
    "BusinessAnalystAgent", 
    "ArchitectAgent",
    "OrchestratorV2",
]
