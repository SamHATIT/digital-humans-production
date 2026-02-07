#!/usr/bin/env python3
import logging
"""
Agent Executor Service - Execute REAL agents with DB persistence

ARCHITECTURE: Database-First + Real Agents
- Appelle les VRAIS scripts agents dans /agents/roles/
- Stream stderr en temps réel pour éviter timeout
- Persistence DB (Execution + Artifacts)
"""
import os
import sys
import json
import asyncio
import tempfile
import subprocess
from datetime import datetime, timezone
logger = logging.getLogger(__name__)
from typing import Optional, Dict, Any, AsyncGenerator, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.execution import Execution, ExecutionStatus
from app.models.artifact import ExecutionArtifact, ArtifactType, ArtifactStatus
from app.salesforce_config import salesforce_config
from app.config import settings

# Test logger for debugging
try:
    from app.services.agent_test_logger import AgentTestLogger
    TEST_LOGGER_AVAILABLE = True
except ImportError:
    TEST_LOGGER_AVAILABLE = False

# RAG check
try:
    from app.services.rag_service import get_salesforce_context
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# ============================================================================
# P3: Direct import agents (migrated from subprocess)
# As agents are migrated, add their class here.
# ============================================================================
try:
    from agents.roles.salesforce_pm import PMAgent
    _PM_AGENT_AVAILABLE = True
except ImportError:
    _PM_AGENT_AVAILABLE = False
    logger.warning("PMAgent not available for direct import, will use subprocess fallback")

try:
    from agents.roles.salesforce_trainer import TrainerAgent
    _TRAINER_AGENT_AVAILABLE = True
except ImportError:
    _TRAINER_AGENT_AVAILABLE = False
    logger.warning("TrainerAgent not available for direct import, will use subprocess fallback")

try:
    from agents.roles.salesforce_devops import DevOpsAgent
    _DEVOPS_AGENT_AVAILABLE = True
except ImportError:
    _DEVOPS_AGENT_AVAILABLE = False
    logger.warning("DevOpsAgent not available for direct import, will use subprocess fallback")

try:
    from agents.roles.salesforce_business_analyst import BusinessAnalystAgent
    _BA_AGENT_AVAILABLE = True
except ImportError:
    _BA_AGENT_AVAILABLE = False
    logger.warning("BusinessAnalystAgent not available for direct import, will use subprocess fallback")

try:
    from agents.roles.salesforce_data_migration import DataMigrationAgent
    _DATA_AGENT_AVAILABLE = True
except ImportError:
    _DATA_AGENT_AVAILABLE = False
    logger.warning("DataMigrationAgent not available for direct import, will use subprocess fallback")

# Registry mapping agent_id -> class for migrated agents
# Agents not in this dict fall back to subprocess execution
MIGRATED_AGENTS: Dict[str, type] = {}
if _PM_AGENT_AVAILABLE:
    MIGRATED_AGENTS["sophie"] = PMAgent
if _TRAINER_AGENT_AVAILABLE:
    MIGRATED_AGENTS["lucas"] = TrainerAgent
    MIGRATED_AGENTS["trainer"] = TrainerAgent
if _DEVOPS_AGENT_AVAILABLE:
    MIGRATED_AGENTS["jordan"] = DevOpsAgent
    MIGRATED_AGENTS["devops"] = DevOpsAgent
if _BA_AGENT_AVAILABLE:
    MIGRATED_AGENTS["olivia"] = BusinessAnalystAgent
    MIGRATED_AGENTS["ba"] = BusinessAnalystAgent
if _DATA_AGENT_AVAILABLE:
    MIGRATED_AGENTS["aisha"] = DataMigrationAgent
    MIGRATED_AGENTS["data"] = DataMigrationAgent

# Default modes when called from agent tester (execute_agent flow).
# Each agent's most common/default mode for testing.
AGENT_DEFAULT_MODES: Dict[str, str] = {
    "sophie": "extract_br",
    "lucas": "sds_strategy",
    "trainer": "sds_strategy",
    "jordan": "spec",
    "devops": "spec",
    "olivia": "generate_uc",
    "ba": "generate_uc",
    "aisha": "sds_strategy",
    "data": "sds_strategy",
}


class LogLevel(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
    WARNING = "WARNING"
    LLM = "LLM"
    SFDX = "SFDX"
    CODE = "CODE"
    DB = "DB"


@dataclass
class ExecutionLog:
    """Single log entry"""
    level: LogLevel
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        result = {"level": self.level.value, "message": self.message, "timestamp": self.timestamp}
        if self.data:
            result["data"] = self.data
        return result
    
    def to_sse(self) -> str:
        return f"data: {json.dumps({'type': 'log', **self.to_dict()})}\n\n"


# ============================================================================
# AGENT CONFIG - Maps UI agent IDs to real scripts
# ============================================================================

AGENTS_PATH = settings.BACKEND_ROOT / "agents" / "roles"

AGENT_CONFIG = {
    "marcus": {"script": "salesforce_solution_architect.py", "display_name": "Marcus (Solution Architect)", "tier": "architect"},
    "diego": {"script": "salesforce_developer_apex.py", "display_name": "Diego (Apex Developer)", "tier": "worker"},
    "zara": {"script": "salesforce_developer_lwc.py", "display_name": "Zara (LWC Developer)", "tier": "worker"},
    "raj": {"script": "salesforce_admin.py", "display_name": "Raj (Salesforce Admin)", "tier": "worker"},
    "admin": {"script": "salesforce_admin.py", "display_name": "Raj (Salesforce Admin)", "tier": "worker"},
    "elena": {"script": "salesforce_qa_tester.py", "display_name": "Elena (QA Engineer)", "tier": "worker"},
    "jordan": {"script": "salesforce_devops.py", "display_name": "Jordan (DevOps Engineer)", "tier": "worker"},
    "aisha": {"script": "salesforce_data_migration.py", "display_name": "Aisha (Data Migration)", "tier": "worker"},
    "olivia": {"script": "salesforce_business_analyst.py", "display_name": "Olivia (Business Analyst)", "tier": "ba"},
    "sophie": {"script": "salesforce_pm.py", "display_name": "Sophie (PM)", "tier": "pm"},
    "lucas": {"script": "salesforce_trainer.py", "display_name": "Lucas (Trainer)", "tier": "worker"},
    "emma": {"script": "salesforce_research_analyst.py", "display_name": "Emma (Research Analyst)", "tier": "research"},
    "research_analyst": {"script": "salesforce_research_analyst.py", "display_name": "Emma (Research Analyst)", "tier": "research"},
    # Aliases for WBS compatibility
    "apex": {"script": "salesforce_developer_apex.py", "display_name": "Diego (Apex Developer)", "tier": "worker"},
    "lwc": {"script": "salesforce_developer_lwc.py", "display_name": "Zara (LWC Developer)", "tier": "worker"},
    "devops": {"script": "salesforce_devops.py", "display_name": "Jordan (DevOps Engineer)", "tier": "worker"},
    "qa": {"script": "salesforce_qa_tester.py", "display_name": "Elena (QA Engineer)", "tier": "worker"},
    "trainer": {"script": "salesforce_trainer.py", "display_name": "Lucas (Trainer)", "tier": "worker"},
}


class AgentExecutor:
    """
    Execute REAL agents with streaming output to avoid timeout
    """
    
    def __init__(self):
        self.logs: List[ExecutionLog] = []
        self.db: Optional[Session] = None
        self.execution: Optional[Execution] = None
        self.temp_dir = Path(tempfile.mkdtemp(prefix="agent_test_"))
    
    def _get_db(self) -> Session:
        if self.db is None:
            self.db = SessionLocal()
        return self.db
    
    def _close_db(self):
        if self.db:
            self.db.close()
            self.db = None
    
    def log(self, level: LogLevel, message: str, data: Optional[Dict] = None) -> ExecutionLog:
        log_entry = ExecutionLog(level=level, message=message, data=data)
        self.logs.append(log_entry)
        return log_entry
    
    def _sse_event(self, event_type: str, **kwargs) -> str:
        data = {"type": event_type, "timestamp": datetime.now().isoformat(), **kwargs}
        return f"data: {json.dumps(data)}\n\n"
    
    def _create_execution(self, agent_id: str, task: str, project_id: int, user_id: int) -> Execution:
        """Create execution record in DB"""
        db = self._get_db()
        
        execution = Execution(
            project_id=project_id,
            user_id=user_id,
            status=ExecutionStatus.RUNNING,
            current_agent=agent_id,
            selected_agents=[agent_id],
            started_at=datetime.now(timezone.utc),
            agent_execution_status={
                agent_id: {"state": "running", "progress": 0, "task": task[:200]}
            }
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        self.execution = execution
        return execution
    
    def _update_execution(self, status: ExecutionStatus, tokens: int = 0, cost: float = 0.0):
        """Update execution record"""
        db = self._get_db()
        
        if self.execution:
            self.execution.status = status
            self.execution.total_tokens_used = tokens
            self.execution.total_cost = cost
            self.execution.logs = json.dumps([log.to_dict() for log in self.logs])
            
            if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                self.execution.completed_at = datetime.now(timezone.utc)
                if self.execution.started_at:
                    delta = self.execution.completed_at - self.execution.started_at
                    self.execution.duration_seconds = int(delta.total_seconds())
            
            db.commit()
    
    def _save_artifact(
        self,
        artifact_type: str,
        content: Dict,
        title: str,
        agent: str
    ) -> ExecutionArtifact:
        """Save artifact to DB"""
        db = self._get_db()
        
        count = db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == self.execution.id,
            ExecutionArtifact.artifact_type == artifact_type
        ).count()
        
        artifact_code = f"{artifact_type.upper()}-{count + 1:03d}"
        
        artifact = ExecutionArtifact(
            execution_id=self.execution.id,
            artifact_type=artifact_type,
            artifact_code=artifact_code,
            title=title,
            producer_agent=agent,
            content=content,
            status=ArtifactStatus.DRAFT
        )
        db.add(artifact)
        db.commit()
        db.refresh(artifact)
        
        return artifact
    
    def _check_salesforce_connection(self) -> Dict[str, Any]:
        """Check if Salesforce org is connected"""
        try:
            result = subprocess.run(
                f"sf org display --target-org {salesforce_config.org_alias} --json",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return {"connected": result.returncode == 0}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    async def execute_agent(
        self,
        agent_id: str,
        task: str,
        deploy: bool = False,
        use_rag: bool = True,
        project_id: int = 53,
        user_id: int = 2
    ) -> AsyncGenerator[str, None]:
        """
        Execute a REAL agent script with STREAMING output to avoid timeout.
        """
        self.logs = []
        code_files = {}
        
        # === INIT DEBUG LOG FILE ===
        debug_log_file = None
        test_log = None
        if TEST_LOGGER_AVAILABLE:
            config = AGENT_CONFIG.get(agent_id, {})
            test_log = AgentTestLogger.start_test(
                agent_id=agent_id,
                agent_name=config.get("display_name", agent_id),
                task=task,
                use_rag=use_rag
            )
            # Create debug log file for RAG/LLM to write to
            debug_log_file = self.temp_dir / f"debug_log_{agent_id}_{test_log.test_id[:8]}.json"
            import json as _json
            with open(debug_log_file, 'w') as f:
                _json.dump({"test_id": test_log.test_id, "steps": []}, f)
        
        config = AGENT_CONFIG.get(agent_id)
        if not config:
            yield self._sse_event("error", message=f"Agent inconnu: {agent_id}")
            return
        
        agent_name = config["display_name"]
        script_path = AGENTS_PATH / config["script"]
        
        try:
            # === STEP 1: Create execution in DB ===
            yield self._sse_event("start", agent=agent_name, task=task[:100] + "...")
            
            execution = self._create_execution(agent_id, task, project_id, user_id)
            yield self.log(LogLevel.DB, f"📝 Exécution #{execution.id} créée en base").to_sse()
            yield self.log(LogLevel.INFO, f"🚀 Agent {agent_name} initialisé").to_sse()
            
            # === STEP 2: Check Salesforce connection ===
            yield self.log(LogLevel.INFO, f"🔗 Vérification connexion Salesforce: {salesforce_config.org_alias}").to_sse()
            
            sf_check = self._check_salesforce_connection()
            if sf_check["connected"]:
                yield self.log(LogLevel.SUCCESS, f"✅ Connecté à {salesforce_config.username}").to_sse()
            else:
                yield self.log(LogLevel.WARNING, f"⚠️ Connexion SF non vérifiée (non bloquant)").to_sse()
            
            # === P3: DIRECT IMPORT PATH for migrated agents ===
            if agent_id in MIGRATED_AGENTS:
                yield self.log(LogLevel.LLM, f"🤖 Running {agent_name} via direct import (P3)...").to_sse()

                agent_class = MIGRATED_AGENTS[agent_id]
                agent_instance = agent_class()

                # Build task_data matching agent class interface
                task_data = {
                    "mode": AGENT_DEFAULT_MODES.get(agent_id, "spec"),
                    "input_content": task,
                    "execution_id": execution.id,
                    "project_id": project_id,
                }

                # Run agent in thread pool (LLM calls are blocking)
                output_data = await asyncio.to_thread(agent_instance.run, task_data)

                if not output_data.get("success"):
                    error_msg = output_data.get("error", "Unknown error")
                    yield self.log(LogLevel.ERROR, f"❌ Agent {agent_id} failed: {error_msg}").to_sse()
                    self._update_execution(ExecutionStatus.FAILED)
                    yield self._sse_event("end", success=False, error=error_msg)
                    return

                output_size = len(json.dumps(output_data))
                yield self.log(LogLevel.SUCCESS, f"✅ Agent {agent_name} completed ({output_size} chars)").to_sse()

                # Persist output as artifact
                yield self.log(LogLevel.DB, "💾 Sauvegarde de l'artifact en base...").to_sse()
                artifact = self._save_artifact(
                    artifact_type="output",
                    content=output_data,
                    title=f"{agent_name} - Output",
                    agent=agent_id
                )
                yield self.log(LogLevel.CODE, f"📄 Artifact {artifact.artifact_code} créé").to_sse()

                # Extract code files (PM doesn't generate code, but keep for future agents)
                code_files = self._extract_code_from_output(output_data, agent_id)
                if code_files:
                    yield self.log(LogLevel.INFO, f"🔍 {len(code_files)} fichier(s) code extrait(s)").to_sse()
                    for filename, code in code_files.items():
                        art_type = "test" if "Test" in filename else "code"
                        code_artifact = self._save_artifact(
                            artifact_type=art_type,
                            content={"filename": filename, "code": code, "lines": len(str(code).split('\n'))},
                            title=filename,
                            agent=agent_id
                        )
                        yield self.log(LogLevel.CODE, f"📄 {filename} → {code_artifact.artifact_code}").to_sse()
                    saved = self._save_to_workspace(code_files, agent_id)
                    if saved:
                        yield self.log(LogLevel.SUCCESS, f"📁 {len(saved)} fichier(s) sauvegardé(s) dans workspace SFDX").to_sse()

                # Deploy if requested
                if deploy and code_files:
                    yield self.log(LogLevel.SFDX, "🚀 Déploiement vers Salesforce...").to_sse()
                    deploy_result = await self._deploy_to_salesforce()
                    if deploy_result["success"]:
                        yield self.log(LogLevel.SUCCESS, "✅ Déploiement réussi!").to_sse()
                    else:
                        yield self.log(LogLevel.ERROR, f"❌ Échec: {deploy_result.get('error', 'Unknown')}").to_sse()

                # Finalize
                self._update_execution(ExecutionStatus.COMPLETED)
                yield self.log(LogLevel.DB, f"✅ Exécution #{execution.id} terminée").to_sse()

                # Finalize debug log
                if TEST_LOGGER_AVAILABLE and test_log:
                    try:
                        AgentTestLogger.complete_test("success", output=output_data)
                    except Exception as e:
                        logger.warning(f"Debug log finalization error: {e}")

                yield self._sse_event(
                    "end",
                    success=True,
                    execution_id=execution.id,
                    agent=agent_name,
                    artifacts_count=len(code_files) if code_files else 1
                )
                return

            # === STEP 3: Prepare input file for agent (subprocess fallback) ===
            yield self.log(LogLevel.INFO, "📝 Préparation de l'input pour l'agent...").to_sse()

            input_file = self.temp_dir / f"input_{agent_id}_{execution.id}.json"
            output_file = self.temp_dir / f"output_{agent_id}_{execution.id}.json"

            with open(input_file, "w") as f:
                f.write(task)

            # === STEP 4: RAG info ===
            if use_rag:
                yield self.log(LogLevel.INFO, "📚 RAG activé pour contexte expert Salesforce").to_sse()

            # === STEP 5: Build command ===
            cmd = [
                "python3",
                str(script_path),
                "--input", str(input_file),
                "--output", str(output_file),
                "--execution-id", str(execution.id),
                "--project-id", str(project_id)
            ]

            # Sophie (PM) requires --mode argument
            if agent_id == "sophie":
                cmd.extend(["--mode", "extract_br"])

            if use_rag and agent_id != "sophie":
                cmd.append("--use-rag")

            yield self.log(LogLevel.LLM, f"🤖 Exécution du script {config['script']}...").to_sse()

            # === STEP 6: Execute with STREAMING stderr + HEARTBEAT ===
            # Prepare env with debug log file if available
            agent_env = {**os.environ}
            if debug_log_file:
                agent_env["AGENT_TEST_LOG_FILE"] = str(debug_log_file)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=agent_env
            )
            
            # Stream stderr line by line with heartbeat to prevent timeout
            stderr_lines = []
            heartbeat_interval = 5  # seconds
            last_heartbeat = datetime.now()
            
            while True:
                try:
                    # Wait for stderr with timeout
                    line = await asyncio.wait_for(
                        process.stderr.readline(),
                        timeout=heartbeat_interval
                    )
                    if not line:
                        break
                    decoded = line.decode().strip()
                    if decoded:
                        stderr_lines.append(decoded)
                        last_heartbeat = datetime.now()
                        # Convert agent logs to SSE
                        if '✅' in decoded:
                            yield self.log(LogLevel.SUCCESS, decoded).to_sse()
                        elif '⚠️' in decoded or 'warning' in decoded.lower():
                            yield self.log(LogLevel.WARNING, decoded).to_sse()
                        elif '❌' in decoded or 'error' in decoded.lower():
                            yield self.log(LogLevel.ERROR, decoded).to_sse()
                        elif '🔍' in decoded or '🤖' in decoded or '📤' in decoded:
                            yield self.log(LogLevel.LLM, decoded).to_sse()
                        else:
                            yield self.log(LogLevel.INFO, decoded).to_sse()
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    if process.returncode is None:  # Process still running
                        elapsed = (datetime.now() - last_heartbeat).seconds
                        yield self._sse_event("heartbeat", message=f"⏳ LLM processing... ({elapsed}s)")
                    else:
                        break
            
            # Wait for process to complete
            await process.wait()
            
            if process.returncode != 0:
                error_msg = "\n".join(stderr_lines[-5:]) if stderr_lines else "Unknown error"
                yield self.log(LogLevel.ERROR, f"❌ Agent {agent_id} a échoué (code {process.returncode})").to_sse()
                self._update_execution(ExecutionStatus.FAILED)
                yield self._sse_event("end", success=False, error=error_msg)
                return
            
            yield self.log(LogLevel.SUCCESS, f"✅ Agent {agent_name} terminé avec succès").to_sse()
            
            # === STEP 7: Read and persist output ===
            if output_file.exists():
                yield self.log(LogLevel.INFO, "📖 Lecture de l'output de l'agent...").to_sse()
                
                with open(output_file) as f:
                    try:
                        output_data = json.load(f)
                    except json.JSONDecodeError:
                        f.seek(0)
                        output_data = {"raw_output": f.read()}
                
                output_size = len(json.dumps(output_data))
                yield self.log(LogLevel.SUCCESS, f"✅ Output récupéré ({output_size} chars)").to_sse()
                
                # Persist output as artifact
                yield self.log(LogLevel.DB, "💾 Sauvegarde de l'artifact en base...").to_sse()
                
                artifact = self._save_artifact(
                    artifact_type="output",
                    content=output_data,
                    title=f"{agent_name} - Output",
                    agent=agent_id
                )
                
                yield self.log(LogLevel.CODE, f"📄 Artifact {artifact.artifact_code} créé").to_sse()
                
                # === STEP 8: Extract and save code files if present ===
                code_files = self._extract_code_from_output(output_data, agent_id)
                if code_files:
                    yield self.log(LogLevel.INFO, f"🔍 {len(code_files)} fichier(s) code extrait(s)").to_sse()
                    
                    for filename, code in code_files.items():
                        art_type = "test" if "Test" in filename else "code"
                        code_artifact = self._save_artifact(
                            artifact_type=art_type,
                            content={"filename": filename, "code": code, "lines": len(str(code).split('\n'))},
                            title=filename,
                            agent=agent_id
                        )
                        yield self.log(LogLevel.CODE, f"📄 {filename} → {code_artifact.artifact_code}").to_sse()
                    
                    # Save to SFDX workspace
                    saved = self._save_to_workspace(code_files, agent_id)
                    if saved:
                        yield self.log(LogLevel.SUCCESS, f"📁 {len(saved)} fichier(s) sauvegardé(s) dans workspace SFDX").to_sse()
            else:
                yield self.log(LogLevel.WARNING, "⚠️ Pas de fichier output généré").to_sse()
            
            # === STEP 9: Deploy if requested ===
            if deploy and code_files:
                yield self.log(LogLevel.SFDX, "🚀 Déploiement vers Salesforce...").to_sse()
                deploy_result = await self._deploy_to_salesforce()
                if deploy_result["success"]:
                    yield self.log(LogLevel.SUCCESS, "✅ Déploiement réussi!").to_sse()
                else:
                    yield self.log(LogLevel.ERROR, f"❌ Échec: {deploy_result.get('error', 'Unknown')}").to_sse()
            
            # === STEP 10: Finalize ===
            self._update_execution(ExecutionStatus.COMPLETED)
            yield self.log(LogLevel.DB, f"✅ Exécution #{execution.id} terminée").to_sse()
            
            # === FINALIZE DEBUG LOG ===
            if TEST_LOGGER_AVAILABLE and test_log and debug_log_file and debug_log_file.exists():
                try:
                    import json as _json
                    with open(debug_log_file, 'r') as f:
                        debug_data = _json.load(f)
                    # Transfer steps to persistent log
                    for step in debug_data.get("steps", []):
                        test_log.add_step(step.get("step", "unknown"), step.get("data", {}))
                    AgentTestLogger.complete_test("success", output=output_data if 'output_data' in dir() else None)
                except Exception as e:
                    logger.warning(f"Debug log finalization error: {e}")
            
            yield self._sse_event(
                "end",
                success=True,
                execution_id=execution.id,
                agent=agent_name,
                artifacts_count=len(code_files) if code_files else 1
            )
            
        except Exception as e:
            yield self.log(LogLevel.ERROR, f"❌ Erreur fatale: {str(e)}").to_sse()
            if self.execution:
                self._update_execution(ExecutionStatus.FAILED)
            yield self._sse_event("end", success=False, error=str(e))
        
        finally:
            self._close_db()
    
    def _extract_code_from_output(self, output: Dict, agent_id: str) -> Dict[str, str]:
        """Extract code files from agent output"""
        import re
        files = {}
        
        if isinstance(output, dict):
            for key in ["code", "apex_code", "lwc_code", "components", "classes", "triggers", "content"]:
                if key in output:
                    content = output[key]
                    if isinstance(content, str):
                        files.update(self._parse_code_blocks(content, agent_id))
                    elif isinstance(content, dict):
                        # Handle dict content - extract only string values
                        for fname, fvalue in content.items():
                            if isinstance(fvalue, str):
                                files[fname] = fvalue
                            elif isinstance(fvalue, dict):
                                # Handle nested dict like {"code": "...", "description": "..."}
                                if "code" in fvalue and isinstance(fvalue["code"], str):
                                    files[fname] = fvalue["code"]
                                elif "content" in fvalue and isinstance(fvalue["content"], str):
                                    files[fname] = fvalue["content"]
                    elif isinstance(content, list):
                        # Handle list of code items
                        for i, item in enumerate(content):
                            if isinstance(item, str):
                                files[f"generated_{i+1}.txt"] = item
                            elif isinstance(item, dict):
                                fname = item.get("filename", item.get("name", f"file_{i+1}"))
                                code = item.get("code", item.get("content", ""))
                                if isinstance(code, str) and code:
                                    files[str(fname)] = code
        
        return files
    
    def _parse_code_blocks(self, content: str, agent_id: str) -> Dict[str, str]:
        """Parse code blocks from text content"""
        import re
        files = {}
        
        if agent_id in ["diego", "elena"]:
            pattern = r'```(?:apex|java)?\s*\n(?://\s*(?:File|Filename):\s*(\S+\.(?:cls|trigger))?\n)?(.*?)```'
        elif agent_id == "zara":
            pattern = r'```(?:javascript|js|html|css)?\s*\n(?://\s*(?:File|Filename):\s*(\S+\.(?:js|html|css))?\n)?(.*?)```'
        else:
            pattern = r'```\w*\s*\n(?://\s*(?:File|Filename):\s*(\S+)?\n)?(.*?)```'
        
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        
        for i, (filename, code) in enumerate(matches):
            code = code.strip()
            if not code:
                continue
            
            if not filename:
                if agent_id in ["diego", "elena"]:
                    class_match = re.search(r'(?:public|private|global)\s+(?:with\s+sharing\s+)?class\s+(\w+)', code)
                    trigger_match = re.search(r'trigger\s+(\w+)\s+on', code)
                    if class_match:
                        filename = f"{class_match.group(1)}.cls"
                    elif trigger_match:
                        filename = f"{trigger_match.group(1)}.trigger"
                    else:
                        filename = f"GeneratedCode_{i+1}.cls"
                elif agent_id == "zara":
                    filename = f"component_{i+1}.js"
                else:
                    filename = f"output_{i+1}.txt"
            
            files[filename] = code
        
        return files
    
    def _save_to_workspace(self, code_files: Dict[str, str], agent_id: str) -> List[str]:
        """Save code files to SFDX workspace"""
        saved = []
        base_path = salesforce_config.force_app_path
        
        for filename, code in code_files.items():
            try:
                if filename.endswith('.trigger'):
                    folder = os.path.join(base_path, 'triggers')
                    meta = self._trigger_meta()
                elif filename.endswith('.cls'):
                    folder = os.path.join(base_path, 'classes')
                    meta = self._class_meta()
                elif filename.endswith(('.js', '.html', '.css')):
                    comp_name = filename.split('.')[0]
                    folder = os.path.join(base_path, 'lwc', comp_name)
                    meta = None
                else:
                    folder = os.path.join(base_path, 'classes')
                    meta = self._class_meta()
                
                os.makedirs(folder, exist_ok=True)
                
                filepath = os.path.join(folder, filename)
                with open(filepath, 'w') as f:
                    f.write(code)
                saved.append(filepath)
                
                if meta:
                    with open(filepath + '-meta.xml', 'w') as f:
                        f.write(meta)
                
            except Exception as e:
                print(f"Error saving {filename}: {e}", file=sys.stderr)
        
        return saved
    
    async def _deploy_to_salesforce(self) -> Dict[str, Any]:
        """Deploy to Salesforce"""
        try:
            result = subprocess.run(
                f"sf project deploy start --source-dir {salesforce_config.force_app_path} --target-org {salesforce_config.org_alias} --json",
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=salesforce_config.sfdx_project_path
            )
            return {"success": result.returncode == 0, "error": result.stderr if result.returncode != 0 else None}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _class_meta(self) -> str:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <status>Active</status>
</ApexClass>'''
    
    def _trigger_meta(self) -> str:
        return '''<?xml version="1.0" encoding="UTF-8"?>
<ApexTrigger xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>60.0</apiVersion>
    <status>Active</status>
</ApexTrigger>'''


# Singleton
_executor: Optional[AgentExecutor] = None

def get_agent_executor() -> AgentExecutor:
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor


# ============================================================================
# BUILD MODE: Run agent synchronously (for IncrementalExecutor)
# ============================================================================

async def run_agent_task(
    agent_id: str,
    mode: str,
    input_data: dict,
    execution_id: int = 0,
    project_id: int = 0,
    timeout: int = 300
) -> dict:
    """
    Run an agent in build mode and return the result.
    Used by IncrementalExecutor for BUILD phase.
    
    Args:
        agent_id: Agent identifier (diego, zara, raj, aisha, elena)
        mode: Agent mode (spec, build, test)
        input_data: Input data dict for the agent
        execution_id: Current execution ID
        project_id: Current project ID
        timeout: Timeout in seconds
        
    Returns:
        dict with success, files, and agent output
    """
    import tempfile
    import subprocess
    import asyncio
    
    config = AGENT_CONFIG.get(agent_id)
    if not config:
        return {"success": False, "error": f"Unknown agent: {agent_id}"}
    
    script_path = AGENTS_PATH / config["script"]
    if not script_path.exists():
        return {"success": False, "error": f"Script not found: {script_path}"}
    
    logger.info(f"[run_agent_task] Running {agent_id} in {mode} mode")

    # P3: Direct import for migrated agents (no subprocess overhead)
    if agent_id in MIGRATED_AGENTS:
        logger.info(f"[run_agent_task] Using direct import for {agent_id} (P3)")
        try:
            agent_class = MIGRATED_AGENTS[agent_id]
            agent_instance = agent_class()
            task_data = {
                "mode": mode,
                "input_content": json.dumps(input_data, ensure_ascii=False),
                "execution_id": execution_id,
                "project_id": project_id,
            }
            result = agent_instance.run(task_data)
            result["success"] = result.get("success", True)
            logger.info(f"[run_agent_task] {agent_id} completed via direct import: {result.get('success')}")
            return result
        except Exception as e:
            logger.error(f"[run_agent_task] Direct import error for {agent_id}: {e}")
            return {"success": False, "error": str(e)}

    # Subprocess fallback for non-migrated agents
    try:
        # Create temp files for input/output
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(input_data, f, ensure_ascii=False)
            input_file = f.name
        
        output_file = tempfile.mktemp(suffix='.json')
        
        # Build command
        cmd = [
            "python3",
            str(script_path),
            "--mode", mode,
            "--input", input_file,
            "--output", output_file,
            "--execution-id", str(execution_id),
            "--project-id", str(project_id),
            "--use-rag"
        ]
        
        logger.info(f"[run_agent_task] Command: {' '.join(cmd)}")
        
        # Run subprocess with environment variables
        import os as os_module
        env = os_module.environ.copy()
        env["PYTHONPATH"] = str(settings.BACKEND_ROOT)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(settings.BACKEND_ROOT),
            env=env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return {"success": False, "error": f"Agent {agent_id} timed out after {timeout}s"}
        
        # Log stderr
        if stderr:
            for line in stderr.decode().split('\n'):
                if line.strip():
                    logger.info(f"[{agent_id}] {line.strip()}")
        
        # Read output file
        if os.path.exists(output_file):
            with open(output_file, 'r') as f:
                result = json.load(f)
            
            # Clean up
            os.unlink(input_file)
            os.unlink(output_file)
            
            # Ensure success flag
            result["success"] = result.get("success", True)
            logger.info(f"[run_agent_task] {agent_id} completed: {result.get('success')}")
            return result
        else:
            os.unlink(input_file)
            return {
                "success": False,
                "error": f"No output file from {agent_id}",
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else ""
            }
            
    except Exception as e:
        logger.error(f"[run_agent_task] Error: {str(e)}")
        return {"success": False, "error": str(e)}
