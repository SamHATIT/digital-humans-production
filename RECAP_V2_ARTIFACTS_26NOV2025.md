# RÉCAPITULATIF V2 ARTIFACTS - 26 Novembre 2025

## 📍 ÉTAT ACTUEL

**Commit:** `b81e99e` - `feat(V2): Add structured artifacts output to all agents`  
**Tag:** `v2.1.0-artifacts`  
**Branche:** `main`  
**Backend:** Redémarré et opérationnel

---

## ✅ CE QUI A ÉTÉ FAIT

### 1. Prompts des Agents Modifiés (7 agents)

| Agent | Fichier | Lignes | Artifacts Produits |
|-------|---------|--------|-------------------|
| BA | `salesforce_business_analyst.py` | 569 | BR-xxx, UC-xxx |
| Architect | `salesforce_solution_architect.py` | 1046 | ADR-xxx, SPEC-xxx |
| Apex | `salesforce_developer_apex.py` | 761 | CODE-xxx |
| LWC | `salesforce_developer_lwc.py` | 912 | CODE-xxx |
| Admin | `salesforce_admin.py` | 736 | CFG-xxx |
| QA | `salesforce_qa_tester.py` | 836 | TEST-xxx |
| Trainer | `salesforce_trainer.py` | 419 | DOC-xxx |

**Ajouts dans chaque prompt :**
- Section `## 📦 STRUCTURED ARTIFACTS OUTPUT (MANDATORY)`
- Format exact à suivre : `### BR-001: [Title]`
- Champs structurés (Priority, Category, Description, Acceptance Criteria, etc.)
- Règles de numérotation
- Exemples de mapping (BR → UC, ADR → SPEC, etc.)

### 2. Fonction d'Extraction Réécrite

**Fichier:** `backend/app/services/pm_orchestrator_service.py`

**Nouvelles fonctions:**
- `_extract_artifacts_from_agent_output()` - Parse le format `### PREFIX-NNN: Title`
- `_parse_artifact_fields()` - Extrait les champs structurés
- `_extract_parent_refs()` - Détecte les références parent

**Logique:**
1. Identifie l'agent (ba, architect, apex, lwc, admin, qa, trainer)
2. Cherche les patterns correspondants (BR/UC pour BA, ADR/SPEC pour Architect, etc.)
3. Parse chaque artifact trouvé avec regex
4. Extrait les champs structurés (Priority, Category, etc.)
5. Détecte les parent_refs (Parent BR, Related UC, etc.)
6. Fallback sur artifact unique si format non détecté

---

## 🧪 À TESTER

### Test à lancer dans la prochaine session

1. **Créer une nouvelle exécution** avec BA + Architect sélectionnés
2. **Vérifier la sortie du BA** :
   - Génère-t-il des `### BR-001:`, `### UC-001:` ?
   - Avec les champs structurés (Priority, Category, etc.) ?
3. **Vérifier le parsing** :
   - Les artifacts sont-ils extraits individuellement ?
   - Les parent_refs sont-ils corrects (UC → BR) ?
4. **Vérifier la base de données** :
   ```sql
   SELECT artifact_code, artifact_type, title, parent_refs 
   FROM execution_artifacts 
   WHERE execution_id = [NEW_ID]
   ORDER BY artifact_code;
   ```

### Résultat attendu

```
BR-001  business_req  Customer Case Management        []
UC-001  use_case      Create case from web form       ["BR-001"]
UC-002  use_case      Create case from email          ["BR-001"]
BR-002  business_req  Lead Scoring System             []
UC-003  use_case      Calculate initial score         ["BR-002"]
...
ADR-001 adr           Use Flow for Case Assignment    ["UC-001", "UC-002"]
SPEC-001 spec         Flow - Auto_Assign_Case         ["ADR-001"]
...
```

---

## 📂 FICHIERS MODIFIÉS

```
backend/
├── agents/roles/
│   ├── salesforce_admin.py              # +80 lignes (CFG-xxx)
│   ├── salesforce_business_analyst.py   # +102 lignes (BR/UC-xxx)
│   ├── salesforce_developer_apex.py     # +70 lignes (CODE-xxx)
│   ├── salesforce_developer_lwc.py      # +83 lignes (CODE-xxx)
│   ├── salesforce_qa_tester.py          # +100 lignes (TEST-xxx)
│   ├── salesforce_solution_architect.py # +166 lignes (ADR/SPEC-xxx)
│   └── salesforce_trainer.py            # +85 lignes (DOC-xxx)
└── app/services/
    └── pm_orchestrator_service.py       # Fonction extraction réécrite
```

---

## 🔗 RÉFÉRENCES

- **Spec V2:** `/mnt/project/SPEC_FINALE_DIGITAL_HUMANS_V2.md`
- **Spec Artifacts:** `/mnt/project/SPEC_EXECUTION_ARTIFACTS.md`
- **Dernière exécution (avant modifs):** #42 - Test V2 Evolution - Telco CRM
- **SDS téléchargeable:** https://digital-humans.fr/downloads/SDS_42_Test_V2_Evolution_-_Telco_CRM.docx

---

## ⚠️ PROBLÈME IDENTIFIÉ (avant modifs)

L'exécution #42 montrait que le BA générait UN SEUL artifact BR-001 contenant tout le markdown en blob, au lieu de BR/UC individuels. C'est ce que les modifications ci-dessus sont censées corriger.

---

*Document créé le 26 novembre 2025 à 15:35*
