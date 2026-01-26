# Digital Humans - État Actuel

**Dernière mise à jour:** 26 janvier 2026

---

## 📊 Métriques Projet

| Métrique | Valeur |
|----------|--------|
| Features totales | 171 |
| Complétées | 142 (83%) |
| En cours | SDS v3 micro-analyse |

---

## 🎯 Priorités Actuelles

### P0 - En cours : SDS v3 Micro-Analyse

**Objectif:** Réduire coût SDS de 10-12€ à ~2€ tout en améliorant la qualité

**État:**
- ✅ Table `uc_requirement_sheets` créée
- ✅ Route `POST /execute/{id}/microanalyze` fonctionnelle
- ✅ Route `GET /execute/{id}/requirement-sheets` fonctionnelle  
- ✅ Test réussi: 8/8 UCs analysés, 18 min, $0 (Mistral local)
- ⏳ Intégrer dans pipeline SDS complet

**Prochaines étapes:**
1. Créer `pm_orchestrator_service_v3.py` (intégrer micro-analyse après Phase 2 Olivia)
2. Créer prompt synthèse Claude (agréger fiches → SDS cohérent)
3. Tester sur projet 120+ UCs
4. Comparer qualité/coût vs v2

### P1 - Validation Cohérence

**Problème identifié:** Olivia génère parfois des incohérences (ex: Case vs Service_Request__c pour même concept)

**Solution:** Ajouter validation Emma pour détecter objets SF incohérents

### P2 - Sécurité Restante

- PERF-001: Remplacer polling WebSocket par events PostgreSQL LISTEN/NOTIFY (~6h)

---

## 🔧 Services Actifs

| Service | Port | État |
|---------|------|------|
| Backend FastAPI | 8002 | ✅ |
| Frontend React | 3000 | ✅ |
| PostgreSQL | 5432 | ✅ (service système) |
| Ollama (Mistral) | 11434 | ✅ |
| Ghost CMS | 2368 | ✅ |
| Blog API | 8765 | ✅ |
| N8N | 5678 | ✅ |

---

## 📁 Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `features.json` | État des 171 features |
| `CURRENT_STATE.md` | Ce fichier - priorités actuelles |
| `SECURITY_TASKS.md` | 8/9 résolus, reste PERF-001 |

---

## 🚀 Commandes Rapides

```bash
# Vérifier services
curl -s http://localhost:8002/health  # Backend
curl -s http://localhost:11434/api/tags | jq  # Ollama

# Lancer micro-analyse (avec token user 2)
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZXhwIjoxNzY5NTM4ODI3fQ.ezj-NJnptM6K0yIrFjhPV5JbSt8V-v6tsSLZ_jSjqCI"
curl -X POST "http://localhost:8002/api/pm-orchestrator/execute/{id}/microanalyze" -H "Authorization: Bearer $TOKEN"

# Redémarrer backend
pkill -f "uvicorn.*8002"
nohup bash -c 'cd /root/workspace/digital-humans-production/backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8002' > /var/log/dh-backend.log 2>&1 &
```

---

*Note: L'historique complet est dans `docs/archives/PROGRESS_archive_*.log`*
