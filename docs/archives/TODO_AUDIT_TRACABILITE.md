# TODO - Système d'Audit et Traçabilité

**Créé** : 4 décembre 2025  
**Priorité** : Post-test E2E  
**Estimation** : ~4-6h total  

---

## 🎯 Objectif

Implémenter un système d'audit complet pour la conformité SOC2/ISO27001 et le suivi des équipes de sécurité.

---

## 📋 Éléments à Implémenter

### 1. Table `audit_logs` (2h)

```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Contexte
    user_id UUID REFERENCES users(id),
    user_email VARCHAR(255),
    session_id VARCHAR(255),
    ip_address INET,
    user_agent TEXT,
    
    -- Action
    action VARCHAR(100) NOT NULL,  -- CREATE, UPDATE, DELETE, VIEW, EXPORT, LOGIN, etc.
    entity_type VARCHAR(100) NOT NULL,  -- project, business_requirement, execution, etc.
    entity_id UUID,
    
    -- Détails
    old_values JSONB,  -- Snapshot avant modification
    new_values JSONB,  -- Snapshot après modification
    changed_fields TEXT[],  -- Liste des champs modifiés
    
    -- Métadonnées
    request_path VARCHAR(500),
    request_method VARCHAR(10),
    response_status INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index pour recherches fréquentes
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

### 2. Middleware FastAPI (1h)

```python
# backend/app/middleware/audit_middleware.py
- Capture automatique de chaque requête
- Extraction user_id depuis JWT
- Logging IP, user_agent, path, method
- Intégration avec le service d'audit
```

### 3. Service d'Audit (1h)

```python
# backend/app/services/audit_service.py
class AuditService:
    async def log_action(
        user_id, action, entity_type, entity_id,
        old_values=None, new_values=None, request=None
    )
    
    async def get_entity_history(entity_type, entity_id)
    async def get_user_activity(user_id, start_date, end_date)
    async def export_audit_log(filters, format='csv')
```

### 4. Triggers sur tables critiques (1h)

Tables à auditer automatiquement :
- `business_requirements` (CREATE, UPDATE, DELETE)
- `projects` (CREATE, UPDATE, DELETE, status changes)
- `executions` (CREATE, status changes)
- `change_requests` (all actions)
- `sds_versions` (CREATE)
- `users` (LOGIN, UPDATE)

### 5. Endpoints API Export (30min)

```
GET  /api/audit/logs              - Liste paginée avec filtres
GET  /api/audit/logs/export       - Export CSV/JSON
GET  /api/audit/entity/{type}/{id} - Historique d'une entité
GET  /api/audit/user/{user_id}    - Activité d'un utilisateur
```

### 6. Interface Admin (optionnel, 2h+)

- Dashboard activité récente
- Recherche avancée
- Export rapports
- Alertes anomalies

---

## 🔍 Actions à Tracer

| Catégorie | Actions |
|-----------|---------|
| Auth | LOGIN, LOGOUT, LOGIN_FAILED, PASSWORD_CHANGE |
| Project | CREATE, UPDATE, DELETE, STATUS_CHANGE |
| BR | CREATE, UPDATE, DELETE, VALIDATE, PRIORITIZE |
| Execution | START, COMPLETE, FAIL, CANCEL |
| CR | CREATE, SUBMIT, ANALYZE, APPROVE, REJECT |
| SDS | GENERATE, DOWNLOAD, APPROVE |
| Chat | MESSAGE_SENT (sans contenu, juste metadata) |
| Export | EXPORT_PDF, EXPORT_DOCX |

---

## 📊 État Actuel vs Cible

| Élément | Actuel | Cible |
|---------|--------|-------|
| Logs applicatifs (console) | ✅ 200+ | ✅ |
| Timestamp modifications | ✅ `updated_at` | ✅ |
| Valeur originale BR | ✅ `original_text` | ✅ |
| Historique multi-modifs | ❌ | ✅ Table audit |
| User ID sur actions | ❌ | ✅ |
| IP tracking | ❌ | ✅ |
| Export audit | ❌ | ✅ |
| Rétention configurable | ❌ | ✅ |

---

## 🔐 Considérations Sécurité

- [ ] Audit logs en append-only (pas de DELETE/UPDATE)
- [ ] Chiffrement données sensibles dans JSONB
- [ ] Rétention 90 jours minimum (configurable)
- [ ] Accès restreint aux admins
- [ ] Alertes sur patterns suspects (multiple login failures, etc.)

---

## 📅 Planning Suggéré

1. **Sprint 1** : Table + Service + Middleware (3h)
2. **Sprint 2** : Triggers + Endpoints export (2h)  
3. **Sprint 3** : Interface admin (optionnel)

