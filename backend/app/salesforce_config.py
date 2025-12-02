"""
Salesforce Configuration for Digital Humans Agents
"""
from dataclasses import dataclass
from typing import Dict

@dataclass
class SalesforceConfig:
    """Salesforce connection configuration"""
    
    # Org Details
    org_alias: str = "digital-humans-dev"
    username: str = "shatit715@agentforce.com"
    org_id: str = "00DgL00000FzQzTUAV"
    instance_url: str = "https://orgfarm-8de2d5ba1d-dev-ed.develop.my.salesforce.com"
    api_version: str = "65.0"
    
    # Paths
    sfdx_project_path: str = "/root/workspace/salesforce-workspace/digital-humans-sf"
    force_app_path: str = "/root/workspace/salesforce-workspace/digital-humans-sf/force-app/main/default"

# Singleton instance
salesforce_config = SalesforceConfig()

# Agent-specific paths
AGENT_PATHS: Dict[str, Dict[str, str]] = {
    "diego": {  # Apex Developer
        "classes": "classes",
        "triggers": "triggers",
    },
    "zara": {  # LWC Developer
        "lwc": "lwc",
        "aura": "aura",
    },
    "raj": {  # Admin/Config
        "objects": "objects",
        "flows": "flows",
        "permissionsets": "permissionsets",
        "profiles": "profiles",
    },
    "elena": {  # QA
        "classes": "classes",  # For test classes
    }
}

def get_agent_path(agent_name: str, component_type: str) -> str:
    """Get the file path for an agent's component type"""
    agent_name = agent_name.lower()
    if agent_name not in AGENT_PATHS:
        raise ValueError(f"Unknown agent: {agent_name}")
    
    if component_type not in AGENT_PATHS[agent_name]:
        raise ValueError(f"Agent {agent_name} doesn't handle {component_type}")
    
    subpath = AGENT_PATHS[agent_name][component_type]
    return f"{salesforce_config.force_app_path}/{subpath}"

def get_sfdx_command(command: str) -> str:
    """Build a SFDX command with the default org"""
    return f"sf {command} --target-org {salesforce_config.org_alias}"
