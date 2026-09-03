#!/bin/bash
# Watchdog DH (remplace le workflow N8N Monitoring qui échouait depuis des semaines)
# Toutes les 15 min : health backend + Spark + services critiques -> alerte Telegram si problème.
# DRY_RUN=1 : n'envoie rien sur Telegram (n'exige pas TOKEN/CHAT), imprime le message
#             qui aurait été envoyé, préfixé "DRY_RUN: ".
# STATE     : fichier anti-spam, surchargeable par l'environnement (utile en test).
ENV=/root/workspace/dh-comite/.env
: "${STATE:=/var/run/dh-watchdog.state}"
DRY_RUN="${DRY_RUN:-0}"

if [ "$DRY_RUN" != "1" ]; then
  TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' $ENV | cut -d= -f2)
  CHAT=$(grep '^TELEGRAM_CHAT_ID=' $ENV | cut -d= -f2)
  [ -z "$TOKEN" ] || [ -z "$CHAT" ] && exit 0
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

if command -v systemctl >/dev/null 2>&1; then
  for S in postgresql nginx n8n; do
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
  if [ "$DRY_RUN" = "1" ]; then
    echo "DRY_RUN: $1"
  else
    curl -s --max-time 10 "https://api.telegram.org/bot$TOKEN/sendMessage" \
      -d chat_id="$CHAT" --data-urlencode text="$1" > /dev/null
  fi
}

if [ -n "$PB" ]; then
  # anti-spam : une alerte max toutes les 30 min pour le même état
  LAST=$(cat "$STATE" 2>/dev/null || echo "")
  NOW="$PB"
  if [ "$LAST" != "$NOW" ] || [ $(( $(date +%s) - $(stat -c %Y "$STATE" 2>/dev/null || echo 0) )) -gt 1800 ]; then
    send_or_print "🔴 DH ALERTE ($(date -u +%H:%M)Z) : $PB"
    echo "$NOW" > "$STATE"
  fi
else
  if [ -s "$STATE" ]; then
    send_or_print "🟢 DH rétabli ($(date -u +%H:%M)Z)"
    > "$STATE"
  fi
fi
