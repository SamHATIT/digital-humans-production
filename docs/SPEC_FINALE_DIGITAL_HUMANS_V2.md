# SPÉCIFICATION FINALE - ARCHITECTURE DIGITAL HUMANS V2
**Date:** 26 Novembre 2025 | **Version:** 2.0 | **Statut:** Validée

## RÉSUMÉ

Refonte architecture Digital Humans :
- 3 agents principaux (PM, BA, Architecte) + 7 workers
- Relation BR → UC (un BR peut avoir plusieurs UC)
- 6 gates de validation par lot
- Artefacts persistants en DB (pas de conversation)
- Questions inter-agents synchrones

## HIÉRARCHIE AGENTS

```
PM (Orchestration) ──► Notifie user aux gates
    │
    ├── BA (Analyse) ◄──► Architecte (Conception)
    │        │                    │
    │        ▼                    ▼
    └────► WORKERS (Exécutent SPEC précises)
           Diego, Zara, Raj, Elena, Jordan, Aisha, Lucas
```

## 6 GATES DE VALIDATION

| Gate | Phase | Artefacts | Qui corrige si rejet |
|------|-------|-----------|---------------------|
| 1 | Analyse | BR, UC | BA |
| 2 | Conception | ADR, SPEC | Architecte |
| 3 | Réalisation | CODE, CFG | Worker concerné |
| 4 | QA | TEST | Elena |
| 5 | Training | DOC | Lucas |
| 6 | Déploiement | - | Jordan |

## TABLES DB

- execution_artifacts (type, code, content JSONB, status, parent_refs)
- validation_gates (gate_number, status, artifacts_count)
- agent_questions (from, to, question, answer, status)

## TYPES ARTEFACTS

REQ → BR → UC → Q → ADR → SPEC → CODE/CFG → TEST → DOC

## STATUTS

draft → pending_review → approved/rejected → superseded

## PROCHAINES ÉTAPES

1. Migration DB
2. Services backend
3. Nouveaux prompts BA + Architecte
4. Interface web validation

---
*Référence complète: SPEC_FINALE_DIGITAL_HUMANS_V2.md*
