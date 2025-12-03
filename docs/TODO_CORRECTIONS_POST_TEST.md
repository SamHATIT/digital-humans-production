# TODO - Corrections Post-Test (3 décembre 2025)

## 🔴 Diego - Erreurs de déploiement Salesforce

### 1. Nettoyer les fichiers résiduels
```bash
rm /root/workspace/salesforce-workspace/digital-humans-sf/force-app/main/default/classes/GeneratedCode_*
```

### 2. Corriger le prompt de Diego
Fichier: `backend/agents/roles/salesforce_developer_apex.py`

**Problèmes identifiés:**
- `System.error()` n'existe pas en Apex → utiliser `System.debug(LoggingLevel.ERROR, msg)`
- Emojis (✅❌) dans le code généré → interdire les caractères non-ASCII
- Tests avec filtres SOQL non supportés (ex: `Description` non filtrable)

**Ajouts au prompt:**
```
CRITICAL APEX RULES:
- NEVER use System.error() - use System.debug(LoggingLevel.ERROR, message) instead
- NEVER use emojis or non-ASCII characters in code
- For test classes, only filter on indexed/filterable fields (Id, Name, CreatedDate)
- Always verify field filterability before using in WHERE clauses
```

### 3. Valider le code avant déploiement
- Ajouter une étape de validation syntax avant `sf project deploy`
- Parser le code pour détecter les erreurs communes

---
*Créé pendant test #74 - à corriger après*

---

## 🔴 SDS Document Generation - Fichier corrompu

### Erreur identifiée (Execution #74)
```
[Phase 5] SDS generation failed: 'str' object has no attribute 'get'
```

### Symptôme
- Le générateur professionnel échoue
- Fallback crée un fichier `.md` (Markdown)
- Frontend le sert comme `.docx` → fichier corrompu

### Fichier à corriger
`backend/app/services/pm_orchestrator_service.py` ou `document_generator.py`

### Cause probable
Un agent a retourné une string au lieu d'un dict. Le code fait `data.get(...)` sur une string.

### Solution à implémenter
1. Ajouter validation des types de données avant génération SDS
2. Si fallback en .md, servir comme .md (pas renommer en .docx)
3. Logger quel agent a retourné des données invalides

---
*Ajouté après analyse execution #74*

---

## 🔴🔴 CRITIQUE: Workflow s'arrête après BA

### Symptôme (Execution #74)
- PM : ✅ 51 BRs extraits
- BA : ✅ 184 use cases générés
- Marcus, Diego, Zara, Raj, Elena, Jordan, Aisha, Lucas : ❌ JAMAIS LANCÉS (restent "waiting")

### Impact
- Seul 10% du travail effectué
- 9 agents sur 10 non exécutés
- SDS quasi-vide

### Fichier à corriger
`backend/app/services/pm_orchestrator_service.py`

### Cause probable
Le workflow ne boucle pas correctement sur tous les agents sélectionnés après le BA.
Vérifier la logique de `_execute_agent_workflow()` ou équivalent.

### Priorité
🔴 CRITIQUE - Sans cette correction, le système ne fonctionne pas

---
