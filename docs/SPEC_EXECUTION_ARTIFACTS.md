# SPÉCIFICATION TECHNIQUE - EXECUTION ARTIFACTS
**Date:** 26 Novembre 2025 | **Version:** 1.0

---

## 1. SCHÉMA BASE DE DONNÉES

### 1.1 Table principale : execution_artifacts

```sql
CREATE TABLE execution_artifacts (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    artifact_type VARCHAR(50) NOT NULL,
    artifact_code VARCHAR(20) NOT NULL,  -- UC-001, BR-001, ADR-001
    producer_agent VARCHAR(20) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    title VARCHAR(255) NOT NULL,
    content JSONB NOT NULL,
    parent_refs JSONB,  -- ["UC-001", "UC-003"]
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT valid_artifact_type CHECK (artifact_type IN (
        'requirement', 'use_case', 'business_rule', 'question',
        'adr', 'spec', 'code', 'config', 'test', 'doc'
    ))
);

CREATE INDEX idx_artifacts_execution ON execution_artifacts(execution_id);
CREATE INDEX idx_artifacts_type ON execution_artifacts(artifact_type);
CREATE INDEX idx_artifacts_code ON execution_artifacts(artifact_code);
CREATE INDEX idx_artifacts_content ON execution_artifacts USING GIN (content);
```

### 1.2 Table artifact_dependencies

```sql
CREATE TABLE artifact_dependencies (
    id SERIAL PRIMARY KEY,
    source_artifact_id INTEGER REFERENCES execution_artifacts(id),
    target_artifact_id INTEGER REFERENCES execution_artifacts(id),
    dependency_type VARCHAR(30) NOT NULL  -- implements, derives_from, answers, tests
);
```

### 1.3 Table agent_conversations

```sql
CREATE TABLE agent_conversations (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER REFERENCES executions(id),
    from_agent VARCHAR(20) NOT NULL,
    to_agent VARCHAR(20) NOT NULL,
    message_type VARCHAR(20) NOT NULL,  -- question, answer, request, delivery
    content TEXT NOT NULL,
    related_artifacts JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 2. TYPES D'ARTEFACTS

| Code | Type | Producteur | Description |
|------|------|------------|-------------|
| REQ | requirement | PM | Input utilisateur parsé |
| UC | use_case | BA | Cas d'utilisation |
| BR | business_rule | BA | Règle métier |
| Q | question | BA/Architect | Question inter-agent |
| ADR | adr | Architect | Architecture Decision Record |
| SPEC | spec | Architect | Spécification technique |
| CODE | code | Workers | Code généré |
| CFG | config | Admin | Configuration SF |
| TEST | test | QA | Cas de test |
| DOC | doc | Trainer | Documentation |

---

## 3. EXEMPLES JSON

### Use Case (UC)
```json
{
  "artifact_code": "UC-003",
  "title": "Scoring comportemental des leads",
  "content": {
    "actors": {"primary": "Système"},
    "trigger": "Création Lead",
    "main_flow": [...],
    "postconditions": [...],
    "related_business_rules": ["BR-007", "BR-008"]
  }
}
```

### Business Rule (BR)
```json
{
  "artifact_code": "BR-007",
  "title": "Score par source",
  "content": {
    "rule_type": "scoring",
    "rule_definition": {
      "Partner Portal": 25,
      "Phone": 20,
      "Web": 15
    },
    "parent_refs": ["UC-003"]
  }
}
```

### Question (Q)
```json
{
  "artifact_code": "Q-004",
  "content": {
    "from_agent": "architect",
    "to_agent": "admin",
    "question": "Limites Territory Rules pour stock?",
    "response": {
      "answer": "TM2 ne supporte pas règles sur objets liés",
      "recommendation": "Assignment Rules + Apex"
    }
  }
}
```

### ADR
```json
{
  "artifact_code": "ADR-003",
  "title": "Stratégie assignation leads",
  "content": {
    "decision": "Assignment Rules + Apex enrichissement",
    "options_evaluated": [...],
    "consequences": {...},
    "parent_refs": ["UC-012", "Q-004"]
  }
}
```

### Spec
```json
{
  "artifact_code": "SPEC-012",
  "title": "LeadScoringService",
  "content": {
    "component_type": "apex_class",
    "implements_use_cases": ["UC-003"],
    "implements_business_rules": ["BR-007"...],
    "interface": {...},
    "assigned_to": "apex"
  }
}
```

---

## 4. FLUX DE CRÉATION

```
REQ-001 (PM)
    ↓
UC-001..N (BA) → BR-001..N (BA)
    ↓
[Q si besoin] → Réponse Worker
    ↓
ADR-001..N (Architect)
    ↓
SPEC-001..N (Architect)
    ↓
CODE/CFG (Workers) → TEST (QA) → DOC (Trainer)
```

---

## 5. CONTEXTE PAR AGENT

### BA reçoit:
- REQ complet
- UC/BR existants (si itération)
- Questions pending de l'Architect

### Architect reçoit:
- REQ condensé
- Tous UC + BR
- Réponses aux questions

### Worker reçoit:
- SPEC assignées
- UC/BR/ADR référencés

---

## 6. API ENDPOINTS

```
POST   /api/artifacts/                    # Créer
GET    /api/artifacts/?execution_id=X     # Lister
GET    /api/artifacts/{code}              # Lire
PUT    /api/artifacts/{code}              # Update (new version)
GET    /api/artifacts/for-agent/{agent}   # Contexte agent
GET    /api/artifacts/graph               # Visualisation
```

---

*Spec v1.0 - 26 novembre 2025*
