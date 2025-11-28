# 📋 TODO LIST - Refonte Architecture Digital Humans V2

**Créé le :** 28 Novembre 2025  
**Dernière mise à jour :** 28 Novembre 2025  
**Statut :** En cours

---

## 🎯 Objectif

Restructurer le workflow des agents pour :
1. Éviter les prompts trop lourds qui "étouffent" les agents
2. Produire des BR/UC atomiques et détaillés
3. Utiliser le RAG efficacement
4. Générer un SDS de qualité professionnelle (spécification, pas build)

---

## 📊 Workflow Cible

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Sophie (PM) : Requirements → BR atomiques                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Olivia (BA) : Pour chaque BR → UC multiples (avec RAG)       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Marcus (Architect) :                                         │
│    ├── Appel 1 : UC → Solution Design (ARCH-001)                │
│    ├── Appel 2 : SFDX → As-Is Analysis (ASIS-001)               │
│    ├── Appel 3 : ARCH + ASIS → Gap Analysis (GAP-001)           │
│    └── Appel 4 : GAP → WBS + Planning (WBS-001)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Sophie (PM) : Consolidation → SDS final                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 : Restructuration du Workflow

### 1.1 - Sophie (PM) : Extraction des BR atomiques
- [ ] Créer nouveau prompt PM focalisé sur l'extraction BR
- [ ] Input : Requirements bruts utilisateur
- [ ] Output : BR-001, BR-002... (1 BR par besoin atomique)
- [ ] Pas besoin de compétence Salesforce
- [ ] Prompt court (~50 lignes max)
- [ ] Traçabilité : chaque BR cite sa source dans les requirements

### 1.2 - Olivia (BA) : Génération UC par BR
- [ ] Modifier le prompt BA pour recevoir 1 seul BR à la fois
- [ ] Intégrer le RAG pour enrichir avec best practices SF
- [ ] Output : UC multiples par BR (3-5 UC minimum)
- [ ] Boucle : Appeler le BA N fois (1 fois par BR)
- [ ] Prompt focalisé (~100 lignes max)

### 1.3 - Marcus (Architect) : 4 appels séquentiels

#### Appel 1 - Solution Design
- [ ] Input : Tous les UC (résumés) + RAG
- [ ] Output : ARTIFACT ARCH-001
  - Architecture globale (ERD Mermaid)
  - Intégrations
  - Sécurité (profils, permissions)
  - Composants techniques

#### Appel 2 - As-Is Analysis
- [ ] Input : Metadata SFDX (par domaine)
- [ ] Output : ARTIFACT ASIS-001
  - Résumé structuré avec `detail_ref`
  - Par catégorie : Data Model, Automation, Security, UI
  - Format JSON indexé

#### Appel 3 - Gap Analysis
- [ ] Input : ARCH-001 (résumé) + ASIS-001 (résumé)
- [ ] Output : ARTIFACT GAP-001
  - Liste des modifications nécessaires
  - Pas de raw data, seulement résumés

#### Appel 4 - WBS (Work Breakdown Structure)
- [ ] Input : GAP-001 + détails à la demande
- [ ] Output : ARTIFACT WBS-001
  - Tâches atomiques
  - Agent assigné (pour phase BUILD future)
  - Dépendances
  - Estimation

### 1.4 - Sophie (PM) : Consolidation SDS
- [ ] Agrège tous les artifacts en document final
- [ ] Structure professionnelle
- [ ] **Inclut :**
  - Flows/Process (diagrammes Mermaid)
  - Règles de validation
  - Profils/Sécurité
  - WBS/Planning
- [ ] **N'inclut PAS :**
  - Code complet Apex/LWC
  - Metadata XML brut

---

## Phase 2 : Gestion du Contexte

### 2.1 - Artifacts comme mémoire externe
- [ ] Chaque étape produit un artifact en DB
- [ ] Format JSON structuré avec `detail_ref` pour les détails
- [ ] Résumés passés entre étapes
- [ ] Détails consultés à la demande (évite explosion contexte)

### 2.2 - Intégration SFDX pour As-Is
- [ ] Script de connexion à l'org Salesforce (auth URL ou credentials)
- [ ] Extraction metadata par catégorie :
  - CustomObject, CustomField, RecordType
  - Flow, ApexTrigger, WorkflowRule
  - Profile, PermissionSet, Role
  - Layout, CustomTab, CustomApplication
- [ ] Parsing XML/JSON → résumé structuré
- [ ] Stockage dans artifacts (ASIS-xxx)

---

## Phase 3 : RAG

### 3.1 - RAG opérationnel ✅ FAIT (28 Nov 2025)
- [x] ChromaDB initialisé avec 33,076 chunks
- [x] 47 documents Salesforce indexés (652 MB de PDFs)
- [x] Service `rag_service.py` créé
- [x] Volume monté dans Docker container
- [x] Intégré au BA et Architect

### 3.2 - Optimisation RAG
- [ ] Filtrer par catégorie selon le contexte (sales_cloud, service_cloud, etc.)
- [ ] Ajuster n_results selon la complexité
- [ ] Tester la qualité des résultats
- [ ] Mesurer l'impact sur la qualité des outputs

---

## Phase 4 : Prompts courts et focalisés

| Agent | Rôle | Prompt actuel | Prompt cible |
|-------|------|---------------|--------------|
| Sophie (PM) | Extract BR | N/A | ~50 lignes |
| Olivia (BA) | BR → UC | ~600 lignes | ~100 lignes |
| Marcus - Design | UC → Archi | ~800 lignes | ~150 lignes |
| Marcus - As-Is | SFDX → Résumé | N/A | ~100 lignes |
| Marcus - Gap | Résumés → Delta | N/A | ~100 lignes |
| Marcus - WBS | Delta → Tâches | N/A | ~100 lignes |
| Sophie (PM) | Consolidation | N/A | ~50 lignes |

---

## Phase 5 : Tests et Validation

- [ ] Test complet avec projet "Gestion de pipelines"
- [ ] Comparer qualité avec/sans RAG
- [ ] Comparer décomposition BR/UC ancienne vs nouvelle
- [ ] Valider que le contexte reste sous 50K tokens par appel
- [ ] Benchmark : temps d'exécution, coût API, qualité output

---

## 📝 Notes de Session

### 28 Nov 2025
- Identification du problème : RAG jamais connecté aux agents malgré 652MB de docs
- Ingestion ChromaDB complète : 33,076 chunks, 47 documents
- Réflexion architecture : décomposition en étapes atomiques
- Décision : SDS = document de spécification (pré-build), pas de code complet
- Test exécution #50 en cours avec RAG activé

---

## 🚀 Priorité Immédiate

1. **1.1** - Créer prompt PM pour extraction BR atomiques
2. **1.2** - Modifier prompt BA pour recevoir 1 BR à la fois
3. **Tester** le nouveau workflow sur cas simple

---

## 📁 Fichiers Concernés

- `/backend/agents/roles/salesforce_business_analyst.py`
- `/backend/agents/roles/salesforce_solution_architect.py`
- `/backend/app/services/rag_service.py` ✅ Créé
- `/backend/app/services/pm_orchestrator_service.py`
- `docker-compose.yml` ✅ Modifié (volume RAG)
