"""A9 (03/09/2026) — la sonde doit voir un fournisseur local inoperant.

Contexte : du 31/08 au 03/09, gpu_nemotron pointait 18080 (tunnel Packet.ai
eteint) avec le model_id "nemotron-3-nano-30b-a3b" que vLLM refuse en 404.
Aucun appel LLM ne pouvait aboutir et rien ne le signalait. Ce test verifie
que les deux formes de panne — endpoint muet, model_id absent — sont detectees,
et qu une configuration saine ne produit AUCUNE anomalie (controle negatif :
sans lui, une sonde qui renvoie toujours une anomalie passerait pour bonne).
"""
import httpx
import pytest

from app.services.llm_router_service import LLMRouterService, ProviderType


def _routeur_avec(providers):
    r = LLMRouterService.__new__(LLMRouterService)
    r.providers = providers
    return r


UN_FOURNISSEUR = {
    "gpu_nemotron": {
        "type": ProviderType.LOCAL,
        "base_url": "http://127.0.0.1:18084/v1",
        "models": {"nemotron": {"model_id": "nemotron-lightning"}},
    }
}


def test_endpoint_injoignable_est_signale(monkeypatch):
    def _refus(*a, **k):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "get", _refus)

    anomalies = _routeur_avec(UN_FOURNISSEUR).verifier_fournisseurs_locaux()

    assert len(anomalies) == 1
    assert "injoignable" in anomalies[0]
    assert "18084" in anomalies[0]


def test_model_id_absent_est_signale(monkeypatch):
    """Le port repond, mais il sert un autre modele : c est le 404 du 31/08."""
    class _Rep:
        def raise_for_status(self): pass
        def json(self): return {"data": [{"id": "un-autre-modele"}]}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Rep())

    anomalies = _routeur_avec(UN_FOURNISSEUR).verifier_fournisseurs_locaux()

    assert len(anomalies) == 1
    assert "nemotron-lightning" in anomalies[0]
    assert "un-autre-modele" in anomalies[0]


def test_configuration_saine_ne_signale_rien(monkeypatch):
    """Controle negatif : la sonde doit savoir se taire."""
    class _Rep:
        def raise_for_status(self): pass
        def json(self): return {"data": [{"id": "nemotron-lightning"}]}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Rep())

    assert _routeur_avec(UN_FOURNISSEUR).verifier_fournisseurs_locaux() == []


def test_fournisseur_distant_est_ignore(monkeypatch):
    """Anthropic et OpenAI ne sont pas sondes : pas de cle brulee au boot."""
    def _interdit(*a, **k):
        pytest.fail("un fournisseur distant a ete sonde")
    monkeypatch.setattr(httpx, "get", _interdit)

    distant = {"anthropic": {"type": ProviderType.ANTHROPIC, "base_url": "https://api.anthropic.com",
                             "models": {"sonnet": {"model_id": "claude-sonnet-4-6"}}}}
    assert _routeur_avec(distant).verifier_fournisseurs_locaux() == []


def test_yaml_reel_declare_un_modele_effectivement_servi():
    """Garde sur le YAML livre : chaque model_id local doit etre celui du serveur.

    C est ce test qui aurait attrape "nemotron-3-nano-30b-a3b".
    """
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load(Path("config/llm_routing.yaml").read_text(encoding="utf-8"))
    gpu = cfg["providers"]["gpu_local"]
    assert gpu["base_url_nemotron"].startswith("http://127.0.0.1:18084"), \
        "18080 = tunnel Packet.ai eteint ; le Spark est sur 18084"
    assert gpu["models"]["nemotron"]["model_id"] == "nemotron-lightning"
    assert "gemma" not in gpu["models"], "Gemma n est plus servi par le Spark"
    assert "qwen" not in gpu["models"], "le GPU loue n a pas d adresse fixe"
