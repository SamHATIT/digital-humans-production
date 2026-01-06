#!/usr/bin/env python3
"""
Blog Article Generator for Digital Humans
- Text: Claude Haiku (API) or Mistral Nemo (Ollama)
- Images: Gemini Nano Banana Pro (API)
- Publish: Ghost CMS
"""

import os
import sys
import json
import jwt
import time
import base64
import requests
import argparse
import re

# Configuration from environment variables
GHOST_URL = os.getenv("GHOST_URL", "https://blog-admin.digital-humans.fr")
GHOST_ADMIN_KEY = os.getenv("GHOST_ADMIN_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Load from .env file if keys not in environment
if not GHOST_ADMIN_KEY or not ANTHROPIC_API_KEY:
    env_file = "/root/workspace/digital-humans-production/.env"
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    if key == "GHOST_ADMIN_KEY" and not GHOST_ADMIN_KEY:
                        GHOST_ADMIN_KEY = value
                    elif key == "ANTHROPIC_API_KEY" and not ANTHROPIC_API_KEY:
                        ANTHROPIC_API_KEY = value
                    elif key == "GEMINI_API_KEY" and not GEMINI_API_KEY:
                        GEMINI_API_KEY = value

AGENTS = {
    'sophie-chen': {'name': 'Sophie Chen', 'role': 'Chef de Projet', 'color': '#8B5CF6',
        'expertise': 'stratégie projet, roadmap, gouvernance', 'style': "Structuré, stratégique.",
        'tip_name': 'Le conseil de Sophie', 'sig_emoji': '🎯', 'sig_title': 'Actions suivantes'},
    'olivia-parker': {'name': 'Olivia Parker', 'role': 'Analyste Métier', 'color': '#3B82F6',
        'expertise': 'requirements, process, use cases', 'style': "Analytique, orienté utilisateur.",
        'tip_name': "Le conseil d'Olivia", 'sig_emoji': '📋', 'sig_title': 'Questions clés'},
    'marcus-johnson': {'name': 'Marcus Johnson', 'role': 'Architecte Solution', 'color': '#F97316',
        'expertise': 'design patterns, intégration, scalabilité', 'style': 'Technique mais accessible.',
        'tip_name': 'Le conseil de Marcus', 'sig_emoji': '🏗️', 'sig_title': 'Architecture'},
    'diego-martinez': {'name': 'Diego Martinez', 'role': 'Développeur Apex', 'color': '#EF4444',
        'expertise': 'Apex, triggers, batches, SOQL', 'style': 'Direct, code-centric.',
        'tip_name': 'Le conseil de Diego', 'sig_emoji': '📝', 'sig_title': 'Code récap'},
    'zara-thompson': {'name': 'Zara Thompson', 'role': 'Développeuse LWC', 'color': '#22C55E',
        'expertise': 'LWC, Aura, CSS/SLDS, UX', 'style': 'Moderne, orienté UX.',
        'tip_name': 'Le conseil de Zara', 'sig_emoji': '✅', 'sig_title': 'Checklist UX'},
    'raj-patel': {'name': 'Raj Patel', 'role': 'Admin Salesforce', 'color': '#EAB308',
        'expertise': 'Flows, Permissions, Validation Rules', 'style': 'Pratique, step-by-step.',
        'tip_name': 'Le conseil de Raj', 'sig_emoji': '⚙️', 'sig_title': 'Config check'},
    'elena-vasquez': {'name': 'Elena Vasquez', 'role': 'Ingénieure QA', 'color': '#6B7280',
        'expertise': 'test strategy, Apex tests, UAT', 'style': 'Méthodique.',
        'tip_name': "Le conseil d'Elena", 'sig_emoji': '🧪', 'sig_title': 'Tests essentiels'},
    'jordan-blake': {'name': 'Jordan Blake', 'role': 'Ingénieur DevOps', 'color': '#1E40AF',
        'expertise': 'SFDX, CI/CD, Git, Sandboxes', 'style': 'Technique, automation.',
        'tip_name': 'Le conseil de Jordan', 'sig_emoji': '💻', 'sig_title': 'Commande SFDX'},
    'aisha-okonkwo': {'name': 'Aisha Okonkwo', 'role': 'Spécialiste Data', 'color': '#92400E',
        'expertise': 'Data Cloud, migration, ETL', 'style': 'Rigoureux.',
        'tip_name': "Le conseil d'Aisha", 'sig_emoji': '📊', 'sig_title': 'Data checklist'},
    'lucas-fernandez': {'name': 'Lucas Fernandez', 'role': 'Responsable Formation', 'color': '#D946EF',
        'expertise': 'formation, documentation, adoption', 'style': 'Pédagogique.',
        'tip_name': 'Le conseil de Lucas', 'sig_emoji': '📌', 'sig_title': 'À retenir'}
}

def get_ghost_token():
    key_id, secret = GHOST_ADMIN_KEY.split(':')
    iat = int(time.time())
    return jwt.encode({'iat': iat, 'exp': iat + 300, 'aud': '/admin/'}, 
                      bytes.fromhex(secret), algorithm='HS256', 
                      headers={'alg': 'HS256', 'typ': 'JWT', 'kid': key_id})

def clean_llm_intro(html_content: str) -> str:
    """Remove typical LLM intro phrases that shouldn't appear in final article."""
    intro_patterns = [
        r'^<p>Voici un article[^<]*?:</p>\s*',
        r'^<p>Voici un article[^<]*?</p>\s*',
        r'^Voici un article[^<\n]*?:\s*\n*',
        r"^<p>Voici l'article[^<]*?:</p>\s*",
        r'^<p>Je vous propose[^<]*?:</p>\s*',
        r'^<p>Voici mon article[^<]*?:</p>\s*',
        r'^<p>Bien sûr[^<]*?:</p>\s*',
        r"^<p>D'accord[^<]*?:</p>\s*",
    ]
    cleaned = html_content.strip()
    for pattern in intro_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    # Remove duplicate title if <p>Title</p> followed by <h2>Title</h2>
    cleaned = re.sub(r'^<p>([^<]{10,80})</p>\s*<h2>\1</h2>', r'<h2>\1</h2>', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()



def generate_source_section(source_url: str = None, source_name: str = None) -> str:
    """Generate HTML section for source attribution."""
    if not source_url and not source_name:
        return ""
    
    source_html = '\n<hr>\n<div class="article-sources">\n<h3>📚 Sources & Références</h3>\n<p>Cet article a été inspiré par l\'actualité Salesforce. Nous remercions les auteurs originaux pour leur travail.</p>\n<ul>\n'
    
    if source_url and source_name:
        source_html += f'<li><a href="{source_url}" target="_blank" rel="noopener">{source_name}</a> — Article source</li>\n'
    elif source_url:
        source_html += f'<li><a href="{source_url}" target="_blank" rel="noopener">Article source</a></li>\n'
    elif source_name:
        source_html += f'<li>{source_name}</li>\n'
    
    source_html += '</ul>\n</div>\n'
    return source_html

def call_haiku(prompt: str, max_tokens: int = 4000) -> str:
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": "claude-3-haiku-20240307", "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
        timeout=90
    )
    if response.status_code != 200:
        raise Exception(f"API Error: {response.status_code}")
    return response.json().get('content', [{}])[0].get('text', '')

def generate_article_haiku(topic: str, agent: dict, agent_slug: str) -> dict:
    print(f"📝 Génération avec Claude Haiku...")
    
    prompt1 = f"""Tu es {agent['name']}, {agent['role']} chez Digital Humans (experts Salesforce).
Style d'écriture: {agent['style']}
Expertise: {agent['expertise']}

Écris un article de blog PROFESSIONNEL en FRANÇAIS sur: {topic}

IMPORTANT: Commence DIRECTEMENT par le contenu. NE COMMENCE PAS par "Voici un article..." ou une phrase méta.

Structure:
1. Introduction engageante (2-3 paragraphes) - parle directement au lecteur
2. 3-4 sections principales avec sous-titres <h2>
3. Exemples concrets, code si pertinent
4. Conclusion avec appel à l'action

Utilise du HTML: <p>, <h2>, <h3>, <pre><code>, <ul>, <li>, <strong>"""

    try:
        html_content = call_haiku(prompt1, 3500)
        print(f"   ✅ Contenu: {len(html_content)} chars")
        
        prompt2 = f"""Voici un article sur "{topic}" écrit par {agent['name']}:

{html_content[:800]}...

Génère les métadonnées. Réponds UNIQUEMENT avec ce JSON (une ligne, pas de retour à la ligne):
{{"title":"Titre accrocheur","excerpt":"Description SEO 150 chars","tip":"Un conseil pratique mémorable en 1 phrase","actions":["Action 1","Action 2","Action 3"]}}"""

        meta_str = call_haiku(prompt2, 300)
        
        js = meta_str.find('{')
        je = meta_str.rfind('}') + 1
        meta = json.loads(meta_str[js:je]) if js >= 0 else {}
        
        title = meta.get('title', topic)
        excerpt = meta.get('excerpt', f"Article sur {topic}")
        tip = meta.get('tip', "Maîtrisez les fondamentaux avant d'explorer les fonctionnalités avancées.")
        actions = meta.get('actions', ["Pratiquez régulièrement", "Consultez la documentation", "Échangez avec la communauté"])
        
        print(f"   ✅ Titre: {title[:50]}...")
        
        expert_tip = f'''

<hr>
<blockquote>
<p><strong>💡 {agent['tip_name']}</strong></p>
<p><em>"{tip}"</em></p>
</blockquote>

<h3>{agent['sig_emoji']} {agent['sig_title']}</h3>
<ul>
<li>{actions[0] if len(actions) > 0 else "Point 1"}</li>
<li>{actions[1] if len(actions) > 1 else "Point 2"}</li>
<li>{actions[2] if len(actions) > 2 else "Point 3"}</li>
</ul>'''
        
        return {"title": title, "excerpt": excerpt, "html": clean_llm_intro(html_content) + expert_tip}
        
    except Exception as e:
        print(f"   ❌ Erreur: {e}")
        return None

def generate_article_ollama(topic: str, agent: dict, agent_slug: str) -> dict:
    print(f"📝 Génération avec Mistral Nemo...")
    print(f"   ⏳ Patientez 4-6 min...")
    
    prompt = f"""Tu es {agent['name']}, {agent['role']}.
Écris un article en FRANÇAIS sur: {topic}
Style: {agent['style']}

HTML avec <p>, <h2>, <pre><code>.
Termine avec:
TITRE: [titre]
EXCERPT: [description]
TIP: [conseil]
ACTIONS: [action1 | action2 | action3]"""

    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate",
            json={"model": "mistral-nemo", "prompt": prompt, "stream": False, "options": {"temperature": 0.7, "num_predict": 3500}},
            timeout=600)
        result = response.json().get('response', '')
        
        title = re.search(r'TITRE:\s*(.+?)(?:\n|$)', result)
        title = title.group(1).strip() if title else topic
        
        excerpt = re.search(r'EXCERPT:\s*(.+?)(?:\n|$)', result)
        excerpt = excerpt.group(1).strip() if excerpt else f"Article sur {topic}"
        
        tip = re.search(r'TIP:\s*(.+?)(?:\n|$)', result)
        tip = tip.group(1).strip() if tip else "Conseil pratique"
        
        actions = re.search(r'ACTIONS:\s*(.+?)(?:\n|$)', result)
        actions = [a.strip() for a in actions.group(1).split('|')] if actions else ["Point 1", "Point 2", "Point 3"]
        
        html = clean_llm_intro(re.sub(r'(TITRE|EXCERPT|TIP|ACTIONS):.*', '', result).strip())
        
        html += f'''

<hr>
<blockquote>
<p><strong>💡 {agent['tip_name']}</strong></p>
<p><em>"{tip}"</em></p>
</blockquote>

<h3>{agent['sig_emoji']} {agent['sig_title']}</h3>
<ul><li>{actions[0]}</li><li>{actions[1] if len(actions)>1 else "Point 2"}</li><li>{actions[2] if len(actions)>2 else "Point 3"}</li></ul>'''
        
        print(f"   ✅ Article: {title[:50]}...")
        return {"title": title, "excerpt": excerpt, "html": html}
    except Exception as e:
        print(f"   ❌ {e}")
        return None

def generate_image(topic: str, agent: dict) -> bytes:
    print(f"🎨 Génération image...")
    if not GEMINI_API_KEY:
        print(f"   ⚠️ GEMINI_API_KEY non configurée")
        return None
    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/nano-banana-pro-preview:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": f"Photorealistic professional blog header for article about \"{topic}\". Style: high-quality stock photo, modern office or tech environment, shallow depth of field. Show realistic workplace scene or metaphorical concept representation. Subtle {agent['color']} accent tones. Corporate aesthetic. NO text, NO logos. 16:9 ratio."}]}],
                  "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}},
            timeout=60)
        data = response.json()
        if 'candidates' in data:
            for part in data['candidates'][0].get('content', {}).get('parts', []):
                if 'inlineData' in part:
                    img = base64.b64decode(part['inlineData']['data'])
                    print(f"   ✅ {len(img)//1024}KB")
                    return img
        return None
    except Exception as e:
        print(f"   ❌ {e}")
        return None

def upload_image_to_ghost(image_bytes: bytes, filename: str) -> str:
    print(f"📤 Upload Ghost...")
    try:
        r = requests.post(f"{GHOST_URL}/ghost/api/admin/images/upload/",
            headers={'Authorization': f'Ghost {get_ghost_token()}'},
            files={'file': (filename, image_bytes, 'image/jpeg')}, timeout=30)
        if r.status_code == 201:
            url = r.json().get('images', [{}])[0].get('url', '')
            print(f"   ✅ {url}")
            return url
        return None
    except: return None

def create_ghost_post(title, html, excerpt, agent_slug, feature_image=None, status='draft'):
    print(f"📰 Création Ghost...")
    post_data = {"posts": [{"title": title, "html": html, "custom_excerpt": excerpt, "status": status, "tags": [{"slug": agent_slug}]}]}
    if feature_image: post_data["posts"][0]["feature_image"] = feature_image
    try:
        r = requests.post(f"{GHOST_URL}/ghost/api/admin/posts/?source=html",
            headers={'Authorization': f'Ghost {get_ghost_token()}', 'Content-Type': 'application/json'},
            json=post_data, timeout=30)
        if r.status_code == 201:
            print(f"   ✅ OK")
            return r.json()['posts'][0]
        print(f"   ❌ {r.status_code}")
        return None
    except: return None

def generate_blog_article(topic, agent_slug='diego-martinez', publish=False, skip_image=False, use_local=False, source_url=None, source_name=None):
    agent = AGENTS.get(agent_slug, AGENTS['diego-martinez'])
    llm = "Mistral Nemo" if use_local else "Claude Haiku"
    
    print(f"\n{'='*60}")
    print(f"🚀 {topic}")
    print(f"👤 {agent['name']} | 🤖 {llm}")
    print(f"{'='*60}\n")
    
    article = generate_article_ollama(topic, agent, agent_slug) if use_local else generate_article_haiku(topic, agent, agent_slug)
    if not article: return {'success': False}
    
    img_url = None
    if not skip_image:
        img = generate_image(topic, agent)
        if img:
            slug = re.sub(r'[^a-z0-9]+', '-', article['title'].lower())[:25]
            img_url = upload_image_to_ghost(img, f"cover-{slug}-{int(time.time())}.jpg")
    
    
    # Add source reference section if provided
    final_html = article['html']
    if source_url or source_name:
        final_html += generate_source_section(source_url, source_name)
    
    post = create_ghost_post(article['title'], final_html, article.get('excerpt', ''), 
                            agent_slug, img_url, 'published' if publish else 'draft')
    
    if post:
        print(f"\n✅ {post['title']}")
        print(f"✏️  {GHOST_URL}/ghost/#/editor/post/{post['id']}\n")
        return {'success': True, 'post': post}
    return {'success': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('topic', nargs='?', default='Les Governor Limits en Apex')
    parser.add_argument('--agent', '-a', default='diego-martinez', choices=list(AGENTS.keys()))
    parser.add_argument('--publish', '-p', action='store_true')
    parser.add_argument('--no-image', action='store_true')
    parser.add_argument('--local', action='store_true', help='Use Mistral Nemo')
    parser.add_argument('--list-agents', '-l', action='store_true')
    parser.add_argument('--source-url', help="URL de l'article source")
    parser.add_argument('--source-name', help="Nom du site source")
    args = parser.parse_args()
    
    if args.list_agents:
        for s, d in AGENTS.items(): print(f"  {s}: {d['name']}")
        sys.exit(0)
    
    # Validate required keys
    if not GHOST_ADMIN_KEY:
        print("❌ GHOST_ADMIN_KEY non configurée. Ajoutez-la dans .env ou en variable d'environnement.")
        sys.exit(1)
    if not args.local and not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY non configurée. Utilisez --local pour Mistral Nemo ou configurez la clé.")
        sys.exit(1)
    
    result = generate_blog_article(args.topic, args.agent, args.publish, args.no_image, args.local, args.source_url, args.source_name)
    sys.exit(0 if result.get('success') else 1)
