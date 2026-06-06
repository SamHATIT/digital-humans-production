
## [TODO mod40] Model capability resolver au démarrage
Au lieu de figer model_id/params dans llm_routing.yaml (maj manuelle tous les ~3 mois) :
- GET /v1/models → résoudre dernier Opus/Sonnet par famille (created_at).
- GET /v1/models/{id} → lire `capabilities` → régler supports_temperature, niveaux effort, type thinking.
- Cache + fallback sur valeurs YAML si API injoignable. Log warning si pin YAML obsolète.
Découvert via : Opus 4.7→4.8 a déprécié `temperature` (remplacé par `effort` low/medium/high/xhigh/max).
Doc : platform.claude.com/docs/en/build-with-claude/effort + /v1/models/{id} capabilities.
