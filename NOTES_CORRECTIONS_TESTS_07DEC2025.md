# 📝 NOTES DE CORRECTIONS - Session de Tests 07 Décembre 2025

## Tests Effectués
- Sophie (PM) ✅ - Extrait 20 BRs correctement
- Olivia (BA) ✅ - Génère 5 UCs cohérents pour BR-001
- Marcus (Architect) ✅ - Solution Design complet et pertinent
- Aisha (Data Migration) ⚠️ - Output overkill / mal utilisée

---

## 🚨 PROBLÈME #1 : Aisha appelée à tort

**Constat :**
- Aisha génère un plan de migration de 115 pages pour une simple capture de leads
- Elle suppose un "Legacy CRM Oracle 12c" avec 250,000 records à migrer
- Budget estimé $198,000 pour 9 personnes sur 12 semaines
- Complètement hors sujet pour un projet greenfield

**Cause :**
- Le prompt d'Aisha est conçu pour des **migrations de données**
- Elle ne devrait être appelée QUE si :
  1. Il y a un système existant avec données à migrer
  2. Marcus identifie explicitement un besoin de migration

**Correction à faire :**
1. Ajouter une logique de décision dans l'orchestrateur :
   - SI project_type == "greenfield" ALORS skip Aisha
   - SI project_type == "migration" OU Marcus.output contient "legacy system" ALORS call Aisha
2. Ou demander explicitement dans le brief initial si c'est une migration ou un nouveau projet
3. Modifier le workflow pour rendre Aisha optionnelle selon le contexte

---

## 🔧 PROBLÈME #2 : Format d'input incohérent entre agents

**Constat :**
- Sophie : accepte texte brut → retourne JSON structuré
- Olivia : attend JSON (BR) → retourne JSON (UCs)
- Marcus : attend JSON (UCs + summary) → retourne JSON (architecture)
- Aisha : attend texte brut → retourne markdown + JSON

**Correction à faire :**
1. Standardiser les formats d'input/output pour faciliter le chaînage
2. Documenter clairement le "contrat" de chaque agent
3. Créer des transformateurs automatiques entre agents si nécessaire

---

## 📋 PROBLÈME #3 : Agents tentent de déployer vers Salesforce

**Constat :**
- Sophie et Aisha tentent un "Déploiement vers Salesforce" à la fin
- Échec car ils n'ont pas de code à déployer

**Correction à faire :**
1. Conditionner le déploiement au type d'agent (seulement pour Diego, Zara, Raj)
2. Ou désactiver complètement le déploiement en mode "test"

---

## 📋 PROBLÈME #4 : Langue de sortie

**Constat :**
- Input en français → Output en anglais
- Pas forcément un problème pour des livrables techniques Salesforce
- Mais pourrait être configurable

**Correction optionnelle :**
- Ajouter paramètre de langue dans le projet
- Adapter les prompts en fonction

---

## ✅ POINTS POSITIFS

1. **Cohérence des outputs** : Les UCs d'Olivia correspondent bien au BR, l'architecture de Marcus utilise les objets définis par Olivia
2. **RAG fonctionnel** : Le contexte Salesforce est bien intégré (Web-to-Lead, Assignment Rules, etc.)
3. **Qualité professionnelle** : Les livrables sont détaillés et exploitables
4. **Chaînage manuel réussi** : On peut passer les outputs d'un agent à l'autre

---

## 🎯 PROCHAINES CORRECTIONS PRIORITAIRES

1. [ ] Rendre Aisha conditionnelle (migration only)
2. [ ] Désactiver déploiement SF pour agents non-dev
3. [ ] Documenter format input/output de chaque agent
4. [ ] Tester Elena, Jordan, Lucas pour compléter la chaîne


---

## 5. ELENA (QA Engineer) - Observations

**Exécution #95 - Input:** Résumé texte architecture Marcus

### Points positifs
- Structure professionnelle et détaillée
- Environnements complets (5 tiers avec config)
- Métriques précises (85% coverage, <500ms API, etc.)
- Format test cases exploitable (template 15 sections)
- WCAG 2.1 AA accessibility inclus
- Risk matrix avec mitigations
- Timeline détaillée sur 9 semaines
- RAG fonctionnel (12,778 chars)

### Points à vérifier/corriger
1. **Specs excessives** - Test Strategy & Methodology très détaillées, peut-être trop pour certains projets
2. **Document tronqué** - 52,321 chars générés, s'arrête à TEST-033 sur 280+ prévus
   - Cause: Limite tokens Haiku (26,593) atteinte
   - Solution: Utiliser Sonnet pour documents longs OU découper en sections
3. **À vérifier dans SDS** - Comment ces specs QA se transmettent dans le document final

### Problème technique RAG
```
❌ Erreur: No module named 'sentence_transformers'
⚠️ Reranker non disponible
✅ Fallback fonctionne (OpenAI embeddings probable)
```
**Fix:** `docker exec digital-humans-backend pip install sentence-transformers`


---

## 6. PROBLÈME GLOBAL - sentence_transformers manquant

**Symptôme:** Apparaît sur tous les agents testés
```
⚠️ Reranker non disponible: No module named 'sentence_transformers'
```

**Impact:** 
- RAG fonctionne quand même (fallback) mais sans reranking
- Contexte RAG récupéré: 12-15K chars (OK)
- Qualité potentiellement dégradée sans reranking des résultats

**Fix à appliquer:**
```bash
docker exec digital-humans-backend pip install sentence-transformers
docker restart digital-humans-backend
```

**Statut:** À corriger après les tests


---

## 7. JORDAN (DevOps Engineer) - Observations

**Exécution #97 - Input:** Résumé composants à déployer + environnements

### Points positifs
- Structure professionnelle (Table of contents, 10 sections prévues)
- CI/CD Pipeline complet avec GitHub Actions YAML (~500 lignes)
- Diagrammes Mermaid pertinents (pipeline flow, environment architecture)
- Environment Strategy détaillée (5 tiers avec specs)
- Scripts bash exécutables (deploy.sh, rollback.sh)
- RAG fonctionnel (14,353 chars)

### Problème identique à Elena : DOCUMENT TRONQUÉ

**Statistiques:**
- Output généré: 54,527 chars
- Tokens utilisés: 22,395 (limite Haiku atteinte)
- Document annoncé: 115 pages
- Document réel: ~25 pages (Sections 1-4 partielles)

**Contenu manquant:**
- Fin de Section 4 (Deployment Automation) - script tronqué à log_info()
- Section 5: Monitoring & Alerting (non générée)
- Section 6: Backup & Disaster Recovery (non générée)
- Section 7: Release Management (non générée)
- Section 8: Version Control Strategy (non générée)
- Section 9: Security in DevOps (non générée)
- Section 10: Performance Optimization (non générée)

**Cause:** Limite tokens Claude Haiku 4.5

### Solution proposée
1. **Option A:** Utiliser Sonnet pour agents générant documents longs (Elena, Jordan, Marcus)
2. **Option B:** Découper génération en sections (plusieurs appels LLM)
3. **Option C:** Réduire verbosité des prompts pour outputs plus concis


---

## 8. POINT À CREUSER : Limites tokens par tier

**Configuration actuelle:**
- PM (Sophie): Opus → 32K output tokens
- BA (Olivia): Sonnet → 64K output tokens  
- Architect (Marcus): Sonnet → 64K output tokens
- Workers (Diego, Zara, Raj, Elena, Jordan, Aisha, Lucas): Haiku → 8K output tokens

**Problème observé:**
Elena et Jordan (workers) génèrent des specs de 50K+ chars mais Haiku limite à ~25-30K chars.

**Question à creuser:**
- Pour la phase SPEC (génération documents), les workers auraient-ils besoin de Sonnet ?
- Différencier tier par PHASE ? (Spec = Sonnet, Implémentation = Haiku)
- Ou réduire verbosité des prompts workers pour tenir dans 8K tokens ?

**Impact coût estimé:**
- Haiku: ~$0.25/1M input, $1.25/1M output
- Sonnet: ~$3/1M input, $15/1M output
- Passer workers en Sonnet = ~12x plus cher pour ces agents


---

## 9. SOPHIE (PM) - Amélioration nécessaire des descriptions BR

**Test #99 - Input complexe:** Système de gestion des demandes de service (Service Requests)

### Observation
Sophie génère 27 BRs bien structurés et cohérents (pas d'hallucinations), mais les descriptions sont trop génériques.

**Exemple BR-004:**
- **Titre:** Customer Information Association
- **Description actuelle:** "Each service request must be linked to the customer who submitted it, including contact information."

**Ce qui manque:**
- Quels champs spécifiques ? (nom, email, téléphone, company ?)
- Type de relation Salesforce ? (Lookup vers Contact, Account, ou les deux ?)
- Gestion des clients inconnus ? (création auto ou erreur ?)
- Champs obligatoires vs optionnels ?

### Impact
Olivia (BA) doit "inventer" les détails manquants pour générer les Use Cases, ce qui peut créer des incohérences ou des hallucinations en aval.

### Solution proposée
Modifier le prompt de Sophie pour :
1. Exiger 3-5 phrases minimum par description
2. Demander les champs/données spécifiques attendus
3. Préciser les règles métier associées
4. Identifier les dépendances avec d'autres BRs

**Format amélioré suggéré:**
```
BR-004: Customer Information Association
Description: Each service request must be linked to the customer record.
Fields Required: Contact (Lookup - required), Account (Lookup - auto-populated from Contact)
Business Rules: 
- Contact must exist in system before SR creation
- Account auto-populated via Contact.AccountId
- If no Contact found, prompt user to create one
Dependencies: BR-002 (unique ID), BR-003 (description)
```



---

## 9. 🚨 BUG CRITIQUE RÉSOLU : Mapping BR workflow → Olivia

**Date:** 07 Décembre 2025 - 17h45
**Exécutions concernées:** #88 (bug), #103 (bug), #104 (fix validé)

### Symptôme
Lors de l'exécution via PM Orchestrator (workflow complet), les UCs générées par Olivia étaient **complètement hors sujet** :

| Requirement (leads automobiles) | UCs générées (exec #88) ❌ |
|--------------------------------|---------------------------|
| "Lead capture from website, phone, email, partner portals" | "Business User Creates Custom Data Model Object" |
| | "Forecast Manager Configures Consumption-Based Forecast" |
| | "Sales Rep Syncs Email Communication to Salesforce" |
| | "Gmail Integration", "Einstein Activity Capture"... |

**Paradoxe :** Les tests individuels avec le même BR via le testeur produisaient des UCs cohérentes.

### Cause racine identifiée

**Fonction `_get_validated_brs()` dans `pm_orchestrator_service_v2.py` :**

```python
# AVANT (bug) - ligne 1185
return [
    {
        "id": br.br_id,
        "category": br.category,
        "requirement": br.requirement,  # ❌ Olivia cherche "description"
        "priority": br.priority.value,  # ❌ Format "should" au lieu de "SHOULD_HAVE"
    }
    for br in brs
]
```

**Olivia construit sa query RAG avec :**
```python
query = f"Salesforce {br.get('category', '')} {br.get('title', '')} {br.get('description', '')}"
```

**Résultat :** `title` et `description` étaient vides → query RAG = `"Salesforce DATA_MODEL "` → RAG retournait du contenu générique hors sujet.

### Correction appliquée

```python
# APRÈS (fix) - ligne 1185
return [
    {
        "id": br.br_id,
        "title": br.br_id,  # ✅ Ajouté (BR ID comme fallback)
        "description": br.requirement,  # ✅ Mappé correctement
        "category": br.category or "OTHER",
        "priority": (br.priority.value.upper() + "_HAVE") if br.priority else "SHOULD_HAVE",
        "stakeholder": "Business User"  # ✅ Ajouté
    }
    for br in brs
]
```

### Validation du fix

**Exec #104 (après fix) :**
```
UC-001-01: Capture Lead from Website Web-to-Lead Form ✅
UC-001-02: Manual Lead Entry by Sales Representative via Phone Call ✅
UC-001-03: Capture Lead from Email Inquiry via Email-to-Lead ✅
UC-001-04: Bulk Import Leads from Partner Portal via Data Import ✅
UC-001-05: Capture Lead from LinkedIn Lead Gen Form Integration ✅
```

**100% cohérent** avec le BR "lead capture from multiple channels".

### Fichier modifié
- `/app/app/services/pm_orchestrator_service_v2.py` - lignes 1185-1195

### Impact
Ce bug explique pourquoi tous les tests via le workflow complet (PM Orchestrator) produisaient des UCs incohérentes alors que les tests individuels fonctionnaient correctement.


---

## 10. Sophie (PM) - Descriptions BR trop génériques

**Observé lors de:** Test Olivia #102 avec BR-004

### Problème

Sophie extrait des BRs avec des descriptions trop courtes/génériques :

**Exemple BR-004 :**
```json
{
  "id": "BR-004",
  "title": "Customer Information Association",
  "description": "Each service request must be linked to the customer who submitted it, including contact information."
}
```

**Ce qui manque :**
- Champs spécifiques (nom, email, téléphone, company ?)
- Type de relation Salesforce (Lookup Contact, Account ?)
- Gestion des clients inconnus (création auto ou erreur ?)
- Champs obligatoires vs optionnels
- Règles de validation

### Impact

Olivia doit "inventer" les détails manquants pour générer des UCs complets, ce qui peut créer :
- Incohérences entre agents
- Hallucinations sur les règles métier
- Divergences avec les attentes client

### Solution proposée

Modifier le prompt de Sophie pour exiger :
1. **3-5 phrases minimum** par description de BR
2. **Champs/données spécifiques** mentionnés
3. **Règles métier** explicites
4. **Dépendances** avec autres BRs identifiées

### Statut
[ ] À corriger dans `salesforce_pm.py`



---

## 11. 🚨 TRONCATURE GÉNÉRALISÉE - Limite tokens atteinte sur plusieurs agents

**Date:** 07 Décembre 2025

### Agents affectés

| Agent | Modèle | Symptôme | Exec |
|-------|--------|----------|------|
| Olivia (BA) | Sonnet | UC-004-05 tronquée (5ème UC incomplète) | #102 |
| Elena (QA) | Haiku | Document tronqué à TEST-033 sur 280+ prévus | #95 |
| Jordan (DevOps) | Haiku | Sections 5-10 non générées | #97 |

### Cause
Les agents génèrent des documents très longs (50-100+ pages) qui dépassent les limites de tokens :
- Haiku : ~8K output tokens → ~25-30K chars max
- Sonnet : ~64K output tokens mais atteint aussi des limites sur contenus très longs

### Impact critique - Volume UCs

**Observation (test #102) :**
- 1 BR génère ~5 UCs
- Chaque UC = ~7K chars
- **1 BR = ~35K chars d'UCs**

**Projection pour workflow complet :**
- 27 BRs → ~135 UCs
- Volume total : ~950K chars
- Risque de troncature systématique sur les derniers BRs

### Solutions à évaluer

1. **Upgrader les workers critiques vers Sonnet** (Elena, Jordan, Aisha, Lucas)
   - Coût plus élevé mais outputs complets
   
2. **Découper la génération en plusieurs appels**
   - Générer section par section
   - Plus complexe à implémenter
   
3. **Réduire la verbosité des prompts**
   - Outputs plus concis mais moins détaillés
   - Risque de perte de qualité

4. **Limiter le nombre d'UCs par BR**
   - Max 3 UCs au lieu de 5
   - Réduirait le volume total

### Statut
[ ] Décision à prendre sur la stratégie


---

## 12. 📋 RÉCAPITULATIF - Problèmes identifiés cette session

| # | Problème | Priorité | Statut |
|---|----------|----------|--------|
| 1 | Bug mapping BR workflow → Olivia (query RAG vide) | 🔴 CRITIQUE | ✅ CORRIGÉ |
| 2 | Troncature Haiku (Elena, Jordan) | 🟠 HAUTE | ⏳ À traiter |
| 3 | Troncature Sonnet (Olivia UC-004-05) | 🟠 HAUTE | ⏳ À traiter |
| 4 | Volume UCs explosif (135 UCs / 950K chars pour 27 BRs) | 🟠 HAUTE | ⏳ À traiter |
| 5 | Descriptions BR trop génériques (Sophie) | 🟡 MOYENNE | ⏳ À traiter |
| 6 | sentence_transformers manquant (reranker) | 🟡 MOYENNE | ⏳ À traiter |
| 7 | Aisha appelée à tort (greenfield vs migration) | 🟡 MOYENNE | ⏳ À traiter |


---

## 13. 🔴 PROBLÈMES DOCUMENT SDS - À traiter demain

**Observé lors des tests workflow complet**

### Problème 1 : Contenu dupliqué sans valeur ajoutée

- **BRs apparaissent 2 fois** dans le document SDS
- Peu d'intérêt de répéter les mêmes informations
- Gaspillage d'espace dans le document final

### Problème 2 : Contenu important tronqué ou manquant

| Élément | Statut actuel | Impact |
|---------|---------------|--------|
| Use Cases (UCs) | ❌ Tronqués | Perte de détails critiques |
| Tests (Elena) | ❌ Incomplets/manquants | Pas de plan de test complet |
| Déploiement (Jordan) | ❌ Manquant | Pas de stratégie DevOps |
| Data Migration (Aisha) | ❓ À vérifier | Si pertinent selon projet |
| Formation (Lucas) | ❓ À vérifier | Plan de formation |

### Actions pour demain

1. **Analyser la structure actuelle du template SDS**
   - Identifier les sections dupliquées
   - Identifier les sections manquantes

2. **Revoir la logique d'assemblage du document**
   - Comment les outputs agents sont intégrés
   - Pourquoi certains sont tronqués

3. **Prioriser le contenu**
   - Réduire/supprimer les duplications
   - S'assurer que les éléments critiques sont complets

### Fichiers à examiner
- Template SDS : `/app/templates/sds_template.docx` (ou équivalent)
- Logique assemblage : chercher dans `pm_orchestrator_service_v2.py` ou service dédié


---

## 14. 📋 PLAN SESSION DEMAIN (08 Décembre 2025)

### Objectif 1 : Finaliser corrections agents et limites tokens

- [ ] Décider stratégie troncature (Sonnet pour tous ? Découpage ? Réduction verbosité ?)
- [ ] Implémenter la solution choisie
- [ ] Tester avec workflow complet

### Objectif 2 : Corriger le document SDS

- [ ] Analyser template et logique d'assemblage
- [ ] Supprimer duplications (BRs x2)
- [ ] S'assurer que UCs complets sont inclus
- [ ] Ajouter sections manquantes (Tests, Déploiement)
- [ ] Tester génération document complet

### Fichiers clés à examiner

1. `pm_orchestrator_service_v2.py` - Logique workflow ✅ (corrigé aujourd'hui)
2. Template/assemblage SDS - À examiner demain
3. Prompts agents (Elena, Jordan, Lucas) - Vérifier outputs
4. `salesforce_pm.py` - Améliorer descriptions BR

