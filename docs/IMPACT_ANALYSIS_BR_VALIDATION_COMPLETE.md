# 📋 Analyse d'Impact Complète - Validation des Business Requirements

**Date**: 4 décembre 2025  
**Version de référence**: main @ 9b7eeed  
**Tag de sauvegarde**: backup-before-br-validation-20251204  
**Backup DB**: backup_before_br_validation_20251204_113010.sql (15 Mo)

---

## 1. 📊 État Actuel du Système

### 1.1 Données Existantes

| Table | Nombre d'entrées | Impact si modifié |
|-------|------------------|-------------------|
| projects | 33 (32 READY, 1 ACTIVE) | ⚠️ CRITIQUE |
| executions | N à vérifier | ⚠️ CRITIQUE |
| users | N à vérifier | ✅ Aucun impact |

### 1.2 Statuts Projet Actuels (enum `projectstatus`)

```
DRAFT → READY → ACTIVE → COMPLETED → ARCHIVED
```

**Projets existants par statut:**
- READY: 32 projets
- ACTIVE: 1 projet
- DRAFT: 0
- COMPLETED: 0
- ARCHIVED: 0

### 1.3 Workflow Actuel

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  NewProject  │ ──► │ ExecutionPage│ ──► │  Monitoring  │
│  (form)      │     │ (agents)     │     │  (progress)  │
└──────────────┘     └──────────────┘     └──────────────┘
     │                      │
     ▼                      ▼
  Crée projet          Lance exécution
  status=READY         status→ACTIVE
```

---

## 2. 🎯 Nouveau Workflow Proposé

### 2.1 Flux Complet

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Upload    │ ──► │   Sophie    │ ──► │  Validate   │ ──► │   Olivia    │
│  Document   │     │ Extract BRs │     │    BRs      │     │  + Suite    │
│  (2 min)    │     │  (~5 min)   │     │  (Client)   │     │ (~90 min)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                    Le client peut :
                                    - ✏️ Modifier un BR
                                    - 🗑️ Supprimer un BR
                                    - ➕ Ajouter un BR
                                    - 📥 Export CSV
                                    - ✅ Valider et continuer
```

### 2.2 Nouveaux Statuts (PROPOSITION)

**Option A: Ajouter de nouveaux statuts**
```
DRAFT → UPLOADED → BRS_EXTRACTED → BRS_VALIDATED → EXECUTING → COMPLETED → ARCHIVED
```

**Option B: Garder les statuts existants et ajouter un champ `workflow_step`**
```sql
ALTER TABLE projects ADD COLUMN workflow_step VARCHAR(50);
-- workflow_step: 'document_upload', 'br_extraction', 'br_validation', 'execution', 'completed'
```

**⚠️ RECOMMANDATION**: Option B est plus sûre car elle ne modifie pas l'enum existant.

---

## 3. 📁 Inventaire Complet des Fichiers

### 3.1 Backend - Fichiers Existants

| Fichier | Lignes | Fonctionnalités Actuelles | Impact |
|---------|--------|---------------------------|--------|
| `app/models/project.py` | 62 | ProjectStatus enum, champs projet | MOYEN |
| `app/models/execution.py` | 63 | Execution, ExecutionStatus | FAIBLE |
| `app/schemas/project.py` | 75 | ProjectBase, ProjectCreate, ProjectUpdate | MOYEN |
| `app/schemas/execution.py` | ~100 | ExecutionCreate, ExecutionSchema | FAIBLE |
| `app/api/routes/pm_orchestrator.py` | ~600 | CRUD projets, exécution, progress | HAUT |
| `app/api/routes/projects.py` | 74 | Transitions de statuts | HAUT |
| `app/services/pm_orchestrator_service_v2.py` | ~500 | Exécution agents | MOYEN |

### 3.2 Frontend - Fichiers Existants

| Fichier | Lignes | Fonctionnalités Actuelles | Impact |
|---------|--------|---------------------------|--------|
| `src/App.tsx` | 75 | Routing (6 routes) | FAIBLE |
| `src/pages/NewProject.tsx` | ~200 | Formulaire création projet | FAIBLE |
| `src/pages/ExecutionPage.tsx` | 220 | Sélection agents, lancement | MOYEN |
| `src/pages/ExecutionMonitoringPage.tsx` | ~300 | Monitoring progression | AUCUN |
| `src/services/api.ts` | 181 | Appels API (projects, executions) | MOYEN |
| `src/constants.ts` | 35 | Définition AGENTS, MANDATORY_AGENTS | AUCUN |

### 3.3 Base de Données - Tables Existantes

| Table | FK vers | Impact si nouvelle table |
|-------|---------|--------------------------|
| projects | users | ✅ Aucun (nouvelle table séparée) |
| executions | projects, users | ⚠️ FK vers business_requirements |
| agent_deliverables | executions | ✅ Aucun |
| outputs | projects, executions | ✅ Aucun |

---

## 4. 🆕 Nouveaux Composants à Créer

### 4.1 Backend

| Fichier | Description | Dépendances |
|---------|-------------|-------------|
| `app/models/business_requirement.py` | Modèle SQLAlchemy | execution.py |
| `app/schemas/business_requirement.py` | Schemas Pydantic | - |
| `app/api/routes/business_requirements.py` | Routes CRUD | models, schemas |
| `alembic/versions/xxx_add_business_requirements.py` | Migration | - |

### 4.2 Frontend

| Fichier | Description | Dépendances |
|---------|-------------|-------------|
| `src/pages/BRValidationPage.tsx` | Page principale | api.ts, constants.ts |
| `src/components/BRTable.tsx` | Tableau éditable | - |
| `src/components/BREditModal.tsx` | Modal édition | - |
| `src/components/BRAddModal.tsx` | Modal ajout | - |
| `src/components/BRExportButton.tsx` | Bouton export CSV | - |

---

## 5. 📝 Spécifications Détaillées

### 5.1 Table `business_requirements`

```sql
CREATE TABLE business_requirements (
    id SERIAL PRIMARY KEY,
    
    -- Relations
    execution_id INTEGER REFERENCES executions(id) ON DELETE CASCADE,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Identifiant unique
    br_id VARCHAR(20) NOT NULL,  -- BR-001, BR-002, etc.
    
    -- Contenu
    category VARCHAR(100),  -- Lead Management, Opportunity, etc.
    requirement TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'should',  -- must, should, could, wont
    
    -- Source et versioning
    source VARCHAR(20) DEFAULT 'extracted',  -- 'extracted' ou 'manual'
    original_text TEXT,  -- Ce que Sophie avait extrait (pour historique)
    
    -- Validation
    status VARCHAR(20) DEFAULT 'pending',  -- pending, validated, modified, deleted
    client_notes TEXT,
    validated_at TIMESTAMP,
    validated_by INTEGER REFERENCES users(id),
    
    -- Métadonnées
    order_index INTEGER DEFAULT 0,  -- Pour maintenir l'ordre
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Index
    UNIQUE(execution_id, br_id)
);

CREATE INDEX idx_br_execution ON business_requirements(execution_id);
CREATE INDEX idx_br_project ON business_requirements(project_id);
CREATE INDEX idx_br_status ON business_requirements(status);
```

### 5.2 API Endpoints

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| POST | `/api/br/extract` | Sophie extrait les BRs | `{project_id, document}` | `{execution_id, brs: [...]}` |
| GET | `/api/br/{execution_id}` | Liste des BRs | - | `{brs: [...], stats}` |
| PUT | `/api/br/{br_id}` | Modifier un BR | `{requirement, category, priority, notes}` | `{br}` |
| DELETE | `/api/br/{br_id}` | Supprimer un BR | - | `{success}` |
| POST | `/api/br/{execution_id}` | Ajouter BR manuel | `{requirement, category, priority}` | `{br}` |
| GET | `/api/br/{execution_id}/export` | Export CSV | - | CSV file |
| POST | `/api/br/{execution_id}/validate-all` | Valider tous les BRs | - | `{validated_count}` |
| POST | `/api/br/{execution_id}/reorder` | Réordonner les BRs | `{order: [br_id, ...]}` | `{success}` |

### 5.3 Interface Frontend - BRValidationPage

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📋 Business Requirements Review                                        │
│  Sophie has extracted 48 requirements from your document                │
├─────────────────────────────────────────────────────────────────────────┤
│  [📥 Export CSV]  [➕ Add BR]  [🔍 Filter...]           Status: 0/48 ✓  │
├─────────────────────────────────────────────────────────────────────────┤
│  ID     │ Category      │ Requirement                    │ Status │ Act │
├─────────────────────────────────────────────────────────────────────────┤
│ BR-001  │ Lead Mgmt     │ Capture leads from multiple    │   ✓    │ ✏️🗑️│
│         │               │ channels (web, phone, email)   │        │     │
├─────────────────────────────────────────────────────────────────────────┤
│ BR-002  │ Lead Mgmt     │ Auto-assign leads based on     │   ✓    │ ✏️🗑️│
│         │               │ territory and availability     │        │     │
├─────────────────────────────────────────────────────────────────────────┤
│ ... (pagination)                                                        │
└─────────────────────────────────────────────────────────────────────────┘
│  💬 Questions? Ask Sophie (chat optionnel)                              │
│                                                                         │
│  [ Cancel ]                    [ ✅ Validate All & Continue to Analysis]│
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Modal d'Édition

```
┌─────────────────────────────────────────────────────────┐
│  ✏️ Edit BR-003                                         │
├─────────────────────────────────────────────────────────┤
│  Category:  [ Lead Scoring ▼ ]                          │
│                                                         │
│  Requirement:                                           │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [Textarea - texte éditable]                     │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Priority:  ○ Must  ● Should  ○ Could  ○ Won't         │
│                                                         │
│  Notes (optional):                                      │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [Textarea - notes client]                       │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  Original (from Sophie):                                │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [Affichage read-only du texte original]         │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  [ Cancel ]                        [ Save Changes ]     │
└─────────────────────────────────────────────────────────┘
```

### 5.5 Export CSV

Format du fichier exporté:
```csv
BR_ID,Category,Requirement,Priority,Status,Client_Notes,Original_Text,Created_At
BR-001,Lead Management,"Capture leads from multiple channels",must,validated,"Approved by sales team","...",2025-12-04T10:30:00
BR-002,Lead Management,"Auto-assign leads based on territory",should,modified,"Added territory rules","...",2025-12-04T10:30:00
```

---

## 6. ⚠️ Risques et Mitigations

| # | Risque | Probabilité | Impact | Mitigation |
|---|--------|-------------|--------|------------|
| 1 | Perte données projets existants | FAIBLE | CRITIQUE | Backup DB fait, pas de modification des tables existantes |
| 2 | Enum ProjectStatus incompatible | MOYEN | HAUT | Utiliser workflow_step au lieu de modifier l'enum |
| 3 | Frontend cassé après modification | MOYEN | MOYEN | Tests manuels après chaque changement |
| 4 | Migration Alembic échoue | FAIBLE | MOYEN | Tester en local d'abord, avoir script rollback |
| 5 | Performance extraction Sophie | FAIBLE | FAIBLE | Timeout configurable, streaming |

---

## 7. 🔄 Plan de Rollback

### 7.1 Git
```bash
# Revenir à l'état initial
git checkout main
git branch -D feature/br-validation  # Si besoin de tout supprimer
```

### 7.2 Base de Données
```bash
# Restaurer le backup
PGPASSWORD='DH_SecurePass2025!' psql -h localhost -U digital_humans digital_humans_db < backups/backup_before_br_validation_20251204_113010.sql
```

### 7.3 Alembic
```bash
# Annuler la dernière migration
cd backend && alembic downgrade -1
```

---

## 8. ✅ Checklist Pré-Implémentation

- [x] Backup base de données (15 Mo)
- [x] Tag Git créé (backup-before-br-validation-20251204)
- [x] Branche feature créée (feature/br-validation)
- [x] Inventaire complet des fichiers existants
- [x] Documentation des dépendances
- [x] Plan de rollback documenté
- [x] Spécifications détaillées des nouveaux composants
- [x] Wireframes interface utilisateur
- [x] Format export CSV défini
- [ ] Tests existants vérifiés (à faire avant implémentation)

---

## 9. 📋 Plan d'Implémentation Séquentiel

### Phase 1: Backend - Modèle et Migration (30 min)
1. Créer `app/models/business_requirement.py`
2. Ajouter relation dans `app/models/__init__.py`
3. Créer migration Alembic
4. Tester migration (up/down)
5. Commit: `feat(db): Add business_requirements table`

### Phase 2: Backend - Schemas (15 min)
1. Créer `app/schemas/business_requirement.py`
2. Tester avec pytest (si disponible)
3. Commit: `feat(api): Add BR schemas`

### Phase 3: Backend - Routes API (45 min)
1. Créer `app/api/routes/business_requirements.py`
2. Ajouter router dans `app/main.py`
3. Tester chaque endpoint avec curl/httpie
4. Commit: `feat(api): Add BR CRUD endpoints`

### Phase 4: Frontend - Page BRValidation (1h)
1. Créer `src/pages/BRValidationPage.tsx`
2. Ajouter route dans `App.tsx`
3. Tester navigation
4. Commit: `feat(ui): Add BR validation page shell`

### Phase 5: Frontend - Composants (1h)
1. Créer `BRTable.tsx` (tableau avec tri, filtre, pagination)
2. Créer `BREditModal.tsx`
3. Créer `BRAddModal.tsx`
4. Créer `BRExportButton.tsx`
5. Commit: `feat(ui): Add BR components`

### Phase 6: Intégration (30 min)
1. Ajouter endpoints dans `api.ts`
2. Connecter composants aux API
3. Tests E2E manuels
4. Commit: `feat: Integrate BR validation workflow`

### Phase 7: Sophie Extraction (30 min)
1. Modifier prompt Sophie pour extraction JSON structurée
2. Parser response et stocker dans DB
3. Commit: `feat: Sophie structured BR extraction`

---

## 10. 🎯 Critères de Succès

| Critère | Description | Validation |
|---------|-------------|------------|
| Tableau éditable | Affiche tous les BRs avec édition inline | ✓ Clic sur BR ouvre modal |
| Modification | Peut modifier requirement, category, priority | ✓ Sauvegarde en DB |
| Suppression | Peut supprimer un BR (soft delete) | ✓ Status = deleted |
| Ajout | Peut ajouter un BR manuel | ✓ Source = manual |
| Export CSV | Télécharge fichier CSV valide | ✓ Ouvre dans Excel |
| Validation | Peut valider tous les BRs | ✓ Passe à l'étape suivante |
| Historique | Garde trace du texte original | ✓ Affiché dans modal |
| Rollback | Peut revenir en arrière | ✓ Backup restaurable |

---

**Document créé le 4 décembre 2025**  
**Prêt pour implémentation après validation par Sam**
