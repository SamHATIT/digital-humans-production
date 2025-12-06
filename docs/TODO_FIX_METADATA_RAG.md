# TODO: Correction Métadonnées + RAG - Session 05 Décembre 2025

## Contexte du Problème

### Symptôme observé
- Le BA génère des UCs génériques ("Business User Creates Custom Object") au lieu d'UCs métier ("Client soumet une demande de service")
- Le RAG retourne du contenu Marketing Cloud/Einstein au lieu de Service Cloud quand on demande "Service Request"

### Causes identifiées

1. **Récupération métadonnées défaillante**
   - `sf org display` ne retourne pas l'édition Salesforce
   - `--sobject-type` flag incorrect → 0 objets récupérés
   - Résultat : `org_edition: Unknown`, `total_objects: 0`

2. **RAG non filtré**
   - Le BA ne filtre pas par catégorie cloud
   - Déséquilibre massif : Marketing Cloud = 4001 chunks, Sales Cloud = 87 chunks
   - Résultat : requêtes polluées par contenu non pertinent

3. **Timing workflow**
   - Métadonnées récupérées APRÈS le BA (pour l'Architect)
   - Le BA n'a donc pas le contexte de l'org pour filtrer le RAG

---

## Corrections à Apporter

### 1. Corriger `_get_salesforce_metadata()` 

**Fichier:** `/backend/app/services/pm_orchestrator_service_v2.py`

**Modifications:**

```python
# A. Ajouter query SOQL pour l'édition
org_query = "SELECT Id, Name, OrganizationType, IsSandbox, InstanceName, LanguageLocaleKey FROM Organization"
org_result = sf data query --query "{org_query}" --target-org {alias} --json

# B. Corriger la commande sobject list
# AVANT (incorrect):
objects_cmd = f"sf sobject list --sobject-type all --target-org {alias} --json"
# APRÈS (correct):
objects_cmd = f"sf sobject list --sobject ALL --target-org {alias} --json"

# C. Ajouter détection des clouds activés
def _detect_enabled_clouds(objects: List[str]) -> Dict[str, bool]:
    return {
        "service_cloud": any(o in objects for o in ["Case", "Entitlement", "WorkOrder"]),
        "sales_cloud": any(o in objects for o in ["Lead", "Opportunity", "Campaign"]),
        "experience_cloud": any(o in objects for o in ["Network", "Site"]),
        "field_service": "ServiceAppointment" in objects,
        "cpq": "SBQQ__Quote__c" in objects,
        "data_cloud": any(o in objects for o in ["DataCloudIngestionAPI", "UnifiedIndividual"])
    }

# D. Enrichir le summary
summary["org_edition"] = org_data["OrganizationType"]  # "Developer Edition", "Enterprise", etc.
summary["enabled_clouds"] = _detect_enabled_clouds(objects)
summary["is_sandbox"] = org_data["IsSandbox"]
```

### 2. Avancer la récupération metadata dans le workflow

**Workflow actuel:**
```
PM (extract BRs) → BA (generate UCs) → [Metadata] → Architect
```

**Workflow proposé:**
```
PM (extract BRs) → [Metadata + Summary] → BA (avec contexte) → Architect (lit DB)
```

**Modifications:**
- Déplacer l'appel `_get_salesforce_metadata()` avant le BA
- Stocker dans DB avec `deliverable_type = "system_salesforce_metadata"`
- L'Architect lit depuis la DB au lieu de recevoir en paramètre

### 3. Modifier le BA pour utiliser le contexte

**Fichier:** `/backend/agents/roles/salesforce_business_analyst.py`

**Option A - Utiliser `salesforce_product` du projet:**
```python
# Dans le service qui appelle le BA
product = project.salesforce_product  # "Service Cloud", "Sales Cloud", etc.
category_map = {
    "Service Cloud": "service_cloud",
    "Sales Cloud": "sales_cloud",
    # ...
}
rag_category = category_map.get(product)

# Passer au BA
input_data = {
    "business_requirement": br,
    "rag_filter": rag_category  # Nouveau paramètre
}
```

**Option B - Utiliser le summary metadata:**
```python
# Dans salesforce_business_analyst.py
if metadata_summary.get("enabled_clouds", {}).get("service_cloud"):
    rag_context = get_salesforce_context(query, n_results=5, category="service_cloud")
```

### 4. (Optionnel) Rééquilibrer le RAG

**Stats actuelles:**
| Catégorie | Chunks |
|-----------|--------|
| marketing_cloud | 4001 |
| service_cloud | 1730 |
| general | 1276 |
| revenue_cloud | 1046 |
| commerce_cloud | 1013 |
| expert_books | 847 |
| sales_cloud | **87** ← Problème |

**Actions possibles:**
- Ajouter plus de documentation Sales Cloud
- Ou toujours filtrer par catégorie (solution retenue)

---

## Points à discuter avant implémentation

1. **Stratégie RAG multi-cloud:** Comment gérer un projet Sales + Service Cloud ?
   - Filtrer par les deux catégories ?
   - Pas de filtre mais query enrichie ?

2. **Licences et applications:** Sam mentionne que les clouds activés sont visibles dans la gestion des licences - à investiguer pour une détection plus fiable

3. **Fallback:** Que faire si les métadonnées ne sont pas disponibles (pas de connexion SFDX) ?
   - Utiliser uniquement `salesforce_product` du projet ?

---

## Fichiers impactés

1. `/backend/app/services/pm_orchestrator_service_v2.py` - Workflow + metadata
2. `/backend/agents/roles/salesforce_business_analyst.py` - Filtrage RAG
3. `/backend/app/services/rag_service.py` - Déjà supporte le paramètre `category`

---

*Document créé le 05/12/2025 - En attente discussion RAG*
