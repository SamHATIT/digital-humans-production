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

---

## 🟡 Marcus - Séquencement des 4 modes

### Problème identifié (Execution #80)
Marcus exécute ses 4 modes dans le mauvais ordre.

### Ordre actuel (observé)
1. design (ARCH-001)
2. gap (GAP-001)
3. ???
4. ???

### Ordre logique (attendu)
1. **as_is** → Analyser l'existant (ASIS-001)
2. **gap** → Identifier les écarts besoins vs existant (GAP-001)
3. **design** → Concevoir la solution (ARCH-001)
4. **wbs** → Décomposer en tâches (WBS-001)

### Fichier à corriger
`backend/app/services/pm_orchestrator_service.py` - logique d'appel de Marcus

### Impact
Sans as_is en premier, l'architecte conçoit une solution sans connaître l'existant.

---
*Ajouté pendant test #80 - 3 décembre 2025*

---

## 🔴🔴 CRITIQUE: Marcus ne récupère pas les métadonnées Salesforce

### Problème identifié (Execution #80)
Marcus conçoit la solution **à l'aveugle** sans connaître l'état réel de l'org Salesforce cible.

### Ce qui existe actuellement
```python
# agent_executor.py ligne 191
sf org display --target-org DevOrg --json  # Vérifie connexion SEULEMENT
sf project deploy start ...                 # Déploie le code
```

### Ce qui manque
```bash
# Récupérer les infos de l'org (édition, version, features)
sf org display --target-org DevOrg --json

# Lister les types de metadata disponibles
sf org list metadata-types --api-version=60.0 --json

# Récupérer les objets/classes/profiles existants  
sf project retrieve start --metadata "CustomObject,ApexClass,Profile,PermissionSet,Flow" --json

# Lister les packages installés (ISV)
sf package installed list --target-org DevOrg --json

# Voir les limites de l'org
sf limits api display --target-org DevOrg --json
```

### Impact
Marcus ne sait pas :
- Quelle édition Salesforce (Enterprise, Professional, Unlimited, édition allégée...)
- Quelle version (Spring '24, Winter '25...)
- Quelles features sont activées/désactivées
- Quels packages ISV sont installés
- Quels custom objects existent déjà
- Quelles limites API s'appliquent
- Si certaines features "standard" sont indisponibles (éditions allégées)

### Solution à implémenter

1. **Créer fonction `_get_org_metadata()`** dans agent_executor.py ou pm_orchestrator_service_v2.py

2. **Workflow corrigé :**
   ```
   AVANT Marcus:
   1. Connexion à l'org (existant)
   2. sf org display → Édition, version, username
   3. sf org list metadata-types → Types disponibles  
   4. sf project retrieve start → État actuel des objets/classes
   5. sf package installed list → ISV installés
   6. Sauvegarder en DB ou passer à Marcus
   7. Marcus mode=as_is avec vraies données
   8. Marcus mode=design (informé des contraintes)
   9. Marcus mode=gap (basé sur réalité)
   10. Marcus mode=wbs
   ```

3. **Fichiers à modifier :**
   - `backend/app/services/agent_executor.py` - ajouter `_get_org_metadata()`
   - `backend/app/services/pm_orchestrator_service_v2.py` - appeler avant Marcus
   - `backend/agents/roles/salesforce_solution_architect.py` - utiliser les metadata dans as_is

### Priorité
🔴🔴 CRITIQUE - Sans cette correction, Marcus conçoit dans le vide et peut proposer des solutions incompatibles avec l'org cible

---
*Ajouté pendant analyse test #80 - 3 décembre 2025*
