#!/bin/bash
# Watchdog DH (remplace le workflow N8N Monitoring qui échouait depuis des semaines)
# Toutes les 15 min : health backend + Spark + services critiques -> alerte Telegram si problème.
# DRY_RUN=1 : n'envoie rien sur Telegram (n'exige pas TOKEN/CHAT), imprime le message
#             qui aurait été envoyé, préfixé "DRY_RUN: ".
# STATE     : fichier anti-spam, surchargeable par l'environnement (utile en test).
# DH_WATCHDOG_ENV : fichier qui porte TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
#             (defaut : le .env du comite). Surchargeable pour que les tests
#             n'aient jamais a lire le vrai jeton.
#
# Vague 2 / file B — OPS-08 (Astra L1020). Trois defauts corriges :
#   1. sans identifiants, le script sortait 0 en silence : il le dit sur
#      stderr (donc dans le journal cron) et sort 2 ;
#   2. l'etat « notifie » etait ecrit meme quand Telegram refusait l'envoi
#      (HTTP non 2xx, `"ok":false`, panne reseau), ce qui supprimait toutes
#      les tentatives suivantes : il n'est ecrit qu'apres un envoi accepte,
#      sinon le script sort 1 ;
#   3. le worker n'etait pas sonde (OPS-02) : service systemd + battement ARQ
#      via /api/pm-orchestrator/workers/health.
ENV="${DH_WATCHDOG_ENV:-/root/workspace/dh-comite/.env}"
: "${STATE:=/var/run/dh-watchdog.state}"
DRY_RUN="${DRY_RUN:-0}"

if [ "$DRY_RUN" != "1" ]; then
  TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' "$ENV" 2>/dev/null | cut -d= -f2)
  CHAT=$(grep '^TELEGRAM_CHAT_ID=' "$ENV" 2>/dev/null | cut -d= -f2)
  if [ -z "$TOKEN" ] || [ -z "$CHAT" ]; then
    echo "dh-watchdog: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID absent de $ENV — aucune alerte ne peut partir, watchdog inerte." >&2
    exit 2
  fi
fi

PB=""
# Ajoute un problème à PB en gérant le séparateur " | " (jamais de " | " en tête).
add_pb() {
  if [ -n "$PB" ]; then PB="$PB | $1"; else PB="$1"; fi
}

# curl -w imprime déjà "000" quand la connexion échoue : ne pas ajouter un second
# "000" derrière (c'était le bug du double "000000").
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8002/health || true)
[ "$HTTP" != "200" ] && add_pb "backend /health = $HTTP"

# Sonde Spark : 18084 = tunnel-spark-vllm vers Spark:8001 (vLLM nemotron-lightning).
# 03/09 : la mission disait 18001, port qui n a jamais existe sur le VPS.
SPARK=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:18084/v1/models || true)
[ "$SPARK" != "200" ] && add_pb "spark /v1/models = $SPARK"

# OPS-02 : battement du worker ARQ (cle `<file>:health-check` posee par le
# worker toutes les 30 s). 503 = pas de battement ou Redis injoignable.
WORKER=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8002/api/pm-orchestrator/workers/health || true)
[ "$WORKER" != "200" ] && add_pb "worker /workers/health = $WORKER"

if command -v systemctl >/dev/null 2>&1; then
  for S in postgresql nginx n8n digital-humans-backend digital-humans-worker; do
    ST=$(systemctl is-active $S 2>/dev/null)
    RC=$?
    if [ $RC -ne 0 ] && [ -z "$ST" ]; then
      # systemctl répond mais sans état exploitable (ex: bus injoignable) :
      # ne pas prétendre que le service est down, le dire explicitement.
      add_pb "$S état indéterminé (systemctl injoignable)"
    elif [ "$ST" != "active" ]; then
      add_pb "$S down ($ST)"
    fi
  done
else
  add_pb "systemctl absent : postgresql/nginx/n8n non vérifiés"
fi

send_or_print() {
  # $1 = message. Envoie sur Telegram sauf en DRY_RUN, où le message est imprimé.
  # Rend 0 seulement si Telegram a ACCEPTE le message : HTTP 2xx ET `"ok":true`
  # dans la reponse. Le transport seul ne suffit pas (Telegram repond 200 a
  # rien, mais 400 avec ok:false pour un chat inconnu, par exemple).
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY_RUN: $1"
    return 0
  fi
  local reponse code corps
  reponse=$(curl -s --max-time 10 -w '\n%{http_code}' "https://api.telegram.org/bot$TOKEN/sendMessage" \
    -d chat_id="$CHAT" --data-urlencode text="$1")
  local rc=$?
  code=$(printf '%s' "$reponse" | tail -n1)
  corps=$(printf '%s' "$reponse" | sed '$d')
  if [ $rc -ne 0 ] || [ "${code#2}" = "$code" ] || ! printf '%s' "$corps" | grep -q '"ok":true'; then
    echo "dh-watchdog: envoi Telegram refuse (curl=$rc, HTTP=$code) : $corps — etat non enregistre, nouvel essai au prochain passage." >&2
    return 1
  fi
  return 0
}

if [ -n "$PB" ]; then
  # anti-spam : une alerte max toutes les 30 min pour le même état
  LAST=$(cat "$STATE" 2>/dev/null || echo "")
  NOW="$PB"
  if [ "$LAST" != "$NOW" ] || [ $(( $(date +%s) - $(stat -c %Y "$STATE" 2>/dev/null || echo 0) )) -gt 1800 ]; then
    send_or_print "🔴 DH ALERTE ($(date -u +%H:%M)Z) : $PB" || exit 1
    echo "$NOW" > "$STATE"
  fi
else
  if [ -s "$STATE" ]; then
    send_or_print "🟢 DH rétabli ($(date -u +%H:%M)Z)" || exit 1
    > "$STATE"
  fi
fi
