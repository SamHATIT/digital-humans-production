# E2E #141 — Coverage Analysis: Why Marcus Stays at ~62%

## TL;DR

Marcus produit une architecture **structurellement complète** (toutes les sections existent) mais **superficielle** — ses éléments sont des noms et listes de features, pas des spécifications implémentables. Emma évalue correctement ce manque de profondeur.

## Scores

| Tentative | Score | Programmatic | LLM | Notes |
|-----------|-------|-------------|-----|-------|
| Run 1 | 64.8% | 45% | 78% | Premier passage |
| Run 2 (ghost) | 61.2% | ? | ? | Ghost job, pas de rapport sauvé |
| Run 3 (revision) | 61.2% | ? | ? | Score identique = même problème |

## Scores par catégorie

| Catégorie | Score | Verdict |
|-----------|-------|---------|
| **Data Model** | 92% | ✅ Excellent — Marcus excelle ici |
| **Integration** | 70% | ⚠️ Noms et directions OK, détails API absents |
| **Automation** | 45% | ❌ Flows listés mais sans éléments Flow (Decision, Get Records...) |
| **Reporting** | 40% | ❌ Aucun report/dashboard défini |
| **UI Components** | 35% | ❌ LWC nommés mais pas de specs composants |
| **Security** | 30% | ❌ Permission sets = liste de permissions, pas de matrice CRUD |
| **UC Traceability** | 0% | ❌ Score programmatique, Emma n'a évalué que 20/136 UCs |

## Diagnostic : Profondeur vs Structure

### Ce que Marcus produit (exemple Flow) :
```json
{
  "name": "Email_to_Case_Processing",
  "type": "Record-Triggered Flow",
  "trigger": "After Create on EmailMessage",
  "purpose": "Process incoming emails...",
  "key_actions": [
    "Parse email body using Email_Extraction_Template__c rules",
    "Route to appropriate queue based on content analysis"
  ]
}
```

### Ce qu'Emma attend pour scorer 80%+ :
```json
{
  "name": "Email_to_Case_Processing",
  "type": "Record-Triggered Flow",
  "trigger": { "object": "EmailMessage", "event": "After Create", "condition": "..." },
  "elements": [
    { "type": "Get Records", "object": "Email_Extraction_Template__c", "filter": "..." },
    { "type": "Decision", "conditions": [
      { "name": "Is Duplicate", "criteria": "..." },
      { "name": "Needs Routing", "criteria": "..." }
    ]},
    { "type": "Create Records", "object": "Case", "field_values": { ... } },
    { "type": "Assignment", "queue": "...", "criteria": "..." }
  ],
  "error_handling": { ... },
  "test_coverage": { ... }
}
```

### Même pattern pour chaque section :

**Security** — Marcus : "Edit Social_Media_Message__c records" → Emma attend : matrice CRUD par objet/champ, profil par rôle, sharing rules avec critères

**LWC** — Marcus : "Dynamic icon based on Channel__c field" → Emma attend : @api properties, wire services, component hierarchy, CSS specs

**Integration** — Marcus : "Email-to-Case (On-Demand or Premium)" → Emma attend : endpoints, auth flow OAuth, payload schemas, error codes, retry strategy

## Gaps Critiques (12)

### 🔴 CRITICAL (2)
1. **Case Creation Flows** — Aucune automation Flow détaillée pour la création de cases (Email, Web, LinkedIn, Instagram, Chatbot)
   - Affecte : UC-001-01, UC-002-01, UC-003-01, UC-004-01
2. **Routing and Assignment Logic** — Pas de règles d'assignment, queues, ni logique de routage
   - Affecte : UC-001-02, UC-003-03, UC-004-03

### 🟡 HIGH (5)
3. **LinkedIn API Integration** — Pas de specs OAuth, webhook, polling
4. **Instagram/Meta API Integration** — Pas de specs Graph API, Meta Business Suite
5. **Permission Sets and Profiles** — Pas de matrice CRUD/FLS
6. **Duplicate Detection Automation** — Pas de Flow/Apex pour exécuter les règles de détection
7. **REST API Specification** — Pas d'endpoints, schemas, auth

### 🔵 MEDIUM (5)
8. Service Console Configuration
9. Social Media Profile Enrichment
10. Email Data Extraction Flow
11. Queue Definitions
12. Chatbot Platform Integration

## Recommandations d'Emma (prioritisées)

1. **P1** : Automation layer complet — Flows avec éléments, pas juste des noms
2. **P1** : Intégrations externes — LinkedIn API, Instagram Graph API, REST API avec auth et error handling
3. **P1** : Modèle sécurité — Permission sets, profiles, sharing rules, FLS détaillés
4. **P2** : UI components — Console config, LWC specs, dashboards
5. **P2** : Queue structure et assignment rules
6. **P3** : Reporting et analytics détaillés

## Pourquoi la révision ne change rien (ARCH-001)

Le cycle de révision est cassé :

1. **Pas de mode `revise`** — Marcus est appelé en `mode=design` (from scratch)
2. **Pas de previous design en input** — il ne sait pas ce qu'il a déjà produit
3. **Feedback vague** — il reçoit : *"Please revise to address 12 critical gaps: ..."* (une phrase)
4. **Pas de checklist** — il ne peut pas vérifier point par point ce qui manque

**Résultat** : il régénère le même type d'architecture shallow à chaque fois → même score.

### Fix proposé (ARCH-001)
- Nouveau mode `revise` pour Marcus
- Input = previous design + checklist structurée d'Emma (gap → composant attendu → action)
- Output = diff/patches sur l'architecture existante
- Validation = Emma checke les points corrigés, pas l'ensemble

## Score programmatique vs LLM

- **Programmatic (45%)** : Vérifie la présence de composants attendus par UC (Flows, LWC, Profiles...) → détecte les manques structurels
- **LLM (78%)** : Évalue la cohérence qualitative → reconnaît que Marcus couvre bien les concepts, même sans détails
- **Overall (64.8%)** : Moyenne pondérée → le score programmatique tire vers le bas

## Conclusion

Le problème n'est pas Marcus, c'est son **prompt**. Il produit une architecture de qualité "présentation client" (vue d'ensemble) au lieu d'une architecture de qualité "implémentation" (specs détaillées). Le prompt `design` doit explicitement demander le niveau de détail attendu par section, avec des exemples de ce qu'un score 90% ressemble.
