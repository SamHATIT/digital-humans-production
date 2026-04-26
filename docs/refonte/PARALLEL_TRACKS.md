# PARALLEL_TRACKS — Pilotage des chantiers en parallèle

> **Maître d'œuvre** : Claude (chat principal Sam)
> **Mis à jour** : 2026-04-26 (après merge A1)
> **Référence** : MASTER_PLAN_V4.md

---


## ⚠️ Règle d'or — production vs preview

**Le site live `digital-humans.fr` (React/Tailwind actuel, blog inclus) ne doit pas être modifié.**

Tout le travail de refonte Studio se fait sur :
- `/var/www/dh-preview/` (basic auth `preview:a88PtPREkPe9`) — version visuelle qu'on construit module par module (`dh-mod1` → `dh-modN`)
- Le repo `digital-humans-website` actuel reste figé jusqu'à la bascule de Phase 2 site.

La bascule prod = remplacement complet du bundle au moment où la version Studio est validée bout-en-bout, pas un patch progressif.

Conséquence pour les briefs :
- Tout brief Track A qui touche au frontend public **doit cibler le preview**, pas `digital-humans-website` en prod
- Les composants prod servent de **référence fonctionnelle** (architecture, intégrations API, etc.) mais sont en lecture seule

---

## Vue d'ensemble

Trois tracks tournent en parallèle pour exécuter le MASTER_PLAN_V4 plus rapidement :

- **Track A** = Claude Code (autonome sur le VPS, branches `claude/*`)
- **Track B** = Claude Design (mockups + specs)
- **Track C** = Sam + Maître d'œuvre (intégration, arbitrages, sujets sensibles)

---

## Statut des tracks

Légende : 🟦 queued · 🟢 running · 🟡 review · 🟣 merged · 🔴 blocked

| Track | Mission | Owner | Brief | Branche | Statut | Notes |
|---|---|---|---|---|---|---|
| **A1** | Finalisation SDS templating | Claude Code | `BRIEF_A1_SDS_TEMPLATING_FINAL.md` | `claude/sds-templating-final-audit-5qtf9` | 🟣 **MERGED** (`b56a76b`, tag `v2026.04-sds-templating-complete`) | Phase 1 du MASTER_PLAN_V4 close |
| **A2** | Audit secrets + Doppler | Claude Code | `BRIEF_A2_SECURITY_AUDIT.md` | `claude/security-secrets-manager` | 🟦 queued | Toujours pertinent. À lancer quand tu veux |
| **B1** | Atelier cinématique agents | Claude Design | `BRIEF_B1_AGENTS_CINEMATIC.md` | n/a (mockups) | 🟣 **VALIDÉ** | Direction retenue : **Casting → Théâtre** (séquentiel) |

---

## Round 1 — bilan

✅ **Track A1 closed** — merged sur main, tag posé, smoke test endpoints OK md5-identique.
✅ **Track B1 closed** — direction Casting → Théâtre validée par Sam (combinaison Casting № 01 onboarding + Théâtre № 02 usage quotidien).
🟦 **Track A2 still queued** — Sam peut le lancer quand il veut (rotation OpenAI déjà faite, le reste = audit + Doppler).

---

## Round 2 — préparation

Briefs à produire pour ce round :

| Track | Mission | Pré-requis |
|---|---|---|
| **A4** | Phase 3.1+3.2 — Schéma DB crédits + CreditService | Aucun |
| **A5** | Phase 4 plateforme UI Studio (Casting→Théâtre) | Spec issue de B1 (existe), Phase 3.1 utile mais non bloquant |
| **B2** | Mockups galerie acte 3 site (cards projets, hover states) | Aucun |
| **B3** (optionnel) | Affinage du flux de transition Casting → Théâtre | Décisions Sam sur conditions de bascule |
| **C1** | Séance arbitrage O1 (planning ouverture) + O2 (Mid tier oui/non) | Sam dispo |

---

## Garde-fous communs

### Pour Claude Code (Track A)
- Une branche par tâche, format `claude/<scope>-<task>` (créée depuis la branche de référence)
- Commits atomiques, conventions `<type>(<scope>): <description>`
- Push sur GitHub à chaque commit logique
- **❌ Jamais de merge sur `main`** — c'est le rôle du maître d'œuvre après revue
- Rapport de fin de session structuré

### Pour Claude Design (Track B)
- Mockups statiques (pas de code)
- Charte Studio respectée (palette, typo, rim rule)
- Spec écrite produite en complément des visuels
- Recommandation explicite + justification

### Pour le maître d'œuvre (Track C / moi)
- Revue systématique de chaque livrable Track A avant merge
- Validation VPS quand Claude Code n'a pas pu (sandbox sans DB/services)
- Rédaction des briefs round suivant en fonction des résultats
- Mise à jour de ce document à chaque transition de statut

---


## Décisions Track C actées

| # | Sujet | Décision | Date |
|---|---|---|---|
| **O1** | Planning d'ouverture (date Free/Pro/Team) | **On finit tous les travaux et on décide.** Pas de date figée maintenant. Wording "early access" générique sur le site. | 2026-04-26 |
| **O2** | Palier Mid 299-399 € au lancement ? | **Non, 3 paliers au lancement** (Free / Pro 49€ / Team 1490€ + Enterprise sur devis). Mid sera ajouté plus tard comme "réponse à demande grandissante" si les agences le demandent. Page tarifs = 3 colonnes. | 2026-04-26 |

---

## Journal des transitions

| Date | Événement |
|---|---|
| 2026-04-26 | 🚀 Création du dispositif. Round 1 lancé. Briefs A1 + A2 + B1 produits. |
| 2026-04-26 | ✅ A1 livré par Claude Code (interpretation conservative, audit + cleanup legacy) |
| 2026-04-26 | ✅ B1 livré par Claude Design (4 directions mockées, recommandation Théâtre + Carte) |
| 2026-04-26 | ✅ A1 validé sur VPS par maître d'œuvre (smoke 3 endpoints md5-identique) |
| 2026-04-26 | 🎯 A1 mergé sur main (`b56a76b`), tag `v2026.04-sds-templating-complete` |
| 2026-04-26 | ✅ B1 validé par Sam — direction **Casting → Théâtre** (séquentielle) retenue |
| 2026-04-26 | 🟦 Round 2 en préparation — briefs A4, A5, B2, B3 à produire |

---

*Document de pilotage · Digital Humans · MASTER PLAN V4 · 26 avril 2026*
