"""
Agent Tester API - Test REAL agents with Salesforce integration

Uses the same agent scripts as pm_orchestrator_service_v2.py
"""
import json
import subprocess
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.salesforce_config import salesforce_config, AGENT_PATHS
from app.services.agent_executor import get_agent_executor, AGENT_CONFIG

router = APIRouter(prefix="/agent-tester", tags=["Agent Tester"])

# UI Agent definitions (display info only - real config is in agent_executor.py)
AGENTS = {
    "olivia": {"name": "Olivia", "role": "Business Analyst", "description": "Analyse les besoins business, crée les Use Cases à partir des BRs", "capabilities": ["requirements", "use_cases", "process_flows"], "color": "#EC4899"},
    "marcus": {"name": "Marcus", "role": "Solution Architect", "description": "Analyse l org existante, conçoit l architecture", "capabilities": ["architecture", "design"], "color": "#8B5CF6"},
    "sophie": {"name": "Sophie", "role": "Product Manager", "description": "Orchestre le projet, extrait les Business Requirements du brief", "capabilities": ["pm", "requirements", "orchestration"], "color": "#6366F1"},
    "diego": {"name": "Diego", "role": "Apex Developer", "description": "Développe classes Apex, triggers et tests", "capabilities": ["classes", "triggers"], "color": "#1E40AF"},
    "zara": {"name": "Zara", "role": "LWC Developer", "description": "Développe Lightning Web Components", "capabilities": ["lwc", "aura"], "color": "#7C3AED"},
    "raj": {"name": "Raj", "role": "Salesforce Admin", "description": "Configure objets, flows, permissions", "capabilities": ["objects", "flows"], "color": "#059669"},
    "elena": {"name": "Elena", "role": "QA Engineer", "description": "Crée et exécute les tests Apex", "capabilities": ["test_classes"], "color": "#DC2626"},
    "jordan": {"name": "Jordan", "role": "DevOps Engineer", "description": "Gère déploiements et CI/CD", "capabilities": ["deployment"], "color": "#F59E0B"},
    "aisha": {"name": "Aisha", "role": "Data Migration Specialist", "description": "Migre et transforme les données", "capabilities": ["data_migration"], "color": "#10B981"},
    "lucas": {"name": "Lucas", "role": "Trainer", "description": "Crée documentation utilisateur et guides de formation", "capabilities": ["training", "documentation"], "color": "#14B8A6"},
    "emma": {"name": "Emma", "role": "Research Analyst", "description": "Analyse les UCs, valide la couverture, rédige le SDS", "capabilities": ["analyze", "validate", "write_sds"], "color": "#F472B6"}
}

class AgentTestRequest(BaseModel):
    task_description: str
    deploy_to_org: bool = False
    use_rag: bool = True

def make_sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"

@router.get("/agents")
async def list_agents():
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
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return AGENTS[agent_id]

@router.get("/org/query")
async def query_org(soql: str):
    result = subprocess.run(
        f'sf data query --query "{soql}" --target-org {salesforce_config.org_alias} --json',
        shell=True, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr)
    return json.loads(result.stdout)

@router.post("/test/{agent_id}/stream")
async def test_agent_stream(agent_id: str, request: AgentTestRequest):
    """
    Test a REAL agent with streaming response.
    Calls the actual agent scripts in /agents/roles/
    """
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    
    # Check if agent is implemented in executor
    if agent_id not in AGENT_CONFIG:
        async def not_implemented():
            yield make_sse({"type": "error", "message": f"Agent {agent_id} non configuré dans AGENT_CONFIG"})
        return StreamingResponse(not_implemented(), media_type="text/event-stream")
    
    executor = get_agent_executor()
    
    # Use generic execute_agent for ALL agents
    generator = executor.execute_agent(
        agent_id=agent_id,
        task=request.task_description,
        deploy=request.deploy_to_org,
        use_rag=request.use_rag
    )
    
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )

@router.get("/workspace/files")
async def list_workspace_files():
    files = {}
    base_path = salesforce_config.force_app_path
    for folder in ["classes", "triggers", "lwc", "flows", "objects"]:
        folder_path = os.path.join(base_path, folder)
        files[folder] = os.listdir(folder_path) if os.path.exists(folder_path) else []
    return {"workspace": salesforce_config.sfdx_project_path, "files": files}

@router.get("/llm/status")
async def get_llm_status():
    try:
        from app.services.llm_service import get_llm_service
        return get_llm_service().get_status()
    except Exception as e:
        return {"error": str(e), "available": False}

# ===== TEST LOGS ENDPOINTS =====
# For debugging and post-execution analysis

@router.get("/logs")
async def list_test_logs(limit: int = 20):
    """List recent agent test logs for debugging"""
    try:
        from app.services.agent_test_logger import get_logger
        logger = get_logger()
        return {"logs": logger.list_logs(limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/{test_id}")
async def get_test_log(test_id: str):
    """Get detailed log for a specific test"""
    try:
        from app.services.agent_test_logger import get_logger
        logger = get_logger()
        log = logger.get_log(test_id)
        if not log:
            # Try by filename
            log = logger.get_log_by_filename(test_id)
        if not log:
            raise HTTPException(status_code=404, detail=f"Log {test_id} not found")
        return log
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/{test_id}/step/{step_number}")
async def get_test_log_step(test_id: str, step_number: int):
    """Get a specific step from a test log"""
    try:
        from app.services.agent_test_logger import get_logger
        logger = get_logger()
        log = logger.get_log(test_id)
        if not log:
            log = logger.get_log_by_filename(test_id)
        if not log:
            raise HTTPException(status_code=404, detail=f"Log {test_id} not found")
        
        steps = log.get("steps", [])
        for step in steps:
            if step.get("step_number") == step_number:
                return step
        
        raise HTTPException(status_code=404, detail=f"Step {step_number} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
