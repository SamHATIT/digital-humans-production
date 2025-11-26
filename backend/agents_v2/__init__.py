"""
V2 Agents - Artifact-based Multi-Agent System

Architecture:
- PM Agent (Sophie): Orchestrates, reviews, coordinates
- BA Agent (Olivia): Produces BR and UC
- Architect Agent (Marcus): Produces ADR and SPEC, iterates with BA
- [Future] Worker Agents: Apex, LWC, Admin, QA, DevOps, Data, Trainer
"""
from .base_agent import BaseAgentV2
from .pm_agent import ProjectManagerAgent
from .ba_agent import BusinessAnalystAgent
from .architect_agent import ArchitectAgent
from .orchestrator import OrchestratorV2

__all__ = [
    "BaseAgentV2",
    "ProjectManagerAgent",
    "BusinessAnalystAgent", 
    "ArchitectAgent",
    "OrchestratorV2",
]
