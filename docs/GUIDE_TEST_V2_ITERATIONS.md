# 🧪 Guide de Test - Workflow V2 avec Itérations BA ↔ Architect

**Date:** 26 Novembre 2025  
**Version:** 2.2.0  
**Commit:** ae26872

---

## 📋 Résumé des Modifications

### 1. Prompt BA - Décomposition Atomique
- **1 BR par requirement** (pas de regroupement)
- **Source Requirement obligatoire** (citation exacte)
- **Minimum 15-25 BR** pour projets complexes
- **Section "Answering Architect Questions"** pour répondre aux Q-xxx

### 2. Prompt Architecte - Phase de Clarification
- **Questions Q-xxx** avant production ADR/SPEC
- **Format standardisé** pour questions (Context, Question, Impact)
- **Minimum 8-15 ADR, 25-50 SPEC**
- Attend les réponses avant de finaliser

### 3. Logique d'Itération
- **MAX_ITERATIONS = 3**
- BA exécuté d'abord
- Architecte peut poser questions
- BA répond automatiquement
- Boucle jusqu'à pas de questions ou max iterations

---

## 🚀 Comment Tester

### Option 1: Via l'Interface Web

1. Aller sur https://digital-humans.fr
2. Se connecter
3. Créer un nouveau projet avec les requirements du concessionnaire auto
4. Sélectionner **seulement BA + Architect** (pas les workers)
5. Lancer l'exécution
6. Observer:
   - Les BR générés (devraient être 15-20, pas 5)
   - Les questions Q-xxx de l'Architecte
   - Les réponses du BA
   - Les ADR/SPEC finaux

### Option 2: Via API (Curl)

```bash
# 1. Login
TOKEN=$(curl -s -X POST https://digital-humans.fr/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"xxx"}' | jq -r '.access_token')

# 2. Créer projet
PROJECT=$(curl -s -X POST https://digital-humans.fr/api/pm-orchestrator/projects \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test V2 Iterations",
    "business_requirements": "PASTE REQUIREMENTS HERE",
    "salesforce_product": "Sales Cloud"
  }')
echo $PROJECT | jq

# 3. Lancer exécution (BA + Architect only)
EXEC=$(curl -s -X POST "https://digital-humans.fr/api/pm-orchestrator/projects/$(echo $PROJECT | jq -r '.id')/execute" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"selected_agents": ["ba", "architect"]}')
echo $EXEC | jq
```

---

## ✅ Critères de Succès

| Critère | Avant (v2.1) | Attendu (v2.2) |
|---------|--------------|----------------|
| Nombre de BR | 5 génériques | 15-25 atomiques |
| Source Requirement | ❌ Absent | ✅ Citation exacte |
| Questions Architect | ❌ Aucune | ✅ 3-8 Q-xxx |
| Itérations | ❌ 0 | ✅ 1-3 |
| Nombre ADR | 2 | 8-15 |
| Nombre SPEC | 2 | 25-50 |
| Contexte métier | ❌ Générique | ✅ Spécifique |

---

## 📊 Vérification Post-Test

### Vérifier les BR
```bash
# Compter les BR
curl -s "https://digital-humans.fr/api/executions/EXEC_ID/artifacts?type=business_req" \
  -H "Authorization: Bearer $TOKEN" | jq 'length'
```

### Vérifier les Questions
```bash
# Voir les questions posées
curl -s "https://digital-humans.fr/api/executions/EXEC_ID/artifacts?type=question" \
  -H "Authorization: Bearer $TOKEN" | jq '.[] | {code: .artifact_code, question: .content.question}'
```

### Vérifier les Itérations (dans les logs)
```bash
docker-compose logs backend | grep "V2 Iteration"
```

---

## 🐛 Problèmes Connus

1. **Si aucune question posée**: L'Architecte a peut-être reçu des BR suffisamment clairs
2. **Si > 3 itérations**: Vérifier que MAX_ITERATIONS est bien à 3
3. **Si BR toujours génériques**: Vérifier que le prompt BA a bien été mis à jour

---

## 📁 Fichiers Modifiés

- `backend/agents/roles/salesforce_business_analyst.py` - Prompt BA
- `backend/agents/roles/salesforce_solution_architect.py` - Prompt Architect
- `backend/app/services/pm_orchestrator_service.py` - Logique itération

---

## 🔄 Rollback si Problème

```bash
git revert ae26872
docker-compose restart backend
```
