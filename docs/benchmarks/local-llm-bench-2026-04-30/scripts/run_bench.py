#!/usr/bin/env python3
"""
Bench croisé local LLMs pour Digital Humans.

Pour chaque modèle, exécute 2 tâches (Marcus design SDS + Diego build BUILD)
et collecte latence, tokens, throughput. Sauvegarde outputs bruts + JSON consolidé.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

BENCH = Path("/root/workspace/digital-humans-production/docs/benchmarks/local-llm-bench-2026-04-30")
OLLAMA = "http://127.0.0.1:11434"

MODELS = [
    "gemma4:26b",
    "qwen3.5:27b",
    "qwen3.6:27b",
    "magistral:24b",
    "devstral:24b",
    "ministral-3:14b",
]

TASKS = ["marcus_design", "diego_build"]


def call_ollama(model: str, system: str, user_prompt: str,
                max_tokens: int, temperature: float, timeout: int = 3600):
    """Appel /api/chat non-streamé. Retourne dict avec output + métriques."""
    url = f"{OLLAMA}/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "keep_alive": 0,  # décharge le modèle après l'appel pour libérer la RAM
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": 32768,
        },
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ],
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
        elapsed = time.time() - t0
        result = json.loads(body)
        message = result.get("message", {})
        output = message.get("content", "")
        # Ollama returns durations in nanoseconds
        eval_count = result.get("eval_count", 0)
        eval_dur_s = result.get("eval_duration", 0) / 1e9
        prompt_eval_count = result.get("prompt_eval_count", 0)
        prompt_eval_dur_s = result.get("prompt_eval_duration", 0) / 1e9
        total_dur_s = result.get("total_duration", 0) / 1e9
        load_dur_s = result.get("load_duration", 0) / 1e9
        return {
            "ok": True,
            "output": output,
            "metrics": {
                "wall_seconds": round(elapsed, 2),
                "load_seconds": round(load_dur_s, 2),
                "prompt_tokens": prompt_eval_count,
                "prompt_eval_seconds": round(prompt_eval_dur_s, 2),
                "prompt_tps": round(prompt_eval_count / prompt_eval_dur_s, 1) if prompt_eval_dur_s else 0,
                "output_tokens": eval_count,
                "output_eval_seconds": round(eval_dur_s, 2),
                "output_tps": round(eval_count / eval_dur_s, 1) if eval_dur_s else 0,
                "total_seconds_ollama": round(total_dur_s, 2),
            },
            "raw_done_reason": result.get("done_reason", "unknown"),
        }
    except urllib.error.URLError as e:
        return {"ok": False, "error": str(e), "elapsed": time.time() - t0}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "elapsed": time.time() - t0}


def main():
    # Charge les configs et prompts
    with open(BENCH / "inputs" / "task_configs.json") as f:
        configs = json.load(f)
    with open(BENCH / "inputs" / "marcus_design_prompt.txt") as f:
        marcus_prompt = f.read()
    with open(BENCH / "inputs" / "diego_build_prompt.txt") as f:
        diego_prompt = f.read()

    prompts = {"marcus_design": marcus_prompt, "diego_build": diego_prompt}

    results = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "models": MODELS,
        "tasks": TASKS,
        "runs": [],
    }
    results_path = BENCH / "outputs" / "results.json"

    total = len(MODELS) * len(TASKS)
    idx = 0
    overall_t0 = time.time()
    for model in MODELS:
        for task in TASKS:
            idx += 1
            cfg = configs[task]
            prompt = prompts[task]
            label = f"[{idx}/{total}] {model} / {task}"
            print(f"\n{'='*60}\n{label}", flush=True)
            print(f"  prompt={len(prompt)} chars, max_tokens={cfg['max_tokens']}, temp={cfg['temperature']}",
                  flush=True)

            run_t0 = time.time()
            result = call_ollama(
                model=model,
                system=cfg["system_prompt"],
                user_prompt=prompt,
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
            )
            run_elapsed = time.time() - run_t0

            # Sauve l'output brut
            safe_model = model.replace(":", "_").replace("/", "_")
            out_file = BENCH / "outputs" / f"{safe_model}__{task}.txt"
            if result["ok"]:
                out_file.write_text(result["output"], encoding="utf-8")
                m = result["metrics"]
                print(f"  ✓ OK in {run_elapsed:.1f}s | "
                      f"in={m['prompt_tokens']}@{m['prompt_tps']}tps | "
                      f"out={m['output_tokens']}@{m['output_tps']}tps | "
                      f"output_size={len(result['output'])} chars",
                      flush=True)
            else:
                out_file.write_text(f"ERROR: {result.get('error')}\n", encoding="utf-8")
                print(f"  ✗ FAIL: {result.get('error')}", flush=True)

            run_record = {
                "model": model,
                "task": task,
                "started_at_run": datetime.now(timezone.utc).isoformat(),
                "ok": result["ok"],
                "elapsed_seconds": round(run_elapsed, 2),
                "output_size_chars": len(result.get("output", "")),
                "output_file": str(out_file.relative_to(BENCH)),
                "metrics": result.get("metrics", {}),
                "error": result.get("error"),
                "done_reason": result.get("raw_done_reason"),
            }
            results["runs"].append(run_record)

            # Save intermediate after each run
            results["last_update"] = datetime.now(timezone.utc).isoformat()
            results["elapsed_total_seconds"] = round(time.time() - overall_t0, 2)
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

    results["completed_at"] = datetime.now(timezone.utc).isoformat()
    results["elapsed_total_seconds"] = round(time.time() - overall_t0, 2)
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n{'='*60}\nDONE in {time.time() - overall_t0:.0f}s. Results: {results_path}", flush=True)


if __name__ == "__main__":
    main()
