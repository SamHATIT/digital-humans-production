"""
Agent Tester API - Test individual agents with Salesforce integration
"""
import asyncio
import json
import subprocess
import os
from datetime import datetime
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.salesforce_config import salesforce_config, AGENT_PATHS

router = APIRouter(prefix="/agent-tester", tags=["Agent Tester"])

# 7 agents who need Salesforce access
AGENTS = {
    "marcus": {
        "name": "Marcus",
        "role": "Solution Architect",
        "description": "Analyse l'org existante, conçoit l'architecture et les spécifications techniques",
        "capabilities": ["architecture", "design", "as_is_analysis"],
        "color": "#8B5CF6"
    },
    "diego": {
        "name": "Diego",
        "role": "Apex Developer",
        "description": "Développe des classes Apex, triggers et tests unitaires",
        "capabilities": ["classes", "triggers"],
        "color": "#1E40AF"
    },
    "zara": {
        "name": "Zara",
        "role": "LWC Developer",
        "description": "Développe des Lightning Web Components et Aura",
        "capabilities": ["lwc", "aura"],
        "color": "#7C3AED"
    },
    "raj": {
        "name": "Raj",
        "role": "Salesforce Admin",
        "description": "Configure les objets, flows, permissions et profiles",
        "capabilities": ["objects", "flows", "permissionsets", "profiles"],
        "color": "#059669"
    },
    "elena": {
        "name": "Elena",
        "role": "QA Engineer",
        "description": "Crée et exécute les tests Apex, valide les déploiements",
        "capabilities": ["test_classes", "validation"],
        "color": "#DC2626"
    },
    "jordan": {
        "name": "Jordan",
        "role": "DevOps Engineer",
        "description": "Gère les déploiements, CI/CD et environnements",
        "capabilities": ["deployment", "cicd", "environments"],
        "color": "#F59E0B"
    },
    "aisha": {
        "name": "Aisha",
        "role": "Data Migration Specialist",
        "description": "Migre et transforme les données, gère les imports/exports",
        "capabilities": ["data_migration", "data_import", "data_export"],
        "color": "#10B981"
    }
}


class AgentTestRequest(BaseModel):
    agent_id: str
    task_description: str
    project_context: Optional[dict] = None
    deploy_to_org: bool = False


class SFDXResult(BaseModel):
    success: bool
    command: str
    stdout: str
    stderr: str
    duration_ms: int


@router.get("/agents")
async def list_agents():
    """List all available agents for testing"""
    return {
        "agents": AGENTS,
        "salesforce_org": {
            "alias": salesforce_config.org_alias,
            "username": salesforce_config.username,
            "instance_url": salesforce_config.instance_url,
            "connected": True
        }
    }


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get details for a specific agent"""
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return AGENTS[agent_id]


@router.post("/execute-sfdx")
async def execute_sfdx_command(command: str):
    """Execute a SFDX command and return result"""
    full_command = f"sf {command} --target-org {salesforce_config.org_alias}"
    
    start_time = datetime.now()
    result = subprocess.run(
        full_command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=salesforce_config.sfdx_project_path
    )
    duration = (datetime.now() - start_time).total_seconds() * 1000
    
    return SFDXResult(
        success=result.returncode == 0,
        command=full_command,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=int(duration)
    )


@router.get("/org/query")
async def query_org(soql: str):
    """Execute a SOQL query on the connected org"""
    result = subprocess.run(
        f'sf data query --query "{soql}" --target-org {salesforce_config.org_alias} --json',
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr)
    
    return json.loads(result.stdout)


@router.post("/deploy")
async def deploy_to_org(path: Optional[str] = None):
    """Deploy code to the Salesforce org"""
    deploy_path = path or salesforce_config.force_app_path
    
    result = subprocess.run(
        f"sf project deploy start --source-dir {deploy_path} --target-org {salesforce_config.org_alias} --json",
        shell=True,
        capture_output=True,
        text=True,
        cwd=salesforce_config.sfdx_project_path
    )
    
    output = json.loads(result.stdout) if result.stdout else {}
    
    return {
        "success": result.returncode == 0,
        "result": output,
        "stderr": result.stderr
    }


def make_log_event(event_type: str, **kwargs) -> str:
    """Create a SSE log event"""
    data = {"type": event_type, **kwargs}
    return f"data: {json.dumps(data)}\n\n"


async def generate_test_logs(agent_id: str, task: str) -> AsyncGenerator[str, None]:
    """Generate SSE logs for agent test execution"""
    agent = AGENTS.get(agent_id)
    if not agent:
        yield make_log_event("error", message=f"Agent {agent_id} not found")
        return
    
    agent_name = agent["name"]
    agent_role = agent["role"]
    
    # Start log
    yield make_log_event("start", agent=agent_name, task=task, timestamp=datetime.now().isoformat())
    await asyncio.sleep(0.1)
    
    # Log: Initializing
    yield make_log_event("log", level="INFO", message=f"Agent {agent_name} ({agent_role}) initialisé")
    await asyncio.sleep(0.2)
    
    # Log: Checking SF connection
    yield make_log_event("log", level="INFO", message=f"Vérification connexion Salesforce: {salesforce_config.org_alias}")
    await asyncio.sleep(0.1)
    
    # Verify org connection
    result = subprocess.run(
        f"sf org display --target-org {salesforce_config.org_alias} --json",
        shell=True,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        yield make_log_event("log", level="SUCCESS", message="✓ Connexion Salesforce OK")
    else:
        yield make_log_event("log", level="ERROR", message=f"✗ Erreur connexion: {result.stderr}")
        return
    
    await asyncio.sleep(0.2)
    
    # Log: Task analysis (placeholder for LLM call)
    yield make_log_event("log", level="INFO", message="Analyse de la tâche en cours...")
    yield make_log_event("log", level="LLM", message=f"Tâche: {task}")
    
    # End
    yield make_log_event("end", message="Test terminé - Mode démo (LLM non connecté)", timestamp=datetime.now().isoformat())


@router.post("/test/{agent_id}/stream")
async def test_agent_stream(agent_id: str, request: AgentTestRequest):
    """Test an agent with SSE streaming logs"""
    return StreamingResponse(
        generate_test_logs(agent_id, request.task_description),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/workspace/files")
async def list_workspace_files():
    """List files in the SFDX workspace"""
    files = {}
    base_path = salesforce_config.force_app_path
    
    for folder in ["classes", "triggers", "lwc", "flows", "objects"]:
        folder_path = os.path.join(base_path, folder)
        if os.path.exists(folder_path):
            files[folder] = os.listdir(folder_path)
        else:
            files[folder] = []
    
    return {
        "workspace": salesforce_config.sfdx_project_path,
        "files": files
    }
