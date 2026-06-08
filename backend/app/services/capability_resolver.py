"""MOD40 — Model capability resolver au démarrage.

Au lieu de figer model_id/params dans ``llm_routing.yaml`` (maintenance manuelle
tous les ~3 mois), ce module interroge l'API Anthropic pour :

- ``GET /v1/models``      → résoudre le dernier modèle d'une famille (par created_at)
  et signaler un *pin* YAML obsolète.
- ``GET /v1/models/{id}`` → lire les ``capabilities`` du modèle épinglé et régler
  les flags du router (ex. ``supports_temperature``) sans édition manuelle.

Principes de sûreté (Lane A — préparé pour relecture Sam) :

- **Opt-in strict** via la variable d'env ``DH_MOD40_CAPABILITY_RESOLVER`` :
    * ``off`` (défaut) → AUCUN appel réseau, AUCUNE mutation : comportement
      identique au runtime actuel, zéro latence de démarrage.
    * ``warn``        → appelle ``/v1/models`` et loggue les pins obsolètes,
      mais ne modifie rien.
    * ``apply``       → en plus, lit les capabilities et met à jour les *flags*
      des modèles épinglés.
- **Jamais** de bascule automatique du ``model_id`` de production : un pin
  obsolète est seulement signalé par un WARNING (le choix du modèle reste humain).
- **Fallback total** sur les valeurs YAML si l'API est injoignable ou si la
  réponse n'a pas le champ attendu. Ce module ne lève jamais vers l'appelant.
- **Cache disque** (TTL) pour éviter de retaper l'API à chaque démarrage.

Découvert via : Opus 4.7→4.8 a déprécié ``temperature`` (remplacé par ``effort``
low/medium/high/xhigh/max). Doc : platform.claude.com/docs/.../v1/models.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Modes valides pour DH_MOD40_CAPABILITY_RESOLVER
MODE_OFF = "off"
MODE_WARN = "warn"
MODE_APPLY = "apply"
_VALID_MODES = {MODE_OFF, MODE_WARN, MODE_APPLY}

# Clé YAML (router) → famille de modèle (sous-chaîne attendue dans l'id API)
_FAMILY_BY_KEY = {
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}

_DEFAULT_TTL_SECONDS = 24 * 3600


def resolver_mode(env: Optional[Dict[str, str]] = None) -> str:
    """Retourne le mode courant (off/warn/apply), normalisé. Défaut: off."""
    raw = (env or os.environ).get("DH_MOD40_CAPABILITY_RESOLVER", MODE_OFF)
    mode = str(raw).strip().lower()
    # tolère les alias booléens historiques
    if mode in ("1", "true", "yes", "on"):
        mode = MODE_APPLY
    if mode in ("0", "false", "no", ""):
        mode = MODE_OFF
    if mode not in _VALID_MODES:
        logger.warning("[MOD40] mode inconnu %r — désactivé (off)", raw)
        return MODE_OFF
    return mode


def _default_cache_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / ".mod40_models_cache.json"


def _to_ts(value: Any) -> float:
    """Convertit created_at (epoch int/float, ou ISO 8601) en timestamp float."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value)
    try:
        return float(s)
    except ValueError:
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _family_from_model_id(model_id: Optional[str]) -> Optional[str]:
    if not model_id:
        return None
    low = model_id.lower()
    for fam in ("opus", "sonnet", "haiku"):
        if fam in low:
            return fam
    return None


def _caps_to_flags(caps: Dict[str, Any]) -> Dict[str, Any]:
    """Traduit le bloc ``capabilities`` de l'API en flags du router.

    Tolérant aux schémas : ne renvoie que les flags effectivement déterminés.
    """
    flags: Dict[str, Any] = {}
    if not isinstance(caps, dict):
        return flags

    # supports_temperature : explicite, sinon déduit de la présence d'effort
    if "supports_temperature" in caps:
        flags["supports_temperature"] = bool(caps["supports_temperature"])
    else:
        has_effort = bool(
            caps.get("effort")
            or caps.get("supports_effort")
            or caps.get("effort_levels")
        )
        if has_effort:
            # effort déprécie temperature (Opus 4.7+)
            flags["supports_temperature"] = False
    return flags


class CapabilityResolver:
    """Encapsule les appels ``/v1/models`` avec cache disque et tolérance aux pannes.

    Le ``client`` est un client Anthropic (sync) exposant ``client.models.list``
    et ``client.models.retrieve`` — passé par injection pour rester testable.
    """

    def __init__(
        self,
        client: Any,
        *,
        cache_path: Optional[str] = None,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    ):
        self.client = client
        self.cache_path = Path(cache_path) if cache_path else _default_cache_path()
        self.ttl_seconds = ttl_seconds

    # --- /v1/models ---------------------------------------------------------
    def list_models(self) -> List[Dict[str, Any]]:
        """Appel direct ``GET /v1/models`` → [{id, created_at, display_name}] (récent d'abord)."""
        page = self.client.models.list(limit=1000)
        data = getattr(page, "data", None)
        if data is None and isinstance(page, dict):
            data = page.get("data")
        out: List[Dict[str, Any]] = []
        for m in data or []:
            mid = getattr(m, "id", None) if not isinstance(m, dict) else m.get("id")
            created = getattr(m, "created_at", None) if not isinstance(m, dict) else m.get("created_at")
            name = getattr(m, "display_name", None) if not isinstance(m, dict) else m.get("display_name")
            out.append({"id": mid, "created_at": _to_ts(created), "display_name": name})
        out.sort(key=lambda x: x["created_at"] or 0.0, reverse=True)
        return out

    def _read_cache(self) -> Optional[List[Dict[str, Any]]]:
        try:
            if not self.cache_path.exists():
                return None
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if time.time() - payload.get("fetched_at", 0) > self.ttl_seconds:
                return None
            return payload.get("models")
        except Exception:
            return None

    def _write_cache(self, models: List[Dict[str, Any]]) -> None:
        try:
            self.cache_path.write_text(
                json.dumps({"fetched_at": time.time(), "models": models}),
                encoding="utf-8",
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug("[MOD40] écriture cache impossible: %s", exc)

    def list_models_cached(self) -> List[Dict[str, Any]]:
        cached = self._read_cache()
        if cached is not None:
            return cached
        models = self.list_models()
        self._write_cache(models)
        return models

    def latest_model_for_family(
        self, family: str, models: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[str]:
        models = models if models is not None else self.list_models_cached()
        fam = family.lower()
        for m in models:  # déjà trié récent d'abord
            if m.get("id") and fam in m["id"].lower():
                return m["id"]
        return None

    # --- /v1/models/{id} ----------------------------------------------------
    def get_model_capabilities(self, model_id: str) -> Dict[str, Any]:
        info = self.client.models.retrieve(model_id)
        caps = getattr(info, "capabilities", None)
        if caps is None and isinstance(info, dict):
            caps = info.get("capabilities")
        if caps is None:
            return {}
        if hasattr(caps, "model_dump"):
            return caps.model_dump()
        if isinstance(caps, dict):
            return dict(caps)
        return {}


def warm_anthropic_capabilities(
    client: Any,
    models_cfg: Dict[str, Dict[str, Any]],
    *,
    mode: Optional[str] = None,
    resolver: Optional[CapabilityResolver] = None,
    cache_path: Optional[str] = None,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> Dict[str, Dict[str, Any]]:
    """MOD40 — réchauffe/valide les capacités des modèles Anthropic au démarrage.

    Mute ``models_cfg`` *en place* (et le retourne) uniquement en mode ``apply``.
    Ne lève jamais : toute erreur retombe sur les valeurs YAML.

    Args:
        client: client Anthropic sync (ou None → no-op).
        models_cfg: dict {clé_router: {model_id, ...}} issu du YAML (muté en place).
        mode: off/warn/apply ; si None, lu depuis l'env.
    """
    mode = mode or resolver_mode()
    if mode == MODE_OFF:
        return models_cfg
    if client is None:
        logger.warning("[MOD40] aucun client Anthropic — résolution sautée (YAML conservé)")
        return models_cfg

    if resolver is None:
        resolver = CapabilityResolver(client, cache_path=cache_path, ttl_seconds=ttl_seconds)

    try:
        models = resolver.list_models_cached()
    except Exception as exc:
        logger.warning("[MOD40] /v1/models injoignable (%s) — conservation des valeurs YAML", exc)
        return models_cfg

    for key, cfg in models_cfg.items():
        if not isinstance(cfg, dict):
            continue
        fam = _FAMILY_BY_KEY.get(key) or _family_from_model_id(cfg.get("model_id"))
        if not fam:
            continue
        pinned = cfg.get("model_id")
        latest = resolver.latest_model_for_family(fam, models)
        if latest and pinned and latest != pinned:
            logger.warning(
                "[MOD40] pin YAML obsolète pour %s : épinglé=%s, dernier disponible=%s "
                "(bascule volontairement manuelle — décision Sam).",
                key, pinned, latest,
            )

        if mode != MODE_APPLY or not pinned:
            continue
        try:
            caps = resolver.get_model_capabilities(pinned)
            flags = _caps_to_flags(caps)
            for fk, fv in flags.items():
                old = cfg.get(fk)
                cfg[fk] = fv
                if old != fv:
                    logger.info("[MOD40] %s.%s : %r → %r (depuis capabilities API)", key, fk, old, fv)
        except Exception as exc:
            logger.warning("[MOD40] capabilities indisponibles pour %s (%s) — YAML conservé", pinned, exc)

    return models_cfg
