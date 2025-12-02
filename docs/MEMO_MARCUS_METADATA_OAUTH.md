# 📋 MÉMO : Marcus + Metadata via OAuth/Tooling API

**Date :** 2 décembre 2025
**Contexte :** Optimisation du mode `as_is` de Marcus

---

## 🎯 Objectif

Permettre à Marcus de récupérer les métadonnées d'une org Salesforce **directement** via OAuth + Tooling API, sans exploser les coûts tokens.

---

## 🏗️ Architecture Cible

```
┌──────────────────────────────────────────────────────────────┐
│  1. OAuth Flow (déjà prévu dans Agent Salesforce)            │
│     └── User autorise → Access Token + Refresh Token         │
├──────────────────────────────────────────────────────────────┤
│  2. Metadata Fetcher (Python, ZERO LLM)                      │
│     └── Tooling API / Metadata API calls                     │
│         ├── describe() pour objets                           │
│         ├── query() pour flows, triggers, classes            │
│         └── Stocke raw → /app/metadata/{project_id}/raw/     │
├──────────────────────────────────────────────────────────────┤
│  3. Metadata Preprocessor (Python, ZERO LLM)                 │
│     └── Parse raw → metadata_summary.json (~10-15 KB)        │
│         ├── Comptages et listes                              │
│         ├── Détection patterns/anti-patterns                 │
│         └── Technical debt indicators                        │
├──────────────────────────────────────────────────────────────┤
│  4. Marcus (LLM) - Mode as_is                                │
│     └── Reçoit SEULEMENT le summary (~5k tokens)             │
│         └── Génère ASIS-001 intelligent                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 📡 APIs Salesforce à utiliser

| API | Usage |
|-----|-------|
| **Tooling API** | Query FlowDefinition, ApexClass, ApexTrigger, CustomObject |
| **Metadata API** | Retrieve profiles, permission sets, sharing rules |
| **REST describe** | /services/data/vXX.0/sobjects/{object}/describe/ |

### Requêtes clés :

```sql
-- Flows
SELECT Id, ApiName, ProcessType, Status FROM FlowDefinition

-- Apex Classes
SELECT Id, Name, ApiVersion, Status FROM ApexClass

-- Apex Triggers  
SELECT Id, Name, TableEnumOrId, Status FROM ApexTrigger

-- Custom Objects
SELECT Id, DeveloperName, NamespacePrefix FROM CustomObject

-- Validation Rules
SELECT Id, EntityDefinition.QualifiedApiName, ValidationName FROM ValidationRule
```

---

## 💾 Stockage

```
/app/metadata/
└── {project_id}/
    ├── raw/                      # JSON bruts des APIs
    │   ├── objects.json
    │   ├── flows.json
    │   ├── classes.json
    │   ├── triggers.json
    │   └── profiles.json
    ├── metadata_summary.json     # Résumé pour Marcus (~10-15 KB)
    └── extraction_log.json       # Timestamp, org_id, stats
```

---

## 💰 Économies attendues

| Métrique | Sans preprocessing | Avec preprocessing |
|----------|-------------------|-------------------|
| Tokens envoyés | 50-200k | ~5-8k |
| Coût par analyse | $3-10 | ~$0.05-0.15 |
| Données conservées | Non | Oui |

---

## 📝 TODO Prochaine Session

1. [ ] Créer `metadata_fetcher.py` (appels Tooling API)
2. [ ] Créer `metadata_preprocessor.py` (parsing + summary)
3. [ ] Modifier `salesforce_solution_architect.py` mode `as_is`
4. [ ] Tester avec une Dev Org Salesforce
5. [ ] Intégrer dans le workflow PM Orchestrator

---

## 🔗 Fichiers liés

- `/backend/agents/roles/salesforce_solution_architect.py` (Marcus)
- À créer : `/backend/app/services/metadata_fetcher.py`
- À créer : `/backend/app/services/metadata_preprocessor.py`
