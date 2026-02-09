# 🔍 AUDIT COMPLET BUILD v2 - Digital Humans

**Date :** 2026-02-03  
**Objectif :** Documenter les attendus de chaque composant BUILD v2 vs ce qui est réellement fourni

---

## 📋 RÉSUMÉ EXÉCUTIF

### Problème Fondamental Identifié

**Le WBS de Marcus contient toutes les informations nécessaires, mais elles ne sont PAS transférées vers `task_executions`.**

| Champ | Dans le WBS de Marcus | Transféré vers task_executions |
|-------|----------------------|--------------------------------|
| description | ✅ Oui (détaillé) | ❌ NON |
| validation_criteria | ✅ Oui | ❌ NON |
| deliverables | ✅ Oui | ❌ NON |
| gap_refs | ✅ Oui | ❌ NON |
| effort_days | ✅ Oui | ❌ NON |
| test_approach | ✅ Oui | ❌ NON |
| task_type | ✅ Oui (ex: dev_data_model) | ⚠️ Partiellement (mapping manuel postérieur) |

---

## 1️⃣ ORCHESTRATEUR PRINCIPAL : PhasedBuildExecutor

### Fichier
`/backend/app/services/phased_build_executor.py`

### Entrée Attendue (`execute_build`)
```python
wbs_tasks: List[Dict]  # Liste de tâches avec structure:
{
    "task_id": str,
    "task_name": str,
    "task_type": str,         # CRITIQUE: pour mapping phase
    "assigned_agent": str,
    "description": str,       # CRITIQUE: pour les prompts agents
    "target_object": str,     # Pour Phase 1 grouping
    "validation_criteria": list,
    "deliverables": list,
    "gap_refs": list,
}
```

### Entrée Réelle
```python
{
    "task_id": "TASK-003",
    "task_name": "Create core custom objects",
    "target_object": "Create core custom objects",  # ⚠️ FALLBACK incorrect
    "task_type": "create_object",
    "description": NULL ou task_name,               # ⚠️ VIDE
}
```

---

## 2️⃣ AGENT RAJ : generate_build_v2 (Phases 1, 4, 5)

### Ce que le LLM reçoit actuellement
```
## TASK
**Target Object:** Create core custom objects
**Description:** 

## SOLUTION DESIGN REFERENCE
Not provided
```

### Ce que le LLM devrait recevoir
```
## TASK
**Target Object:** Training_Course__c
**Description:** Build Training_Course__c object with all required fields: 
Course_Name__c (Text 255), Course_Code__c (Text 50 unique), Description__c (Rich Text),
Duration_Hours__c (Number), Max_Participants__c (Number), Prerequisites__c (Long Text),
Category__c (Picklist), Status__c (Picklist: Draft/Active/Archived), Price__c (Currency)

## SOLUTION DESIGN REFERENCE
(extrait du Solution Design de Marcus avec les spécifications)
```

---

## 3️⃣ CODE RACINE DU PROBLÈME

### Fichier
`/backend/app/services/pm_orchestrator_service_v2.py` (ligne 2295)

### Code Actuel (PROBLÈME)
```python
task_exec = TaskExecution(
    execution_id=execution.id,
    task_id=task.get("id"),
    task_name=task.get("name"),
    phase_name=task.get("phase_name"),
    assigned_agent=agent_id,
    status=TaskStatus.PENDING,
    depends_on=task.get("dependencies", [])
    # ❌ MANQUANTS:
    # description
    # validation_criteria
    # deliverables
    # gap_refs
    # effort_days
    # test_approach
    # task_type
)
```

### Code Corrigé Proposé
```python
task_exec = TaskExecution(
    execution_id=execution.id,
    task_id=task.get("id"),
    task_name=task.get("name"),
    phase_name=task.get("phase_name"),
    assigned_agent=agent_id,
    status=TaskStatus.PENDING,
    depends_on=task.get("dependencies", []),
    # ✅ AJOUTER:
    description=task.get("description"),
    validation_criteria=task.get("validation_criteria"),
    deliverables=task.get("deliverables"),
    gap_refs=task.get("gap_refs"),
    effort_days=task.get("effort_days"),
    test_approach=task.get("test_approach"),
    task_type=self._map_task_type(task.get("task_type")),
)
```

---

## 4️⃣ EXEMPLE CONCRET : TASK-003

### Données WBS de Marcus (disponibles mais non transférées)
```json
{
  "id": "TASK-003",
  "name": "Create core custom objects",
  "description": "Build Training_Course__c, Training_Session__c, Training_Enrollment__c, and Payment__c objects with all required fields.",
  "task_type": "dev_data_model",
  "gap_refs": ["GAP-001-01", "GAP-001-02", "GAP-001-03", "GAP-001-04"],
  "deliverables": ["4 custom objects with fields", "Object relationships"],
  "validation_criteria": [
    "DONE WHEN: All 4 objects created with complete field sets and relationships",
    "VERIFIED BY: Query each object schema and verify field count matches requirements"
  ]
}
```

### Données dans task_executions (réel)
```
task_id: TASK-003
task_name: Create core custom objects
task_type: create_object
description: NULL ❌
validation_criteria: NULL ❌
deliverables: NULL ❌
gap_refs: NULL ❌
```

---

## 5️⃣ PLAN DE CORRECTION

### Étape 1 : Modifier pm_orchestrator_service_v2.py
Transférer tous les champs du WBS vers TaskExecution.

### Étape 2 : Ajouter mapping task_type
```python
def _map_wbs_task_type_to_build(self, wbs_type: str) -> str:
    mapping = {
        "dev_data_model": "create_object",
        "dev_flow": "flow",
        "dev_apex": "apex_class",
        "dev_lwc": "lwc_component",
        "config_profiles": "permission_set",
        "config_sharing": "sharing_rule",
        "setup_environment": "devops_setup",
    }
    return mapping.get(wbs_type, "manual")
```

### Étape 3 : Régénérer les TaskExecution pour exécution 131
Supprimer les existantes et les recréer avec données complètes.

### Étape 4 : Ajouter Solution Design au contexte
Récupérer architect_solution_design et le passer aux agents.

---

## 6️⃣ CONCLUSION

Le problème n'est pas dans BUILD v2 lui-même, mais dans le **transfert des données du WBS vers task_executions**. 

**Une seule correction à un seul endroit** (pm_orchestrator_service_v2.py ligne ~2295) résoudra la majorité des problèmes.

---

*Document généré le 2026-02-03*
