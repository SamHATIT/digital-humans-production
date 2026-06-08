# GIT-CLEANUP-001 — inventaire & plan de nettoyage des branches

**Analyse** : 2026-06-08 (agent Vague 1). `git fetch --prune` puis classement par
statut de merge dans `origin/main`.

> ⚠️ La suppression de branches distantes est **irréversible** et n'est pas relisible
> via PR. L'agent **ne supprime rien** : il fournit cet inventaire + le script
> `scripts/git_cleanup_001.sh` (exécution manuelle par Sam).

## Chiffres
- **58** branches distantes au total.
- **4** entièrement mergées dans `origin/main` → **suppression sûre** (zéro perte).
- **53** non mergées → **arbitrage humain requis** (travail potentiellement utile).

## A. Sûres à supprimer (mergées dans origin/main)
Vérifiées via `git branch -r --merged origin/main`. Aucune perte possible :

- `feat/platform-studio`
- `feat/stream-001`   *(STREAM-001 déjà mergé sur main — 04ea3c5)*
- `feature/freemium-realignment`
- `feature/journal-publication`

→ `bash scripts/git_cleanup_001.sh --apply` les supprime (avec confirmation).
Le script **recalcule** la liste mergée au moment de l'exécution (source de vérité),
donc il restera correct même si d'autres branches sont mergées entre-temps.

## B. NON mergées — NE PAS supprimer automatiquement
Les ~50 branches `claude/*` de la refonte (févr.→avr. 2026) ne sont **pas** contenues
dans `origin/main` (la refonte n'a pas été fusionnée linéairement ; `main` a longtemps
été en retard). Les supprimer **perdrait** du travail non fusionné. Elles demandent un
arbitrage : soit elles ont été intégrées autrement (cherry-pick/squash) et sont
réellement obsolètes, soit elles portent encore du code utile.

Exclusions explicites de tout nettoyage automatique :
- `feat/sds-templating` — **active** (Lane B : merge + tag `v2.0-sds-db-driven` à venir, gate Sam).
- `claude/build-hitl-backend-routes-dnM9E` — référencée dans le backlog P2 (HITL MVP).
- Toutes les branches `fix/*`, `feat/*`, `chore/*` ouvertes par la Vague 1 (en cours de revue).

### Méthode suggérée pour le lot B (à faire avec Sam)
Pour chaque branche `claude/*`, déterminer si son contenu est déjà dans `main` :
```bash
# nombre de commits de la branche absents de main (0 = tout est dans main → supprimable)
git rev-list --count origin/main..origin/<branche>
```
Les branches avec `0` commit en avance peuvent rejoindre le lot A. Les autres
nécessitent une décision (garder / cherry-pick / abandonner).

## Exécution
```bash
bash scripts/git_cleanup_001.sh          # dry-run (liste seulement)
bash scripts/git_cleanup_001.sh --apply  # suppression réelle (confirmation 'yes')
```
