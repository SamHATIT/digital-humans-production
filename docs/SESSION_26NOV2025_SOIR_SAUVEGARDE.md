# 📋 SAUVEGARDE SESSION 26 NOVEMBRE 2025 - SOIR

**Date:** 26 novembre 2025, 17h30 UTC
**Dernière exécution:** #46
**Branche:** main
**Dernier commit:** ae26872

---

## 🎯 OBJECTIF DE LA SESSION

Tester le nouveau workflow V2 avec :
- Décomposition atomique des BR (15-25 BR au lieu de 5)
- Itérations BA ↔ Architect (questions Q-xxx)
- Traçabilité Source Requirement

---

## 📊 RÉSULTAT DU TEST #46

### Métriques

| Métrique | Attendu | Obtenu | Status |
|----------|---------|--------|--------|
| BR produits | 15-25 | 5 | ❌ |
| UC produits | 30-60 | 4 | ❌ |
| ADR produits | 8-15 | 2 | ❌ |
| SPEC produits | 25-50 | 2 | ❌ |
| Questions Q-xxx | ≥1 | 0 | ❌ |
| Itérations BA↔Architect | 1-3 | 0 | ❌ |
| SDS généré | Oui | Oui (48KB) | ✅ |

### Problèmes Identifiés

1. **GPT-4 ne suit pas les instructions** - Malgré les prompts modifiés demandant 15-25 BR atomiques, il produit toujours 5 BR génériques
2. **Architect ne pose pas de questions** - Le prompt demande des Q-xxx mais l'Architect génère directement les ADR/SPEC
3. **Itérations non déclenchées** - Sans questions Q-xxx, la boucle d'itération ne s'active pas

### SDS Disponible

- URL: https://digital-humans.fr/downloads/SDS_46_Test_V2_Iterations_-_Concessionnaire_Auto.docx
- Taille: 48 KB
- Comparaison avec référence: qualité insuffisante (même niveau que #44)

---

## ✅ CE QUI A ÉTÉ FAIT

### 1. Prompts Modifiés

**BA (salesforce_business_analyst.py):**
- Section "ATOMIC DECOMPOSITION RULES" ajoutée
- "Source Requirement" obligatoire pour chaque BR
- Minimum 15-25 BR, 30-60 UC
- Section "Answering Architect Questions"

**Architect (salesforce_solution_architect.py):**
- Section "CLARIFICATION PHASE" ajoutée
- Format Q-xxx pour questions
- Minimum 8-15 ADR, 25-50 SPEC

### 2. Logique d'Itération (pm_orchestrator_service.py)

```python
MAX_ITERATIONS = 3
use_iteration_mode = "ba" in sorted_agents and "architect" in sorted_agents
_handle_ba_architect_iterations()  # Gère la boucle BA↔Architect
_ba_answer_questions()  # BA répond aux Q-xxx
```

### 3. Correction Bug Import

```python
# Corrigé: from app.models.execution_artifact → from app.models.artifact
```

### 4. Commits

- `ae26872` - feat(v2): Implement BA-Architect iteration workflow with atomic decomposition
- `1368254` - docs: Add test guide for V2 iterations workflow

---

## 🔧 PROCHAINE ÉTAPE PROPOSÉE

### Tester avec Claude au lieu de GPT-4

Claude est souvent meilleur pour suivre des instructions structurées complexes.

**Modifications nécessaires (~45 min):**

```python
# AVANT (OpenAI)
from openai import OpenAI
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=16000
)
output = response.choices[0].message.content

# APRÈS (Claude)
from anthropic import Anthropic
client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=16000,
    messages=[{"role": "user", "content": prompt}]
)
output = response.content[0].text
```

**Fichiers à modifier:**
- backend/agents/roles/salesforce_business_analyst.py
- backend/agents/roles/salesforce_solution_architect.py
- backend/agents/roles/salesforce_developer_apex.py
- backend/agents/roles/salesforce_developer_lwc.py
- backend/agents/roles/salesforce_admin.py
- backend/agents/roles/salesforce_qa_tester.py
- backend/agents/roles/salesforce_trainer.py
- backend/agents/roles/salesforce_devops.py
- backend/agents/roles/salesforce_data_migration.py

**Ou créer une abstraction LLM:**
- backend/app/services/llm_service.py (nouveau)

---

## 📁 FICHIERS CLÉS

```
backend/
├── app/services/pm_orchestrator_service.py  # Logique d'itération V2
├── agents/roles/
│   ├── salesforce_business_analyst.py       # Prompt BA modifié
│   └── salesforce_solution_architect.py     # Prompt Architect modifié
└── app/models/artifact.py                   # Modèle ExecutionArtifact

docs/
├── SESSION_26NOV2025_SOIR_SAUVEGARDE.md     # CE FICHIER
├── RECAP_V2_ARTIFACTS_26NOV2025.md          # Recap V2 artifacts
└── SPEC_FINALE_DIGITAL_HUMANS_V2.md         # Spec architecture V2
```

---

## 🗄️ BASE DE DONNÉES

- **Projet #36:** Test V2 Iterations - Concessionnaire Auto
- **Exécution #46:** completed, 13 artifacts (5 BR, 4 UC, 2 ADR, 2 SPEC)
- **Token:** Regénérer avec login admin@digital-humans.com / test123

---

## 🚀 POUR REPRENDRE

```bash
# 1. Vérifier l'état
cd /root/workspace/digital-humans-production
git status
docker ps

# 2. Se connecter
curl -s -X POST http://localhost:8002/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@digital-humans.com", "password": "test123"}'

# 3. Option A: Relancer un test avec GPT-4 (prompts plus stricts)
# 4. Option B: Migrer vers Claude API
```

---

## 📝 NOTES

- Le problème n'est pas dans le code mais dans la capacité de GPT-4 à suivre des instructions complexes
- Les prompts sont techniquement corrects mais GPT-4 les "résume" au lieu de les suivre littéralement
- Claude Sonnet pourrait mieux respecter les contraintes de décomposition atomique
- Alternative: forcer programmatiquement (rejeter si < 10 BR, relancer)

