# 🏗️ BUILD v2 — Spécification Technique Exhaustive

**Version** : 1.0
**Date** : 2026-02-02
**Auteur** : Sam Hatit + Claude
**Statut** : APPROUVÉ — Prêt pour implémentation

---

## Table des Matières

1. [Contexte et Problématique](#1-contexte-et-problématique)
2. [Architecture BUILD v2 — Vue d'ensemble](#2-architecture-build-v2)
3. [Les 6 Phases du BUILD](#3-les-6-phases-du-build)
4. [Stratégie Sub-Batching (gestion volume LLM)](#4-stratégie-sub-batching)
5. [Spécifications par Agent](#5-spécifications-par-agent)
6. [Services à créer / modifier](#6-services-à-créer--modifier)
7. [Modèle de données (nouvelles tables)](#7-modèle-de-données)
8. [Plan d'implémentation](#8-plan-dimplémentation)
9. [Checklist de validation](#9-checklist-de-validation)

---

## 1. Contexte et Problématique

### 1.1 État actuel du BUILD (pré-v2)

Le BUILD phase n'a **jamais déployé avec succès** sur une org Salesforce. L'audit du 02/02/2026 a identifié les causes racines :

**Problèmes critiques identifiés :**

| Agent | Problème | Impact |
|---|---|---|
| **Raj** | `_get_metadata_type` ne reconnaît que 3 types sur 15+ | 60% des tâches BUILD échouent |
| **Raj** | `deploy_metadata` aplatit l'arborescence SFDX | XML invalide pour Salesforce |
| **Raj** | Extensions de fichier incorrectes (`.xml` au lieu de `.field-meta.xml`) | Deploy rejeté par SFDX |
| **Raj** | Pas de regroupement Object + Fields pour deploy | Fichiers orphelins |
| **Aisha** | Fichiers CSV/SDL/SQL traités comme metadata SF | Deploy impossible |
| **Jordan** | Classé `non_build_agents` → jamais appelé | Aucun orchestrateur de deploy |
| **Elena** | Auto-PASS si JSON parse error | Bugs non détectés |
| **Diego** | Pas de vérification que les objets/champs référencés existent | Erreurs compilation |
| **Zara** | Pas de validation nommage camelCase LWC | Deploy rejeté |
| **Tous** | Workflow task-by-task crée des dépendances en cascade | Architecture fragile |

### 1.2 Décisions d'architecture (validées avec Sam)

1. **Workflow par phases** au lieu de task-by-task → élimine les dépendances par construction
2. **Raj travaille via Tooling API** comme un vrai admin → plus de XML fragile
3. **Jordan = Tech Lead** du déploiement → responsabilité unique et claire
4. **Elena review par phase** → vision d'ensemble cohérente
5. **Sub-batching** pour la génération LLM → un lot = un objet/classe/composant
6. **Aisha avec config data sources** → paramétrage projet des imports (V1 : CSV)
7. **PR par phase** dans Git → traçabilité et rollback simples

---

## 2. Architecture BUILD v2

### 2.1 Flow global

```
SDS_APPROVED
    ↓
┌─────────────────────────────────────────────────────────────────┐
│                     PHASED BUILD EXECUTOR                        │
│                                                                  │
│  1. Charger toutes les tâches WBS                                │
│  2. Regrouper automatiquement par phase (via task_type)          │
│  3. Pour chaque phase (1→6 séquentiellement) :                   │
│                                                                  │
│     ┌─────────────────────────────────────────────────────┐      │
│     │ A. Agent génère par lots (sub-batching)             │      │
│     │    - Lot 1 → output + update context registry       │      │
│     │    - Lot 2 → output + update context registry       │      │
│     │    - ...                                            │      │
│     │ B. Agrégation de tous les lots                      │      │
│     │ C. Sanitize + validation structurelle               │      │
│     │ D. Elena review la phase complète                   │      │
│     │    → FAIL : feedback → retour A (max 3 retries)     │      │
│     │    → PASS : continue                                │      │
│     │ E. Git : feature branch + PR pour la phase          │      │
│     │ F. Jordan : merge + deploy + validation             │      │
│     │    → FAIL : revert merge → retry ou stop            │      │
│     │    → OK : tag + update deployed_components          │      │
│     │ G. Toutes les tâches de la phase → COMPLETED        │      │
│     └─────────────────────────────────────────────────────┘      │
│                         ↓                                        │
│                    Phase suivante                                 │
│                                                                  │
│  4. Fin : Jordan package final + tag release                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
    ↓
BUILD_COMPLETED
```

### 2.2 Fichiers principaux (nouveaux et modifiés)

| Fichier | Action | Rôle |
|---|---|---|
| `phased_build_executor.py` | **NOUVEAU** | Orchestrateur principal (remplace incremental_executor pour le BUILD) |
| `phase_aggregator.py` | **NOUVEAU** | Fusionne les sous-lots par phase |
| `phase_context_registry.py` | **NOUVEAU** | Contexte progressif inter-lots et inter-phases |
| `sf_admin_service.py` | **NOUVEAU** | Exécute les plans JSON Raj via Tooling API |
| `jordan_deploy_service.py` | **NOUVEAU** | Service de déploiement centralisé (Jordan) |
| `salesforce_admin.py` | **MODIFIER** | Nouveau prompt BUILD → sortie JSON au lieu de XML |
| `salesforce_developer_apex.py` | **MODIFIER** | Prompt enrichi + sanitize post-processing |
| `salesforce_developer_lwc.py` | **MODIFIER** | Validation nommage + parser robuste |
| `salesforce_qa_tester.py` | **MODIFIER** | 6 prompts review par phase + validation structurelle |
| `salesforce_devops.py` | **MODIFIER** | Nouveau rôle Tech Lead deploy |
| `salesforce_data_migration.py` | **MODIFIER** | Intégration data sources config |
| `incremental_executor.py` | **CONSERVER** | Reste utilisé pour get_task_summary, load_tasks_from_wbs |
| `sfdx_service.py` | **MODIFIER** | Ajout retrieve_metadata, execute_anonymous |
| `git_service.py` | **MODIFIER** | Ajout merge_pr, revert_merge, create_phase_branch |
| `agent_executor.py` | **MODIFIER** | Retirer Jordan et Elena de non_build_agents |

---

## 3. Les 6 Phases du BUILD

### 3.1 Vue d'ensemble

| Phase | Nom | Agent principal | Méthode deploy | Dépend de |
|---|---|---|---|---|
| 1 | Data Model | Raj | Tooling API | Rien |
| 2 | Business Logic | Diego | SFDX source deploy | Phase 1 |
| 3 | UI Components | Zara | SFDX source deploy | Phase 1 + 2 |
| 4 | Automation | Raj | Tooling API | Phase 1 + 2 |
| 5 | Security & Access | Raj | SFDX source deploy | Phase 1 + 2 + 3 + 4 |
| 6 | Data Migration | Aisha | Scripts (Apex anonymous + Data Loader) | Phase 1 + 2 + 4 + 5 |

### 3.2 Phase 1 — Data Model (Raj)

**Contenu :**
- Custom Objects (avec nameField, sharingModel)
- Custom Fields (tous types : Text, Number, Picklist, Lookup, Master-Detail, Formula, etc.)
- Record Types
- List Views
- Validation Rules **simples** (formules sans référence Apex)

**task_types inclus** : `create_object`, `create_field`, `record_type`, `list_view`, `simple_validation_rule`

**Ne PAS inclure** : Flows, Permission Sets, Profiles, Page Layouts, Validation Rules qui appellent du code Apex

**Sortie agent** : Plan JSON (voir §5.3)

**Deploy** : Tooling API via `sf_admin_service.py`, puis `sf project retrieve start` par Jordan pour récupérer le metadata source format propre

**Rollback** : Metadata API delete des objets créés

### 3.3 Phase 2 — Business Logic (Diego)

**Contenu :**
- Apex Classes (services, handlers, utilities)
- Apex Triggers
- Apex Test Classes
- Classes helper / wrapper

**task_types inclus** : `apex_class`, `apex_trigger`, `apex_test`, `apex_helper`

**Sortie agent** : Fichiers `.cls` + `.trigger` avec convention `// FILE: force-app/...`

**Deploy** : SFDX `sf project deploy start --source-dir` via Jordan

**Prérequis garanti** : Phase 1 terminée → tous les objets/champs existent dans la sandbox

**Post-processing obligatoire** :
- `sanitize_apex_code()` : corrige placement `WITH SECURITY_ENFORCED`
- Vérification accolades équilibrées

### 3.4 Phase 3 — UI Components (Zara)

**Contenu :**
- Lightning Web Components (html + js + css + meta)
- FlexiPages (Lightning Record Pages)
- Custom Tabs

**task_types inclus** : `lwc_component`, `flexipage`, `custom_tab`

**Sortie agent** : Bundles LWC complets avec convention `// FILE: force-app/.../lwc/...`

**Deploy** : SFDX source deploy (bundles) via Jordan

**Prérequis garanti** : Phase 1 (objets) + Phase 2 (controllers Apex) terminées

**Post-processing obligatoire** :
- `validate_lwc_naming()` : force camelCase
- Vérification `export default class` + `LightningElement`

### 3.5 Phase 4 — Automation (Raj)

**Contenu :**
- Flows (Record-Triggered, Screen, Auto-Launched, Scheduled)
- Validation Rules **complexes** (avec formules avancées ou dépendances)
- Approval Processes
- Workflow Rules (si legacy)

**task_types inclus** : `flow`, `complex_validation_rule`, `approval_process`, `workflow_rule`

**Sortie agent** : Plan JSON pour les Validation Rules, XML pour les Flows (les Flows sont trop complexes pour Tooling API en JSON)

**Deploy** : Mix Tooling API (VR, Approval) + SFDX source deploy (Flows) via Jordan

**Prérequis garanti** : Phase 1 (objets) + Phase 2 (Apex invocable) terminées

**Distinction simple_validation_rule vs complex_validation_rule** :
- Simple = formule ne référence QUE des champs de l'objet (ISBLANK, ISPICKVAL, etc.)
- Complex = formule qui utilise VLOOKUP, référence cross-objet, ou appelle un Apex invocable

**Méthode de distinction** : Si la tâche WBS a une dépendance vers une tâche Diego → `complex_validation_rule` → Phase 4. Sinon → `simple_validation_rule` → Phase 1.

### 3.6 Phase 5 — Security & Access (Raj)

**Contenu :**
- Permission Sets (Object Permissions + Field-Level Security)
- Profiles (modifications, pas création)
- Sharing Rules
- Page Layouts (et assignments aux profils/record types)

**task_types inclus** : `permission_set`, `profile`, `sharing_rule`, `page_layout`, `page_layout_assignment`

**Sortie agent** : Plan JSON pour Permission Sets, XML source format pour Profiles et Layouts

**Deploy** : SFDX source deploy via Jordan (les Permission Sets sont mieux gérés en metadata XML que via Tooling API)

**Prérequis garanti** : Toutes les phases précédentes terminées → tous les objets, champs, classes, composants existent

**Note** : Les Permission Sets doivent référencer EXACTEMENT les API names des objets et champs créés en Phase 1. Le registre de contexte fournit cette liste.

### 3.7 Phase 6 — Data Migration (Aisha)

**Contenu :**
- Scripts de mapping (SDL) adaptés aux CSV configurés dans le projet
- Scripts de transformation (Apex anonymous)
- Requêtes de validation pré/post-import (SOQL)
- Documentation de migration

**task_types inclus** : `data_migration`, `data_load`, `data_transform`, `data_validation`

**Sortie agent** : Fichiers SDL + CSV templates + scripts Apex anonymous + requêtes SOQL

**Deploy** :
- Scripts Apex anonymous → `sf apex run --file script.apex` via Jordan
- Fichiers SDL/CSV/SOQL → Git commit uniquement (pas de deploy SF)

**Prérequis garanti** : Tout est en place (objets, champs, automations, sécurité)

**Configuration data sources** : Aisha reçoit la config des sources de données du projet (voir §7.2)

---

## 4. Stratégie Sub-Batching

### 4.1 Principe

Le LLM ne voit jamais "toute la phase" d'un coup. Il génère par **petits lots** (1 objet, 1 classe, 1 composant). Puis un agrégateur fusionne les lots. Elena et Jordan travaillent sur la phase agrégée.

```
Unité de GÉNÉRATION (LLM) : 1 lot = 1 objet / 1 classe / 1 composant
Unité de REVIEW (Elena)    : 1 phase = agrégation de tous les lots
Unité de DEPLOY (Jordan)   : 1 phase = tous les fichiers d'un coup
```

### 4.2 Découpage par phase

| Phase | Unité de lot | Taille estimée output | Risque overflow |
|---|---|---|---|
| 1. Data Model | 1 objet + ses champs + RTs + VRs | ~1500 tokens | ✅ Faible |
| 2. Business Logic | 1 service class + son test class | ~2500 tokens | ⚠️ Moyen |
| 3. UI Components | 1 composant LWC complet (4 fichiers) | ~1500 tokens | ✅ Faible |
| 4. Automation | 1 Flow OU groupe de VRs par objet | ~2000 tokens | ✅ Faible |
| 5. Security | 1 Permission Set complet | ~2000 tokens | ✅ Faible |
| 6. Data Migration | 1 objet cible (mapping + script) | ~1500 tokens | ✅ Faible |

### 4.3 Registre de contexte progressif

Chaque lot enrichit un registre partagé. Les lots suivants (même phase et phases ultérieures) reçoivent ce contexte dans leur prompt.

**Données du registre :**

```python
class PhaseContextRegistry:
    # Phase 1 alimente :
    generated_objects: list[str]              # ["Formation__c", "Session__c", ...]
    generated_fields: dict[str, list[str]]    # {"Formation__c": ["Titre__c", "Statut__c"], ...}
    generated_record_types: dict[str, list]   # {"Formation__c": ["Presentiel", "Distanciel"]}
    generated_validation_rules: list[str]     # ["Formation__c.Titre_Required"]

    # Phase 2 alimente :
    generated_classes: dict[str, list[str]]   # {"FormationService": ["getFormation(Id)", "create(...)"], ...}
    generated_triggers: list[str]             # ["FormationTrigger"]

    # Phase 3 alimente :
    generated_components: dict[str, list[str]] # {"formationList": ["@api recordId", "@api filters"]}

    # Phase 4 alimente :
    generated_flows: list[str]                # ["FormationAutoNotification"]
    generated_complex_vrs: list[str]          # ["Session__c.DateCoherente"]
```

**Contexte injecté dans le prompt du lot :**

| Phase du lot | Contexte reçu |
|---|---|
| Phase 1 (lot N) | Objets + champs créés dans lots 1..N-1 de Phase 1 |
| Phase 2 (lot N) | TOUT Phase 1 + classes créées dans lots 1..N-1 de Phase 2 |
| Phase 3 (lot N) | TOUT Phase 1 + signatures classes Phase 2 + composants lots 1..N-1 Phase 3 |
| Phase 4 (lot N) | TOUT Phase 1 + signatures classes Phase 2 + flows lots 1..N-1 Phase 4 |
| Phase 5 (lot N) | TOUT Phase 1-4 (objets, champs, classes, composants, flows) |
| Phase 6 (lot N) | TOUT Phase 1-5 + config data sources du projet |

**Important** : Le contexte des phases précédentes transmet les **signatures** (noms + méthodes publiques), pas le code complet. Ça évite d'exploser la fenêtre de contexte.

### 4.4 Estimation volume (projet FormaPro, 62 UCs)

| Phase | Nb lots estimé | Input/lot | Output/lot | Total output | Coût Claude Sonnet |
|---|---|---|---|---|---|
| 1. Data Model | ~15 | ~2k tok | ~1.5k tok | ~22k tok | ~$0.07 |
| 2. Business Logic | ~10 | ~3k tok | ~2.5k tok | ~25k tok | ~$0.08 |
| 3. UI Components | ~8 | ~2.5k tok | ~1.5k tok | ~12k tok | ~$0.04 |
| 4. Automation | ~6 | ~2k tok | ~2k tok | ~12k tok | ~$0.04 |
| 5. Security | ~3 | ~2k tok | ~2k tok | ~6k tok | ~$0.02 |
| 6. Data Migration | ~4 | ~2k tok | ~1.5k tok | ~6k tok | ~$0.02 |
| **Elena reviews** | 6 | ~5k tok | ~1k tok | ~6k tok | ~$0.02 |
| **TOTAL** | **~52 lots** | | | **~89k tok** | **~$0.29** |

---

## 5. Spécifications par Agent

### 5.1 Diego (Apex Developer)

**Mode** : `build`
**Phase** : 2 (Business Logic)
**Input** : Tâche WBS + architecture context + modèle de données (Phase 1) + signatures classes précédentes
**Output** : Fichiers `.cls` / `.trigger`

**Corrections à apporter :**

**5.1.1 Sanitize Apex Code** (post-processing)
```python
def sanitize_apex_code(content: str) -> str:
    """Corrige les erreurs LLM courantes dans le code Apex."""
    import re
    
    # Fix 1: WITH SECURITY_ENFORCED mal placé (après GROUP BY au lieu d'avant)
    content = re.sub(
        r'(GROUP\s+BY\s+[^\]]+?)\s+(WITH\s+SECURITY_ENFORCED)',
        r'\2 \1', content, flags=re.IGNORECASE
    )
    content = re.sub(
        r'(ORDER\s+BY\s+[^\]]+?)\s+(WITH\s+SECURITY_ENFORCED)',
        r'\2 \1', content, flags=re.IGNORECASE
    )
    
    # Fix 2: Double point-virgule
    content = re.sub(r';;', ';', content)
    
    # Fix 3: Accolades d'ouverture sur ligne seule (style C# vs Java)
    # Pas de fix automatique — juste détection pour Elena
    
    return content
```

**5.1.2 Prompt enrichi**
Ajouter au BUILD_PROMPT de Diego :
```
## MODÈLE DE DONNÉES DISPONIBLE (Phase 1 déployée)
{data_model_context}
UTILISEZ UNIQUEMENT ces objets et champs dans vos requêtes SOQL/SOSL.

## CLASSES APEX DÉJÀ GÉNÉRÉES (lots précédents de cette phase)
{class_signatures}
Vous pouvez importer ces classes. NE LES incluez PAS dans votre output.
```

**5.1.3 Validation pré-Elena**
- Accolades équilibrées : `content.count('{') == content.count('}')`
- Commence par un modificateur d'accès : `@isTest`, `public`, `private`, `global`, `abstract`, `virtual`
- Pas de référence à des Exception classes custom non incluses dans l'output

### 5.2 Zara (LWC Developer)

**Mode** : `build`
**Phase** : 3 (UI Components)
**Input** : Tâche WBS + modèle de données + signatures Apex + composants précédents
**Output** : Bundles LWC (html + js + css + js-meta.xml)

**Corrections à apporter :**

**5.2.1 Validation nommage camelCase**
```python
def validate_lwc_naming(component_name: str) -> str:
    """Force le nommage camelCase pour les composants LWC."""
    import re
    if '_' in component_name or '-' in component_name:
        parts = re.split(r'[_-]', component_name)
        component_name = parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])
    component_name = component_name[0].lower() + component_name[1:]
    return component_name
```

**5.2.2 Parser robuste multi-stratégies**
```python
def parse_lwc_files_robust(content: str) -> dict:
    """Parse les fichiers LWC avec fallback progressif."""
    # Stratégie 1: Regex actuels (4 patterns)
    files = _parse_with_regex(content)
    if files:
        return files
    
    # Stratégie 2: Markers textuels (// FILE: ou <!-- FILE: -->)
    files = _parse_with_markers(content)
    if files:
        return files
    
    # Stratégie 3: Extraction par blocs de code (```)
    files = _parse_with_code_blocks(content)
    return files
```

**5.2.3 Validation pré-Elena**
- Chaque fichier `.js` contient `export default class` et `LightningElement`
- Le fichier `.js-meta.xml` existe dans le bundle
- Le nom du composant dans le path est en camelCase

### 5.3 Raj (Salesforce Admin)

**Mode** : `build`
**Phases** : 1 (Data Model), 4 (Automation), 5 (Security)
**Changement majeur** : **Sortie JSON au lieu de XML**

**5.3.1 Nouveau format de sortie — Plan JSON**

```json
{
  "phase": "data_model",
  "target_object": "Formation__c",
  "operations": [
    {
      "order": 1,
      "type": "create_object",
      "api_name": "Formation__c",
      "label": "Formation",
      "plural_label": "Formations",
      "sharing_model": "ReadWrite",
      "name_field_type": "Text",
      "description": "Gestion des formations professionnelles"
    },
    {
      "order": 2,
      "type": "create_field",
      "object": "Formation__c",
      "api_name": "Titre__c",
      "label": "Titre de la formation",
      "field_type": "Text",
      "length": 255,
      "required": true,
      "description": "Titre officiel de la formation"
    },
    {
      "order": 3,
      "type": "create_field",
      "object": "Formation__c",
      "api_name": "Statut__c",
      "label": "Statut",
      "field_type": "Picklist",
      "values": [
        {"api_name": "Brouillon", "label": "Brouillon", "default": true},
        {"api_name": "Publie", "label": "Publié", "default": false},
        {"api_name": "Archive", "label": "Archivé", "default": false}
      ],
      "required": true
    },
    {
      "order": 4,
      "type": "create_field",
      "object": "Formation__c",
      "api_name": "Organisme__c",
      "label": "Organisme de formation",
      "field_type": "Lookup",
      "reference_to": "Account",
      "relationship_name": "Formations",
      "relationship_label": "Formations"
    },
    {
      "order": 5,
      "type": "create_field",
      "object": "Formation__c",
      "api_name": "DateDebut__c",
      "label": "Date de début",
      "field_type": "Date",
      "required": false
    },
    {
      "order": 6,
      "type": "create_field",
      "object": "Formation__c",
      "api_name": "NombreHeures__c",
      "label": "Nombre d'heures",
      "field_type": "Number",
      "precision": 5,
      "scale": 1,
      "required": false
    },
    {
      "order": 7,
      "type": "create_field",
      "object": "Formation__c",
      "api_name": "Description__c",
      "label": "Description",
      "field_type": "LongTextArea",
      "length": 32768,
      "visible_lines": 5
    },
    {
      "order": 8,
      "type": "create_record_type",
      "object": "Formation__c",
      "api_name": "Presentiel",
      "label": "Présentiel",
      "description": "Formation en présentiel"
    },
    {
      "order": 9,
      "type": "create_record_type",
      "object": "Formation__c",
      "api_name": "Distanciel",
      "label": "Distanciel",
      "description": "Formation à distance"
    },
    {
      "order": 10,
      "type": "create_list_view",
      "object": "Formation__c",
      "api_name": "All_Formations",
      "label": "Toutes les formations",
      "columns": ["Titre__c", "Statut__c", "DateDebut__c", "Organisme__c"],
      "filter_scope": "Everything"
    },
    {
      "order": 11,
      "type": "create_validation_rule",
      "object": "Formation__c",
      "api_name": "Titre_Required_When_Published",
      "active": true,
      "formula": "AND(ISPICKVAL(Statut__c, 'Publie'), ISBLANK(Titre__c))",
      "error_message": "Le titre est obligatoire pour une formation publiée.",
      "error_field": "Titre__c"
    }
  ]
}
```

**5.3.2 Types d'opérations supportés**

| Operation type | Phase | Propriétés clés |
|---|---|---|
| `create_object` | 1 | api_name, label, plural_label, sharing_model, name_field_type |
| `create_field` | 1 | object, api_name, label, field_type, + props selon type |
| `create_record_type` | 1 | object, api_name, label |
| `create_list_view` | 1 | object, api_name, label, columns, filter_scope |
| `create_validation_rule` | 1 ou 4 | object, api_name, formula, error_message, error_field |
| `create_flow` | 4 | api_name, flow_type, object (si record-triggered), description |
| `create_approval_process` | 4 | object, api_name, entry_criteria, approvers |
| `create_permission_set` | 5 | api_name, label, object_permissions[], field_permissions[] |
| `create_page_layout` | 5 | object, api_name, sections[] |
| `create_sharing_rule` | 5 | object, api_name, criteria, access_level |

**5.3.3 Types de champs supportés**

| field_type | Propriétés spécifiques |
|---|---|
| `Text` | length (défaut: 255) |
| `LongTextArea` | length (défaut: 32768), visible_lines (défaut: 5) |
| `Number` | precision, scale |
| `Currency` | precision, scale |
| `Percent` | precision, scale |
| `Date` | (aucune) |
| `DateTime` | (aucune) |
| `Checkbox` | default_value (true/false) |
| `Email` | (aucune) |
| `Phone` | (aucune) |
| `Url` | (aucune) |
| `Picklist` | values: [{api_name, label, default}], restricted (défaut: true) |
| `MultiselectPicklist` | values, visible_lines (défaut: 4) |
| `Lookup` | reference_to, relationship_name, relationship_label |
| `MasterDetail` | reference_to, relationship_name, relationship_label |
| `Formula` | formula, return_type (Text/Number/Date/Currency/Percent/Checkbox) |
| `AutoNumber` | format (ex: "FORM-{0000}"), start_number (défaut: 1) |

### 5.4 Elena (QA Tester)

**Mode** : `test` (review)
**Phases** : Toutes (review après chaque phase)

**Corrections à apporter :**

**5.4.1 Supprimer l'auto-PASS**
```python
# AVANT (ligne 216, salesforce_qa_tester.py)
except json.JSONDecodeError:
    review_data = {"verdict": "PASS", "summary": "Auto-pass (parse error)"}

# APRÈS
except json.JSONDecodeError:
    # Retry avec prompt strict
    retry_result = await _retry_review(code_files)
    if retry_result:
        review_data = retry_result
    else:
        review_data = {
            "verdict": "FAIL",
            "summary": "Review impossible — format de réponse invalide. Veuillez resoumettre.",
            "issues": [{"severity": "critical", "description": "Parse error on review output"}],
            "feedback_for_developer": "Elena n'a pas pu produire un avis structuré. Resoumettez sans modification."
        }
```

**5.4.2 Validation structurelle pré-LLM**

Avant la review LLM, Elena exécute des vérifications techniques automatiques :

```python
async def structural_validation(files: dict, phase: int) -> dict:
    issues = []
    
    # ── Vérifications communes ──
    for path, content in files.items():
        if path.endswith('.xml'):
            try:
                ET.fromstring(content)
            except ET.ParseError as e:
                issues.append({"file": path, "severity": "critical", "issue": f"XML invalide: {e}"})
    
    # ── Phase 1: Data Model (JSON) ──
    if phase == 1:
        plan = json.loads(content)  # Le plan agrégé
        objects_seen = set()
        for op in plan.get("operations", []):
            if op["type"] == "create_object":
                if op["api_name"] in objects_seen:
                    issues.append({"severity": "critical", "issue": f"Objet dupliqué: {op['api_name']}"})
                objects_seen.add(op["api_name"])
            if op["type"] == "create_field":
                if op["object"] not in objects_seen:
                    issues.append({"severity": "critical", "issue": f"Champ {op['api_name']} référence objet inexistant {op['object']}"})
    
    # ── Phase 2: Apex ──
    if phase == 2:
        for path, content in files.items():
            if path.endswith('.cls'):
                if content.count('{') != content.count('}'):
                    issues.append({"file": path, "severity": "critical",
                        "issue": f"Accolades déséquilibrées: {content.count('{')} ouvrantes vs {content.count('}')} fermantes"})
                if not any(content.strip().startswith(kw) for kw in ['@isTest','public','private','global','abstract','virtual']):
                    issues.append({"file": path, "severity": "warning", "issue": "Ne commence pas par un modificateur d'accès valide"})
    
    # ── Phase 3: LWC ──
    if phase == 3:
        for path, content in files.items():
            if path.endswith('.js') and '/lwc/' in path:
                if 'export default class' not in content:
                    issues.append({"file": path, "severity": "critical", "issue": "Manque 'export default class'"})
                if 'LightningElement' not in content:
                    issues.append({"file": path, "severity": "warning", "issue": "Ne référence pas LightningElement"})
    
    has_critical = any(i['severity'] == 'critical' for i in issues)
    return {"valid": not has_critical, "issues": issues}
```

**5.4.3 Prompts review par phase**

Elena reçoit un prompt adapté à chaque phase. Exemples :

**Phase 1 (Data Model)** :
```
Revois ce modèle de données Salesforce. Vérifie :
- Cohérence avec le SDS (tous les objets/champs du SDS sont présents)
- Relations correctes (Lookup vs Master-Detail selon la cardinalité)
- Naming conventions (API names en PascalCase + __c)
- Pas de champs en doublon entre objets
- Record Types pertinents
- Validation rules avec des formules syntaxiquement correctes
```

**Phase 2 (Business Logic)** :
```
Revois cet ensemble de classes Apex. Vérifie :
- Chaque classe est self-contained (pas de référence à une classe non incluse ni non standard)
- Bulkification correcte (pas de SOQL/DML dans les boucles)
- Tests avec couverture suffisante
- Gestion d'erreur avec AuraHandledException
- Les objets/champs référencés existent dans le modèle de données ci-dessous
```

### 5.5 Jordan (DevOps — Tech Lead)

**Mode** : `deploy`
**Rôle** : Gate keeper du déploiement. Merge PR → Deploy → Validate → Tag

**Corrections à apporter :**

**5.5.1 Retirer de non_build_agents**
```python
# agent_executor.py, execute_single_task
# AVANT
non_build_agents = ["devops", "qa", "trainer", "jordan", "elena", "lucas",
                     "architect", "marcus", "emma", "research_analyst"]
# APRÈS
non_build_agents = ["trainer", "lucas", "architect", "marcus", "emma", "research_analyst"]
```

**5.5.2 Service Jordan (nouveau)**

Voir §6.4 pour la spec complète de `jordan_deploy_service.py`.

Responsabilités :
1. Merge la PR de phase
2. Router le deploy selon l'agent (Tooling API pour Raj, SFDX pour Diego/Zara, scripts pour Aisha)
3. Gérer les erreurs et rollback (revert merge)
4. Après deploy Raj Tooling API → `sf project retrieve start` pour récupérer le metadata propre → commit Git
5. Mettre à jour le registre `deployed_components`
6. Tag Git après succès : `deployed/phase-{N}-{phase_name}`
7. En fin de BUILD : package.xml final + tag release

### 5.6 Aisha (Data Migration)

**Mode** : `build`
**Phase** : 6 (Data Migration)

**Corrections à apporter :**

**5.6.1 Intégration config data sources**

Aisha reçoit la config des sources de données du projet dans son contexte :
```
## SOURCES DE DONNÉES CONFIGURÉES
Source 1: "Contacts clients"
  → Objet cible: Contact
  → Format: CSV
  → Fichier: contacts_export.csv
  → Colonnes: Nom, Prénom, Email, Téléphone, Entreprise
  
Source 2: "Tickets support"
  → Objet cible: Case
  → Format: CSV
  → Fichier: tickets_zendesk.csv
  → Colonnes: ID, Sujet, Description, Statut, Date_Creation
```

**5.6.2 Sortie attendue par source**
- Mapping SDL (colonnes CSV → champs SF)
- Script de transformation Apex anonymous (si transformations nécessaires)
- Requête SOQL de validation post-import
- CSV template nettoyé (si besoin de reformatage)

**5.6.3 Deploy**
- Fichiers SDL/CSV/SOQL → Git commit uniquement
- Scripts Apex anonymous → `sf apex run --file script.apex` via Jordan
- Jordan ordonne : d'abord les objets parents, puis les enfants (respect des relations)

---

## 6. Services à créer / modifier

### 6.1 phased_build_executor.py (NOUVEAU)

**Rôle** : Orchestrateur principal du BUILD v2. Remplace l'usage de incremental_executor pour le flow BUILD.

**Méthodes principales :**

```python
class PhasedBuildExecutor:
    BUILD_PHASES = [...]  # Voir §3.1
    
    async def execute_build(execution_id: int) -> dict
        # Charge les tâches WBS, regroupe par phase, exécute séquentiellement
    
    async def execute_phase(phase_config: dict, tasks: list) -> dict
        # Pour une phase : sub-batch generate → aggregate → Elena review → Jordan deploy
    
    async def generate_phase_batches(agent: str, tasks: list, phase: int, context: PhaseContextRegistry) -> list
        # Génère les sous-lots pour une phase
    
    def group_tasks_by_phase(all_tasks: list) -> dict
        # Regroupe les tâches WBS par phase en fonction du task_type
    
    def classify_validation_rule(task: TaskExecution) -> str
        # Distingue simple_validation_rule (Phase 1) de complex (Phase 4)
```

### 6.2 phase_aggregator.py (NOUVEAU)

**Rôle** : Fusionne les outputs des sous-lots en un output de phase unifié.

```python
class PhaseAggregator:
    def aggregate_data_model(batch_results: list) -> dict
        # Fusionne les plans JSON Raj en un plan unifié, vérifie pas de collision d'API names
    
    def aggregate_source_code(batch_results: list) -> dict
        # Fusionne les fichiers .cls/.trigger/.js/.html en un dict unique
    
    def aggregate_automation(batch_results: list) -> dict
        # Fusionne flows + validation rules
    
    def aggregate_security(batch_results: list) -> dict
        # Fusionne permission sets + profiles
    
    def aggregate_data_migration(batch_results: list) -> dict
        # Fusionne scripts migration
```

### 6.3 phase_context_registry.py (NOUVEAU)

**Rôle** : Maintient le contexte entre les lots et les phases.

Voir §4.3 pour la spec complète.

**Méthodes principales :**
```python
class PhaseContextRegistry:
    def get_context_for_batch(phase: int) -> str
        # Retourne le contexte à injecter dans le prompt du lot
    
    def register_batch_output(phase: int, output: dict)
        # Met à jour le registre après un lot
    
    def get_full_data_model() -> str
        # Retourne le modèle de données complet (pour phases 2+)
    
    def get_class_signatures() -> str
        # Retourne les signatures Apex (pour phases 3+)
    
    def get_component_signatures() -> str
        # Retourne les signatures LWC (pour phases 4+)
```

### 6.4 jordan_deploy_service.py (NOUVEAU)

**Rôle** : Service centralisé de déploiement, utilisé par Jordan.

```python
class JordanDeployService:
    async def deploy_phase(phase_config: dict, pr_url: str, output: dict) -> dict
        # Point d'entrée unique. Route vers la bonne méthode selon phase.
    
    async def merge_pr(pr_url: str) -> dict
        # Merge la PR de phase
    
    async def deploy_admin_config(plan: dict) -> dict
        # Phase 1/4/5: Exécute le plan JSON via Tooling API
    
    async def deploy_source_code(files: dict) -> dict
        # Phase 2/3: Deploy via SFDX source deploy
    
    async def execute_data_migration(scripts: dict) -> dict
        # Phase 6: Execute Anonymous Apex + commit artifacts
    
    async def retrieve_metadata(objects: list) -> dict
        # Post-Raj: Récupère metadata propre depuis sandbox
    
    async def rollback_phase(merge_sha: str) -> dict
        # Revert le merge en cas d'échec
    
    async def tag_phase(phase: int, phase_name: str) -> dict
        # Tag Git après succès
    
    async def generate_final_package_xml(all_phases: list) -> dict
        # Fin de BUILD: package.xml complet
```

### 6.5 sf_admin_service.py (NOUVEAU)

**Rôle** : Exécute les plans JSON Raj via l'API Salesforce (Tooling API / Metadata API).

```python
class SFAdminService:
    OPERATION_HANDLERS = {
        'create_object': '_create_custom_object',
        'create_field': '_create_custom_field',
        'create_record_type': '_create_record_type',
        'create_list_view': '_create_list_view',
        'create_validation_rule': '_create_validation_rule',
        'create_flow': '_create_flow',
        'create_permission_set': '_create_permission_set',
        'create_page_layout': '_create_page_layout',
        'create_sharing_rule': '_create_sharing_rule',
        'create_approval_process': '_create_approval_process',
    }
    
    async def execute_plan(plan: dict) -> dict
        # Exécute les opérations séquentiellement (respecte l'order)
    
    async def _create_custom_object(op: dict) -> dict
        # POST /services/data/v59.0/tooling/sobjects/CustomObject/
    
    async def _create_custom_field(op: dict) -> dict
        # POST /services/data/v59.0/tooling/sobjects/CustomField/
        # Gère tous les field_types (Text, Picklist, Lookup, etc.)
    
    async def _tooling_api_create(sobject_type: str, payload: dict) -> dict
        # Appel Tooling API générique avec gestion erreurs
    
    async def _tooling_api_delete(sobject_type: str, id: str) -> dict
        # Pour rollback
```

**Authentification** : Utilise la connexion Salesforce déjà configurée dans le projet (SFDX auth ou OAuth).

### 6.6 Modifications sfdx_service.py

**Ajouts :**

```python
async def retrieve_metadata(metadata_type: str, metadata_name: str) -> dict
    # sf project retrieve start --metadata {type}:{name}
    # Utilisé après deploy Tooling API de Raj pour récupérer le source format

async def execute_anonymous(apex_code: str) -> dict
    # sf apex run --file {temp_file}
    # Utilisé pour les scripts data migration d'Aisha

async def deploy_with_manifest(package_xml_path: str) -> dict
    # sf project deploy start --manifest {path}
    # Deploy avec package.xml explicite
```

### 6.7 Modifications git_service.py

**Ajouts :**

```python
async def create_branch(branch_name: str, from_branch: str = "develop") -> dict
    # Crée une feature branch pour la phase

async def create_pr(branch: str, title: str, body: str, base: str = "develop") -> dict
    # Crée une Pull Request via GitHub API

async def merge_pr(pr_number: int) -> dict
    # Merge la PR via GitHub API

async def revert_merge(merge_sha: str) -> dict
    # Revert un merge commit

async def tag(tag_name: str, message: str) -> dict
    # Crée un tag Git
    
async def get_pr_files(pr_number: int) -> list
    # Liste les fichiers d'une PR
```

---

## 7. Modèle de données

### 7.1 Modifications table task_executions

Ajouter la colonne `build_phase` :

```sql
ALTER TABLE task_executions ADD COLUMN build_phase INTEGER;
-- Phase 1-6, rempli par le PhasedBuildExecutor lors du regroupement
```

### 7.2 Nouvelle table : project_data_sources

```sql
CREATE TABLE project_data_sources (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,               -- "Contacts clients"
    target_object VARCHAR(100) NOT NULL,       -- "Contact", "Case", "Formation__c"
    source_type VARCHAR(50) NOT NULL DEFAULT 'csv',  -- V1: 'csv' uniquement
    config JSONB NOT NULL,                     -- Config spécifique au type
    column_mapping JSONB,                      -- Mapping colonnes source → champs SF
    import_order INTEGER DEFAULT 0,            -- Ordre d'import (parents avant enfants)
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index
CREATE INDEX idx_project_data_sources_project ON project_data_sources(project_id);

-- Config CSV example:
-- {
--   "file_path": "/data/imports/contacts.csv",
--   "encoding": "utf-8",
--   "delimiter": ",",
--   "has_header": true,
--   "columns": ["Nom", "Prénom", "Email", "Téléphone"]
-- }

-- Config Database example (V2):
-- {
--   "host": "db.example.com",
--   "port": 5432,
--   "database": "legacy_crm",
--   "schema": "public",
--   "table": "contacts",
--   "api_format": "postgresql"
-- }
```

### 7.3 Nouvelle table : build_phase_executions

```sql
CREATE TABLE build_phase_executions (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER NOT NULL REFERENCES executions(id),
    phase_number INTEGER NOT NULL,             -- 1-6
    phase_name VARCHAR(50) NOT NULL,           -- "data_model", "business_logic", etc.
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, running, review, deploying, completed, failed
    agent_id VARCHAR(20) NOT NULL,             -- raj, diego, zara, aisha
    
    -- Lots
    total_batches INTEGER DEFAULT 0,
    completed_batches INTEGER DEFAULT 0,
    
    -- Review Elena
    elena_verdict VARCHAR(10),                 -- PASS, FAIL
    elena_feedback TEXT,
    elena_review_count INTEGER DEFAULT 0,      -- Nombre de reviews (retries)
    
    -- Deploy Jordan
    deploy_method VARCHAR(20),                 -- tooling_api, sfdx_source, data_scripts
    deploy_result JSONB,
    
    -- Git
    branch_name VARCHAR(100),
    pr_url VARCHAR(255),
    pr_number INTEGER,
    merge_sha VARCHAR(40),
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Errors
    last_error TEXT,
    attempt_count INTEGER DEFAULT 0,
    
    UNIQUE(execution_id, phase_number)
);

CREATE INDEX idx_build_phases_execution ON build_phase_executions(execution_id);
```

---

## 8. Plan d'implémentation

### 8.1 Ordre des tâches

| Étape | Composant | Description | Dépend de | Effort |
|---|---|---|---|---|
| **A** | `phase_context_registry.py` | Registre de contexte (fondation) | - | 1h |
| **B** | `phase_aggregator.py` | Agrégateur de lots | - | 1h |
| **C** | `sf_admin_service.py` | Tooling API pour Raj | - | 3h |
| **D** | Raj prompts BUILD (JSON) | Nouveau prompt Phase 1/4/5 | C | 1.5h |
| **E** | Diego corrections | sanitize + prompt enrichi | A | 45min |
| **F** | Zara corrections | naming + parser robuste | - | 45min |
| **G** | Elena corrections | auto-PASS fix + validation structurelle + 6 prompts | - | 2h |
| **H** | `jordan_deploy_service.py` | Service deploy centralisé | C | 2h |
| **I** | git_service.py extensions | PR, merge, revert, tag | - | 1.5h |
| **J** | sfdx_service.py extensions | retrieve, execute_anonymous | - | 1h |
| **K** | agent_executor.py fix | Retirer Jordan/Elena de non_build_agents | - | 10min |
| **L** | DB migrations | Tables build_phase_executions + project_data_sources | - | 30min |
| **M** | `phased_build_executor.py` | Orchestrateur principal | A,B,C,D,E,F,G,H,I,J,K,L | 3h |
| **N** | Aisha data sources | Config + prompt Phase 6 | L | 2h |
| **O** | Frontend BUILD monitoring | Adapter BuildMonitoringPage pour afficher les phases | M | 2h |
| **P** | Test end-to-end FormaPro | Exécution BUILD complète | M | 2h |

### 8.2 Regroupement en sessions

**Session 1 : Fondations** (A + B + L + K)
- PhaseContextRegistry
- PhaseAggregator
- Migrations DB
- Fix agent_executor non_build_agents
- Estimé : 3h

**Session 2 : Raj + Tooling API** (C + D)
- sf_admin_service.py
- Prompts Raj JSON (Phase 1, 4, 5)
- Test unitaire : créer un objet + champs via Tooling API sur sandbox
- Estimé : 4h

**Session 3 : Jordan + Git** (H + I + J)
- jordan_deploy_service.py
- Extensions git_service (PR, merge, revert, tag)
- Extensions sfdx_service (retrieve, execute_anonymous)
- Test unitaire : merge PR + deploy + tag
- Estimé : 4h

**Session 4 : Diego + Zara + Elena** (E + F + G)
- Diego sanitize + prompt enrichi
- Zara naming + parser
- Elena : fix auto-PASS + validation structurelle + 6 prompts review
- Estimé : 3.5h

**Session 5 : Orchestrateur** (M)
- phased_build_executor.py (le cœur)
- Intègre tous les services créés en sessions 1-4
- Test : exécuter Phase 1 seule sur FormaPro
- Estimé : 3h

**Session 6 : Aisha + Frontend + E2E** (N + O + P)
- Aisha data sources config + prompt
- Frontend BuildMonitoringPage adapté aux phases
- Test end-to-end BUILD complet sur FormaPro
- Estimé : 4h

**Total : ~6 sessions, ~21h de travail**

### 8.3 Critères de succès par session

| Session | DONE si... |
|---|---|
| 1 | PhaseContextRegistry unit tests passent + table créée en DB |
| 2 | `sf_admin_service.execute_plan()` crée un objet + 3 champs sur sandbox FormaPro |
| 3 | Jordan merge une PR, deploy le contenu, tag → vérifié sur GitHub + sandbox |
| 4 | Diego sanitize corrige un SOQL mal formé + Elena rejette un code avec accolades déséquilibrées |
| 5 | Phase 1 de FormaPro : Raj génère → Elena review → Jordan deploy → objets visibles dans sandbox |
| 6 | BUILD complet FormaPro : 6 phases → code déployé → données importées → tout fonctionne |

---

## 9. Checklist de validation

### 9.1 Avant de commencer une session

- [ ] Lire PROGRESS.log (dernières 50 lignes)
- [ ] Vérifier que les sessions précédentes sont bien commitées
- [ ] Identifier la session cible dans le plan §8.2
- [ ] Vérifier les prérequis (sessions antérieures terminées)

### 9.2 Pendant le développement

- [ ] UNE fonctionnalité à la fois
- [ ] Tests unitaires pour chaque service créé
- [ ] Ne pas modifier incremental_executor.py (on le conserve, on construit à côté)
- [ ] Respecter les noms de fichiers et méthodes de cette spec
- [ ] Logger avec le format `[PhasedBuild]`, `[Jordan]`, `[Elena]`, `[Raj]`, etc.

### 9.3 Tests end-to-end (Session 6)

- [ ] Phase 1 : Tous les objets/champs FormaPro créés dans la sandbox
- [ ] Phase 2 : Toutes les classes Apex déployées et compilent
- [ ] Phase 3 : Tous les LWC déployés et chargent
- [ ] Phase 4 : Tous les Flows actifs
- [ ] Phase 5 : Permission Sets attribués
- [ ] Phase 6 : Données de test importées
- [ ] Git : 6 PRs mergées + 6 tags + 1 tag release
- [ ] Pas d'erreur dans les logs backend
- [ ] Coût total BUILD < $1
- [ ] Temps total BUILD < 30 minutes

---

## ANNEXES

### A. Mapping task_type → phase

```python
TASK_TYPE_TO_PHASE = {
    # Phase 1: Data Model
    "create_object": 1,
    "create_field": 1,
    "record_type": 1,
    "list_view": 1,
    "simple_validation_rule": 1,
    
    # Phase 2: Business Logic
    "apex_class": 2,
    "apex_trigger": 2,
    "apex_test": 2,
    "apex_helper": 2,
    "apex_batch": 2,
    "apex_scheduler": 2,
    
    # Phase 3: UI Components
    "lwc_component": 3,
    "aura_component": 3,
    "flexipage": 3,
    "custom_tab": 3,
    
    # Phase 4: Automation
    "flow": 4,
    "complex_validation_rule": 4,
    "approval_process": 4,
    "workflow_rule": 4,
    
    # Phase 5: Security & Access
    "permission_set": 5,
    "profile": 5,
    "sharing_rule": 5,
    "page_layout": 5,
    "page_layout_assignment": 5,
    
    # Phase 6: Data Migration
    "data_migration": 6,
    "data_load": 6,
    "data_transform": 6,
    "data_validation": 6,
}
```

### B. Statuts de phase

```python
class PhaseStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"     # Agent en train de générer les lots
    AGGREGATING = "aggregating"   # Fusion des lots
    REVIEWING = "reviewing"       # Elena review
    PR_CREATED = "pr_created"     # PR créée, en attente Jordan
    DEPLOYING = "deploying"       # Jordan déploie
    RETRIEVING = "retrieving"     # Jordan retrieve metadata (post-Raj)
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"               # En retry après feedback Elena ou échec deploy
```

### C. Ordre de priorité implémentation (résumé)

```
Session 1: Fondations (registry, aggregator, DB, fix agent_executor)
Session 2: Raj + Tooling API
Session 3: Jordan + Git + SFDX extensions
Session 4: Diego + Zara + Elena fixes
Session 5: PhasedBuildExecutor (le cœur)
Session 6: Aisha + Frontend + Test E2E
```
