# Analyse d'Impact : Post-SDS Workflow

## Date: 2025-12-04
## Objectif: Ajouter le workflow post-SDS (Chat, Change Requests, Versioning)

---

## 1. NOUVELLES FONCTIONNALITÉS

### 1.1 Chat avec Sophie
- Interface de conversation contextuelle
- Sophie a accès à tous les artifacts du projet
- Historique des échanges sauvegardé

### 1.2 Change Requests
- Formulaire structuré par catégorie
- Analyse d'impact automatique par Sophie
- Workflow: DRAFT → SUBMITTED → ANALYZED → APPROVED → PROCESSING → COMPLETED
- Re-génération ciblée des sections impactées

### 1.3 Versioning SDS
- Chaque CR approuvée génère une nouvelle version
- Historique complet téléchargeable
- Version courante clairement identifiée

### 1.4 Validation SDS
- Bouton pour approuver le SDS
- Transition vers phase BUILD

---

## 2. MODÈLE DE DONNÉES

### 2.1 Nouvelles tables

```sql
-- Table pour les versions de SDS
CREATE TABLE sds_versions (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    execution_id INTEGER REFERENCES executions(id),
    version_number INTEGER NOT NULL,
    file_path VARCHAR(500),
    file_size INTEGER,
    generated_at TIMESTAMP,
    change_request_id INTEGER REFERENCES change_requests(id), -- NULL pour v1
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Table pour les Change Requests
CREATE TABLE change_requests (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    execution_id INTEGER REFERENCES executions(id),
    
    -- Classification
    cr_number VARCHAR(20), -- CR-001, CR-002...
    category VARCHAR(50), -- business_rule, data_model, process, ui, integration, security
    related_br_id INTEGER REFERENCES business_requirements(id),
    
    -- Contenu
    title VARCHAR(200),
    description TEXT,
    priority VARCHAR(20), -- low, medium, high, critical
    
    -- Analyse d'impact (JSON de Sophie)
    impact_analysis JSONB,
    estimated_cost DECIMAL(10,2),
    agents_to_rerun TEXT[], -- ['ba', 'architect', 'apex']
    
    -- Statut
    status VARCHAR(30) DEFAULT 'draft',
    
    -- Résultat
    resolution_notes TEXT,
    resulting_sds_version INTEGER,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    submitted_at TIMESTAMP,
    analyzed_at TIMESTAMP,
    approved_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Utilisateur
    created_by INTEGER REFERENCES users(id)
);

-- Table pour le chat projet
CREATE TABLE project_conversations (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    execution_id INTEGER REFERENCES executions(id),
    
    role VARCHAR(20), -- 'user' ou 'assistant'
    message TEXT,
    
    -- Contexte utilisé pour la réponse
    context_snapshot JSONB,
    
    -- Metadata
    tokens_used INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.2 Modification table projects

```sql
-- Nouveaux statuts à ajouter
ALTER TYPE projectstatus ADD VALUE 'SDS_GENERATED';
ALTER TYPE projectstatus ADD VALUE 'SDS_IN_REVIEW';
ALTER TYPE projectstatus ADD VALUE 'SDS_APPROVED';
ALTER TYPE projectstatus ADD VALUE 'BUILD_READY';

-- Nouveau champ
ALTER TABLE projects ADD COLUMN current_sds_version INTEGER DEFAULT 1;
```

---

## 3. FICHIERS À CRÉER

### Backend
- models/sds_version.py
- models/change_request.py  
- models/project_conversation.py
- schemas/sds_version.py
- schemas/change_request.py
- schemas/project_conversation.py
- api/routes/sds_versions.py
- api/routes/change_requests.py
- api/routes/project_chat.py
- services/sophie_chat_service.py (chat contextuel)
- services/change_request_service.py (analyse impact + re-génération)

### Frontend
- pages/ProjectDetailPage.tsx (refonte de ExecutionPage pour post-SDS)
- components/SophieChat.tsx
- components/ChangeRequestModal.tsx
- components/SDSVersionList.tsx
- components/ChangeRequestList.tsx

---

## 4. FICHIERS EXISTANTS IMPACTÉS

### Backend
| Fichier | Modification |
|---------|--------------|
| models/__init__.py | Ajouter imports nouveaux modèles |
| main.py | Enregistrer nouveaux routers |
| models/project.py | Ajouter relation sds_versions, change_requests |
| models/execution.py | Ajouter relation sds_versions |

### Frontend
| Fichier | Modification |
|---------|--------------|
| App.tsx | Ajouter route /project/:id |
| constants.ts | Ajouter nouvelles constantes |
| services/api.ts | Ajouter endpoints chat, CR, versions |
| pages/Dashboard.tsx | Click projet → ProjectDetailPage |
| pages/Projects.tsx | Click projet → ProjectDetailPage |

---

## 5. WORKFLOW DÉTAILLÉ

### 5.1 Après génération SDS
```
Execution COMPLETED 
    → Créer sds_versions (version 1)
    → Project.status = SDS_GENERATED
    → Project.current_sds_version = 1
```

### 5.2 Client revient sur projet
```
Click projet 
    → Si status in [SDS_GENERATED, SDS_IN_REVIEW]
        → Afficher ProjectDetailPage avec:
            - Liste versions SDS
            - Chat Sophie
            - Bouton New CR
            - Bouton Approve SDS
```

### 5.3 Change Request
```
1. Client clique "New CR"
2. Remplit formulaire (catégorie, BR lié, description)
3. Soumet → status = SUBMITTED
4. Sophie analyse:
   - Charge contexte projet (BRs, UCs, Arch, SDS)
   - Identifie impacts
   - Calcule agents à relancer
   - Estime coût
5. Affiche analyse → status = ANALYZED
6. Client approuve → status = APPROVED
7. Orchestrateur relance agents ciblés
8. Nouveau SDS généré → sds_versions (version N+1)
9. CR status = COMPLETED
```

### 5.4 Validation SDS
```
Client clique "Approve SDS"
    → Project.status = SDS_APPROVED
    → Afficher options BUILD (phase suivante)
```

---

## 6. RISQUES ET MITIGATIONS

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Complexité re-génération partielle | Élevé | V1: Re-générer sections complètes, pas delta |
| Context window Sophie | Moyen | Résumer artifacts, pas tout envoyer |
| Conflits versions SDS | Faible | Une seule CR active à la fois |
| Perte données | Élevé | Backup DB avant migration |

---

## 7. ESTIMATION EFFORT

| Composant | Effort |
|-----------|--------|
| DB + Models | 1h |
| API endpoints | 2h |
| Sophie Chat Service | 1.5h |
| CR Analysis Service | 2h |
| Frontend ProjectDetailPage | 2h |
| Frontend components | 1.5h |
| Tests | 1h |
| **TOTAL** | **~11h** |

---

## 8. ORDRE D'IMPLÉMENTATION

1. ✅ Backup DB + Git tag
2. Créer tables DB (sds_versions, change_requests, project_conversations)
3. Créer models + schemas
4. Créer API endpoints basiques (CRUD)
5. Créer Sophie Chat Service
6. Créer frontend ProjectDetailPage
7. Intégrer Chat Sophie
8. Ajouter CR workflow
9. Ajouter versioning SDS
10. Tests E2E
