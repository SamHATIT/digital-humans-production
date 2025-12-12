"""
Connection Validator Service
Tests real connections to Salesforce and Git repositories.
"""
import subprocess
import os
import tempfile
import json
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ConnectionResult:
    """Result of a connection test."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ConnectionValidatorService:
    """Service for validating external connections."""
    
    def test_salesforce_connection(
        self,
        instance_url: str,
        access_token: str,
        username: str = None
    ) -> ConnectionResult:
        """
        Test Salesforce connection using REST API.
        
        Args:
            instance_url: Salesforce instance URL (e.g., https://mycompany.my.salesforce.com)
            access_token: OAuth access token
            username: Optional username for logging
            
        Returns:
            ConnectionResult with success status and org details
        """
        if not instance_url or not access_token:
            return ConnectionResult(
                success=False,
                message="Missing instance URL or access token"
            )
        
        try:
            import requests
            
            # Normalize URL
            if not instance_url.startswith('https://'):
                instance_url = f'https://{instance_url}'
            instance_url = instance_url.rstrip('/')
            
            # Call Salesforce identity endpoint
            identity_url = f"{instance_url}/services/oauth2/userinfo"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(identity_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_info = response.json()
                return ConnectionResult(
                    success=True,
                    message="Salesforce connection successful",
                    details={
                        "org_id": user_info.get("organization_id"),
                        "user_id": user_info.get("user_id"),
                        "username": user_info.get("preferred_username"),
                        "display_name": user_info.get("name"),
                        "instance_url": instance_url
                    }
                )
            elif response.status_code == 401:
                return ConnectionResult(
                    success=False,
                    message="Invalid or expired access token",
                    error="INVALID_TOKEN"
                )
            else:
                return ConnectionResult(
                    success=False,
                    message=f"Salesforce API error: {response.status_code}",
                    error=response.text[:200]
                )
                
        except requests.exceptions.Timeout:
            return ConnectionResult(
                success=False,
                message="Connection timeout - Salesforce not reachable",
                error="TIMEOUT"
            )
        except requests.exceptions.ConnectionError as e:
            return ConnectionResult(
                success=False,
                message="Connection failed - check instance URL",
                error=str(e)[:200]
            )
        except Exception as e:
            return ConnectionResult(
                success=False,
                message=f"Unexpected error: {str(e)}",
                error=str(e)
            )
    
    def test_sfdx_connection(
        self,
        instance_url: str,
        access_token: str
    ) -> ConnectionResult:
        """
        Test Salesforce connection using SFDX CLI.
        
        Args:
            instance_url: Salesforce instance URL
            access_token: OAuth access token
            
        Returns:
            ConnectionResult with success status
        """
        if not instance_url or not access_token:
            return ConnectionResult(
                success=False,
                message="Missing instance URL or access token"
            )
        
        try:
            # Create temporary SFDX auth file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                auth_data = {
                    "instanceUrl": instance_url,
                    "accessToken": access_token
                }
                json.dump(auth_data, f)
                auth_file = f.name
            
            # Try SFDX auth
            result = subprocess.run(
                ['sf', 'org', 'login', 'access-token', 
                 '--instance-url', instance_url,
                 '--no-prompt'],
                input=access_token,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Clean up
            os.unlink(auth_file)
            
            if result.returncode == 0:
                return ConnectionResult(
                    success=True,
                    message="SFDX connection successful",
                    details={"output": result.stdout[:500]}
                )
            else:
                return ConnectionResult(
                    success=False,
                    message="SFDX authentication failed",
                    error=result.stderr[:500]
                )
                
        except subprocess.TimeoutExpired:
            return ConnectionResult(
                success=False,
                message="SFDX timeout",
                error="TIMEOUT"
            )
        except FileNotFoundError:
            return ConnectionResult(
                success=False,
                message="SFDX CLI not installed",
                error="SFDX_NOT_FOUND"
            )
        except Exception as e:
            return ConnectionResult(
                success=False,
                message=f"SFDX error: {str(e)}",
                error=str(e)
            )
    
    def test_git_connection(
        self,
        repo_url: str,
        token: str,
        branch: str = "main"
    ) -> ConnectionResult:
        """
        Test Git repository connection.
        
        Args:
            repo_url: Git repository URL (HTTPS)
            token: Personal access token
            branch: Branch to check
            
        Returns:
            ConnectionResult with success status
        """
        if not repo_url or not token:
            return ConnectionResult(
                success=False,
                message="Missing repository URL or token"
            )
        
        try:
            # Build authenticated URL
            if 'github.com' in repo_url:
                # GitHub format: https://TOKEN@github.com/org/repo.git
                auth_url = repo_url.replace('https://', f'https://{token}@')
            elif 'gitlab.com' in repo_url:
                # GitLab format: https://oauth2:TOKEN@gitlab.com/org/repo.git
                auth_url = repo_url.replace('https://', f'https://oauth2:{token}@')
            else:
                # Generic format
                auth_url = repo_url.replace('https://', f'https://{token}@')
            
            # Add .git if missing
            if not auth_url.endswith('.git'):
                auth_url += '.git'
            
            # Use git ls-remote to test connection
            result = subprocess.run(
                ['git', 'ls-remote', '--heads', auth_url],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
            )
            
            if result.returncode == 0:
                # Parse branches
                branches = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        ref = line.split('\t')[1] if '\t' in line else ''
                        if ref.startswith('refs/heads/'):
                            branches.append(ref.replace('refs/heads/', ''))
                
                branch_exists = branch in branches
                
                return ConnectionResult(
                    success=True,
                    message="Git connection successful",
                    details={
                        "repo_url": repo_url,
                        "branches": branches[:10],  # Limit to 10
                        "branch_exists": branch_exists,
                        "target_branch": branch
                    }
                )
            else:
                error_msg = result.stderr[:200]
                if 'Authentication failed' in error_msg or '401' in error_msg:
                    return ConnectionResult(
                        success=False,
                        message="Git authentication failed - check token",
                        error="AUTH_FAILED"
                    )
                elif 'not found' in error_msg.lower() or '404' in error_msg:
                    return ConnectionResult(
                        success=False,
                        message="Repository not found - check URL",
                        error="NOT_FOUND"
                    )
                else:
                    return ConnectionResult(
                        success=False,
                        message="Git connection failed",
                        error=error_msg
                    )
                    
        except subprocess.TimeoutExpired:
            return ConnectionResult(
                success=False,
                message="Git connection timeout",
                error="TIMEOUT"
            )
        except FileNotFoundError:
            return ConnectionResult(
                success=False,
                message="Git not installed",
                error="GIT_NOT_FOUND"
            )
        except Exception as e:
            return ConnectionResult(
                success=False,
                message=f"Git error: {str(e)}",
                error=str(e)
            )


# Singleton
_validator_instance = None

def get_connection_validator() -> ConnectionValidatorService:
    """Get the connection validator singleton."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ConnectionValidatorService()
    return _validator_instance


# Test
if __name__ == "__main__":
    validator = get_connection_validator()
    
    # Test Git (with fake token - will fail but shows the flow)
    print("Testing Git connection (fake token)...")
    result = validator.test_git_connection(
        "https://github.com/SamHATIT/digital-humans-production",
        "fake-token",
        "main"
    )
    print(f"  Success: {result.success}")
    print(f"  Message: {result.message}")
    if result.error:
        print(f"  Error: {result.error}")
