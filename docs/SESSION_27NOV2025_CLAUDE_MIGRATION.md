# 📋 SESSION 27 NOVEMBRE 2025 - Migration Claude API

**Date:** 27 novembre 2025
**Objectif:** Migrer tous les agents de GPT-4 vers Claude API avec stratification par tier

---

## ✅ TRAVAIL ACCOMPLI

### 1. LLM Service Créé
**Fichier:** `backend/app/services/llm_service.py`

- Support multi-provider (Anthropic + OpenAI fallback)
- Stratification par tier d'agent :
  - **ORCHESTRATOR (PM):** Claude Opus 4.5 - Meilleur raisonnement
  - **ANALYST (BA, Architect):** Claude Sonnet 4.5 - Équilibré
  - **WORKER (Apex, LWC, Admin, QA, etc.):** Claude Haiku 4.5 - Rapide & économique
- Fallback automatique vers OpenAI si Anthropic échoue

### 2. Agents Migrés (9 agents)
| Agent | Tier | Modèle Claude |
|-------|------|---------------|
| BA (Olivia) | Analyst | claude-sonnet-4-5 |
| Architect (Marcus) | Analyst | claude-sonnet-4-5 |
| Apex (Diego) | Worker | claude-haiku-4-5 |
| LWC (Zara) | Worker | claude-haiku-4-5 |
| Admin (Raj) | Worker | claude-haiku-4-5 |
| QA (Elena) | Worker | claude-haiku-4-5 |
| Trainer (Lucas) | Worker | claude-haiku-4-5 |
| DevOps (Jordan) | Worker | claude-haiku-4-5 |
| Data Migration (Aisha) | Worker | claude-haiku-4-5 |

### 3. Infrastructure
- Clé `ANTHROPIC_API_KEY` ajoutée au `.env` et `docker-compose.yml`
- Package `anthropic==0.39.0` ajouté aux requirements
- Script de rollback créé : `scripts/rollback_to_openai.sh`

---

## 📊 TESTS EFFECTUÉS

### Test Claude Sonnet (BA tier)
```
Provider: anthropic
Model: claude-sonnet-4-5-20250929
Tokens: 160
✅ Réponse de qualité sur Salesforce best practices
```

### Test Claude Haiku (Apex tier)
```
Provider: anthropic
Model: claude-haiku-4-5-20251001
Tokens: 280
✅ Code Apex valide généré (trigger avec bulkification)
```

---

## 💰 IMPACT COÛT ESTIMÉ

| Tier | Modèle | Input/1M | Output/1M | Usage type |
|------|--------|----------|-----------|------------|
| Orchestrator | Opus 4.5 | $15.00 | $75.00 | 1-2x/projet |
| Analyst | Sonnet 4.5 | $3.00 | $15.00 | 2-4x/projet |
| Worker | Haiku 4.5 | $1.00 | $5.00 | 5-10x/projet |

**Estimation par exécution complète:** ~$2-5 (vs ~$5-10 avec GPT-4 seul)

---

## 🔄 ROLLBACK

En cas de problème :
```bash
cd /root/workspace/digital-humans-production
./scripts/rollback_to_openai.sh
```

Ou via Git :
```bash
git checkout backup-pre-claude-migration-27nov2025 -- backend/
docker restart digital-humans-backend
```

---

## 🎯 PROCHAINE ÉTAPE

**Tester une exécution complète** avec le nouveau système :
1. Créer un nouveau projet via l'interface
2. Lancer une exécution avec BA + Architect
3. Vérifier :
   - Nombre de BR produits (objectif: 15-25)
   - Nombre de UC produits (objectif: 30-60)
   - Qualité de la décomposition atomique
   - Questions Q-xxx de l'Architect

---

## 📁 COMMITS

- `2e1fa27` - feat(llm): Migrate all agents to Claude API with tier-based model selection
- `19d9f62` - fix(llm): Update Claude model names to correct versions

**Tag de backup:** `backup-pre-claude-migration-27nov2025`
