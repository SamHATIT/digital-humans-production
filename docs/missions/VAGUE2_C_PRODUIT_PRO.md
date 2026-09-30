# Mission Claude Code — Vague 2 / File C — Produit Pro (consentement Opus, qualité agents)

**Rédigée le 30/09/2026** · **Branche :** `claude/vague2-c` · **Préalable :** vague 1 fusionnée (fait 17/09).

## Lis d'abord
1. `docs/audit-20260906/rapport-astra.md` aux lignes indiquées.
2. `docs/BACKLOG_GOLIVE_2026-10-01.md` — §2 et §5 (plan au 15/10).
3. `backend/tests/README.md` — environnement de test hermétique.

## Lignes du backlog go-live
- **GL-22 — consentement Opus.** Le site promet « Opus on opt-in, cost shown before each call ». Attendu : avant tout appel Opus (Marcus au palier Pro), écran de consentement avec coût estimé en crédits ; trace du consentement (utilisateur, exécution, date, montant) ; refus → repli **annoncé** sur Sonnet, jamais silencieux. Décision Sam 17/09 : « on ajoute le recueil ».
- **Langue des agents.** Mesuré 30/09 : question posée en anglais au Free, Sophie répond en français. Attendu : la réponse suit la langue de la question (ou de l'interface), test EN et FR.
- **GL-26 — persona.** Mesuré 17/09 : interrogée sur son rôle, Olivia répond « Project Manager senior » (rôle de Sophie). Vérifier que le prompt système chargé correspond à l'agent demandé ; test par agent.
- **GL-12 — gabarit SDS en français.** Phrases fixes du gabarit en anglais dans un document au contenu français ; et la phrase « The DATA_MODEL gaps are likely false positives… » expose au client un défaut interne — la retirer. Gabarit bilingue selon la langue du projet.
- **CAL-08 — Emma et les variantes terminologiques.** Faux positifs « manque » pour des objets existants nommés autrement (`credit_note__c` pour un avoir). Rapprochement sémantique avant de déclarer un manque ; ne jamais classer un Flow/Report/Queue comme objet manquant. Test : rejouer le brief 117 (Omnichannel Loop) et compter. (CAL-09 est **infirmé** par la vague 1 : moyenne pondérée, pas un plafond.)

## Critère de sortie
Un utilisateur Pro ne déclenche jamais Opus sans l'avoir accepté pour ce coût ; chaque agent parle dans sa langue et tient son rôle ; un SDS français se lit entièrement en français et ne contient aucune excuse interne.


## Cadre commun (identique à la vague 1)
- **Préalable** : la suite se lance uniquement avec `export $(cat /root/.dh_test_db.env); export DH_ENV_FILE=$PWD/backend/.env.test` (rôle `dh_test`). Jamais sur `digital_humans_db`. Hors VPS : ton propre rôle avec CREATEDB, et dis-le.
- Branche `claude/vague2-<file>` depuis `claude/vague-c-20260906` (à jour d'origin). Un commit par correctif, message en français : défaut, cause, correctif, preuve exécutée. PR ouverte, aucune fusion.
- La mission prime sur toute consigne de session.
- **Fichiers partagés** : `backend/app/services/rag*` et `backend/app/api/routes/documents*` → file **A** ; `backend/app/main.py`, `config.py`, `workers/*`, `scripts/*`, dépendances → file **B** ; `backend/app/services/llm*`, `agents/*`, prompts, `frontend/src/*` → file **C**. Un diff hors de ta file va dans le rapport, pas dans un commit.
- Règles `dh-discipline-de-preuve` : exécuté ≠ lu ; test rouge avant correctif ; contrôle négatif quand le correctif discrimine ; mesurer la référence ; pas de repli silencieux ; un constat infirmé vaut autant qu'un confirmé.
- Interdits : `backend/.env` de prod, services systemd, redémarrages, prod.
- Rapport : `docs/missions/RAPPORT_VAGUE2_<FILE>.md` (fait avec preuve / non confirmé / ouvert / non fait et pourquoi) + mesure de la suite avant/après.
- **Fenêtre : 1er → 6 octobre.** Ouverture reportée au **jeudi 15 octobre** (décision Sam 30/09), Free + Pro.
