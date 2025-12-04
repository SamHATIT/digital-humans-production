# Analyse d'Impact - Validation des Business Requirements

**Date**: 4 décembre 2025
**Version de référence**: main @ 9b7eeed
**Tag de sauvegarde**: backup-before-br-validation-20251204

---

## 1. Résumé Exécutif

### Objectif
Ajouter une étape de validation des Business Requirements (BRs) entre l'extraction par Sophie et l'exécution des agents. Cela permet au client de :
- Modifier/Supprimer/Ajouter des BRs
- Exporter en CSV pour validation interne
- Valider avant de continuer l'analyse

### ROI
- **Coût d'une erreur détectée à ce stade** : ~0.50€
- **Coût d'une erreur détectée après SDS** : ~10€+
- **Économie potentielle** : 95% par erreur

---

## 2. Fichiers Impactés

### 2.1 Backend - Modèles (À MODIFIER)

| Fichier | Impact | Modifications |
|---------|--------|---------------|
| `backend/app/models/project.py` | MOYEN | Nouveaux statuts dans `ProjectStatus` |
| `backend/app/models/execution.py` | AUCUN | Pas de modification nécessaire |
| **NOUVEAU** `backend/app/models/business_requirement.py` | NOUVEAU | Créer le modèle BR avec versioning |

### 2.2 Backend - Routes API (À MODIFIER)

| Fichier | Impact | Modifications |
|---------|--------|---------------|
| `backend/app/api/routes/projects.py` | HAUT | Nouvelles transitions de statuts |
| **NOUVEAU** `backend/app/api/routes/business_requirements.py` | NOUVEAU | CRUD pour BRs |
| `backend/app/api/routes/pm_orchestrator.py` | MOYEN | Endpoint extraction Sophie |

### 2.3 Backend - Schemas (À CRÉER)

| Fichier | Impact | Modifications |
|---------|--------|---------------|
| **NOUVEAU** `backend/app/schemas/business_requirement.py` | NOUVEAU | Schemas Pydantic pour BRs |

### 2.4 Frontend - Pages (À MODIFIER/CRÉER)

| Fichier | Impact | Modifications |
|---------|--------|---------------|
| **NOUVEAU** `frontend/src/pages/BRValidationPage.tsx` | NOUVEAU | Page principale de validation |
| `frontend/src/App.tsx` | FAIBLE | Ajouter la route |
| `frontend/src/pages/ExecutionPage.tsx` | MOYEN | Lien vers validation BR |

### 2.5 Base de Données (MIGRATION)

| Action | Risque | Notes |
|--------|--------|-------|
| Nouvelle table `business_requirements` | FAIBLE | Table additionnelle, pas de modification existante |
| Nouveaux statuts `ProjectStatus` | MOYEN | Nécessite migration Alembic |

---

## 3. Nouveaux Statuts de Projet

### 3.1 Workflow Actuel
```
DRAFT → READY → ACTIVE → SDS_COMPLETED → BUILDING → DEPLOYED
```

### 3.2 Workflow Proposé
```
DRAFT → UPLOADED → BRS_EXTRACTED → BRS_VALIDATED → EXECUTING → SDS_REVIEW → SDS_APPROVED → BUILD
                        │                │
                        ▼                ▼
                  Client review    Lance agents
                   des BRs         (Olivia+)
```

### 3.3 Mapping des Transitions

| Ancien Statut | Nouveau Statut | Notes |
|--------------|----------------|-------|
| DRAFT | DRAFT | Inchangé |
| READY | UPLOADED | Renommé pour clarté |
| ACTIVE | BRS_EXTRACTED → BRS_VALIDATED → EXECUTING | Divisé en 3 étapes |
| COMPLETED | SDS_APPROVED | Renommé |

---

## 4. Nouveau Modèle de Données

### 4.1 Table `business_requirements`

```sql
CREATE TABLE business_requirements (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER REFERENCES executions(id),
    br_id VARCHAR(20),  -- BR-001
    
    -- Contenu
    category VARCHAR(100),
    requirement TEXT,
    priority VARCHAR(20),  -- must, should, could, wont
    
    -- Source
    source VARCHAR(20),  -- 'extracted' ou 'manual'
    original_text TEXT,  -- Ce que Sophie avait extrait
    
    -- Validation
    status VARCHAR(20),  -- pending, validated, modified, deleted
    client_notes TEXT,
    validated_at TIMESTAMP,
    validated_by INTEGER REFERENCES users(id),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. Risques et Mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| Migration statuts existants | MOYEN | HAUT | Script de migration incrémentale |
| Incompatibilité frontend/backend | MOYEN | MOYEN | Tests E2E après chaque étape |
| Perte de données projets existants | FAIBLE | CRITIQUE | Backup DB avant migration |
| Performance extraction Sophie | FAIBLE | MOYEN | Timeout configurable |

---

## 6. Plan d'Implémentation

### Phase 1: Backend (2-3h)
1. ✅ Backup DB + Tag Git
2. Créer modèle `BusinessRequirement`
3. Créer migration Alembic
4. Créer schemas Pydantic
5. Créer routes API CRUD
6. Modifier transitions statuts

### Phase 2: Frontend (2-3h)
1. Créer `BRValidationPage.tsx`
2. Créer composants: BRTable, BREditModal
3. Intégrer dans le workflow existant
4. Tests manuels

### Phase 3: Intégration Sophie (1-2h)
1. Modifier prompt Sophie pour extraction structurée
2. Parser JSON response
3. Stocker dans `business_requirements`

### Phase 4: Tests & Validation (1h)
1. Test E2E complet
2. Validation avec données réelles
3. Documentation

---

## 7. Points de Rollback

### 7.1 Git
```bash
# Retour à l'état initial
git checkout backup-before-br-validation-20251204
```

### 7.2 Base de Données
```bash
# Restauration DB
PGPASSWORD='...' psql -h localhost -U digital_humans digital_humans_db < backups/backup_before_br_validation_20251204_113010.sql
```

### 7.3 Alembic
```bash
# Downgrade migration
cd backend && alembic downgrade -1
```

---

## 8. Checklist Avant de Commencer

- [x] Backup base de données effectué
- [x] Tag Git créé
- [x] Documentation des fichiers impactés
- [x] Plan de rollback documenté
- [ ] Branche feature créée
- [ ] Tests existants vérifiés

---

## 9. Commandes de Démarrage

```bash
# Créer branche feature
cd /root/workspace/digital-humans-production
git checkout -b feature/br-validation

# Vérifier que tout fonctionne encore
docker logs digital-humans-backend --tail 20
curl http://localhost:8000/health
```
