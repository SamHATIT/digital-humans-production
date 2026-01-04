# 🔒 Liste des Correctifs - Revue de Code Digital Humans

**Date de l'analyse initiale**: 15 décembre 2025  
**Dernière mise à jour**: 4 janvier 2026

---

## 📊 Résumé

| Catégorie | Total | Résolus | Restants |
|-----------|-------|---------|----------|
| 🔴 CRITIQUE | 2 | 2 | 0 |
| 🟠 SÉCURITÉ | 3 | 3 | 0 |
| 🟡 CLEANUP | 2 | 2 | 0 |
| 🟢 PERFORMANCE | 1 | 0 | 1 |
| 🔵 DOCUMENTATION | 1 | 1 | 0 |
| **TOTAL** | **9** | **8** | **1** |

---

## 🔴 CRITIQUES

### BUG-010: Fix import SDS_PHASES cassé ✅ RÉSOLU
**Résolu le**: 29 décembre 2025

**Problème**: La route `/execute/{id}/resume` importait `SDS_PHASES` qui n'existait plus.

**Solution**: Code mort supprimé. Vérifié le 04/01/2026 : aucune occurrence de `SDS_PHASES` dans pm_orchestrator.py.

---

### SEC-001: Supprimer wildcard CORS ✅ RÉSOLU
**Résolu le**: 29 décembre 2025

**Problème**: CORS configuré avec `"*"` ET `allow_credentials=True`.

**Solution**: Wildcard supprimé, seuls les domaines explicites sont autorisés.
```python
# main.py ligne 39-51
allow_origins=[
    "http://72.61.161.222",
    "http://srv1064321.hstgr.cloud",
    # ... domaines spécifiques
    # Note: "*" removed for security
],
```

---

## 🟠 SÉCURITÉ

### SEC-002: Implémenter rate limiting API ✅ RÉSOLU
**Résolu le**: 29 décembre 2025

**Problème**: Aucune limite de requêtes.

**Solution**: `slowapi` installé avec configuration complète dans `backend/app/rate_limiter.py`:
- Login/Register: 5/minute par IP
- API authentifiée: 100-200/minute
- Exécutions LLM: 10/heure (SDS), 5/heure (BUILD)
- Headers `X-RateLimit-*` inclus
- Retourne 429 si dépassement

---

### SEC-003: Générer SECRET_KEY automatiquement ✅ RÉSOLU
**Résolu le**: 29 décembre 2025

**Problème**: App crash si `.env` mal configuré.

**Solution**: Dans `backend/app/config.py`:
- Dev (DEBUG=True): auto-génération avec `secrets.token_urlsafe(32)` + warning
- Prod (DEBUG=False): erreur explicite si SECRET_KEY manquant

---

### CLEAN-002: Supprimer mot de passe par défaut ✅ RÉSOLU
**Résolu le**: 29 décembre 2025

**Problème**: `POSTGRES_PASSWORD: ${DB_PASSWORD:-changeme}`

**Solution**: Valeur par défaut supprimée dans docker-compose.yml:
```yaml
POSTGRES_PASSWORD: ${DB_PASSWORD}
```

---

## 🟡 CLEANUP

### CLEAN-001: Supprimer fichiers .bak du repo ✅ RÉSOLU
**Résolu le**: 29 décembre 2025

**Solution**: 
- `*.bak*` ajouté à `.gitignore`
- Fichiers .bak existants ignorés par Git
- 2 fichiers locaux (backups de debug) non versionnés

---

## 🟢 PERFORMANCE

### PERF-001: Remplacer polling WebSocket par events ⏳ EN ATTENTE
**Priorité**: 3 | **Temps estimé**: 6h

**Problème**: 4 boucles `asyncio.sleep()` pour polling constant dans pm_orchestrator.py

**Impact**: Charge serveur inutile, latence updates.

**Solution proposée**: PostgreSQL LISTEN/NOTIFY ou Redis Pub/Sub

**Note**: Optimisation de performance, non bloquant pour la production.

---

## 🔵 DOCUMENTATION

### DOC-001: Compléter README setup ✅ RÉSOLU
**Résolu le**: Documenté dans CONTEXT.md

Les instructions de déploiement sont maintenant dans CONTEXT.md section configuration.

---

## ✅ Résumé Final

**8/9 tâches résolues** - Seule PERF-001 (optimisation performance) reste à faire.

Toutes les vulnérabilités de sécurité critiques ont été corrigées.
