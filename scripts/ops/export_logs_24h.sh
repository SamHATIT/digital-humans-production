#!/usr/bin/env bash
# =====================================================================
# DEC-2026-0804-01 — Export fiabilise des logs pour le comite (Delivery)
# FIX-LOGEXPORT-001 (05/08)
#
# Remplace le one-liner de /etc/cron.d/dh-comite-logs, qui exportait
# 25 heures dans un fichier nomme "24h", sans aucun moyen pour le Delivery
# de verifier ce que le fichier couvrait reellement sans passer par grep.
#
# Trois corrections :
#   1. fenetre de 24 h exactement (etait 25 h) ;
#   2. en-tete portant les bornes reellement couvertes, le nombre de lignes
#      et le nombre de rafales d'activite ;
#   3. horodatage uniforme (-o short-iso) : le mode "cat" melangeait deux
#      formats (texte applicatif et JSON structure), ce qui rendait le
#      fichier non mesurable sans expression reguliere ad hoc.
#
# Le worker est exporte dans un fichier frere : les incidents que le
# Delivery cherche a corroborer s'y produisent, et il n'etait pas exporte.
#
# Ecriture atomique (fichier temporaire puis mv) : un export interrompu ne
# laisse jamais un fichier tronque en place.
# =====================================================================
set -uo pipefail

DEST_DIR="/var/log/digital-humans"
WINDOW_HOURS=24
GAP_SECONDS=300   # coupure entre deux rafales d'activite

export_unit() {
    local unit="$1" outfile="$2"
    local tmp="${outfile}.tmp" body="${outfile}.body"

    local now_epoch since_epoch now_iso since_iso
    now_epoch=$(date -u +%s)
    since_epoch=$(( now_epoch - WINDOW_HOURS * 3600 ))
    now_iso=$(date -u -d "@${now_epoch}" +%Y-%m-%dT%H:%M:%S+00:00)
    since_iso=$(date -u -d "@${since_epoch}" +%Y-%m-%dT%H:%M:%S+00:00)

    journalctl -u "$unit" --since "@${since_epoch}" -o short-iso --no-pager > "$body" 2>/dev/null
    # journalctl ecrit "-- No entries --" quand il n'a rien : ce n'est pas une
    # ligne de log, elle fausserait le compteur qui sert justement a distinguer
    # un service muet d'un export en echec.
    sed -i '/^-- No entries --$/d' "$body"

    # Mesure reelle du contenu : bornes, amplitude, rafales.
    # Lit le corps une seule fois ; ne suppose aucun format applicatif,
    # seulement le prefixe ISO ajoute par journalctl.
    local stats
    stats=$(GAP="$GAP_SECONDS" WIN="$WINDOW_HOURS" python3 - "$body" <<'PYEOF'
import sys, os, datetime
gap = int(os.environ["GAP"]); win_h = int(os.environ["WIN"])
ts = []
with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
    for line in f:
        head = line[:25]
        try:
            ts.append(datetime.datetime.strptime(head[:19], "%Y-%m-%dT%H:%M:%S"))
        except ValueError:
            continue          # ligne sans prefixe ISO exploitable
n_lines = sum(1 for _ in open(sys.argv[1], encoding="utf-8", errors="replace"))
if not ts:
    print(f"{n_lines}|0|-|-|0|0|0.0")
else:
    ts.sort()
    span = (ts[-1] - ts[0]).total_seconds()
    bursts = 1 + sum(1 for a, b in zip(ts, ts[1:]) if (b - a).total_seconds() > gap)
    pct = 100.0 * span / (win_h * 3600)
    print(f"{n_lines}|{len(ts)}|{ts[0].isoformat()}+00:00|{ts[-1].isoformat()}+00:00|"
          f"{int(span)}|{bursts}|{pct:.1f}")
PYEOF
)
    IFS='|' read -r n_lines n_dated first last span_s bursts pct <<< "$stats"

    local span_h=$(( span_s / 3600 )) span_m=$(( (span_s % 3600) / 60 ))

    {
      printf '# ===== EXPORT LOGS %sH — %s =====\n' "$WINDOW_HOURS" "$unit"
      printf '# Genere le            : %s\n' "$now_iso"
      printf '# Fenetre demandee     : %s -> %s (%sh00)\n' "$since_iso" "$now_iso" "$WINDOW_HOURS"
      printf '# Lignes exportees     : %s\n' "$n_lines"
      printf '# Lignes horodatees    : %s\n' "$n_dated"
      printf '# Premiere ligne datee : %s\n' "$first"
      printf '# Derniere ligne datee : %s\n' "$last"
      printf '# Amplitude couverte   : %sh%02dm sur %sh00 (%s %%)\n' "$span_h" "$span_m" "$WINDOW_HOURS" "$pct"
      printf "# Rafales d'activite   : %s (coupure a %s min d'inactivite)\n" "$bursts" "$(( GAP_SECONDS / 60 ))"
      printf '#\n'
      printf '# COMMENT LIRE CE FICHIER\n'
      printf '#   Une amplitude faible ne signifie PAS un export ampute : le service\n'
      printf "#   n'emet des lignes que lorsqu'il travaille, et reste muet au repos.\n"
      printf '#   Un export reellement en echec afficherait "Lignes exportees : 0".\n'
      printf '#   Verifier ce champ en premier, avant de conclure a une perte de logs.\n'
      printf '# ============================================================\n'
      cat "$body"
    } > "$tmp"

    mv -f "$tmp" "$outfile"
    rm -f "$body"
    printf '%s : %s lignes, amplitude %sh%02dm (%s %%), %s rafale(s)\n' \
           "$(basename "$outfile")" "$n_lines" "$span_h" "$span_m" "$pct" "$bursts"
}

export_unit digital-humans-backend "${DEST_DIR}/backend-24h.log"
export_unit digital-humans-worker  "${DEST_DIR}/worker-24h.log"
