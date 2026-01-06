#!/usr/bin/env python3
"""
Ghost API Helper for Digital Humans Blog
"""

import jwt
import time
import requests
from datetime import datetime

# Configuration
GHOST_URL = "https://blog-admin.digital-humans.fr"
GHOST_ADMIN_KEY = "695a5936e3b3d60001bcd398:1e384dc5f1c00c38c1deb03594c10369904f81e3e0c0b3a809bb6a41ac66e430"
GHOST_CONTENT_KEY = "9985b20698251c494e823ca162"

# Les 10 agents blogueurs
AGENTS = [
    {
        "name": "Sophie Chen",
        "slug": "sophie-chen",
        "email": "sophie@digital-humans.fr",
        "role": "Project Manager",
        "bio": "Senior Project Manager. Stratégie, roadmap et gouvernance projet. \"Un projet réussi commence par une vision claire et une équipe alignée.\"",
        "color": "#8B5CF6"
    },
    {
        "name": "Olivia Parker",
        "slug": "olivia-parker",
        "email": "olivia@digital-humans.fr",
        "role": "Business Analyst",
        "bio": "Senior Business Analyst. Requirements, process mapping et use cases. \"Comprendre le besoin avant de construire la solution.\"",
        "color": "#3B82F6"
    },
    {
        "name": "Marcus Johnson",
        "slug": "marcus-johnson",
        "email": "marcus@digital-humans.fr",
        "role": "Solution Architect",
        "bio": "Principal Solution Architect. Design patterns, intégration et scalabilité. \"Penser architecture avant de penser code.\"",
        "color": "#F97316"
    },
    {
        "name": "Diego Martinez",
        "slug": "diego-martinez",
        "email": "diego@digital-humans.fr",
        "role": "Apex Developer",
        "bio": "Senior Apex Developer. Apex, triggers, batches et governor limits. \"Un excellent développeur écrit du code que les autres peuvent maintenir.\"",
        "color": "#EF4444"
    },
    {
        "name": "Zara Thompson",
        "slug": "zara-thompson",
        "email": "zara@digital-humans.fr",
        "role": "LWC Developer",
        "bio": "Lead LWC Developer. Lightning Web Components, UX et accessibilité. \"L'expérience utilisateur n'est pas un luxe, c'est le produit.\"",
        "color": "#22C55E"
    },
    {
        "name": "Raj Patel",
        "slug": "raj-patel",
        "email": "raj@digital-humans.fr",
        "role": "Salesforce Admin",
        "bio": "Senior Salesforce Administrator. Flows, permissions et configuration. \"La meilleure configuration est celle qu'on n'a pas besoin d'expliquer.\"",
        "color": "#EAB308"
    },
    {
        "name": "Elena Vasquez",
        "slug": "elena-vasquez",
        "email": "elena@digital-humans.fr",
        "role": "QA Engineer",
        "bio": "QA Lead Engineer. Test strategy, Apex tests et qualité. \"Tester, ce n'est pas douter. C'est garantir.\"",
        "color": "#6B7280"
    },
    {
        "name": "Jordan Blake",
        "slug": "jordan-blake",
        "email": "jordan@digital-humans.fr",
        "role": "DevOps Engineer",
        "bio": "DevOps Engineer. SFDX, CI/CD, Git et deployment. \"Automatiser tout ce qui peut l'être. Documenter le reste.\"",
        "color": "#1E40AF"
    },
    {
        "name": "Aisha Okonkwo",
        "slug": "aisha-okonkwo",
        "email": "aisha@digital-humans.fr",
        "role": "Data Specialist",
        "bio": "Data Integration Specialist. Data Cloud, migration et ETL. \"Les données sont le fondement. Traitez-les avec respect.\"",
        "color": "#92400E"
    },
    {
        "name": "Lucas Fernandez",
        "slug": "lucas-fernandez",
        "email": "lucas@digital-humans.fr",
        "role": "Training Lead",
        "bio": "Training & Adoption Lead. Formation, documentation et change management. \"La meilleure technologie est inutile si personne ne sait l'utiliser.\"",
        "color": "#D946EF"
    }
]


def get_admin_token():
    """Generate JWT token for Ghost Admin API"""
    key_id, secret = GHOST_ADMIN_KEY.split(':')
    
    iat = int(time.time())
    header = {'alg': 'HS256', 'typ': 'JWT', 'kid': key_id}
    payload = {
        'iat': iat,
        'exp': iat + 5 * 60,  # 5 minutes
        'aud': '/admin/'
    }
    
    token = jwt.encode(payload, bytes.fromhex(secret), algorithm='HS256', headers=header)
    return token


def api_get(endpoint):
    """GET request to Ghost Admin API"""
    token = get_admin_token()
    headers = {'Authorization': f'Ghost {token}'}
    url = f"{GHOST_URL}/ghost/api/admin/{endpoint}"
    
    response = requests.get(url, headers=headers)
    return response.json()


def api_post(endpoint, data):
    """POST request to Ghost Admin API"""
    token = get_admin_token()
    headers = {
        'Authorization': f'Ghost {token}',
        'Content-Type': 'application/json'
    }
    url = f"{GHOST_URL}/ghost/api/admin/{endpoint}"
    
    response = requests.post(url, headers=headers, json=data)
    return response.json(), response.status_code


def test_api():
    """Test API connection"""
    result = api_get("site/")
    print("✅ API Connection OK")
    print(f"   Site: {result.get('site', {}).get('title', 'Unknown')}")
    return result


def list_users():
    """List all Ghost users/staff"""
    result = api_get("users/")
    users = result.get('users', [])
    print(f"\n📋 Users ({len(users)}):")
    for user in users:
        print(f"   - {user['name']} ({user['email']}) - {user['slug']}")
    return users


def create_tags():
    """Create tags for each agent"""
    print("\n🏷️ Creating agent tags...")
    
    for agent in AGENTS:
        tag_data = {
            "tags": [{
                "name": agent['name'],
                "slug": agent['slug'],
                "description": agent['bio'],
                "accent_color": agent['color']
            }]
        }
        
        result, status = api_post("tags/", tag_data)
        
        if status == 201:
            print(f"   ✅ Created tag: {agent['name']}")
        elif 'errors' in result and 'already exists' in str(result):
            print(f"   ⏭️ Tag exists: {agent['name']}")
        else:
            print(f"   ❌ Error for {agent['name']}: {result}")


if __name__ == "__main__":
    print("🔌 Testing Ghost API...")
    test_api()
    list_users()
    create_tags()
