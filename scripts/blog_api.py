#!/usr/bin/env python3
"""
Simple HTTP API wrapper for blog_generator
Runs on port 8765
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import subprocess
import os
import jwt
import time

app = FastAPI(title="Blog Generator API")

class ArticleRequest(BaseModel):
    topic: str
    agent: str = "diego-martinez"
    publish: bool = False

@app.post("/generate")
async def generate_article(request: ArticleRequest):
    """Generate a blog article"""
    cmd = [
        "python3", 
        "/root/workspace/digital-humans-production/scripts/blog_generator.py",
        request.topic,
        "--agent", request.agent
    ]
    
    if request.publish:
        cmd.append("--publish")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Generation timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents")
async def list_agents():
    """List available agents"""
    return {
        "agents": [
            {"slug": "sophie-chen", "name": "Sophie Chen", "role": "Chef de Projet"},
            {"slug": "olivia-parker", "name": "Olivia Parker", "role": "Analyste Métier"},
            {"slug": "marcus-johnson", "name": "Marcus Johnson", "role": "Architecte Solution"},
            {"slug": "diego-martinez", "name": "Diego Martinez", "role": "Développeur Apex"},
            {"slug": "zara-thompson", "name": "Zara Thompson", "role": "Développeuse LWC"},
            {"slug": "raj-patel", "name": "Raj Patel", "role": "Administrateur Salesforce"},
            {"slug": "elena-vasquez", "name": "Elena Vasquez", "role": "Ingénieure QA"},
            {"slug": "jordan-blake", "name": "Jordan Blake", "role": "Ingénieur DevOps"},
            {"slug": "aisha-okonkwo", "name": "Aisha Okonkwo", "role": "Spécialiste Data"},
            {"slug": "lucas-fernandez", "name": "Lucas Fernandez", "role": "Responsable Formation"},
        ]
    }

@app.get("/ghost-token")
async def get_ghost_token():
    """Generate a Ghost Admin API JWT token (valid 5 minutes)"""
    ghost_key = os.getenv("GHOST_ADMIN_KEY")
    if not ghost_key:
        raise HTTPException(status_code=500, detail="GHOST_ADMIN_KEY not configured")
    
    try:
        key_id, secret = ghost_key.split(':')
    except ValueError:
        raise HTTPException(status_code=500, detail="Invalid GHOST_ADMIN_KEY format")
    
    iat = int(time.time())
    exp = iat + 300  # 5 minutes
    
    header = {'alg': 'HS256', 'typ': 'JWT', 'kid': key_id}
    payload = {'iat': iat, 'exp': exp, 'aud': '/admin/'}
    
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers=header)
    
    return {"token": token, "expires_in": 300}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)
