#!/bin/bash
BENCH=/root/workspace/digital-humans-production/docs/benchmarks/local-llm-bench-2026-04-30
LOG=$BENCH/logs/bench_run.log
echo "[$(date -Is)] Waiting for ollama pulls to complete..." > $LOG

# Attendre la fin des pulls (max 30 min)
for i in $(seq 1 60); do
  active=$(pgrep -af "ollama pull" | wc -l)
  echo "[$(date -Is)] Pulls actifs: $active" >> $LOG
  if [ "$active" -eq 0 ]; then
    echo "[$(date -Is)] Tous les pulls terminés." >> $LOG
    break
  fi
  sleep 30
done

echo "[$(date -Is)] Modèles dispo:" >> $LOG
ollama list >> $LOG 2>&1

# Vérifier que les 6 modèles attendus sont là
expected="gemma4:26b qwen3.5:27b qwen3.6:27b magistral:24b devstral:24b ministral-3:14b"
missing=""
for m in $expected; do
  ollama list 2>/dev/null | grep -q "^${m%:*}.*${m##*:}" || missing="$missing $m"
done

if [ -n "$missing" ]; then
  echo "[$(date -Is)] AVERTISSEMENT — modèles manquants:$missing" >> $LOG
  echo "[$(date -Is)] Bench lancé quand même avec ce qui est dispo." >> $LOG
fi

echo "[$(date -Is)] Lancement du bench Python..." >> $LOG
python3 $BENCH/scripts/run_bench.py >> $LOG 2>&1
echo "[$(date -Is)] Bench terminé." >> $LOG
