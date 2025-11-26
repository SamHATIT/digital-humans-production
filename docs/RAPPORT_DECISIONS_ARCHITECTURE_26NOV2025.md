# RAPPORT DE DÉCISIONS - REFONTE ARCHITECTURE DIGITAL HUMANS

**Date:** 26 Novembre 2025  
**Session:** Analyse critique SDS + Refonte architecture agents  
**Statut:** Décisions actées, en attente d'implémentation

---

## RÉSUMÉ EXÉCUTIF

Suite à l'analyse du SDS généré (score 4/10), décision de refondre l'architecture :
- **3 agents principaux** : PM (orchestration), BA (analyse), Architecte (conception)
- **7 workers** : Exécutent des specs précises au lieu de générer librement
- **Logique artefacts** : Documents persistants en DB pour éviter explosion contexte
- **RAGs spécialisés** : Par agent, "principes à appliquer" au lieu de "exemples à copier"

---

## ARCHITECTURE

```
        PM (Orchestration)
              │
    ┌─────────┴─────────┐
    ▼                   ▼
   BA  ◄──────────►  Architecte
    │                   │
    └─────────┬─────────┘
              ▼
         WORKERS
   (Diego, Zara, Raj, Elena, Jordan, Aisha, Lucas)
```

## FLUX

1. Requirements → BA décompose en Use Cases + Business Rules
2. BA ↔ Architecte itèrent via artefacts (pas conversation)
3. Architecte demande specs précises aux workers
4. Workers exécutent et reportent au PM

## TABLE ARTEFACTS

```sql
execution_artifacts (
    id, execution_id, artifact_type, producer_agent,
    version, content JSONB, parent_artifact_id, created_at
)
```

Types: use_cases, business_rules, questions, adrs, specs, code

## PROCHAINES ÉTAPES

1. Schéma execution_artifacts détaillé
2. Format JSON des artefacts
3. Nouveaux prompts BA + Architecte
4. Mécanisme questions inter-agents
5. Implémentation DB
6. Test end-to-end

---

*Référence session 26 novembre 2025*
