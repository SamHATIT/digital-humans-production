"""
Environment Service - Manage SFDX environments and credentials.
Based on SPEC Section 7.2
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any, List
import subprocess
import json
import tempfile
import os

from app.utils.encryption import encrypt_credential, decrypt_credential
from app.models.project_credential import ProjectCredential, CredentialType


class EnvironmentService:
    """
    Service pour gérer les environnements SFDX et les credentials.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    # ========================================
    # CREDENTIAL MANAGEMENT
    # ========================================
    
    def store_credential(
        self,
        project_id: int,
        credential_type: CredentialType,
        value: str,
        label: str = None,
        expires_at: datetime = None
    ) -> ProjectCredential:
        """
        Store an encrypted credential for a project.
        Replaces any existing credential of the same type.
        """
        # Delete existing credential of same type
        self.db.query(ProjectCredential).filter(
            ProjectCredential.project_id == project_id,
            ProjectCredential.credential_type == credential_type
        ).delete()
        
        # Create new credential
        credential = ProjectCredential(
            project_id=project_id,
            credential_type=credential_type,
            encrypted_value=encrypt_credential(value),
            label=label,
            expires_at=expires_at
        )
        
        self.db.add(credential)
        self.db.commit()
        self.db.refresh(credential)
        
        return credential
    
    def get_credential(
        self,
        project_id: int,
        credential_type: CredentialType
    ) -> Optional[str]:
        """
        Get and decrypt a credential for a project.
        Returns the decrypted value or None if not found.
        """
        credential = self.db.query(ProjectCredential).filter(
            ProjectCredential.project_id == project_id,
            ProjectCredential.credential_type == credential_type
        ).first()
        
        if credential:
            return decrypt_credential(credential.encrypted_value)
        return None
    
    def delete_credential(
        self,
        project_id: int,
        credential_type: CredentialType
    ) -> bool:
        """Delete a credential. Returns True if deleted."""
        deleted = self.db.query(ProjectCredential).filter(
            ProjectCredential.project_id == project_id,
            ProjectCredential.credential_type == credential_type
        ).delete()
        
        self.db.commit()
        return deleted > 0
    
    def get_all_credentials(self, project_id: int) -> List[Dict[str, Any]]:
        """
        Get all credentials for a project (metadata only, not decrypted values).
        """
        credentials = self.db.query(ProjectCredential).filter(
            ProjectCredential.project_id == project_id
        ).all()
        
        return [
            {
                "id": c.id,
                "type": c.credential_type.value,
                "label": c.label,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "has_value": bool(c.encrypted_value)
            }
            for c in credentials
        ]
    
    def rotate_credential(
        self,
        project_id: int,
        credential_type: CredentialType,
        new_value: str
    ) -> ProjectCredential:
        """
        Rotate a credential (update with new value).
        """
        return self.store_credential(project_id, credential_type, new_value)
    
    # ========================================
    # SALESFORCE CONNECTION
    # ========================================
    
    def test_salesforce_connection(
        self,
        instance_url: str,
        access_token: str,
        username: str = None
    ) -> Dict[str, Any]:
        """
        Test Salesforce connection using REST API.
        """
        if not instance_url or not access_token:
            return {"success": False, "error": "Missing instance URL or access token"}
        
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
            
            response = requests.get(identity_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                user_info = response.json()
                return {
                    "success": True,
                    "org_id": user_info.get("organization_id"),
                    "user_id": user_info.get("user_id"),
                    "username": user_info.get("preferred_username"),
                    "display_name": user_info.get("name"),
                    "instance_url": instance_url
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "Invalid or expired access token"
                }
            else:
                return {
                    "success": False,
                    "error": f"Salesforce API error: {response.status_code}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_sfdx_jwt_connection(
        self,
        instance_url: str,
        username: str,
        client_id: str,
        private_key: str,
        alias: str = "temp_test"
    ) -> Dict[str, Any]:
        """
        Test SFDX connection using JWT authentication.
        """
        if not all([instance_url, username, client_id, private_key]):
            return {"success": False, "error": "Missing required credentials"}
        
        # Write private key to temp file
        key_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
                f.write(private_key)
                key_file = f.name
            
            # Authenticate
            auth_cmd = [
                "sf", "org", "login", "jwt",
                "--client-id", client_id,
                "--jwt-key-file", key_file,
                "--username", username,
                "--instance-url", instance_url,
                "--alias", alias,
                "--json"
            ]
            
            result = subprocess.run(
                auth_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                try:
                    error_data = json.loads(result.stdout)
                    error_msg = error_data.get("message", result.stderr)
                except:
                    error_msg = result.stderr or "Authentication failed"
                return {"success": False, "error": error_msg}
            
            # Get org info
            info_cmd = ["sf", "org", "display", "--target-org", alias, "--json"]
            info_result = subprocess.run(
                info_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if info_result.returncode == 0:
                info_data = json.loads(info_result.stdout)
                org_result = info_data.get("result", {})
                return {
                    "success": True,
                    "org_id": org_result.get("id"),
                    "username": org_result.get("username"),
                    "instance_url": org_result.get("instanceUrl")
                }
            
            return {"success": True, "message": "Authentication successful"}
            
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Connection timeout"}
        except FileNotFoundError:
            return {"success": False, "error": "SFDX CLI not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if key_file and os.path.exists(key_file):
                os.unlink(key_file)
    
    def test_sfdx_web_connection(self, alias: str) -> Dict[str, Any]:
        """
        Test existing SFDX web login connection.
        """
        try:
            info_cmd = ["sf", "org", "display", "--target-org", alias, "--json"]
            result = subprocess.run(
                info_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Not authenticated. Please run: sf org login web -a {alias}"
                }
            
            info_data = json.loads(result.stdout)
            org_result = info_data.get("result", {})
            
            return {
                "success": True,
                "org_id": org_result.get("id"),
                "username": org_result.get("username"),
                "instance_url": org_result.get("instanceUrl")
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========================================
    # GIT CONNECTION
    # ========================================
    
    def test_git_connection(
        self,
        repo_url: str,
        token: str,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Test Git repository connection.
        """
        if not repo_url or not token:
            return {"success": False, "error": "Missing repository URL or token"}
        
        try:
            # Build authenticated URL
            if 'github.com' in repo_url:
                auth_url = repo_url.replace('https://', f'https://{token}@')
            elif 'gitlab.com' in repo_url:
                auth_url = repo_url.replace('https://', f'https://oauth2:{token}@')
            else:
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
                    if line and '\t' in line:
                        ref = line.split('\t')[1]
                        if ref.startswith('refs/heads/'):
                            branches.append(ref.replace('refs/heads/', ''))
                
                return {
                    "success": True,
                    "repo_url": repo_url,
                    "branches": branches[:10],
                    "branch_exists": branch in branches,
                    "target_branch": branch
                }
            else:
                error_msg = result.stderr[:200] if result.stderr else "Connection failed"
                if 'Authentication failed' in error_msg or '401' in error_msg:
                    return {"success": False, "error": "Authentication failed - check token"}
                elif 'not found' in error_msg.lower() or '404' in error_msg:
                    return {"success": False, "error": "Repository not found - check URL"}
                else:
                    return {"success": False, "error": error_msg}
                    
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Connection timeout"}
        except FileNotFoundError:
            return {"success": False, "error": "Git not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Factory function
def get_environment_service(db: Session) -> EnvironmentService:
    """Get an EnvironmentService instance."""
    return EnvironmentService(db)
