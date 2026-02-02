"""
Git Service - ORCH-03c
Handles Git operations: clone, commit, push, and PR management.

Supports:
- GitHub (via API)
- GitLab (via API)
- Generic Git (CLI only)

Author: Digital Humans Team
Created: 2025-12-08
"""
import asyncio
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
from app.services.audit_service import audit_service, ActorType, ActionCategory
import httpx

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Git operation failed"""
    pass


class GitService:
    """
    Service for Git operations and PR management.
    
    Supports GitHub and GitLab for PR operations.
    """
    
    def __init__(
        self,
        repo_url: str,
        branch: str = "main",
        token: str = None,
        work_dir: str = None,
        project_id: int = None,
        execution_id: int = None,
        task_id: str = None
    ):
        """
        Initialize Git service.
        
        Args:
            repo_url: Repository URL (HTTPS preferred)
            branch: Default branch name
            token: Auth token for GitHub/GitLab API and git operations
            work_dir: Working directory (created if None)
        """
        self.repo_url = repo_url
        self.branch = branch
        self.token = token
        self.work_dir = work_dir or tempfile.mkdtemp(prefix="git_work_")
        self.repo_path = None
        self.project_id = project_id
        self.execution_id = execution_id
        self.task_id = task_id
        
        # Detect provider
        self.provider = self._detect_provider()
        self.api_base = self._get_api_base()
        self.repo_info = self._parse_repo_url()
        
    def _detect_provider(self) -> str:
        """Detect Git provider from URL"""
        if "github.com" in self.repo_url:
            return "github"
        elif "gitlab.com" in self.repo_url or "gitlab" in self.repo_url:
            return "gitlab"
        else:
            return "generic"
    
    def _get_api_base(self) -> str:
        """Get API base URL for provider"""
        if self.provider == "github":
            return "https://api.github.com"
        elif self.provider == "gitlab":
            # Could be self-hosted
            parsed = urlparse(self.repo_url)
            return f"{parsed.scheme}://{parsed.netloc}/api/v4"
        return ""
    
    def _parse_repo_url(self) -> Dict[str, str]:
        """Parse repo URL to extract owner/repo"""
        parsed = urlparse(self.repo_url)
        path_parts = parsed.path.strip("/").replace(".git", "").split("/")
        
        if len(path_parts) >= 2:
            return {
                "owner": path_parts[0],
                "repo": path_parts[1],
                "full_name": f"{path_parts[0]}/{path_parts[1]}"
            }
        return {"owner": "", "repo": "", "full_name": ""}
    
    
    def _log_operation(self, operation: str, commit_sha: str = None, branch: str = None, pr_url: str = None, success: bool = True, error_message: str = None, duration_ms: int = None):
        """Log Git operation to audit trail"""
        if self.execution_id:  # Only log if context is set
            audit_service.log_git_operation(
                operation=operation,
                execution_id=self.execution_id,
                project_id=self.project_id,
                task_id=self.task_id,
                commit_sha=commit_sha,
                branch=branch,
                pr_url=pr_url,
                success=success,
                error_message=error_message,
                duration_ms=duration_ms
            )
    
    def _get_auth_url(self) -> str:
        """Get URL with embedded auth token"""
        if not self.token:
            return self.repo_url
        
        parsed = urlparse(self.repo_url)
        if self.provider == "github":
            return f"https://{self.token}@github.com/{self.repo_info['full_name']}.git"
        elif self.provider == "gitlab":
            return f"https://oauth2:{self.token}@{parsed.netloc}/{self.repo_info['full_name']}.git"
        return self.repo_url
    
    async def _run_git(
        self, 
        args: List[str], 
        cwd: str = None,
        timeout: int = 120
    ) -> Tuple[bool, str, str]:
        """
        Run git command.
        
        Returns:
            Tuple of (success, stdout, stderr)
        """
        cmd = ["git"] + args
        work_cwd = cwd or self.repo_path or self.work_dir
        
        logger.info(f"[Git] Running: git {' '.join(args)} in {work_cwd}")
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_cwd
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')
            
            success = process.returncode == 0
            
            if not success:
                logger.warning(f"[Git] Command failed: {stderr_str}")
            
            return success, stdout_str, stderr_str
            
        except asyncio.TimeoutError:
            logger.error(f"[Git] Command timed out")
            return False, "", "Timeout"
        except Exception as e:
            logger.error(f"[Git] Exception: {str(e)}")
            return False, "", str(e)
    
    async def clone(self, shallow: bool = True) -> Dict[str, Any]:
        """
        Clone repository.
        
        Args:
            shallow: If True, clone with depth=1
            
        Returns:
            Dict with clone result
        """
        repo_name = self.repo_info.get("repo", "repo")
        self.repo_path = os.path.join(self.work_dir, repo_name)
        
        # Remove if exists
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)
        
        args = ["clone"]
        if shallow:
            args.extend(["--depth", "1"])
        args.extend(["-b", self.branch, self._get_auth_url(), self.repo_path])
        
        success, stdout, stderr = await self._run_git(args, cwd=self.work_dir)
        
        if success:
            # Configure user
            await self._run_git(["config", "user.email", "digital-humans@agent.ai"])
            await self._run_git(["config", "user.name", "Digital Humans Agent"])
            
            return {
                "success": True,
                "path": self.repo_path,
                "branch": self.branch
            }
        else:
            return {
                "success": False,
                "error": stderr
            }
    
    async def checkout_branch(self, branch_name: str, create: bool = True) -> Dict[str, Any]:
        """
        Checkout or create branch.
        
        Args:
            branch_name: Branch name
            create: Create if doesn't exist
            
        Returns:
            Dict with result
        """
        if create:
            # Try to create, fallback to checkout if exists
            success, _, stderr = await self._run_git(["checkout", "-b", branch_name])
            if not success and "already exists" in stderr:
                success, _, _ = await self._run_git(["checkout", branch_name])
        else:
            success, _, _ = await self._run_git(["checkout", branch_name])
        
        return {"success": success, "branch": branch_name}
    
    async def add_files(self, files: List[str] = None) -> Dict[str, Any]:
        """
        Stage files for commit.
        
        Args:
            files: List of file paths (relative to repo), or None for all
            
        Returns:
            Dict with result
        """
        if files:
            args = ["add"] + files
        else:
            args = ["add", "-A"]
        
        success, _, stderr = await self._run_git(args)
        return {"success": success, "error": stderr if not success else None}
    
    async def commit(
        self, 
        message: str, 
        task_id: str = None
    ) -> Dict[str, Any]:
        """
        Create commit.
        
        Args:
            message: Commit message
            task_id: Optional WBS task ID to include in message
            
        Returns:
            Dict with commit SHA
        """
        if task_id:
            message = f"[{task_id}] {message}"
        
        success, stdout, stderr = await self._run_git(["commit", "-m", message])
        
        if success:
            # Get commit SHA
            _, sha, _ = await self._run_git(["rev-parse", "HEAD"])
            self._log_operation("commit", commit_sha=sha.strip(), branch=self.branch)
            return {
                "success": True,
                "sha": sha.strip(),
                "message": message
            }
        else:
            # Check if nothing to commit
            if "nothing to commit" in stderr:
                return {
                    "success": True,
                    "sha": None,
                    "message": "Nothing to commit"
                }
            self._log_operation("commit", success=False, error_message=stderr)
            return {
                "success": False,
                "error": stderr
            }
    
    async def push(self, branch: str = None, force: bool = False) -> Dict[str, Any]:
        """
        Push to remote.
        
        Args:
            branch: Branch to push (default: current)
            force: Force push
            
        Returns:
            Dict with result
        """
        args = ["push", "origin"]
        if branch:
            args.append(branch)
        if force:
            args.append("--force")
        
        success, _, stderr = await self._run_git(args)
        if success:
            self._log_operation("push", branch=branch or self.branch)
        else:
            self._log_operation("push", success=False, error_message=stderr)
        return {"success": success, "error": stderr if not success else None}
    
    async def create_pr(
        self,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = None
    ) -> Dict[str, Any]:
        """
        Create Pull Request via API.
        
        Args:
            title: PR title
            body: PR description
            head_branch: Source branch
            base_branch: Target branch (default: repo default)
            
        Returns:
            Dict with PR URL and number
        """
        base_branch = base_branch or self.branch
        
        if self.provider == "github":
            return await self._create_github_pr(title, body, head_branch, base_branch)
        elif self.provider == "gitlab":
            return await self._create_gitlab_mr(title, body, head_branch, base_branch)
        else:
            return {
                "success": False,
                "error": f"PR creation not supported for provider: {self.provider}"
            }
    
    async def _create_github_pr(
        self, 
        title: str, 
        body: str, 
        head: str, 
        base: str
    ) -> Dict[str, Any]:
        """Create GitHub Pull Request"""
        url = f"{self.api_base}/repos/{self.repo_info['full_name']}/pulls"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json"
        }
        
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                
                if response.status_code == 201:
                    result = response.json()
                    self._log_operation("pr_create", pr_url=result["html_url"], branch=head)
                    return {
                        "success": True,
                        "pr_number": result["number"],
                        "pr_url": result["html_url"],
                        "state": result["state"]
                    }
                else:
                    self._log_operation("pr_create", success=False, error_message=response.text)
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }
            except Exception as e:
                self._log_operation("pr_create", success=False, error_message=str(e))
                return {"success": False, "error": str(e)}
    
    async def _create_gitlab_mr(
        self, 
        title: str, 
        body: str, 
        source: str, 
        target: str
    ) -> Dict[str, Any]:
        """Create GitLab Merge Request"""
        # URL encode project path
        project_path = self.repo_info['full_name'].replace("/", "%2F")
        url = f"{self.api_base}/projects/{project_path}/merge_requests"
        
        headers = {
            "Private-Token": self.token
        }
        
        data = {
            "title": title,
            "description": body,
            "source_branch": source,
            "target_branch": target
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                
                if response.status_code == 201:
                    result = response.json()
                    return {
                        "success": True,
                        "mr_iid": result["iid"],
                        "mr_url": result["web_url"],
                        "state": result["state"]
                    }
                else:
                    return {
                        "success": False,
                        "error": response.text,
                        "status_code": response.status_code
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}
    
    async def merge_pr(self, pr_number: int) -> Dict[str, Any]:
        """
        Merge Pull Request via API.
        
        Args:
            pr_number: PR number to merge
            
        Returns:
            Dict with result
        """
        if self.provider == "github":
            url = f"{self.api_base}/repos/{self.repo_info['full_name']}/pulls/{pr_number}/merge"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.put(url, headers=headers)
                
                if response.status_code == 200:
                    return {"success": True, "merged": True}
                else:
                    return {"success": False, "error": response.text}
        
        elif self.provider == "gitlab":
            project_path = self.repo_info['full_name'].replace("/", "%2F")
            url = f"{self.api_base}/projects/{project_path}/merge_requests/{pr_number}/merge"
            headers = {"Private-Token": self.token}
            
            async with httpx.AsyncClient() as client:
                response = await client.put(url, headers=headers)
                
                if response.status_code == 200:
                    return {"success": True, "merged": True}
                else:
                    return {"success": False, "error": response.text}
        
        return {"success": False, "error": "Provider not supported"}
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current repo status"""
        success, stdout, _ = await self._run_git(["status", "--porcelain"])
        
        if success:
            changes = [line for line in stdout.strip().split("\n") if line]
            return {
                "clean": len(changes) == 0,
                "changes": len(changes),
                "files": changes[:20]  # Limit to 20
            }
        return {"clean": False, "error": "Failed to get status"}
    
    async def get_current_branch(self) -> str:
        """Get current branch name"""
        success, stdout, _ = await self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return stdout.strip() if success else ""
    
    def cleanup(self):
        """Remove working directory"""
        if self.work_dir and os.path.exists(self.work_dir):
            shutil.rmtree(self.work_dir, ignore_errors=True)
            logger.info(f"[Git] Cleaned up {self.work_dir}")


    
    # ═══════════════════════════════════════════════════════════════
    # BUILD V2 EXTENSIONS
    # ═══════════════════════════════════════════════════════════════
    
    async def create_branch(self, branch_name: str, from_branch: str = None) -> Dict[str, Any]:
        """
        Create a new branch.
        
        Args:
            branch_name: Name of the new branch
            from_branch: Base branch (defaults to self.branch)
            
        Returns:
            Dict with success status and branch info
        """
        base = from_branch or self.branch
        
        # Fetch latest
        await self._run_git(["fetch", "origin", base])
        
        # Create and checkout new branch
        success, stdout, stderr = await self._run_git([
            "checkout", "-b", branch_name, f"origin/{base}"
        ])
        
        if success:
            logger.info(f"[Git] Created branch: {branch_name} from {base}")
            return {"success": True, "branch_name": branch_name, "base": base}
        else:
            # Branch might already exist, try to checkout
            success2, _, _ = await self._run_git(["checkout", branch_name])
            if success2:
                return {"success": True, "branch_name": branch_name, "existed": True}
            return {"success": False, "error": stderr}
    
    async def revert_merge(self, merge_sha: str) -> Dict[str, Any]:
        """
        Revert a merge commit.
        
        Args:
            merge_sha: SHA of the merge commit to revert
            
        Returns:
            Dict with success status
        """
        # Revert the merge commit
        success, stdout, stderr = await self._run_git([
            "revert", "-m", "1", merge_sha, "--no-edit"
        ])
        
        if not success:
            logger.error(f"[Git] Failed to revert merge {merge_sha}: {stderr}")
            return {"success": False, "error": stderr}
        
        # Push the revert
        push_result = await self.push()
        
        if push_result.get("success"):
            logger.info(f"[Git] Reverted merge {merge_sha[:8]}")
            return {"success": True, "reverted_sha": merge_sha}
        else:
            return {"success": False, "error": f"Revert succeeded but push failed: {push_result.get('error')}"}
    
    async def tag(self, tag_name: str, message: str) -> Dict[str, Any]:
        """
        Create and push a Git tag.
        
        Args:
            tag_name: Name of the tag
            message: Tag message
            
        Returns:
            Dict with success status
        """
        # Create annotated tag
        success, stdout, stderr = await self._run_git([
            "tag", "-a", tag_name, "-m", message
        ])
        
        if not success:
            # Tag might already exist
            if "already exists" in stderr:
                logger.warning(f"[Git] Tag {tag_name} already exists")
                return {"success": True, "tag_name": tag_name, "existed": True}
            return {"success": False, "error": stderr}
        
        # Push the tag
        success, stdout, stderr = await self._run_git([
            "push", "origin", tag_name
        ])
        
        if success:
            logger.info(f"[Git] Created and pushed tag: {tag_name}")
            return {"success": True, "tag_name": tag_name}
        else:
            return {"success": False, "error": f"Tag created but push failed: {stderr}"}
    
    async def commit_files(self, files: Dict[str, str], message: str) -> Dict[str, Any]:
        """
        Write files and commit them.
        
        Args:
            files: Dict of {path: content}
            message: Commit message
            
        Returns:
            Dict with success status and commit SHA
        """
        if not self.repo_path:
            return {"success": False, "error": "Repository not cloned"}
        
        # Write files
        written_files = []
        for path, content in files.items():
            full_path = os.path.join(self.repo_path, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            written_files.append(path)
        
        # Add files
        for path in written_files:
            await self._run_git(["add", path])
        
        # Commit
        success, stdout, stderr = await self._run_git([
            "commit", "-m", message
        ])
        
        if not success:
            if "nothing to commit" in stderr or "nothing to commit" in stdout:
                return {"success": True, "message": "Nothing to commit", "files": written_files}
            return {"success": False, "error": stderr}
        
        # Get commit SHA
        sha_success, sha, _ = await self._run_git(["rev-parse", "HEAD"])
        commit_sha = sha.strip() if sha_success else ""
        
        # Push
        push_result = await self.push()
        
        if push_result.get("success"):
            logger.info(f"[Git] Committed {len(written_files)} files: {commit_sha[:8]}")
            return {"success": True, "commit_sha": commit_sha, "files": written_files}
        else:
            return {"success": False, "error": f"Commit succeeded but push failed: {push_result.get('error')}"}
    
    async def get_pr_files(self, pr_number: int) -> Dict[str, Any]:
        """
        Get list of files in a PR.
        
        Args:
            pr_number: PR number
            
        Returns:
            Dict with files list
        """
        if self.provider != "github":
            return {"success": False, "error": "PR files only supported for GitHub"}
        
        url = f"{self.api_base}/repos/{self.repo_info['owner']}/{self.repo_info['repo']}/pulls/{pr_number}/files"
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}" if self.token else ""
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                files_data = response.json()
                files = [f["filename"] for f in files_data]
                return {"success": True, "files": files, "count": len(files)}
            else:
                return {"success": False, "error": f"GitHub API error: {response.status_code}"}

async def commit_and_pr(
    repo_url: str,
    token: str,
    files: Dict[str, str],
    branch_name: str,
    commit_message: str,
    pr_title: str,
    pr_body: str,
    task_id: str = None,
    base_branch: str = "main"
) -> Dict[str, Any]:
    """
    High-level function: Clone, commit files, push, create PR.
    
    Args:
        repo_url: Repository URL
        token: Auth token
        files: Dict of {relative_path: content}
        branch_name: New branch name
        commit_message: Commit message
        pr_title: PR title
        pr_body: PR description
        task_id: Optional WBS task ID
        base_branch: Target branch for PR
        
    Returns:
        Dict with commit SHA and PR URL
    """
    git = GitService(repo_url, branch=base_branch, token=token)
    
    try:
        # Clone
        result = await git.clone()
        if not result["success"]:
            return {"success": False, "error": f"Clone failed: {result.get('error')}"}
        
        # Create branch
        result = await git.checkout_branch(branch_name)
        if not result["success"]:
            return {"success": False, "error": "Branch creation failed"}
        
        # Write files
        for path, content in files.items():
            full_path = os.path.join(git.repo_path, path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
        
        # Add and commit
        await git.add_files()
        commit_result = await git.commit(commit_message, task_id=task_id)
        if not commit_result["success"]:
            return {"success": False, "error": f"Commit failed: {commit_result.get('error')}"}
        
        # Push
        push_result = await git.push(branch_name)
        if not push_result["success"]:
            return {"success": False, "error": f"Push failed: {push_result.get('error')}"}
        
        # Create PR
        pr_result = await git.create_pr(
            title=pr_title,
            body=pr_body,
            head_branch=branch_name,
            base_branch=base_branch
        )
        
        return {
            "success": True,
            "commit_sha": commit_result.get("sha"),
            "pr_url": pr_result.get("pr_url") or pr_result.get("mr_url"),
            "pr_number": pr_result.get("pr_number") or pr_result.get("mr_iid"),
            "branch": branch_name
        }
        
    finally:
        git.cleanup()
