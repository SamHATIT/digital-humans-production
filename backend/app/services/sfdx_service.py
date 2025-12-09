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

logger = logging.getLogger(__name__)


class SFDXError(Exception):
    """SFDX operation failed"""
    pass


class SFDXService:
    """
    Service for interacting with Salesforce via SFDX CLI.
    
    All operations are async and return structured results.
    """
    
    def __init__(self, target_org: str = None):
        """
        Initialize SFDX service.
        
        Args:
            target_org: Org alias or username. If None, uses default org.
        """
        self.target_org = target_org
        self.sfdx_path = self._find_sfdx()
        
    def _find_sfdx(self) -> str:
        """Find SFDX CLI path"""
        for path in ["/usr/bin/sfdx", "/usr/local/bin/sfdx", "/usr/local/bin/sf", "sfdx"]:
            if os.path.exists(path) or path == "sfdx":
                return path
        raise SFDXError("SFDX CLI not found")
    
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
