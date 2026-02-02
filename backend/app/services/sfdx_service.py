"""
SFDX Service - ORCH-03b
Handles Salesforce deployments and test execution via SFDX CLI.

Capabilities:
- Deploy source to sandbox
- Run Apex tests
- Retrieve deployment/test results
- Manage org connections

Author: Digital Humans Team
Created: 2025-12-08
"""
import asyncio
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from app.services.audit_service import audit_service, ActorType, ActionCategory

logger = logging.getLogger(__name__)


class SFDXError(Exception):
    """SFDX operation failed"""
    pass


class SFDXService:
    """
    Service for interacting with Salesforce via SFDX CLI.
    
    All operations are async and return structured results.
    """
    
    def __init__(self, target_org: str = None, project_id: int = None, execution_id: int = None, task_id: str = None):
        """
        Initialize SFDX service.
        
        Args:
            target_org: Org alias or username. If None, uses default org.
        """
        self.target_org = target_org
        self.sfdx_path = self._find_sfdx()
        self.project_id = project_id
        self.execution_id = execution_id
        self.task_id = task_id
        
    def _find_sfdx(self) -> str:
        """Find SFDX CLI path"""
        for path in ["/usr/bin/sfdx", "/usr/local/bin/sfdx", "/usr/local/bin/sf", "sfdx"]:
            if os.path.exists(path) or path == "sfdx":
                return path
        raise SFDXError("SFDX CLI not found")
    
    def _log_operation(self, operation: str, component_type: str = None, component_name: str = None, success: bool = True, error_message: str = None, duration_ms: int = None, extra: dict = None):
        """Log SFDX operation to audit trail"""
        if self.execution_id:  # Only log if context is set
            audit_service.log_sfdx_operation(
                operation=operation,
                execution_id=self.execution_id,
                project_id=self.project_id,
                task_id=self.task_id,
                component_type=component_type,
                component_name=component_name,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms,
                extra_data=extra
            )
    
    async def _run_command(
        self, 
        args: List[str], 
        timeout: int = 300,
        cwd: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Run SFDX command and return parsed result.
        
        Args:
            args: Command arguments (without 'sfdx' prefix)
            timeout: Command timeout in seconds
            cwd: Working directory
            
        Returns:
            Tuple of (success, result_dict)
        """
        cmd = [self.sfdx_path] + args + ["--json"]
        
        if self.target_org:
            cmd.extend(["--target-org", self.target_org])
        
        logger.info(f"[SFDX] Running: {' '.join(cmd)}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=timeout
            )
            
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')
            
            # Parse JSON output
            try:
                result = json.loads(stdout_str) if stdout_str.strip() else {}
            except json.JSONDecodeError:
                result = {"raw_output": stdout_str}
            
            success = process.returncode == 0 and result.get("status", 1) == 0
            
            if not success:
                logger.warning(f"[SFDX] Command failed: {stderr_str or result.get('message', 'Unknown error')}")
                result["stderr"] = stderr_str
            
            return success, result
            
        except asyncio.TimeoutError:
            logger.error(f"[SFDX] Command timed out after {timeout}s")
            return False, {"error": f"Timeout after {timeout}s"}
        except Exception as e:
            logger.error(f"[SFDX] Command exception: {str(e)}")
            return False, {"error": str(e)}
    
    async def check_connection(self) -> Dict[str, Any]:
        """
        Check org connection status.
        
        Returns:
            Dict with org info or error
        """
        success, result = await self._run_command(["org", "display"])
        
        if success:
            org_info = result.get("result", {})
            return {
                "connected": True,
                "username": org_info.get("username"),
                "org_id": org_info.get("id"),
                "instance_url": org_info.get("instanceUrl"),
                "alias": org_info.get("alias"),
            }
        else:
            return {
                "connected": False,
                "error": result.get("message", result.get("error", "Unknown error"))
            }
    
    async def deploy_source(
        self,
        source_path: str,
        test_level: str = "NoTestRun",
        check_only: bool = False,
        cwd: str = None
    ) -> Dict[str, Any]:
        """
        Deploy source to target org.
        
        Args:
            source_path: Path to source directory or file
            test_level: NoTestRun, RunSpecifiedTests, RunLocalTests, RunAllTestsInOrg
            check_only: If True, validate only without deploying
            cwd: Working directory (must contain sfdx-project.json)
            
        Returns:
            Dict with deployment result
        """
        args = ["project", "deploy", "start", "--source-dir", source_path]
        
        if test_level:
            args.extend(["--test-level", test_level])
        
        if check_only:
            args.append("--dry-run")
        
        # Longer timeout for deployments
        success, result = await self._run_command(args, timeout=600, cwd=cwd)
        
        if success:
            deploy_result = result.get("result", {})
            self._log_operation("deploy", extra={"components_deployed": deploy_result.get("numberComponentsDeployed", 0)})
            return {
                "success": True,
                "deployed": True,
                "components_deployed": deploy_result.get("numberComponentsDeployed", 0),
                "components_failed": deploy_result.get("numberComponentErrors", 0),
                "id": deploy_result.get("id"),
                "status": deploy_result.get("status"),
                "details": deploy_result
            }
        else:
            self._log_operation("deploy", success=False, error_message=result.get("message", "Deployment failed"))
            return {
                "success": False,
                "deployed": False,
                "error": result.get("message", result.get("error", "Deployment failed")),
                "details": result
            }
    
    async def deploy_metadata(
        self,
        metadata_type: str,
        metadata_name: str,
        content: str,
        project_path: str = None
    ) -> Dict[str, Any]:
        """
        Deploy a single metadata component.
        
        Creates temporary project structure and deploys.
        
        Args:
            metadata_type: e.g., "ApexClass", "ApexTrigger", "LightningComponentBundle"
            metadata_name: Component name
            content: File content
            project_path: Existing project path, or creates temp
            
        Returns:
            Dict with deployment result
        """
        # Create temp directory with SFDX project structure
        with tempfile.TemporaryDirectory(prefix="sfdx_deploy_") as temp_dir:
            # Create sfdx-project.json
            project_json = {
                "packageDirectories": [{"path": "force-app", "default": True}],
                "namespace": "",
                "sfdcLoginUrl": "https://login.salesforce.com",
                "sourceApiVersion": "59.0"
            }
            
            project_file = Path(temp_dir) / "sfdx-project.json"
            project_file.write_text(json.dumps(project_json, indent=2))
            
            # Create metadata structure
            type_folder_map = {
                "ApexClass": "classes",
                "ApexTrigger": "triggers",
                "LightningComponentBundle": "lwc",
                "CustomObject": "objects",
                "Flow": "flows",
                "PermissionSet": "permissionsets",
            }
            
            folder = type_folder_map.get(metadata_type, metadata_type.lower())
            metadata_dir = Path(temp_dir) / "force-app" / "main" / "default" / folder
            metadata_dir.mkdir(parents=True, exist_ok=True)
            
            # Write content
            if metadata_type == "ApexClass":
                (metadata_dir / f"{metadata_name}.cls").write_text(content)
                (metadata_dir / f"{metadata_name}.cls-meta.xml").write_text(
                    f'''<?xml version="1.0" encoding="UTF-8"?>
<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <status>Active</status>
</ApexClass>'''
                )
            elif metadata_type == "ApexTrigger":
                (metadata_dir / f"{metadata_name}.trigger").write_text(content)
                (metadata_dir / f"{metadata_name}.trigger-meta.xml").write_text(
                    f'''<?xml version="1.0" encoding="UTF-8"?>
<ApexTrigger xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <status>Active</status>
</ApexTrigger>'''
                )
            else:
                # Generic handling
                (metadata_dir / f"{metadata_name}.xml").write_text(content)
            
            # Deploy from temp directory (contains sfdx-project.json)
            return await self.deploy_source(
                source_path=str(metadata_dir),
                test_level="NoTestRun",
                cwd=temp_dir
            )
    

    async def deploy_lwc_bundle(
        self,
        component_name: str,
        files: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Deploy a LWC bundle (multiple files as one component).
        
        Args:
            component_name: Name of the LWC component
            files: Dict of filename -> content (e.g., {'component.js': '...', 'component.html': '...'})
            
        Returns:
            Dict with deployment result
        """
        import tempfile
        
        with tempfile.TemporaryDirectory(prefix="sfdx_lwc_") as temp_dir:
            # Create sfdx-project.json
            project_json = {
                "packageDirectories": [{"path": "force-app", "default": True}],
                "namespace": "",
                "sfdcLoginUrl": "https://login.salesforce.com",
                "sourceApiVersion": "59.0"
            }
            
            project_file = Path(temp_dir) / "sfdx-project.json"
            project_file.write_text(json.dumps(project_json, indent=2))
            
            # Create LWC bundle structure: lwc/componentName/files
            bundle_dir = Path(temp_dir) / "force-app" / "main" / "default" / "lwc" / component_name
            bundle_dir.mkdir(parents=True, exist_ok=True)
            
            # Write all component files
            for filename, content in files.items():
                # Extract just the filename from the path
                if '/' in filename:
                    filename = filename.split('/')[-1]
                (bundle_dir / filename).write_text(content)
                logger.info(f"[SFDX] Created LWC file: {bundle_dir / filename}")
            
            # Deploy the entire bundle
            return await self.deploy_source(
                source_path=str(bundle_dir),
                test_level="NoTestRun",
                cwd=temp_dir
            )


    async def run_tests(
        self,
        test_classes: List[str] = None,
        test_suite: str = None,
        code_coverage: bool = True,
        timeout: int = 600
    ) -> Dict[str, Any]:
        """
        Run Apex tests.
        
        Args:
            test_classes: List of test class names to run
            test_suite: Test suite name (alternative to test_classes)
            code_coverage: Include code coverage in results
            timeout: Test timeout in seconds
            
        Returns:
            Dict with test results
        """
        args = ["apex", "run", "test", "--synchronous", "--wait", "10"]
        
        if test_classes:
            args.extend(["--tests", ",".join(test_classes)])
        elif test_suite:
            args.extend(["--suite-names", test_suite])
        else:
            # Run all tests
            args.append("--test-level=RunLocalTests")
        
        if code_coverage:
            args.append("--code-coverage")
        
        success, result = await self._run_command(args, timeout=timeout)
        
        if success:
            test_result = result.get("result", {})
            summary = test_result.get("summary", {})
            self._log_operation("test", success=True, extra={"tests_run": summary.get("testsRan", 0), "passing": summary.get("passing", 0), "failing": summary.get("failing", 0)})
            
            return {
                "success": True,
                "outcome": summary.get("outcome", "Unknown"),
                "tests_run": summary.get("testsRan", 0),
                "passing": summary.get("passing", 0),
                "failing": summary.get("failing", 0),
                "skipped": summary.get("skipped", 0),
                "pass_rate": summary.get("passRate", "0%"),
                "coverage": summary.get("testRunCoverage"),
                "org_coverage": summary.get("orgWideCoverage"),
                "test_run_id": summary.get("testRunId"),
                "failures": test_result.get("tests", []),  # Detailed failures
                "details": test_result
            }
        else:
            self._log_operation("test", success=False, error_message=result.get("message", "Test run failed"))
            return {
                "success": False,
                "outcome": "Failed",
                "error": result.get("message", result.get("error", "Test run failed")),
                "details": result
            }
    
    async def run_specific_test_methods(
        self,
        class_name: str,
        method_names: List[str]
    ) -> Dict[str, Any]:
        """
        Run specific test methods from a class.
        
        Args:
            class_name: Test class name
            method_names: List of method names
            
        Returns:
            Dict with test results
        """
        # Format: ClassName.methodName
        tests = [f"{class_name}.{method}" for method in method_names]
        return await self.run_tests(test_classes=tests)
    
    async def get_test_results(self, test_run_id: str) -> Dict[str, Any]:
        """
        Get results of a previous test run.
        
        Args:
            test_run_id: ID from run_tests result
            
        Returns:
            Dict with test results
        """
        args = ["apex", "get", "test", "--test-run-id", test_run_id]
        success, result = await self._run_command(args)
        
        return result if success else {"error": result.get("error", "Failed to get results")}
    
    async def retrieve_source(
        self,
        metadata_types: List[str] = None,
        package_names: List[str] = None,
        output_dir: str = None
    ) -> Dict[str, Any]:
        """
        Retrieve metadata from org.
        
        Args:
            metadata_types: e.g., ["ApexClass", "ApexTrigger"]
            package_names: Package names to retrieve
            output_dir: Where to save retrieved source
            
        Returns:
            Dict with retrieve result
        """
        args = ["project", "retrieve", "start"]
        
        if metadata_types:
            args.extend(["--metadata", ",".join(metadata_types)])
        
        if package_names:
            args.extend(["--package-name", ",".join(package_names)])
        
        if output_dir:
            args.extend(["--output-dir", output_dir])
        
        success, result = await self._run_command(args, timeout=300)
        
        return {
            "success": success,
            "retrieved": success,
            "details": result
        }
    
    async def list_orgs(self) -> List[Dict[str, Any]]:
        """List all connected orgs"""
        success, result = await self._run_command(["org", "list"])
        
        if success:
            return result.get("result", {}).get("nonScratchOrgs", [])
        return []
    
    async def get_limits(self) -> Dict[str, Any]:
        """Get org limits"""
        success, result = await self._run_command(["org", "list", "limits"])
        
        if success:
            return result.get("result", {})
        return {"error": result.get("error", "Failed to get limits")}



    # ========== BLD-01: Package Generation ==========
    
    async def generate_sfdx_package(
        self,
        files: Dict[str, str],
        package_name: str = "digital-humans-package",
        api_version: str = "59.0"
    ) -> Dict[str, Any]:
        """
        Generate a complete SFDX package structure from agent-generated files.
        
        Args:
            files: Dict mapping file paths to content
            package_name: Name of the package
            api_version: Salesforce API version
            
        Returns:
            Dict with package path and manifest
        """
        import tempfile
        
        package_dir = Path(tempfile.mkdtemp(prefix=f"sfdx_{package_name}_"))
        
        try:
            # Create sfdx-project.json
            project_config = {
                "packageDirectories": [{"path": "force-app", "default": True}],
                "namespace": "",
                "sfdcLoginUrl": "https://login.salesforce.com",
                "sourceApiVersion": api_version,
                "name": package_name
            }
            
            project_file = package_dir / "sfdx-project.json"
            with open(project_file, 'w') as f:
                json.dump(project_config, f, indent=2)
            
            # Create force-app structure
            force_app = package_dir / "force-app" / "main" / "default"
            force_app.mkdir(parents=True, exist_ok=True)
            
            # Categorize components
            components_created = {
                "classes": [], "triggers": [], "lwc": [], "objects": [],
                "flows": [], "permissionsets": [], "profiles": [], "other": []
            }
            
            for file_path, file_content in files.items():
                if not file_path.startswith("force-app"):
                    file_path = f"force-app/main/default/{file_path}"
                
                full_path = package_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                
                # Categorize
                if "/classes/" in file_path:
                    components_created["classes"].append(file_path)
                elif "/triggers/" in file_path:
                    components_created["triggers"].append(file_path)
                elif "/lwc/" in file_path:
                    components_created["lwc"].append(file_path)
                elif "/objects/" in file_path:
                    components_created["objects"].append(file_path)
                elif "/flows/" in file_path:
                    components_created["flows"].append(file_path)
                elif "/permissionsets/" in file_path:
                    components_created["permissionsets"].append(file_path)
                elif "/profiles/" in file_path:
                    components_created["profiles"].append(file_path)
                else:
                    components_created["other"].append(file_path)
            
            # Generate package.xml
            manifest = self._generate_package_xml(components_created, api_version)
            manifest_dir = package_dir / "manifest"
            manifest_dir.mkdir(exist_ok=True)
            with open(manifest_dir / "package.xml", 'w') as f:
                f.write(manifest)
            
            self._log_operation("generate_package", "Package", package_name,
                              extra={"files_count": len(files), "path": str(package_dir)})
            
            return {
                "success": True,
                "package_path": str(package_dir),
                "package_name": package_name,
                "api_version": api_version,
                "components": components_created,
                "manifest_path": str(manifest_dir / "package.xml"),
                "project_file": str(project_file)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SFDX package: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_package_xml(self, components: Dict[str, List[str]], api_version: str) -> str:
        """Generate package.xml manifest"""
        type_mapping = {
            "classes": "ApexClass", "triggers": "ApexTrigger",
            "lwc": "LightningComponentBundle", "objects": "CustomObject",
            "flows": "Flow", "permissionsets": "PermissionSet", "profiles": "Profile"
        }
        
        xml = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<Package xmlns="http://soap.sforce.com/2006/04/metadata">']
        
        for comp_type, files in components.items():
            if files and comp_type in type_mapping:
                xml.append("    <types>")
                seen = set()
                for fp in files:
                    name = Path(fp).stem.replace('.cls-meta', '').replace('.trigger-meta', '')
                    if comp_type == "lwc":
                        name = Path(fp).parent.name
                    if name not in seen:
                        xml.append(f"        <members>{name}</members>")
                        seen.add(name)
                xml.append(f"        <name>{type_mapping[comp_type]}</name>")
                xml.append("    </types>")
        
        xml.append(f"    <version>{api_version}</version>")
        xml.append("</Package>")
        return "\n".join(xml)

    # ========== DPL-04: Rollback Support ==========
    
    async def create_deployment_snapshot(self, deployment_id: str, components: List[str] = None) -> Dict[str, Any]:
        """Create a snapshot of current org state before deployment."""
        import tempfile
        
        if components is None:
            components = ["ApexClass", "ApexTrigger", "LightningComponentBundle", "CustomObject", "Flow"]
        
        snapshot_dir = Path(tempfile.mkdtemp(prefix=f"snapshot_{deployment_id}_"))
        
        try:
            for comp_type in components:
                await self.retrieve_source(metadata_type=comp_type, output_dir=str(snapshot_dir / comp_type))
            
            snapshot_meta = {
                "deployment_id": deployment_id,
                "created_at": datetime.now().isoformat(),
                "components": components,
                "org": self.target_org,
                "path": str(snapshot_dir)
            }
            
            with open(snapshot_dir / "snapshot_meta.json", 'w') as f:
                json.dump(snapshot_meta, f, indent=2)
            
            self._log_operation("create_snapshot", "Deployment", deployment_id, extra={"components": components})
            
            return {"success": True, "snapshot_id": deployment_id, "snapshot_path": str(snapshot_dir)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def rollback_deployment(self, snapshot_path: str, deployment_id: str = None) -> Dict[str, Any]:
        """Rollback to a previous snapshot state."""
        snapshot_dir = Path(snapshot_path)
        
        if not snapshot_dir.exists():
            return {"success": False, "error": f"Snapshot not found: {snapshot_path}"}
        
        rollback_results = []
        
        for comp_dir in snapshot_dir.iterdir():
            if comp_dir.is_dir():
                result = await self.deploy_source(source_path=str(comp_dir), test_level="NoTestRun")
                rollback_results.append({"component": comp_dir.name, "success": result.get("success", False)})
        
        success = all(r["success"] for r in rollback_results)
        self._log_operation("rollback", "Deployment", deployment_id or "unknown", success=success)
        
        return {"success": success, "rollback_results": rollback_results}

    # ========== DPL-05: Release Notes Generation ==========
    
    def generate_release_notes(self, deployment_id: str, components: Dict[str, List[str]], project_name: str = "Digital Humans") -> Dict[str, Any]:
        """Generate release notes for a deployment."""
        notes = [f"# Release Notes - {project_name}",
                 f"\n**Deployment ID:** {deployment_id}",
                 f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 f"**Target Org:** {self.target_org or 'Default'}",
                 "\n---\n",
                 f"## Summary\nTotal components: **{sum(len(v) for v in components.values())}**\n",
                 "## Components\n"]
        
        labels = {"classes": "Apex Classes", "triggers": "Apex Triggers", "lwc": "LWC",
                  "objects": "Custom Objects", "flows": "Flows", "permissionsets": "Permission Sets"}
        
        for comp_type, items in components.items():
            if items:
                notes.append(f"### {labels.get(comp_type, comp_type.title())} ({len(items)})")
                for item in items:
                    notes.append(f"- {Path(item).stem}")
                notes.append("")
        
        notes.extend(["## Technical Details", "- API Version: 59.0", "- Generated by: Digital Humans AI Platform"])
        
        return {"success": True, "release_notes": "\n".join(notes), "format": "markdown"}

    # ========== DPL-06: Multi-Environment Support ==========
    
    async def get_environments(self) -> List[Dict[str, Any]]:
        """Get all configured Salesforce environments/orgs"""
        orgs = await self.list_orgs()
        
        environments = []
        for org in orgs:
            env_type = "production"
            instance = org.get("instanceUrl", "").lower()
            alias = org.get("alias", "").lower()
            if "sandbox" in instance or "sandbox" in alias or "uat" in alias:
                env_type = "sandbox"
            elif "scratch" in alias:
                env_type = "scratch"
            elif "dev" in alias:
                env_type = "development"
            
            environments.append({
                "alias": org.get("alias", ""),
                "username": org.get("username", ""),
                "org_id": org.get("orgId", ""),
                "instance_url": org.get("instanceUrl", ""),
                "is_default": org.get("isDefaultUsername", False),
                "status": "connected" if org.get("connectedStatus") == "Connected" else "disconnected",
                "env_type": env_type
            })
        
        return environments
    
    async def promote_to_environment(self, source_path: str, target_env: str, test_level: str = "RunLocalTests", dry_run: bool = False) -> Dict[str, Any]:
        """Promote code from one environment to another."""
        target_service = SFDXService(target_org=target_env)
        
        conn_check = await target_service.check_connection()
        if not conn_check.get("connected"):
            return {"success": False, "error": f"Cannot connect to: {target_env}"}
        
        snapshot = None
        if not dry_run:
            snapshot = await target_service.create_deployment_snapshot(
                deployment_id=f"pre_promote_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
        
        deploy_result = await target_service.deploy_source(source_path=source_path, test_level=test_level, dry_run=dry_run)
        
        self._log_operation("promote" if not dry_run else "validate_promotion", "Environment", target_env,
                          success=deploy_result.get("success", False))
        
        return {
            "success": deploy_result.get("success", False),
            "target_env": target_env,
            "dry_run": dry_run,
            "deployment_result": deploy_result,
            "snapshot_path": snapshot.get("snapshot_path") if snapshot else None,
            "rollback_available": snapshot is not None and not dry_run
        }

    
    # ═══════════════════════════════════════════════════════════════
    # BUILD V2 EXTENSIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def retrieve_metadata(self, metadata_type: str, metadata_name: str) -> Dict[str, Any]:
        """
        Retrieve specific metadata from org.
        
        Args:
            metadata_type: Type of metadata (CustomObject, ApexClass, etc.)
            metadata_name: API name of the metadata
            
        Returns:
            Dict with success status and retrieved files
        """
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal sfdx-project.json
            project_json = {
                "packageDirectories": [{"path": "force-app", "default": True}],
                "namespace": "",
                "sfdcLoginUrl": "https://login.salesforce.com",
                "sourceApiVersion": "59.0"
            }
            
            with open(os.path.join(tmpdir, "sfdx-project.json"), 'w') as f:
                json.dump(project_json, f)
            
            os.makedirs(os.path.join(tmpdir, "force-app", "main", "default"), exist_ok=True)
            
            # Run retrieve command
            cmd = [
                self.sfdx_path, "project", "retrieve", "start",
                "--metadata", f"{metadata_type}:{metadata_name}",
                "--output-dir", tmpdir
            ]
            
            if self.target_org:
                cmd.extend(["--target-org", self.target_org])
            
            start_time = time.time()
            result = await self._run_command(cmd)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if not result["success"]:
                self._log_operation(
                    "retrieve_metadata", metadata_type, metadata_name,
                    success=False, error_message=result.get("error", ""), duration_ms=duration_ms
                )
                return result
            
            # Read retrieved files
            files = {}
            force_app_path = os.path.join(tmpdir, "force-app")
            
            if os.path.exists(force_app_path):
                for root, _, filenames in os.walk(force_app_path):
                    for filename in filenames:
                        full_path = os.path.join(root, filename)
                        rel_path = os.path.relpath(full_path, tmpdir)
                        
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            files[rel_path] = f.read()
            
            self._log_operation(
                "retrieve_metadata", metadata_type, metadata_name,
                success=True, duration_ms=duration_ms,
                extra={"files_count": len(files)}
            )
            
            return {
                "success": True,
                "files": files,
                "metadata_type": metadata_type,
                "metadata_name": metadata_name
            }
    
    async def execute_anonymous(self, apex_code: str) -> Dict[str, Any]:
        """
        Execute anonymous Apex code.
        
        Args:
            apex_code: Apex code to execute
            
        Returns:
            Dict with success status and execution output
        """
        import tempfile
        import os
        
        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.apex', delete=False) as f:
            f.write(apex_code)
            temp_file = f.name
        
        try:
            cmd = [
                self.sfdx_path, "apex", "run",
                "--file", temp_file
            ]
            
            if self.target_org:
                cmd.extend(["--target-org", self.target_org])
            
            start_time = time.time()
            result = await self._run_command(cmd)
            duration_ms = int((time.time() - start_time) * 1000)
            
            self._log_operation(
                "execute_anonymous", "ApexAnonymous", "anonymous_block",
                success=result["success"],
                error_message=result.get("error", "") if not result["success"] else None,
                duration_ms=duration_ms
            )
            
            return {
                "success": result["success"],
                "output": result.get("stdout", ""),
                "logs": result.get("stderr", ""),
                "execution_time_ms": duration_ms
            }
            
        finally:
            # Cleanup temp file
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    async def deploy_with_manifest(self, manifest_path: str, source_dir: str = None) -> Dict[str, Any]:
        """
        Deploy using a package.xml manifest.
        
        Args:
            manifest_path: Path to package.xml
            source_dir: Source directory (optional)
            
        Returns:
            Dict with deployment result
        """
        cmd = [
            self.sfdx_path, "project", "deploy", "start",
            "--manifest", manifest_path,
            "--wait", "30"
        ]
        
        if source_dir:
            cmd.extend(["--source-dir", source_dir])
        
        if self.target_org:
            cmd.extend(["--target-org", self.target_org])
        
        start_time = time.time()
        result = await self._run_command(cmd)
        duration_ms = int((time.time() - start_time) * 1000)
        
        self._log_operation(
            "deploy_manifest", "Package", manifest_path,
            success=result["success"],
            error_message=result.get("error", "") if not result["success"] else None,
            duration_ms=duration_ms
        )
        
        return {
            "success": result["success"],
            "output": result.get("stdout", ""),
            "error": result.get("error", ""),
            "duration_ms": duration_ms
        }
    


# Singleton instance for default org
_default_service: Optional[SFDXService] = None


def get_sfdx_service(target_org: str = None) -> SFDXService:
    """
    Get SFDX service instance.
    
    Args:
        target_org: Specific org, or None for default
        
    Returns:
        SFDXService instance
    """
    global _default_service
    
    if target_org:
        return SFDXService(target_org)
    
    if _default_service is None:
        _default_service = SFDXService()
    
    return _default_service
