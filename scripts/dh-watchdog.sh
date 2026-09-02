#!/bin/bash
# Watchdog DH (remplace le workflow N8N Monitoring qui échouait depuis des semaines)
# Toutes les 15 min : health backend + services critiques -> alerte Telegram si problème.
ENV=/root/workspace/dh-comite/.env
TOKEN=$(grep '^TELEGRAM_BOT_TOKEN=' $ENV | cut -d= -f2)
CHAT=$(grep '^TELEGRAM_CHAT_ID=' $ENV | cut -d= -f2)
[ -z "$TOKEN" ] || [ -z "$CHAT" ] && exit 0
STATE=/var/run/dh-watchdog.state
PB=""
HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:8002/health || echo 000)
[ "$HTTP" != "200" ] && PB="backend /health = $HTTP"
for S in postgresql nginx n8n; do systemctl is-active --quiet $S || PB="$PB | $S down"; done
if [ -n "$PB" ]; then
  # anti-spam : une alerte max toutes les 30 min pour le même état
  LAST=$(cat $STATE 2>/dev/null || echo "")
  NOW="$PB"
  if [ "$LAST" != "$NOW" ] || [ $(( $(date +%s) - $(stat -c %Y $STATE 2>/dev/null || echo 0) )) -gt 1800 ]; then
    curl -s --max-time 10 "https://api.telegram.org/bot$TOKEN/sendMessage" \
      -d chat_id="$CHAT" --data-urlencode text="🔴 DH ALERTE ($(date -u +%H:%M)Z) : $PB" > /dev/null
    echo "$NOW" > $STATE
  fi
else
  if [ -s $STATE ]; then
    curl -s --max-time 10 "https://api.telegram.org/bot$TOKEN/sendMessage" \
      -d chat_id="$CHAT" --data-urlencode text="🟢 DH rétabli ($(date -u +%H:%M)Z)" > /dev/null
    > $STATE
  fi
fi
