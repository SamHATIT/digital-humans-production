"""Tests MOD40 — capability_resolver (client Anthropic mocké, aucun appel réseau)."""
import types

import pytest

from app.services import capability_resolver as cr


# --- Fakes -----------------------------------------------------------------
def _model(mid, created, name=None):
    return types.SimpleNamespace(id=mid, created_at=created, display_name=name or mid)


class _FakeModels:
    def __init__(self, models, caps_by_id=None, raise_on_list=False):
        self._models = models
        self._caps = caps_by_id or {}
        self._raise_on_list = raise_on_list
        self.list_calls = 0
        self.retrieve_calls = 0

    def list(self, limit=1000):
        self.list_calls += 1
        if self._raise_on_list:
            raise RuntimeError("network down")
        return types.SimpleNamespace(data=list(self._models))

    def retrieve(self, model_id):
        self.retrieve_calls += 1
        return types.SimpleNamespace(capabilities=self._caps.get(model_id))


class _FakeClient:
    def __init__(self, models, caps_by_id=None, raise_on_list=False):
        self.models = _FakeModels(models, caps_by_id, raise_on_list)


# --- resolver_mode ---------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    (None, cr.MODE_OFF),
    ("off", cr.MODE_OFF), ("0", cr.MODE_OFF), ("false", cr.MODE_OFF),
    ("warn", cr.MODE_WARN),
    ("apply", cr.MODE_APPLY), ("1", cr.MODE_APPLY), ("true", cr.MODE_APPLY),
    ("garbage", cr.MODE_OFF),
])
def test_resolver_mode(raw, expected):
    env = {} if raw is None else {"DH_MOD40_CAPABILITY_RESOLVER": raw}
    assert cr.resolver_mode(env) == expected


# --- list_models / latest --------------------------------------------------
def test_list_models_sorted_recent_first_mixed_date_formats():
    client = _FakeClient([
        _model("claude-opus-4-7", "2026-02-01T00:00:00Z"),  # ISO
        _model("claude-opus-4-8", 1800000000),              # epoch 2027 (plus récent)
        _model("claude-sonnet-4-6", "2026-01-01T00:00:00Z"),
    ])
    res = cr.CapabilityResolver(client, cache_path="/tmp/_mod40_test_nocache_1.json", ttl_seconds=0)
    models = res.list_models()
    assert [m["id"] for m in models][0] == "claude-opus-4-8"
    assert res.latest_model_for_family("opus", models) == "claude-opus-4-8"
    assert res.latest_model_for_family("sonnet", models) == "claude-sonnet-4-6"
    assert res.latest_model_for_family("haiku", models) is None


# --- _caps_to_flags --------------------------------------------------------
def test_caps_to_flags_explicit_and_effort():
    assert cr._caps_to_flags({"supports_temperature": True})["supports_temperature"] is True
    assert cr._caps_to_flags({"supports_temperature": False})["supports_temperature"] is False
    # effort présent → temperature dépréciée
    assert cr._caps_to_flags({"effort_levels": ["low", "high"]})["supports_temperature"] is False
    # rien de déterminable
    assert cr._caps_to_flags({}) == {}
    assert cr._caps_to_flags(None) == {}


# --- warm: off -------------------------------------------------------------
def test_warm_off_is_total_noop():
    client = _FakeClient([_model("claude-opus-4-8", 10)])
    cfg = {"claude-opus": {"model_id": "claude-opus-4-7"}}
    out = cr.warm_anthropic_capabilities(client, cfg, mode=cr.MODE_OFF)
    assert out["claude-opus"] == {"model_id": "claude-opus-4-7"}  # inchangé
    assert client.models.list_calls == 0  # aucun appel réseau
    assert client.models.retrieve_calls == 0


# --- warm: warn ------------------------------------------------------------
def test_warm_warn_logs_stale_without_mutation(caplog):
    client = _FakeClient([_model("claude-opus-4-8", 100), _model("claude-opus-4-7", 50)])
    cfg = {"claude-opus": {"model_id": "claude-opus-4-7", "supports_temperature": False}}
    with caplog.at_level("WARNING"):
        cr.warm_anthropic_capabilities(client, cfg, mode=cr.MODE_WARN,
                                       cache_path="/tmp/_mod40_test_nocache_2.json", ttl_seconds=0)
    assert "pin YAML obsolète" in caplog.text
    assert "claude-opus-4-8" in caplog.text
    assert cfg["claude-opus"]["model_id"] == "claude-opus-4-7"  # pas de bascule auto
    assert client.models.retrieve_calls == 0  # warn ne lit pas les capabilities


# --- warm: apply -----------------------------------------------------------
def test_warm_apply_updates_flags_from_capabilities():
    client = _FakeClient(
        [_model("claude-opus-4-8", 100)],
        caps_by_id={"claude-opus-4-8": {"effort_levels": ["low", "high", "max"]}},
    )
    cfg = {"claude-opus": {"model_id": "claude-opus-4-8", "supports_temperature": True}}
    cr.warm_anthropic_capabilities(client, cfg, mode=cr.MODE_APPLY,
                                   cache_path="/tmp/_mod40_test_nocache_3.json", ttl_seconds=0)
    # effort_levels présent → supports_temperature forcé à False
    assert cfg["claude-opus"]["supports_temperature"] is False
    assert client.models.retrieve_calls == 1


# --- warm: API down → fallback, jamais d'exception -------------------------
def test_warm_apply_api_down_falls_back_silently():
    client = _FakeClient([], raise_on_list=True)
    cfg = {"claude-opus": {"model_id": "claude-opus-4-8", "supports_temperature": False}}
    out = cr.warm_anthropic_capabilities(client, cfg, mode=cr.MODE_APPLY,
                                         cache_path="/tmp/_mod40_test_nocache_4.json", ttl_seconds=0)
    assert out["claude-opus"]["supports_temperature"] is False  # YAML conservé
