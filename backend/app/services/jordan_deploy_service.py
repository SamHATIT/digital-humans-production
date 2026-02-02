"""
Jordan Deploy Service - BUILD v2
Service centralisé de déploiement, utilisé par Jordan (Tech Lead).
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeployMethod(str, Enum):
    TOOLING_API = "tooling_api"
    SFDX_SOURCE = "sfdx_source"
    DATA_SCRIPTS = "data_scripts"
    SFDX_MANIFEST = "sfdx_manifest"


@dataclass
class PhaseDeployConfig:
    """Configuration de déploiement par phase."""
    phase: int
    phase_name: str
    agent: str
    deploy_method: DeployMethod
    requires_retrieve: bool = False


PHASE_CONFIGS = {
    1: PhaseDeployConfig(1, "data_model", "raj", DeployMethod.TOOLING_API, requires_retrieve=True),  # Via sf_admin_service (JSON→XML→SFDX)
    2: PhaseDeployConfig(2, "business_logic", "diego", DeployMethod.SFDX_SOURCE),
    3: PhaseDeployConfig(3, "ui_components", "zara", DeployMethod.SFDX_SOURCE),
    4: PhaseDeployConfig(4, "automation", "raj", DeployMethod.TOOLING_API, requires_retrieve=True),  # Mix avec SFDX pour flows
    5: PhaseDeployConfig(5, "security", "raj", DeployMethod.SFDX_SOURCE),  # Permission sets better via SFDX
    6: PhaseDeployConfig(6, "data_migration", "aisha", DeployMethod.DATA_SCRIPTS),
}


class JordanDeployService:
    """
    Service de déploiement centralisé pour BUILD v2.
    Jordan = Tech Lead qui orchestre merge PR → deploy → validate → tag.
    """
    
    def __init__(self, project_id: int, db):
        self.project_id = project_id
        self.db = db
        self.git_service = None
        self.sfdx_service = None
        self.sf_admin_service = None
    
    async def initialize(self):
        """Initialise les services nécessaires."""
        from sqlalchemy import text
        from app.services.git_service import GitService
        from app.services.sfdx_service import SFDXService
        from app.services.sf_admin_service import create_sf_admin_service
        from app.utils.encryption import decrypt_credential
        
        # Récupérer les infos du projet
        project_result = self.db.execute(
            text("SELECT sf_username, git_repo_url, git_branch FROM projects WHERE id = :id"),
            {"id": self.project_id}
        ).fetchone()
        
        if not project_result:
            raise ValueError(f"Project {self.project_id} not found")
        
        sf_username = project_result.sf_username
        git_repo_url = project_result.git_repo_url
        git_branch = project_result.git_branch or "main"
        
        # Récupérer le token Git depuis project_credentials
        git_cred = self.db.execute(
            text("SELECT encrypted_value FROM project_credentials WHERE project_id = :id AND credential_type = 'GIT_TOKEN'"),
            {"id": self.project_id}
        ).fetchone()
        
        git_token = None
        if git_cred and git_cred.encrypted_value:
            # Le token Git n'est pas encrypté dans cette table (stocké en clair)
            git_token = git_cred.encrypted_value
            logger.info(f"[Jordan] Git token loaded from project_credentials")
        
        # Créer GitService
        if git_repo_url:
            self.git_service = GitService(
                repo_url=git_repo_url,
                branch=git_branch,
                token=git_token,
                project_id=self.project_id
            )
            logger.info(f"[Jordan] GitService initialized for {git_repo_url}")
        else:
            logger.warning(f"[Jordan] No git_repo_url for project {self.project_id}")
        
        # Créer SFDXService
        if sf_username:
            self.sfdx_service = SFDXService(
                target_org=sf_username,
                project_id=self.project_id
            )
            logger.info(f"[Jordan] SFDXService initialized for {sf_username}")
        else:
            logger.warning(f"[Jordan] No sf_username for project {self.project_id}")
        
        # Créer SFAdminService
        self.sf_admin_service = await create_sf_admin_service(self.project_id, self.db)
        
        logger.info(f"[Jordan] Services initialized for project {self.project_id}")
    
    async def close(self):
        """Ferme les connexions."""
        # sf_admin_service n'a plus de connexion persistante (utilise SFDX CLI)
        pass
    
    # ═══════════════════════════════════════════════════════════════
    # MAIN DEPLOYMENT FLOW
    # ═══════════════════════════════════════════════════════════════
    
    async def deploy_phase(
        self,
        phase: int,
        aggregated_output: Dict[str, Any],
        branch_name: str,
        pr_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Déploie une phase complète.
        
        Flow:
        1. Merge PR (si fournie)
        2. Deploy selon méthode de la phase
        3. Retrieve metadata (si Tooling API)
        4. Validate deployment
        5. Tag success
        
        Args:
            phase: Numéro de phase (1-6)
            aggregated_output: Output agrégé de la phase
            branch_name: Nom de la branche
            pr_url: URL de la PR à merger (optionnel)
            
        Returns:
            Résultat du déploiement
        """
        config = PHASE_CONFIGS.get(phase)
        if not config:
            return {"success": False, "error": f"Unknown phase: {phase}"}
        
        logger.info(f"[Jordan] Deploying phase {phase} ({config.phase_name}) via {config.deploy_method}")
        
        result = {
            "phase": phase,
            "phase_name": config.phase_name,
            "deploy_method": config.deploy_method.value,
            "success": False,
            "steps": [],
        }
        
        try:
            # Step 1: Merge PR if provided
            if pr_url:
                merge_result = await self.merge_pr_from_url(pr_url)
                result["steps"].append({"step": "merge_pr", "result": merge_result})
                if not merge_result.get("success"):
                    result["error"] = f"PR merge failed: {merge_result.get('error')}"
                    return result
                result["merge_sha"] = merge_result.get("sha")
            
            # Step 2: Deploy based on method
            if config.deploy_method == DeployMethod.TOOLING_API:
                deploy_result = await self.deploy_admin_config(aggregated_output)
            elif config.deploy_method == DeployMethod.SFDX_SOURCE:
                deploy_result = await self.deploy_source_code(aggregated_output)
            elif config.deploy_method == DeployMethod.DATA_SCRIPTS:
                deploy_result = await self.execute_data_migration(aggregated_output)
            else:
                deploy_result = {"success": False, "error": f"Unknown deploy method: {config.deploy_method}"}
            
            result["steps"].append({"step": "deploy", "result": deploy_result})
            
            if not deploy_result.get("success"):
                result["error"] = f"Deploy failed: {deploy_result.get('error')}"
                # Rollback merge if we merged
                if result.get("merge_sha"):
                    await self.revert_merge(result["merge_sha"])
                    result["steps"].append({"step": "rollback", "result": "Merge reverted"})
                return result
            
            # Step 3: Retrieve metadata if needed (post-Tooling API)
            if config.requires_retrieve:
                retrieve_result = await self.retrieve_and_commit_metadata(aggregated_output, branch_name)
                result["steps"].append({"step": "retrieve", "result": retrieve_result})
            
            # Step 4: Tag success
            tag_name = f"deployed/phase-{phase}-{config.phase_name}"
            tag_result = await self.tag_phase(tag_name, f"Phase {phase} ({config.phase_name}) deployed successfully")
            result["steps"].append({"step": "tag", "result": tag_result})
            
            result["success"] = True
            result["deployed_components"] = deploy_result.get("deployed_components", [])
            
            logger.info(f"[Jordan] Phase {phase} deployed successfully")
            return result
            
        except Exception as e:
            logger.exception(f"[Jordan] Phase {phase} deployment failed")
            result["error"] = str(e)
            return result
    
    # ═══════════════════════════════════════════════════════════════
    # GIT OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def create_phase_branch(self, phase: int, phase_name: str) -> Dict[str, Any]:
        """Crée une branche pour la phase."""
        branch_name = f"build/phase-{phase}-{phase_name}"
        
        if not self.git_service:
            return {"success": False, "error": "Git service not initialized"}
        
        result = await self.git_service.create_branch(branch_name)
        return {"success": True, "branch_name": branch_name, **result}
    
    async def create_phase_pr(
        self,
        branch_name: str,
        phase: int,
        phase_name: str,
        files_count: int
    ) -> Dict[str, Any]:
        """Crée une PR pour la phase."""
        title = f"[BUILD Phase {phase}] {phase_name.replace('_', ' ').title()}"
        body = f"""## Phase {phase}: {phase_name}

### Summary
- Files: {files_count}
- Agent: {PHASE_CONFIGS[phase].agent}
- Deploy method: {PHASE_CONFIGS[phase].deploy_method.value}

### Review checklist
- [ ] Code review completed
- [ ] Elena QA review passed
- [ ] Ready for deployment
"""
        
        if not self.git_service:
            return {"success": False, "error": "Git service not initialized"}
        
        result = await self.git_service.create_pr(branch_name, title, body)
        return result
    
    async def merge_pr_from_url(self, pr_url: str) -> Dict[str, Any]:
        """Merge une PR à partir de son URL."""
        # Extract PR number from URL
        import re
        match = re.search(r'/pull/(\d+)', pr_url)
        if not match:
            return {"success": False, "error": f"Invalid PR URL: {pr_url}"}
        
        pr_number = int(match.group(1))
        return await self.merge_pr(pr_number)
    
    async def merge_pr(self, pr_number: int) -> Dict[str, Any]:
        """Merge une PR."""
        if not self.git_service:
            return {"success": False, "error": "Git service not initialized"}
        
        result = await self.git_service.merge_pr(pr_number)
        return result
    
    async def revert_merge(self, merge_sha: str) -> Dict[str, Any]:
        """Revert un merge en cas d'échec de déploiement."""
        if not self.git_service:
            return {"success": False, "error": "Git service not initialized"}
        
        result = await self.git_service.revert_merge(merge_sha)
        logger.warning(f"[Jordan] Merge {merge_sha[:8]} reverted")
        return result
    
    async def tag_phase(self, tag_name: str, message: str) -> Dict[str, Any]:
        """Crée un tag Git."""
        if not self.git_service:
            return {"success": False, "error": "Git service not initialized"}
        
        result = await self.git_service.tag(tag_name, message)
        return result
    
    async def commit_files(self, files: Dict[str, str], message: str) -> Dict[str, Any]:
        """Commit des fichiers."""
        if not self.git_service:
            return {"success": False, "error": "Git service not initialized"}
        
        result = await self.git_service.commit_files(files, message)
        return result
    
    # ═══════════════════════════════════════════════════════════════
    # DEPLOYMENT METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def deploy_admin_config(self, aggregated_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 1/4: Déploie via SFDX CLI (plans JSON de Raj → XML → deploy).
        """
        if not self.sf_admin_service:
            return {"success": False, "error": "SF Admin service not initialized"}
        
        operations = aggregated_output.get("operations", [])
        if not operations:
            return {"success": False, "error": "No operations to deploy"}
        
        logger.info(f"[Jordan] Deploying {len(operations)} operations via SFDX CLI")
        
        plan = {"operations": operations}
        
        # execute_plan est synchrone, on l'appelle dans un thread
        import asyncio
        result = await asyncio.to_thread(self.sf_admin_service.execute_plan, plan)
        
        # Convertir DeployResult en dict
        return {
            "success": result.success,
            "components_deployed": result.components_deployed,
            "components_failed": result.components_failed,
            "errors": result.errors,
            "deployed_components": [c["name"] for c in result.created_components],
            "deploy_id": result.deploy_id
        }
    
    async def deploy_source_code(self, aggregated_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 2/3/5: Déploie via SFDX source deploy.
        """
        if not self.sfdx_service:
            return {"success": False, "error": "SFDX service not initialized"}
        
        files = aggregated_output.get("files", {})
        if not files:
            # Check if there are XML files in operations
            files = aggregated_output.get("xml_files", {})
        
        if not files:
            return {"success": False, "error": "No files to deploy"}
        
        logger.info(f"[Jordan] Deploying {len(files)} files via SFDX")
        
        # Write files to temp directory
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            for path, content in files.items():
                full_path = os.path.join(tmpdir, path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
            
            # Deploy using SFDX
            result = await self.sfdx_service.deploy_source(tmpdir)
        
        if result.get("success"):
            result["deployed_components"] = list(files.keys())
        
        return result
    
    async def execute_data_migration(self, aggregated_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Phase 6: Exécute les scripts de migration de données.
        """
        if not self.sfdx_service:
            return {"success": False, "error": "SFDX service not initialized"}
        
        scripts = aggregated_output.get("scripts", [])
        files = aggregated_output.get("files", {})
        
        results = {
            "success": True,
            "scripts_executed": 0,
            "files_committed": 0,
            "details": [],
        }
        
        # Execute Apex anonymous scripts
        for script in scripts:
            script_name = script.get("name", "unnamed")
            script_code = script.get("code", "")
            
            if script_code:
                exec_result = await self.sfdx_service.execute_anonymous(script_code)
                results["details"].append({
                    "script": script_name,
                    "success": exec_result.get("success", False),
                    "output": exec_result.get("output", "")
                })
                
                if exec_result.get("success"):
                    results["scripts_executed"] += 1
                else:
                    results["success"] = False
        
        # Commit data files (SDL, CSV, SOQL) to Git
        if files:
            commit_result = await self.commit_files(files, "chore: add data migration files")
            results["files_committed"] = len(files)
            results["details"].append({"step": "commit_files", "result": commit_result})
        
        results["deployed_components"] = [s.get("name", "script") for s in scripts]
        
        return results
    
    async def retrieve_and_commit_metadata(
        self,
        aggregated_output: Dict[str, Any],
        branch_name: str
    ) -> Dict[str, Any]:
        """
        Post-Tooling API: Récupère le metadata propre depuis la sandbox et commit.
        """
        if not self.sfdx_service:
            return {"success": False, "error": "SFDX service not initialized"}
        
        # Extract object names from operations
        objects_to_retrieve = set()
        for op in aggregated_output.get("operations", []):
            if op.get("type") == "create_object":
                objects_to_retrieve.add(op.get("api_name"))
            elif op.get("type") == "create_field":
                objects_to_retrieve.add(op.get("object"))
        
        if not objects_to_retrieve:
            return {"success": True, "message": "No objects to retrieve"}
        
        logger.info(f"[Jordan] Retrieving metadata for: {objects_to_retrieve}")
        
        # Retrieve each object
        retrieved_files = {}
        for obj in objects_to_retrieve:
            result = await self.sfdx_service.retrieve_metadata("CustomObject", obj)
            if result.get("success") and result.get("files"):
                retrieved_files.update(result["files"])
        
        if retrieved_files:
            # Commit retrieved metadata
            commit_result = await self.commit_files(
                retrieved_files,
                f"chore: retrieve metadata from sandbox ({len(retrieved_files)} files)"
            )
            return {"success": True, "files_retrieved": len(retrieved_files), "commit": commit_result}
        
        return {"success": True, "message": "No files retrieved"}
    
    # ═══════════════════════════════════════════════════════════════
    # FINAL PACKAGING
    # ═══════════════════════════════════════════════════════════════
    
    async def generate_final_package_xml(self, deployed_phases: List[int]) -> Dict[str, Any]:
        """
        Génère le package.xml final après toutes les phases.
        """
        logger.info(f"[Jordan] Generating final package.xml for phases: {deployed_phases}")
        
        # Collect all deployed components
        all_components = {
            "CustomObject": [],
            "CustomField": [],
            "ApexClass": [],
            "ApexTrigger": [],
            "LightningComponentBundle": [],
            "Flow": [],
            "PermissionSet": [],
            "Layout": [],
        }
        
        # This would normally query deployed components from DB
        # For now, return a template
        
        package_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>*</members>
        <name>CustomObject</name>
    </types>
    <types>
        <members>*</members>
        <name>CustomField</name>
    </types>
    <types>
        <members>*</members>
        <name>ApexClass</name>
    </types>
    <types>
        <members>*</members>
        <name>ApexTrigger</name>
    </types>
    <types>
        <members>*</members>
        <name>LightningComponentBundle</name>
    </types>
    <types>
        <members>*</members>
        <name>Flow</name>
    </types>
    <types>
        <members>*</members>
        <name>PermissionSet</name>
    </types>
    <version>59.0</version>
</Package>
"""
        
        # Commit package.xml
        files = {"manifest/package.xml": package_xml}
        commit_result = await self.commit_files(files, "chore: add final package.xml")
        
        # Create release tag
        tag_result = await self.tag_phase("release/v1.0.0", "BUILD complete - all phases deployed")
        
        return {
            "success": True,
            "package_xml": package_xml,
            "commit": commit_result,
            "tag": tag_result,
        }
