# Session 01 Décembre 2025 - Refonte Database-First

## Résumé Exécutif

Diagnostic et correction d'un problème architectural majeur : le BA consommait 223K tokens pour générer 0 Use Cases exploitables à cause d'une cascade de bugs.

## Problèmes Identifiés (Exécution #60)

### Bug #1 : max_tokens insuffisant
- **Cause** : `max_tokens=4000` dans le BA
- **Effet** : JSON tronqué à ~16,000 caractères (4000 tokens × 4 chars)
- **Symptôme** : "Unterminated string" errors

### Bug #2 : Architecture "all-or-nothing"
- **Cause** : Agrégation en mémoire, sauvegarde unique à la fin
- **Effet** : Si 1 BR échoue → tous les résultats perdus
- **Coût** : 223,024 tokens gaspillés pour 0 UCs

### Bug #3 : Pas de récupération du raw
- **Cause** : Le contenu "raw" n'était pas sauvegardé
- **Effet** : Impossible de récupérer le travail du LLM

## Solutions Implémentées

### 1. Nouvelle table `deliverable_items`
```sql
CREATE TABLE deliverable_items (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER REFERENCES executions(id),
    agent_id VARCHAR(50),        -- 'ba', 'architect', etc.
    parent_ref VARCHAR(100),     -- 'BR-001' (source)
    item_id VARCHAR(100),        -- 'UC-001-01'
    item_type VARCHAR(50),       -- 'use_case', 'gap', 'task'
    content_parsed JSONB,        -- Si parsing OK
    content_raw TEXT,            -- TOUJOURS stocké
    parse_success BOOLEAN,
    parse_error TEXT,
    tokens_used INTEGER,
    model_used VARCHAR(100),
    created_at TIMESTAMP
);
```

### 2. Nouvelles méthodes dans l'orchestrateur
- `_save_deliverable_item()` : Sauvegarde immédiate après chaque appel LLM
- `_save_use_cases_from_result()` : Parse et sauvegarde chaque UC séparément
- `_get_use_cases(execution_id, limit)` : Récupère les UCs depuis la DB
- `_get_use_case_count()` : Statistiques

### 3. Correction max_tokens
- BA : 4000 → **8000**
- Architect : déjà à 8000 (OK)

## Fichiers Modifiés

| Fichier | Modification |
|---------|--------------|
| `backend/app/models/deliverable_item.py` | **Nouveau** - Modèle SQLAlchemy |
| `backend/app/models/__init__.py` | Import DeliverableItem |
| `backend/app/models/execution.py` | Relation deliverable_items |
| `backend/app/services/pm_orchestrator_service_v2.py` | Phase 2 database-first |
| `backend/agents/roles/salesforce_business_analyst.py` | max_tokens 8000 |

## Test Exécution #61

- Lancé avec 18 BRs
- Database-first fonctionnel : items sauvegardés immédiatement
- **Mais** : Tous en "raw" car max_tokens pas encore corrigé au lancement
- Interrompu pour corriger max_tokens

## Prochaines Étapes

1. ✅ Relancer exécution avec max_tokens=8000
2. 📋 Discuter stratégie métadonnées Salesforce (as-is analysis)
3. 📋 Options : Greenfield assumé vs filtrage ciblé vs questionnaire

## Fichiers Générés

- `EXEC_61_Business_Requirements.xlsx` : 18 BRs extraits en Excel

## Commit Git

```
218494d feat: Database-first architecture for BA deliverables + max_tokens fix
```
