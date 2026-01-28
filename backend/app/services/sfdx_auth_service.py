"""
SFDX Authentication Service
Uses SFDX CLI for Salesforce authentication
"""
import subprocess
import json
import logging

logger = logging.getLogger(__name__)


class SFDXAuthService:
    """Service to get Salesforce access tokens via SFDX CLI"""
    
    @staticmethod
    def get_access_token(alias_or_username: str) -> dict:
        """
        Get access token for a Salesforce org using SFDX
        
        Args:
            alias_or_username: SFDX alias or Salesforce username
            
        Returns:
            dict with access_token, instance_url, username, org_id
        """
        try:
            result = subprocess.run(
                ["sfdx", "force:org:display", "--target-org", alias_or_username, "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"SFDX error: {result.stderr}")
                return {"error": f"SFDX failed: {result.stderr}"}
            
            data = json.loads(result.stdout)
            
            if data.get("status") == 0:
                org_info = data.get("result", {})
                return {
                    "success": True,
                    "access_token": org_info.get("accessToken"),
                    "instance_url": org_info.get("instanceUrl"),
                    "username": org_info.get("username"),
                    "org_id": org_info.get("id"),
                }
            else:
                return {"error": data.get("message", "Unknown SFDX error")}
                
        except subprocess.TimeoutExpired:
            return {"error": "SFDX command timed out"}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON from SFDX: {e}"}
        except Exception as e:
            logger.exception("SFDX auth error")
            return {"error": str(e)}
    
    @staticmethod
    def list_authenticated_orgs() -> list:
        """List all authenticated Salesforce orgs"""
        try:
            result = subprocess.run(
                ["sfdx", "auth:list", "--json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get("result", [])
            return []
        except Exception as e:
            logger.exception("Failed to list SFDX orgs")
            return []
    
    @staticmethod
    def test_connection(alias_or_username: str) -> dict:
        """Test if we can connect to a Salesforce org"""
        auth = SFDXAuthService.get_access_token(alias_or_username)
        
        if auth.get("error"):
            return {"success": False, "message": auth["error"]}
        
        if auth.get("access_token"):
            return {
                "success": True,
                "message": f"Connected to {auth.get('username')}",
                "org_id": auth.get("org_id"),
                "instance_url": auth.get("instance_url")
            }
        
        return {"success": False, "message": "Could not get access token"}


# Singleton instance
sfdx_auth = SFDXAuthService()
