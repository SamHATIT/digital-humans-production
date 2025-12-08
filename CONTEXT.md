# DIGITAL HUMANS - CONTEXTE PROJET

> **Version** : 1.0 | **Dernière MAJ** : 8 décembre 2025

---

## ⚠️ PROTOCOLE DE SESSION OBLIGATOIRE

### Début de session — AVANT TOUTE RÉPONSE
```
1. Lire /root/workspace/digital-humans-production/PROGRESS.log (dernières sessions)
2. Lire /root/workspace/digital-humans-production/features.json (état des fonctionnalités)
3. Confirmer à l'utilisateur : "J'ai lu les fichiers. Dernière session : [date]. Prochaine tâche identifiée : [X]"
```

### Pendant la session
```
4. Travailler sur UNE SEULE fonctionnalité à la fois
5. Tester le résultat avant de déclarer "terminé"
6. Ne JAMAIS dire "c'est fait" sans preuve (log, test, capture)
```

### Fin de session — SUR DEMANDE "fin de session"
```
7. Mettre à jour features.json (statut de la/les fonctionnalité(s) traitée(s))
8. Ajouter une entrée dans PROGRESS.log
9. Commit Git avec message descriptif
10. Confirmer : "Session clôturée. Fichiers mis à jour. Prochaine étape : [X]"
```

---

## 1. VISION & OBJECTIFS

**Digital Humans** est une plateforme SaaS multi-agents IA qui automatise l'intégralité du cycle de développement Salesforce : de l'analyse des besoins jusqu'au déploiement en production.

**Proposition de valeur** : Réduire de 70% le temps et le coût des projets Salesforce grâce à des agents IA spécialisés qui collaborent comme une équipe de consultants.

**Cible** : Mars 2026 — Lancement sur Salesforce AgentExchange

---

## 2. ARCHITECTURE TECHNIQUE

### Stack
| Composant | Technologie |
|-----------|-------------|
| Backend | FastAPI + Python 3.11 |
| Frontend | React 18 + TypeScript + Tailwind |
| Base de données | PostgreSQL 15 |
| RAG | ChromaDB (40K chunks) |
| LLM | Anthropic Claude (Sonnet/Haiku) + OpenAI GPT-4 |
| Infra | VPS Hostinger, Ubuntu 24.04, Docker |

### Chemins clés
```
VPS : srv1064321.hstgr.cloud
Repo : /root/workspace/digital-humans-production
GitHub : https://github.com/SamHATIT/digital-humans-production
Site web : /var/www/digital-humans.fr
```

### Structure du repo
```
digital-humans-production/
├── backend/
│   └── app/
│       ├── api/routes/        # Endpoints FastAPI
│       ├── models/            # SQLAlchemy models
│       ├── services/          # Logique métier (agents, RAG, LLM)
│       ├── schemas/           # Pydantic schemas
│       └── utils/             # Auth, helpers
├── frontend/
│   └── src/
│       ├── components/        # Composants React
│       ├── pages/             # Pages principales
│       ├── hooks/             # Custom hooks
│       └── services/          # API calls
├── docs/                      # Documentation
├── outputs/                   # Fichiers générés (SDS, etc.)
├── features.json              # État des fonctionnalités
├── PROGRESS.log               # Journal des sessions
└── CONTEXT.md                 # Ce fichier
```

---

## 3. LES 10 AGENTS

| Agent | Rôle | Phase | Obligatoire |
|-------|------|-------|-------------|
| Sophie (PM) | Extraction BRs depuis documents client | ANALYSE | ✅ Oui |
| Olivia (BA) | Génération Use Cases depuis BRs | ANALYSE | ✅ Oui |
| Marcus (Architect) | Solution Design + WBS | ANALYSE | ✅ Oui |
| Diego (Apex) | Code backend Salesforce | BUILD | ❌ Conditionnel |
| Zara (LWC) | Composants UI Lightning | BUILD | ❌ Conditionnel |
| Raj (Admin) | Configuration déclarative | BUILD | ❌ Conditionnel |
| Elena (QA) | Tests et validation | BUILD | ❌ Conditionnel |
| Aisha (Data) | Migration de données | BUILD | ❌ Conditionnel |
| Jordan (DevOps) | CI/CD et déploiement | DEPLOY | ❌ Conditionnel |
| Lucas (Trainer) | Formation (2 modes : SDS + Delivery) | SDS + DEPLOY | ❌ Conditionnel |

---

## 4. WORKFLOW ACTUEL

### Phase 1 — ANALYSE (fonctionnel)
```
Documents client → Sophie (BRs) → Olivia (UCs) → Marcus (SDS + WBS)
```

### Phase 2 — BUILD (à implémenter)
```
WBS → [Diego, Zara, Raj, Aisha] en parallèle conditionnel → Elena valide chaque livrable
```

### Phase 3 — DEPLOY (à implémenter)
```
Livrables validés → Jordan (package + déploiement) → Lucas (formation)
```

---

## 5. CONVENTIONS DE CODE

### Backend (Python)
- Type hints obligatoires
- Docstrings Google style
- Services dans `/services/`, routes dans `/api/routes/`
- Logs avec `logger.info()` / `logger.error()`

### Frontend (TypeScript)
- Composants fonctionnels avec hooks
- Props typées avec interfaces
- Tailwind pour le styling (pas de CSS custom)
- API calls via services dédiés

### Git
- Messages de commit descriptifs : `[SCOPE] Description`
- Scopes : `FIX`, `FEAT`, `REFACTOR`, `DOCS`, `TEST`
- Exemple : `[FIX] SSE progress auth via query param`

---

## 6. DÉCISIONS ARCHITECTURALES (ADR)

### ADR-001 : LLM par agent
- **Décision** : Claude Sonnet pour agents complexes (Sophie, Olivia, Marcus), Haiku pour agents simples
- **Raison** : Équilibre coût/qualité

### ADR-002 : RAG V2 avec reranking
- **Décision** : ChromaDB + sentence-transformers pour reranking
- **Raison** : Améliorer la pertinence des chunks récupérés

### ADR-003 : Logique conditionnelle agents BUILD
- **Décision** : Le WBS de Marcus détermine quels agents BUILD sont nécessaires
- **Raison** : Éviter d'exécuter des agents inutiles (ex: pas d'Apex = pas de Diego)

### ADR-004 : Mode incrémental (à implémenter)
- **Décision** : Exécution tâche par tâche avec validation Elena entre chaque
- **Raison** : Éviter la dérive sur projets complexes (méthodologie Anthropic)

---

## 7. BUGS CONNUS & LIMITATIONS

| ID | Description | Statut |
|----|-------------|--------|
| BUG-001 | SSE Progress 403 (EventSource + auth) | 🔴 Non résolu |
| BUG-002 | Troncature outputs agents (limite tokens) | 🔴 Non résolu |
| BUG-003 | AgentThoughtModal ne fonctionne pas | 🔴 Non résolu |
| BUG-004 | Page se vide entre agents | 🔴 Non résolu |
| BUG-005 | sentence_transformers manquant (reranker) | 🟡 Fallback OK |

---

## 8. FICHIERS DE SUIVI

| Fichier | Rôle | Fréquence MAJ |
|---------|------|---------------|
| `CONTEXT.md` | Contexte stable (ce fichier) | Rarement |
| `features.json` | État des 72 fonctionnalités | Chaque session |
| `PROGRESS.log` | Journal chronologique | Chaque session |

---

## 9. CONTACTS & RESSOURCES

- **Propriétaire** : Sam HATIT
- **Repo GitHub** : https://github.com/SamHATIT/digital-humans-production
- **Article référence** : https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

---

*Ce document ne doit être modifié que lors de changements majeurs d'architecture ou de vision.*
