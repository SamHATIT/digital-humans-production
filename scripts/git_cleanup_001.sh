#!/usr/bin/env bash
# GIT-CLEANUP-001 — suppression des branches distantes STALE.
#
# IMPORTANT (sûreté) :
#  - La suppression de branches distantes est IRRÉVERSIBLE et n'est PAS relisible
#    via PR. Ce script est donc fourni pour exécution MANUELLE par Sam.
#  - Il ne supprime QUE les branches vérifiées comme entièrement mergées dans
#    origin/main (aucune perte de travail possible).
#  - Les branches de la refonte (claude/*) NON mergées ne sont PAS touchées :
#    elles contiennent du travail potentiellement utile → arbitrage humain requis
#    (cf. docs/GIT_CLEANUP_001.md).
#
# Usage :
#   bash scripts/git_cleanup_001.sh          # dry-run (affiche seulement)
#   bash scripts/git_cleanup_001.sh --apply  # supprime réellement (demande confirmation)
set -euo pipefail

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

git fetch --prune origin

# Branches PROUVÉES mergées dans origin/main (recalcul dynamique = source de vérité).
MERGED=$(git branch -r --merged origin/main \
  | sed 's/^[* ]*//' \
  | grep -E '^origin/' \
  | grep -vE '^origin/(HEAD|main$)' \
  | sed 's#^origin/##' || true)

if [[ -z "${MERGED}" ]]; then
  echo "Aucune branche mergée à supprimer."
  exit 0
fi

echo "Branches distantes ENTIÈREMENT MERGÉES dans origin/main (candidates sûres) :"
echo "${MERGED}" | sed 's/^/  - /'
echo

if [[ "${APPLY}" -ne 1 ]]; then
  echo "(dry-run) Relancer avec --apply pour supprimer. Aucune action effectuée."
  exit 0
fi

read -r -p "Supprimer ces branches sur origin ? Tape 'yes' pour confirmer : " ans
[[ "${ans}" == "yes" ]] || { echo "Annulé."; exit 1; }

while IFS= read -r b; do
  [[ -z "${b}" ]] && continue
  echo "Suppression origin/${b} ..."
  git push origin --delete "${b}"
done <<< "${MERGED}"

echo "Terminé."
