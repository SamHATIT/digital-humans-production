# Bench LLM locaux — VPS Hostinger KVM 8 (CPU only) — 30 avr 2026

## Contexte
Test de modèles open-weights sur VPS sans GPU (8 vCPU AMD EPYC, 32 GB RAM)
pour usages : workflows N8N, admin plateforme, R&D nouveaux produits.

## Matrice de tests visée

| Modèle | Architecture | Marcus design (8K in / 12K out) | Diego build (3K in / ~4K out) |
|---|---|---|---|
| gemma4:26b | MoE (3.8B actifs) | ✓ 23min, 6.8 tps | ✓ 7min, 8.4 tps |
| qwen3.5:27b | Dense | ✗ timeout 1h | ✗ timeout 1h |
| qwen3.6:27b | Dense | ✗ timeout 1h | ✗ timeout 1h |
| magistral:24b | Dense | ✗ timeout 1h | ✗ timeout 1h |
| devstral:24b | Dense | ✗ timeout 1h | ✗ timeout 1h |
| ministral-3:14b | Dense | ✗ timeout 1h | ✗ timeout 1h |

## Conclusion principale

**Sur CPU 8 cœurs sans GPU, seuls les modèles MoE sont viables pour des prompts
longs.** Les modèles denses 14-27B ont un prefill (traitement du prompt d'entrée)
trop long pour la fenêtre OLLAMA_LOAD_TIMEOUT par défaut (1h).

Cause technique : avec un prompt de 8000 tokens, le prefill sur CPU prend
30-60 min pour un dense 24B+ → aucun token généré dans la fenêtre.
Gemma 4 26B MoE n'active que ~3.8B params à l'inférence → prefill ~5-10 min, OK.

## Note Gemma 4 (seul modèle évalué)

**Marcus design** : architecture cohérente (4/5), JSON cassé (typo `_api_name`,
1/5), couvre data_model + UI + flows + permissions mais omet business_logic,
security, integrations, data_migration. Score global 3/5.

**Diego build** : pattern handler respecté (4/5), bug critique de mélange de
champs `Status__c` vs `Condition_Status__c` (2/5 bulk-safety), invente
RentalContract__c. Score global 3/5.

## À refaire sur Mac (M-series)
- Prefill 5-10× plus rapide grâce à Metal + mémoire unifiée
- Ré-essayer les 5 modèles denses avec mêmes prompts
- Ajouter aussi : claude-sonnet (réf), gemma3:27b (référence dense Google)

## Fichiers conservés
- `inputs/` : prompts Marcus (réduit à 1/3 UC) + Diego avec configs YAML
- `outputs/` : 2 outputs Gemma 4 réussis + 10 traces d'erreur
- `outputs.attempt1_truncated_4096/` : runs avant fix num_ctx (à ignorer)
- `outputs.attempt2_marcus_timeout/` : runs avant cadrage Marcus (à ignorer)
- `scripts/run_bench.py` : framework Python réutilisable

## Variables Ollama à augmenter pour re-bench sur Mac
```bash
export OLLAMA_LOAD_TIMEOUT=4h
export OLLAMA_KEEP_ALIVE=1h
export OLLAMA_NUM_PARALLEL=1
```
