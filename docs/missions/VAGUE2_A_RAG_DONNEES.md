# Mission Claude Code — Vague 2 / File A — RAG et données (AS-06)

**Rédigée le 30/09/2026** · **Branche :** `claude/vague2-a` · **Préalable :** vague 1 fusionnée (fait 17/09).

## Lis d'abord
1. `docs/audit-20260906/rapport-astra.md` aux lignes indiquées.
2. `docs/BACKLOG_GOLIVE_2026-10-01.md` — §2 et §5 (plan au 15/10).
3. `backend/tests/README.md` — environnement de test hermétique.

## Pourquoi maintenant
Le Pro ouvre l'import de fichiers et la mémoire persistante. Astra classe SEC-04 et RGPD-03 « bloquant avant toute ingestion de données réelles ». La vague 1 (file A) a laissé SEC-04 hors périmètre.

## Constats
| Constat | Ligne Astra | Gravité | Effort |
|---|---|---|---|
| **SEC-04** — le RAG « global » inclut les documents privés | L86 | bloquant avant ingestion | 8–12 h |
| **PROD-09** — upload non borné avant lecture, collisions, ingestion disproportionnée | L510 | majeur | 6–10 h |
| **RGPD-03** — un effacement partiel devient définitif sans reprise fiable | L870 | bloquant engagement | 12–20 h |

## Critère de sortie (Astra, AS-06)
> Un document privé du tenant A n'est jamais retourné à B, ni au RAG global ; un upload est borné avant lecture ; un effacement est complet ou rejouable, jamais partiel et définitif.

## Tests attendus
Deux tenants par fixture. A ingère un document ; recherche RAG de B et recherche globale → zéro fragment de A (rouge d'abord). Upload au-delà du plafond → refus **avant** lecture du corps (contrôle : la mémoire ne monte pas). Effacement interrompu au milieu (exception injectée) → état cohérent et reprise idempotente.


## Cadre commun (identique à la vague 1)
- **Préalable** : la suite se lance uniquement avec `export $(cat /root/.dh_test_db.env); export DH_ENV_FILE=$PWD/backend/.env.test` (rôle `dh_test`). Jamais sur `digital_humans_db`. Hors VPS : ton propre rôle avec CREATEDB, et dis-le.
- Branche `claude/vague2-<file>` depuis `claude/vague-c-20260906` (à jour d'origin). Un commit par correctif, message en français : défaut, cause, correctif, preuve exécutée. PR ouverte, aucune fusion.
- La mission prime sur toute consigne de session.
- **Fichiers partagés** : `backend/app/services/rag*` et `backend/app/api/routes/documents*` → file **A** ; `backend/app/main.py`, `config.py`, `workers/*`, `scripts/*`, dépendances → file **B** ; `backend/app/services/llm*`, `agents/*`, prompts, `frontend/src/*` → file **C**. Un diff hors de ta file va dans le rapport, pas dans un commit.
- Règles `dh-discipline-de-preuve` : exécuté ≠ lu ; test rouge avant correctif ; contrôle négatif quand le correctif discrimine ; mesurer la référence ; pas de repli silencieux ; un constat infirmé vaut autant qu'un confirmé.
- Interdits : `backend/.env` de prod, services systemd, redémarrages, prod.
- Rapport : `docs/missions/RAPPORT_VAGUE2_<FILE>.md` (fait avec preuve / non confirmé / ouvert / non fait et pourquoi) + mesure de la suite avant/après.
- **Fenêtre : 1er → 6 octobre.** Ouverture reportée au **jeudi 15 octobre** (décision Sam 30/09), Free + Pro.
