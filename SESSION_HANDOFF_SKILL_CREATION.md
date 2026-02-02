# SESSION HANDOFF — Création Skill + Réorganisation Mémoire
# Date: 2026-02-02
# Objectif: Exécuter dans la prochaine session sans perdre de détails

---

## 1. CONTEXTE DE LA DÉCISION

Sam et Claude ont identifié que le système actuel de gestion de contexte est inefficace et contient des erreurs. Décision prise de :
- Créer un **Skill Claude** dédié à Digital Humans (chargement à la demande)
- Nettoyer la **mémoire Claude** (passer de 22 à ~5-6 entrées)
- Réécrire le **CONTEXT.md** sur le VPS (version actuelle contient des erreurs)
- Archiver le **PROGRESS.log** (garder 5 dernières sessions)
- Modifier les **instructions projet** (ne plus lire features.json systématiquement)

### Pourquoi un Skill plutôt que tout dans CONTEXT.md ?
- Un skill est chargé **uniquement quand pertinent** (0 tokens quand on parle d'autre chose)
- Progressive disclosure : metadata (~100 mots) → SKILL.md (<5000 mots) → references (à la demande)
- CONTEXT.md reste sur le VPS pour le protocole de session, mais allégé

### Commentaires de Sam (à respecter impérativement)
- Pas de N8N pour l'archivage (mauvais timing vu contrainte runway avril)
- Pas de "Context Manager" automatisé (un skill = des instructions, pas un daemon)
- Backup simple via cron suffit
- Sam veut relire le SKILL.md ensemble avant validation
- Règle "#1 pas de DONE sans preuve" doit rester prominente
- Préférence : toujours montrer les logs de validation avant de dire "c'est fait"
- Si feature "completed" dans features.json, ne pas la mentionner sauf si Sam demande historique

---

## 2. ERREURS ACTUELLES À CORRIGER

### CONTEXT.md actuel (VPS) - ERREURS IDENTIFIÉES :
1. ❌ Dit "Backend Port **8000**" → CORRECT = **8002**
2. ❌ Dit `docker compose logs backend` → Backend NE TOURNE PAS en Docker, c'est uvicorn direct
3. ❌ Dit `docker compose restart backend` → FAUX, commande = `fuser -k 8002/tcp` puis relancer uvicorn
4. ❌ Aucune mention d'Ollama (service critique pour SDS v3)
5. ❌ Aucune mention de SFDX (critique pour BUILD)
6. ❌ Aucune mention du MCP server (port 8000)
7. ❌ Aucune mention des commandes de démarrage manuelles
8. ❌ Aucune mention de Ghost blog (Docker, port 2368)
9. ❌ Aucune mention de Nginx comme reverse proxy HTTPS
10. ❌ Aucune mention de ChromaDB (RAG, port 8100)
11. ❌ Aucune mention de N8N (port 5678)

### Mémoire Claude - ENTRÉES À MIGRER DANS LE SKILL :
Ligne 1: Ports/VPS → skill/references/server-admin.md
Ligne 2: Agents → skill/references/architecture.md
Ligne 3: SDS Phases → skill/references/architecture.md
Ligne 4: BUILD Phase → skill/references/architecture.md
Ligne 5: Project Status flow → skill/references/architecture.md
Ligne 6: Storage/Tables → skill/references/architecture.md
Ligne 7: Key Files → skill/references/architecture.md
Ligne 8: Endpoints → skill/references/architecture.md
Ligne 9: Tracking files → skill/SKILL.md
Ligne 10: Paths → skill/references/server-admin.md
Ligne 11: PostgreSQL note → skill/references/troubleshooting.md
Ligne 12: Mandatory Agents → skill/references/architecture.md
Ligne 16: Ollama config → skill/references/server-admin.md
Ligne 17: Services auto → skill/references/server-admin.md
Ligne 18: Services manuels → skill/references/server-admin.md
Ligne 19: Start Backend cmd → skill/references/server-admin.md
Ligne 20: Start Frontend cmd → skill/references/server-admin.md
Ligne 21: Stop cmds + Logs → skill/references/server-admin.md
Ligne 22: SFDX config → skill/references/server-admin.md

### Mémoire Claude - ENTRÉES À GARDER (mises à jour si besoin) :
Ligne 13: SDS v3 architecture (Mistral 7B + Claude) → GARDER
Ligne 14: État réel projet → GARDER (mettre à jour régulièrement)
Ligne 15: Priorités actuelles → GARDER (mettre à jour régulièrement)

### Mémoire Claude - NOUVELLES ENTRÉES À AJOUTER :
- "Sam: toujours montrer preuves/logs avant de confirmer DONE. Ne jamais mentionner features completed sauf si demandé."
- "Sam: préfère réflexion commune avant action. Ne pas aller trop vite. Réponses en français."
- "DH Skill: /mnt/skills/user/digital-humans/ contient architecture, admin, troubleshooting. Lire au lieu de mémoire."

---

## 3. PLAN D'ACTION (5 ÉTAPES)

### ÉTAPE 1 — Créer le Skill Digital Humans

Emplacement : Le skill doit être créé dans l'environnement Claude claude.ai, PAS sur le VPS.
Chemin : `/mnt/skills/user/digital-humans/`

Note importante : `/mnt/skills/user/` n'existe pas encore. Il faudra peut-être que Sam
l'ajoute manuellement via l'interface Claude (Settings → Skills) ou qu'on utilise le
script init_skill.py de `/mnt/skills/examples/skill-creator/scripts/init_skill.py`.

Structure prévue :
```
/mnt/skills/user/digital-humans/
├── SKILL.md                     ← Instructions principales + protocole session
├── references/
│   ├── architecture.md          ← Agents, phases, endpoints, DB schema, key files
│   ├── server-admin.md          ← Ports, services, commandes, SFDX, Nginx, Ollama
│   └── troubleshooting.md       ← Problèmes courants + solutions connues
└── scripts/
    └── health_check.py          ← Script vérifiant que tous les services tournent
```

#### SKILL.md — CONTENU PRÉVU :

```yaml
---
name: digital-humans
description: >
  Plateforme multi-agents IA pour automatiser le développement Salesforce.
  Utiliser ce skill quand la conversation concerne : Digital Humans, les agents IA
  (Sophie/Olivia/Marcus/Diego/Zara/Raj/Elena/Jordan/Aisha/Lucas), le SDS, le BUILD,
  le déploiement Salesforce, la configuration serveur VPS (72.61.161.222), ou tout
  aspect du projet digital-humans-production. Aussi quand Sam mentionne : agents,
  SDS, BUILD, Formapro, features.json, PROGRESS.log, CONTEXT.md, backend port 8002,
  frontend port 3000, Ollama, SFDX, ou le repo GitHub SamHATIT/digital-humans-production.
---

# Digital Humans — Skill Claude

## Protocole de Session OBLIGATOIRE

### Début de session
1. Lire PROGRESS.log sur le VPS (dernières 50 lignes uniquement) via MCP
2. Confirmer : "Dernière session : [date]. Prochaine tâche : [X]"
3. NE PAS lire features.json sauf demande explicite de Sam

### Pendant la session
4. UNE SEULE fonctionnalité à la fois
5. Tester AVANT de déclarer terminé
6. JAMAIS dire "c'est fait" sans preuve (log, test, capture)

### Fin de session (sur demande "fin de session")
7. Mettre à jour features.json si pertinent
8. Ajouter entrée dans PROGRESS.log
9. Commit Git avec message descriptif
10. Confirmer : "Session clôturée. Prochaine étape : [X]"

## Règle #1 — PAS DE DONE SANS PREUVE
- ❌ "ça compile" ≠ DONE
- ❌ "j'ai écrit le code" ≠ DONE
- ✅ "testé + preuve ci-dessous" = DONE

## Vue d'ensemble
- **Stack** : FastAPI (8002) + React (3000) + PostgreSQL + ChromaDB + Claude/Mistral
- **VPS** : 72.61.161.222 | Repo : SamHATIT/digital-humans-production
- **10 Agents** : Sophie(PM) → Olivia(BA) → Marcus(Architect) → Spécialistes → Elena(QA) → Jordan(DevOps)
- **2 Phases** : SDS (génération specs) puis BUILD (génération code + déploiement SF)

## Références détaillées
- **Architecture complète** (agents, phases, endpoints, DB) : voir `references/architecture.md`
- **Administration serveur** (ports, services, commandes, SFDX) : voir `references/server-admin.md`
- **Résolution de problèmes** : voir `references/troubleshooting.md`

## Fichiers de suivi (VPS)
- `/root/workspace/digital-humans-production/PROGRESS.log` — Journal sessions (lire au début)
- `/root/workspace/digital-humans-production/features.json` — 188 features (146 completed, 42 restantes). Consulter UNIQUEMENT si Sam demande un état spécifique.
- `/root/workspace/digital-humans-production/CONTEXT.md` — Renvoi vers ce skill
```

#### references/architecture.md — CONTENU PRÉVU :

```markdown
# Digital Humans — Architecture

## Les 10 Agents

| Agent | Rôle | Fichier | Mode SDS | Mode BUILD |
|-------|------|---------|----------|------------|
| Sophie | PM | salesforce_pm.py | Extrait BRs | - |
| Olivia | BA | salesforce_business_analyst.py | Génère UCs | - |
| Marcus | Architect | salesforce_solution_architect.py | As-Is/Gap/Design/WBS | - |
| Diego | Apex Dev | salesforce_developer_apex.py | spec | build (Apex code) |
| Zara | LWC Dev | salesforce_developer_lwc.py | spec | build (LWC code) |
| Raj | Admin | salesforce_admin.py | spec | build (config) |
| Elena | QA | salesforce_qa_tester.py | spec | test (validation) |
| Jordan | DevOps | salesforce_devops.py | spec | deploy |
| Aisha | Data | salesforce_data_migration.py | spec | build (migration) |
| Lucas | Trainer | salesforce_trainer.py | sds_strategy | - |
| Emma | Research Analyst | salesforce_research_analyst.py | UC digest/coverage/SDS | - |

Notes :
- Agents OBLIGATOIRES frontend (constants.ts) : pm, ba, architect
- SDS experts optionnels
- BUILD agents déterminés par assignees dans le WBS

## Phases SDS

```
Phase 1 : Sophie → extrait Business Requirements (BRs)
   ↓ WAITING_BR_VALIDATION (utilisateur valide)
Phase 2 : Olivia → génère Use Cases (UCs) depuis BRs validés
   ↓ Gate: vérifie UCs > 0
Phase 3 : Marcus → As-Is Analysis, Gap Analysis, Solution Design, WBS
Phase 4 : Experts parallèles (Elena QA spec, Jordan DevOps spec, Lucas Training, Aisha Data)
   ↓ Emma : UC digest, coverage report, SDS final synthesis
   ↓ Génération DOCX
```

### SDS v3 (Janvier 2026)
Pipeline optimisé coût :
- Pass 1 : Mistral 7B local (Ollama) → micro-analyse par UC → Fiche Besoin JSON
- Pass 2 : Python agrégation par domaine fonctionnel
- Pass 3 : Claude Sonnet → synthèse professionnelle par section
- Pass 4 : Assemblage final DOCX (ERD, permissions, WBS)
- Coût : ~$0.11 pour 8 UCs (vs $2-5 pipeline v2)
- Fichiers clés : llm_router_service.py, config/llm_routing.yaml, sds_synthesis_service.py

### Pipeline v2 actuel (celui qui a produit FormaPro)
- Workflow complet via pm_orchestrator_service_v2.py
- Tous les agents tournent séquentiellement
- Coût : ~$2-5 par SDS complet
- Qualité PRO validée (FormaPro : 4878 lignes, 62 UCs, 15 clusters fonctionnels)

## Phase BUILD

```
Prérequis : SDS_APPROVED + Git configuré + Salesforce connecté

WBS tasks → incremental_executor.py
   ↓
Diego/Zara/Raj/Aisha (mode=build) → génèrent code/config
   ↓
SFDX deploy (sfdx_service.py) → déploiement sur org Salesforce
   ↓
Elena (mode=test) → validation code déployé
   ↓
Git commit (git_service.py) → versioning
   ↓
Jordan → packaging final
```

Statut actuel BUILD : ⚠️ Jamais déployé bout-en-bout sur Salesforce.
Blocage identifié : déploiement SFDX échoue sur certains metadata types.

## Flow Statut Projet
```
DRAFT → READY → [SDS] → SDS_GENERATED → SDS_IN_REVIEW → SDS_APPROVED → [BUILD] → BUILD_IN_PROGRESS → BUILD_COMPLETED
```

## API Endpoints principaux

### SDS
- POST `/api/execute` — Lance exécution SDS
- POST `/execute/{id}/generate-sds-v3` — Pipeline SDS v3 complet
- GET `/execute/{id}/download-sds-v3` — Télécharge DOCX

### BUILD
- POST `/projects/{id}/start-build` — Lance BUILD
- GET `/execute/{id}/build-tasks` — Liste tâches BUILD
- POST `/execute/{id}/pause-build` — Pause BUILD
- POST `/execute/{id}/resume-build` — Reprend BUILD

### Projet
- GET/PUT `/api/projects/{id}/settings` — Config Git/Salesforce
- POST `/api/projects/{id}/test-salesforce` — Test connexion SF
- POST `/api/projects/{id}/test-git` — Test connexion Git

## Base de Données (PostgreSQL: digital_humans_db)

### Tables principales (par taille)
| Table | Taille | Rôle |
|-------|--------|------|
| audit_logs | 16 MB | Logs d'audit complets |
| deliverable_items | 11 MB | Items parsés (UCs, BRs détaillés) |
| llm_interactions | 8 MB | Historique appels LLM avec coûts |
| agent_deliverables | 5 MB | Livrables bruts JSON des agents |
| execution_artifacts | 1.6 MB | Fichiers générés (DOCX, etc.) |
| business_requirements | 616 KB | BRs extraits par Sophie |
| task_executions | 464 KB | Tâches BUILD avec statuts |
| projects | 384 KB | Projets avec config |
| executions | 296 KB | Exécutions SDS/BUILD |
| uc_requirement_sheets | 128 KB | Fiches besoin SDS v3 |

### Tables secondaires
- project_git_config, project_environments, project_credentials — Config connexions
- validation_gates — Gates de validation entre phases
- blog_topics — Sujets blog Ghost
- users — 4 utilisateurs (internes)
- agents — Définitions agents
- sds_versions, sds_templates — Versioning SDS

### Notes PostgreSQL
- Tourne comme service système (PAS Docker). Vérifier : `pg_isready`
- Connexion : `sudo -u postgres psql -d digital_humans_db`
- Les enums doivent être mis à jour via ALTER TYPE AVANT d'utiliser de nouvelles valeurs
- Pas de migration Alembic active, modifications manuelles

## Services Backend clés

| Service | Fichier | Rôle |
|---------|---------|------|
| pm_orchestrator_service_v2.py | Orchestration SDS (phases 1-4) |
| incremental_executor.py | Orchestration BUILD (tâches WBS) |
| agent_executor.py | Exécution individuelle d'un agent |
| sfdx_service.py | Déploiement Salesforce via SFDX CLI |
| git_service.py | Opérations Git (commit, push) |
| llm_router_service.py | Routage LLM (local/cloud) selon complexité |
| llm_service.py | Appels LLM (Anthropic, OpenAI) |
| sds_synthesis_service.py | Synthèse SDS v3 par domaine |
| sds_docx_generator_v3.py | Génération DOCX professionnel |
| rag_service.py | RAG Salesforce (ChromaDB, 70k+ chunks) |
| sfdx_auth_service.py | Auth Salesforce (SFDX CLI ou OAuth) |
| sophie_chat_service.py | Chat interactif avec Sophie |

## Frontend Pages clés

| Page | Fichier | Rôle |
|------|---------|------|
| Dashboard | Dashboard.tsx | Vue d'ensemble projets |
| Projet détail | ProjectDetailPage.tsx | Config + lancement SDS/BUILD |
| Monitoring SDS | ExecutionMonitoringPage.tsx | Suivi exécution SDS en temps réel |
| Monitoring BUILD | BuildMonitoringPage.tsx | Suivi tâches BUILD |
| Validation BRs | BRValidationPage.tsx | Validation Business Requirements |
| Nouveau projet | ProjectWizard.tsx / NewProject.tsx | Création projet |

## Features (features.json)
- Total : 188 features
- Completed : 146 | Done : 15 | Not started : 19 | Pending : 8
- Features critiques restantes :
  - SDS-V3-001 [pending] : Pipeline SDS v3 intégration complète
  - BUILD-VALID-001 [pending] : Validation BUILD sur org SF réelle
  - B2B-001/002 [pending] : Profil entreprise SIRET, multi-utilisateurs
  - PAY-001/002/003 [pending] : Stripe, facturation, système tokens
  - BILLING-001 à 005 [not_started] : Facturation détaillée
  - BUILD-TEST-001 [not_started] : Tests BUILD
  - GTM-001 à 005 [not_started] : Go-to-market
```

#### references/server-admin.md — CONTENU PRÉVU :

```markdown
# Digital Humans — Administration Serveur

## Infos Serveur
- **VPS** : 72.61.161.222
- **OS** : Ubuntu
- **Domaine** : digital-humans.fr (HTTPS via Let's Encrypt + Nginx)
- **Repo** : /root/workspace/digital-humans-production
- **GitHub** : git@github.com:SamHATIT/digital-humans-production.git

## Ports et Services

| Port | Service | Type | Notes |
|------|---------|------|-------|
| 80/443 | Nginx | Auto-start | Reverse proxy HTTPS → backends |
| 3000 | React Frontend | Manuel | Vite dev server |
| 5432 | PostgreSQL | Auto-start | digital_humans_db (service système, PAS Docker) |
| 8000 | MCP Server | Auto-start | /root/system-mcp-server.py (accès Claude → VPS) |
| 8002 | FastAPI Backend | Manuel | API principale Digital Humans |
| 8100 | ChromaDB | Manuel | Vector DB pour RAG Salesforce |
| 11434 | Ollama | Auto-start | LLM local (Mistral 7B + Nemo) |
| 2368 | Ghost Blog | Auto-start (Docker) | CMS blog digital-humans.fr |
| 5678 | N8N | Manuel | Workflows automation |
| 3306 | MySQL | Auto-start | Utilisé par Ghost |
| 6379 | Redis | Auto-start | Cache |

## Services Auto-démarrage (boot)
- PostgreSQL (`postgresql@16-main.service`)
- Nginx (`nginx.service`)
- Docker → Ghost blog (`ghost-blog` container)
- Redis (`redis-server.service`)
- MySQL (`mysql.service`)
- Ollama (démarre auto)
- MCP Server (port 8000)

## Services à Démarrer Manuellement après reboot

### Backend (port 8002)
```bash
cd /root/workspace/digital-humans-production/backend
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload > /tmp/backend.log 2>&1 &
```

### Frontend (port 3000)
```bash
cd /root/workspace/digital-humans-production/frontend
nohup npm run dev -- --host 0.0.0.0 > /tmp/frontend.log 2>&1 &
```

### ChromaDB (port 8100)
```bash
# TODO: documenter commande exacte
```

### N8N (port 5678)
```bash
nohup n8n start > /tmp/n8n.log 2>&1 &
```

## Commandes d'Arrêt

```bash
# Arrêter Backend
fuser -k 8002/tcp

# Arrêter Frontend
pkill -f 'vite'

# Arrêter N8N
pkill -f 'n8n'
```

## Fichiers de Logs
- Backend : `/tmp/backend.log`
- Frontend : `/tmp/frontend.log`
- Ollama : `/var/log/ollama.log`
- Nginx : `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- PostgreSQL : `/var/log/postgresql/`

## Nginx Configuration
- Fichier : `/etc/nginx/sites-enabled/digital-humans`
- SSL : Let's Encrypt (`/etc/letsencrypt/live/digital-humans.fr/`)
- Proxy principal : `proxy_pass http://localhost:8002`
- HTTP → HTTPS redirect automatique

## Salesforce (SFDX)
- **CLI** : SFDX v2.113.6
- **Org authentifiée** : shatit715@agentforce.com
- **Alias** : digital-humans-dev
- **Org ID** : 00DgL00000FzQzTUAV
- **Login** : login.salesforce.com (Developer Edition, PAS test.salesforce.com)
- **Vérifier** : `sf org list`
- **Ouvrir** : `sf org open --target-org digital-humans-dev`

## Ollama (LLM local)
- **URL** : http://localhost:11434
- **Modèles installés** :
  - `mistral:7b-instruct` (4.4 GB) — Tâches simples, Fiches Besoin SDS v3
  - `mistral-nemo:latest` (7.1 GB) — Tâches moyennes
- **Démarrage** : `nohup ollama serve > /var/log/ollama.log 2>&1 &`
- **Test** : `curl http://localhost:11434/api/tags`
- **Config routage** : `backend/config/llm_routing.yaml`
  - simple → local/mistral:7b-instruct (gratuit)
  - medium → anthropic/claude-haiku
  - complex/critical → anthropic/claude-sonnet

## Backend .env (variables clés, sans secrets)
```
DATABASE_URL=postgresql://...
SECRET_KEY=...
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=...
PROJECT_NAME=Digital Humans
DEBUG=true
BACKEND_CORS_ORIGINS=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
AGENTS_DIR=/root/workspace/digital-humans-production/backend/agents/roles
UPLOAD_DIR=...
```

## Vérifications Santé

```bash
# PostgreSQL
pg_isready

# Backend API
curl -s http://localhost:8002/api/health | head -20

# Frontend
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000

# Ollama
curl -s http://localhost:11434/api/tags | python3 -m json.tool

# SFDX
sf org list

# Nginx
systemctl status nginx

# MCP
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000
```

## Docker
- Seul container : `ghost-blog` (Ghost 5 Alpine, port 2368)
- Le backend NE tourne PAS en Docker (uvicorn direct)
- Le frontend NE tourne PAS en Docker (vite direct)

## Git
- Remote : `git@github.com:SamHATIT/digital-humans-production.git`
- Tag de backup : `v1-full-workflow-backup`
- Branches : main
```

#### references/troubleshooting.md — CONTENU PRÉVU :

```markdown
# Digital Humans — Troubleshooting

## Problèmes Fréquents

### Backend ne démarre pas
1. Vérifier qu'aucun process n'occupe le port : `fuser 8002/tcp`
2. Vérifier le venv : `source backend/venv/bin/activate && which python`
3. Vérifier les dépendances : `pip list | grep fastapi`
4. Vérifier .env : `cat backend/.env` (DATABASE_URL, API keys présentes ?)
5. Vérifier PostgreSQL : `pg_isready`
6. Lire les logs : `tail -50 /tmp/backend.log`

### Frontend ne démarre pas
1. Vérifier port : `fuser 3000/tcp`
2. Vérifier VITE_API_URL dans `frontend/.env` → doit être VIDE (utilise proxy Nginx)
3. `cd frontend && npm run dev -- --host 0.0.0.0`

### Erreur "OpenAI API Key"
- Le backend charge OPENAI_API_KEY depuis `backend/.env`
- Si la clé est invalide/expirée, les agents utilisant GPT-4 échouent
- Solution : mettre à jour la clé dans `backend/.env` et relancer le backend

### Agents tournent avec 0 BRs/UCs
- Cause : `resume_from` condition skipait Phase 1
- Fix appliqué : condition `resume_from not in (None, "phase1", "phase1_pm")`
- Gates de validation ajoutées : vérifie BRs > 0 avant Phase 2, UCs > 0 après Phase 2
- Fichier : `pm_orchestrator_service_v2.py`

### BUILD échoue au lancement
- Vérifier config projet : Git + Salesforce doivent être configurés
- Vérifier SFDX auth : `sf org list` (status = Connected ?)
- Vérifier tâche TASK-001 (setup env) : c'est une tâche manuelle
- TASK-037 (UAT) est aussi manuelle

### Déploiement Salesforce échoue
- Certains metadata types ne sont pas supportés par le déploiement incrémental
- Vérifier les filtres dans `sfdx_service.py`
- Le BUILD n'a JAMAIS réussi bout-en-bout (février 2026)

### Cache navigateur frontend
- Si boutons manquants après mise à jour : Ctrl+Shift+R (hard refresh)
- VITE_API_URL doit être vide dans `frontend/.env` pour utiliser proxy Nginx

### Erreur PostgreSQL enums
- Les enums PostgreSQL doivent être mis à jour AVANT d'utiliser de nouvelles valeurs
- Commande : `ALTER TYPE enum_name ADD VALUE 'new_value';`
- Ne pas oublier de commit la transaction

### Tokens consommés par erreur
- Sessions 129 : ~27K tokens Claude perdus (agents ont tourné avec 0 BRs)
- Session BUILD : ~$0.15-0.20 Opus perdus sur BUILD sans config
- Toujours vérifier les prérequis AVANT de lancer une exécution

### Chemins Docker vs VPS
- Les prompts agents référençaient `/app/agents/roles/` (chemin Docker)
- Chemin correct VPS : `/root/workspace/digital-humans-production/backend/agents/roles/`
- Corrigé dans `pm_orchestrator_service_v2.py` et `agent_executor.py`
```

#### scripts/health_check.py — CONTENU PRÉVU :

```python
#!/usr/bin/env python3
"""Digital Humans — Health Check Script
Vérifie que tous les services critiques tournent.
Usage: python3 health_check.py
"""
import subprocess
import urllib.request
import json
import sys

def check(name, cmd):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        ok = result.returncode == 0
        print(f"{'✅' if ok else '❌'} {name}")
        if not ok and result.stderr:
            print(f"   {result.stderr.strip()[:100]}")
        return ok
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

def check_url(name, url, expected_code=200):
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=5)
        ok = resp.getcode() == expected_code
        print(f"{'✅' if ok else '❌'} {name} (HTTP {resp.getcode()})")
        return ok
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

print("=== Digital Humans Health Check ===\n")
results = []
results.append(check("PostgreSQL", "pg_isready"))
results.append(check("Nginx", "systemctl is-active nginx"))
results.append(check("Ollama", "curl -s http://localhost:11434/api/tags > /dev/null"))
results.append(check_url("Backend API", "http://localhost:8002/api/health"))
results.append(check_url("Frontend", "http://localhost:3000"))
results.append(check_url("MCP Server", "http://localhost:8000"))
results.append(check("SFDX Auth", "sf org list 2>/dev/null | grep -q Connected"))
results.append(check("Ghost Blog", "docker ps | grep -q ghost"))

print(f"\n{'='*40}")
ok_count = sum(results)
total = len(results)
print(f"Résultat : {ok_count}/{total} services OK")
if ok_count < total:
    print("⚠️  Certains services nécessitent attention")
    sys.exit(1)
else:
    print("✅ Tous les services sont opérationnels")
    sys.exit(0)
```

---

## 4. NOUVEAU CONTEXT.md (VPS) — CONTENU PRÉVU

Remplace l'actuel `/root/workspace/digital-humans-production/CONTEXT.md` :

```markdown
# DIGITAL HUMANS — CONTEXTE PROJET

## ⛔ RÈGLE #1 : JAMAIS DE "DONE" SANS PREUVE DE TEST RÉEL
1. EXÉCUTER un test réel (UI, curl, ou via l'app)
2. CAPTURER la preuve (log backend, screenshot, response JSON)
3. COLLER la preuve dans PROGRESS.log
4. SEULEMENT ALORS marquer DONE dans features.json

## Référence Technique
Toutes les infos techniques (architecture, admin, troubleshooting) sont dans le
**Skill Claude "digital-humans"**. Ne pas les dupliquer ici.

## État Actuel (Février 2026)
- SDS : Qualité PRO validée (FormaPro : 4878 lignes, 62 UCs)
- BUILD : Jamais déployé bout-en-bout sur Salesforce
- Clients : 0 (produit en développement)
- Priorité #1 : Finaliser BUILD (déploiement SF)
- Priorité #2 : Trouver 2-3 cabinets SF pilotes
- Priorité #3 : Associé technique

## Fichiers de Suivi
- `PROGRESS.log` — Journal sessions (lire les 50 dernières lignes au début)
- `features.json` — 188 features. Consulter UNIQUEMENT si besoin spécifique.
- Ce fichier — Contexte stable (rarement modifié)

## Liens Rapides
- VPS : 72.61.161.222
- Repo : git@github.com:SamHATIT/digital-humans-production.git
- Backend : port 8002 | Frontend : port 3000
```

---

## 5. ARCHIVAGE PROGRESS.log

### Action :
1. Créer `/root/workspace/digital-humans-production/archives/`
2. Copier PROGRESS.log actuel → `archives/PROGRESS_before_2026-02-02.log`
3. Garder dans PROGRESS.log uniquement les sessions à partir de 2026-01-27 (dernières 5 sessions)
4. Ajouter un cron simple pour backup quotidien :
   ```bash
   0 2 * * * cp /root/workspace/digital-humans-production/CONTEXT.md /root/workspace/digital-humans-production/archives/CONTEXT_$(date +\%Y\%m\%d).md
   ```

---

## 6. MODIFICATION INSTRUCTIONS PROJET

Les instructions projet (dans le projet Claude) doivent être mises à jour :
- Supprimer "Lire features.json" du protocole obligatoire
- Garder "Lire PROGRESS.log (dernières 50 lignes)"
- Ajouter "Le skill digital-humans contient toutes les refs techniques"

Instructions actuelles à modifier (dans le système prompt du projet Claude) :
```
### Début de session — AVANT TOUTE RÉPONSE
1. Lire /root/workspace/digital-humans-production/PROGRESS.log (dernières sessions)
2. [SUPPRIMÉ] Lire features.json
3. Confirmer : "J'ai lu PROGRESS.log. Dernière session : [date]. Prochaine tâche : [X]"
```

---

## 7. NETTOYAGE MÉMOIRE CLAUDE — PLAN EXACT

### À SUPPRIMER (migrés dans le skill) :
- Ligne 1 (Ports/VPS)
- Ligne 2 (Agents)
- Ligne 3 (SDS Phases)
- Ligne 4 (BUILD Phase)
- Ligne 5 (Project Status)
- Ligne 6 (Storage/Tables)
- Ligne 7 (Key Files)
- Ligne 8 (Endpoints)
- Ligne 9 (Tracking files)
- Ligne 10 (Paths)
- Ligne 11 (PostgreSQL note)
- Ligne 12 (Mandatory Agents)
- Ligne 16 (Ollama)
- Ligne 17 (Services Auto)
- Ligne 18 (Services Manuels)
- Ligne 19 (Start Backend)
- Ligne 20 (Start Frontend)
- Ligne 21 (Stop/Logs)
- Ligne 22 (SFDX)

Total à supprimer : 19 entrées

### À GARDER (mettre à jour) :
- Ligne 13 → "DH SDS v3: Mistral 7B local (Fiche Besoin) + Claude Sonnet (synthèse). Config: llm_routing.yaml"
- Ligne 14 → "DH État (Fév 2026): SDS qualité PRO, BUILD jamais déployé SF. 0 client. Runway → avril."
- Ligne 15 → "DH Next: 1.Finaliser BUILD 2.Pilotes cabinets SF 3.Associé technique 4.Skill Claude créé"

### À AJOUTER :
- "DH Skill: /mnt/skills/user/digital-humans/ = architecture, admin serveur, troubleshooting. Toujours charger pour tâches DH."
- "Sam: montrer preuves avant DONE. Ne pas mentionner features completed sauf demande. Préfère réflexion avant action."
- "Sam: entrepreneur Salesforce, cherche investisseurs BA opérateurs, runway avril 2026. Réponses en français."

### Résultat final : 6 entrées / 30 (24 slots libres)

---

## 8. CHECKLIST D'EXÉCUTION POUR LA PROCHAINE SESSION

```
[ ] 1. Lire ce fichier (SESSION_HANDOFF_SKILL_CREATION.md)
[ ] 2. Créer le skill dans /mnt/skills/user/digital-humans/
    [ ] 2a. SKILL.md (copier contenu section 3)
    [ ] 2b. references/architecture.md
    [ ] 2c. references/server-admin.md
    [ ] 2d. references/troubleshooting.md
    [ ] 2e. scripts/health_check.py
[ ] 3. MONTRER À SAM pour relecture avant validation
[ ] 4. Créer /archives/ sur VPS et archiver ancien PROGRESS.log
[ ] 5. Réécrire CONTEXT.md sur VPS (version allégée section 4)
[ ] 6. Nettoyer mémoire Claude (supprimer 19 lignes, garder 3, ajouter 3)
[ ] 7. Ajouter cron backup sur VPS
[ ] 8. Mettre à jour instructions projet (supprimer lecture features.json obligatoire)
[ ] 9. Tester le skill (démarrer une tâche DH et vérifier que le skill se charge)
[ ] 10. Commit Git avec tout
```

---

## 9. DONNÉES DE RÉFÉRENCE SUPPLÉMENTAIRES

### Projet #84 (FormaPro) — dernier projet testé
- Status : SDS_GENERATED (puis APPROVED puis BUILD tenté)
- Exécution SDS #130 : COMPLETED (~$2.02, 43 min)
- SDS : 4878 lignes, 62 UCs, 15 clusters, qualité PRO
- Git configuré : https://github.com/SamHATIT/formapro-salesforce
- SF configuré : shatit715@agentforce.com via SFDX
- BUILD : Tenté mais échoué (TASK-001 manuelle non gérée)

### Coûts historiques
- SDS v2 (pipeline complet) : ~$2-5 par SDS
- SDS v3 (micro-analyse) : ~$0.11 pour 8 UCs (testé exécution 86 seulement)
- BUILD tentative : ~$0.15-0.20 (tokens Opus perdus)
- Erreur agents sans données : ~$0.27 (27K tokens Sonnet perdus)

### LLM Routing Config (llm_routing.yaml)
- simple → local/mistral:7b-instruct (gratuit)
- medium → anthropic/claude-haiku ($0.25/$1.25 per M tokens)
- complex → anthropic/claude-sonnet ($3/$15 per M tokens)
- critical → anthropic/claude-sonnet

### Abonnement Sam
- Claude MAX (upgrade février 2026)
- Accès : Cowork, Skills, Sub-agents

