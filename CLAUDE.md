# CLAUDE.md — Digital Humans Production

## 🎯 Projet

Plateforme SaaS multi-agents IA automatisant le développement Salesforce.  
11 agents spécialisés génèrent des spécifications (SDS) puis du code déployable (BUILD).

- **Stack** : FastAPI 0.104.1 (Python 3.12) + React/Vite + PostgreSQL 16 + ChromaDB RAG (70K chunks) + Ollama/Mistral
- **VPS** : 72.61.161.222 — Ubuntu 24.04 — /root/workspace/digital-humans-production/
- **Repo** : github.com/SamHATIT/digital-humans-production
- **Services** : backend port 8002, frontend port 3000, PostgreSQL 5432, Ollama 11434

---

## 📊 État actuel (Avril 2026)

| Composant | État | Dernière action |
|-----------|------|-----------------|
| SDS v3 | ✅ Fonctionnel — $0.11/exécution | Optimisé jan 2026 |
| BUILD v2 | ⚠️ Code corrigé — jamais testé E2E réel | Fixes fév 2026 |
| Architecture async | ✅ ARQ workers + State Machine 24 états | Horizon 2 ✅ |
| LLM Router v3 | ✅ Opus/Sonnet/Haiku selon agent | Opérationnel |
| Horizon 3 | 🔄 En cours | Budget Manager + HITL + RAG dynamique |

**Prochain test critique** : E2E BUILD v2 sur projet FormaPro (Session 6 de BUILD_V2_SPEC.md)

---

## 🏗️ Architecture

```
backend/
├── app/
│   ├── api/routes/          # FastAPI routes (21 fichiers)
│   ├── models/              # SQLAlchemy models (29 fichiers)  
│   ├── services/            # Business logic (40+ fichiers)
│   │   ├── pm_orchestrator_service_v2.py  # Orchestrateur principal
│   │   ├── llm_router_service.py          # LLM Router v3
│   │   ├── rag_service.py                 # ChromaDB RAG
│   │   └── [agent]_service.py             # Services par agent
│   └── main.py
├── agents/roles/            # 11 agents Python
├── config/llm_routing.yaml  # Config LLM Router
└── venv/

frontend/src/
├── pages/                   # Dashboard, Execution, Projects
├── components/
└── services/api.ts

RAG : /opt/digital-humans/rag/chromadb_data/ (2.4GB, 70251 chunks)
```

---

## 🤖 Les 11 agents

| Agent | Rôle | Modèle LLM |
|-------|------|------------|
| Sophie (PM) | Orchestration, extraction BR, consolidation SDS | Claude Opus |
| Olivia (BA) | Analyse fonctionnelle BR | Claude Opus (promu) |
| Emma (Research) | UC Digest, validation couverture | Claude Sonnet |
| Marcus (Architect) | Architecture SF, gap analysis, WBS | Claude Sonnet |
| Diego (Apex) | Code Apex, triggers, classes | Claude Haiku |
| Zara (LWC) | Composants Lightning Web | Claude Haiku |
| Jordan (Admin/DevOps) | Config SF metadata + déploiement | Claude Haiku |
| Aisha (Data) | Migration données, Bulk API | Claude Haiku |
| Elena (QA) | Tests fonctionnels | Claude Haiku |
| Raj (QA Engineer) | Validation structurelle | Claude Haiku |
| Lucas (Trainer) | Documentation utilisateur | Claude Haiku |

---

## 🔧 Règles de développement

### Git — OBLIGATOIRE
```bash
# Toujours créer une branche avant de toucher au code
git checkout -b claude/[description-courte]-[4chars-random]

# Commits atomiques avec prefix
git commit -m "fix: description" / "feat: description" / "refactor: description"

# JAMAIS merger directement sur main sans validation
# JAMAIS de git push --force
# Tag avant chaque session importante : git tag pre-session-YYYYMMDD
```

### Tests — OBLIGATOIRE avant tout commit
```bash
cd backend && python -m pytest tests/ -x -q 2>&1 | tail -20
# Si les tests passent → commit autorisé
# Si échec → corriger d'abord
```

### Services — vérification avant tout travail
```bash
systemctl is-active digital-humans-backend digital-humans-frontend postgresql
# Si un service est down → le redémarrer avant de commencer
```

---

## 📋 Backlog prioritaire (ordre d'exécution)

### P0 — TEST E2E BUILD FormaPro (CRITIQUE)
**Objectif** : Valider que la chaîne SDS → BUILD → déploiement Salesforce fonctionne bout en bout  
**Référence** : BUILD_V2_SPEC.md Session 6  
**Org Salesforce** : shatit715@agentforce.com (alias: digital-humans-dev)  
**Commande de départ** :
```bash
cd /root/workspace/digital-humans-production
cat BUILD_V2_SPEC.md | grep -A 50 "Session 6"
```

### P1 — Horizon 3 : Budget Manager + Circuit Breaker
- Implémenter le budget manager avec alertes par projet
- Circuit breaker si coût > seuil configuré
- Référence : DIGITAL_HUMANS_CONTEXT.md section Horizon 3

### P2 — Horizon 3 : Human-in-the-Loop MVP
- Gate de validation entre SDS et BUILD
- Interface de revue des BR avant génération
- Branche existante : `remotes/origin/claude/build-hitl-backend-routes-dnM9E`

### P3 — Horizon 3 : RAG dynamique
- Isolation multi-tenant des collections ChromaDB
- RAG dynamique par projet/client

### P4 — Dette technique
- Finaliser résolution split brain pm.py v1/v2 (P1 partiel)
- Transactions atomiques (P7 partiel)
- BaseAgent commun (P10 backlog)

---

## 🛡️ Règles de sécurité autonome

1. **Backup avant session** : `cd /root/workspace && tar -czf backups/auto-$(date +%Y%m%d-%H%M).tar.gz digital-humans-production/ --exclude=venv --exclude=node_modules --exclude=.git`
2. **Ne jamais modifier** : `.env`, `database.py`, `main.py` sans backup préalable
3. **Ne jamais supprimer** : Tables PostgreSQL, collections ChromaDB
4. **Rollback disponible** : `git checkout main && git reset --hard HEAD~1` si besoin
5. **Si le backend crash** : `systemctl restart digital-humans-backend && sleep 5 && curl -s http://localhost:8002/health`

---

## 📊 Reporting (sessions autonomes)

À la fin de chaque session ou toutes les 2h de travail, envoyer un rapport :
```python
import urllib.request, urllib.parse, datetime
msg = f"[Rapport Digital Humans — {datetime.datetime.now().strftime('%d/%m %H:%M')}]\n\n[résumé des actions]\n[commits effectués]\n[tests passés/échoués]\n[prochaine étape]"
data = urllib.parse.urlencode({'chat_id':'6562956255','text':msg}).encode()
urllib.request.urlopen('https://api.telegram.org/bot8671596568:AAGC4L3JnqHM64oVhEyAI5EJ0LvZD8TOdy8/sendMessage', data=data, timeout=10)
```

---

## 🔍 Commandes de diagnostic utiles

```bash
# Statut services
systemctl status digital-humans-backend --no-pager -l | tail -20

# Logs backend temps réel
journalctl -u digital-humans-backend -f --no-pager | tail -50

# Dernières exécutions DB
sudo -u postgres psql -d digital_humans_db -c "SELECT id, status, created_at FROM execution_entity ORDER BY id DESC LIMIT 5;"

# Test API
curl -s http://localhost:8002/health | python3 -m json.tool

# Git état propre
git status && git log --oneline -5

# ChromaDB vérification
sqlite3 /opt/digital-humans/rag/chromadb_data/chroma.sqlite3 "SELECT COUNT(*) FROM embeddings;"
```

---

## 📁 Fichiers clés à connaître

- `PROGRESS.log` — Journal de toutes les sessions
- `BUILD_V2_SPEC.md` — Spécification BUILD v2 (1236 lignes) — référence pour P0
- `features.json` — 188 features trackées
- `CHANGELOG.md` — Toutes les modifications
- `backend/config/llm_routing.yaml` — Config LLM Router v3
- `tasks/` — Répertoire pour les plans de session

---

*CLAUDE.md mis à jour le 12 avril 2026 — Samhatit Consulting*
