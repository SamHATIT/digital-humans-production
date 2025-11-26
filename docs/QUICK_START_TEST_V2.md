# 🚀 QUICK START - TEST V2 AVEC GPT-4

## Contexte
Session du 26 novembre 2025. Architecture V2 implémentée avec:
- PM Agent (Sophie) - orchestrateur
- BA Agent (Olivia) - BR + UC  
- Architect Agent (Marcus) - ADR + SPEC + itérations Q&A
- 6 validation gates
- Système d'artifacts persistants

## Execution à tester
- **Execution ID:** 40
- **Project ID:** 31 (Concessionnaire auto)
- **Status:** Initialisé, 6 gates créées, Gate 1 pending

## Commandes de test

```bash
# 1. Vérifier l'état actuel
curl -s "http://localhost:8002/api/v2/orchestrator/status/40" | python3 -m json.tool

# 2. Phase 0: PM Analysis (créer REQ + PLAN)
curl -X POST "http://localhost:8002/api/v2/orchestrator/phase/pm-analysis" \
  -H "Content-Type: application/json" \
  -d @/root/workspace/digital-humans-production/docs/test_request_phase0.json

# 3. Phase 1: BA Analysis (créer BR + UC)
curl -X POST "http://localhost:8002/api/v2/orchestrator/phase/analysis" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40}'

# 4. Approuver Gate 1
curl -X POST "http://localhost:8002/api/v2/orchestrator/gate/approve" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40}'

# 5. Phase 2: Architecture (ADR + SPEC avec itérations)
curl -X POST "http://localhost:8002/api/v2/orchestrator/phase/architecture" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40}'

# 6. Si auto_continue=true, continuer:
curl -X POST "http://localhost:8002/api/v2/orchestrator/phase/architecture/continue" \
  -H "Content-Type: application/json" \
  -d '{"execution_id": 40}'

# 7. Voir les artifacts créés
curl -s "http://localhost:8002/api/v2/artifacts?execution_id=40" | python3 -m json.tool

# 8. Voir le graphe de dépendances
curl -s "http://localhost:8002/api/v2/graph?execution_id=40" | python3 -m json.tool
```

## Fichiers clés
- `/root/workspace/digital-humans-production/backend/agents_v2/` - Agents V2
- `/root/workspace/digital-humans-production/docs/SESSION_26NOV2025_SAUVEGARDE.md` - Sauvegarde complète

## TODO après le test
1. Comparer qualité avec SDS du matin (note 4/10)
2. Implémenter agents workers si résultats OK
3. Créer interface frontend
