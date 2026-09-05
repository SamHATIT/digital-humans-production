"""Hotfix 05/09/2026 — le premier parcours Free de bout en bout (03/09).

Deux defauts, anterieurs aux vagues :
1. `_call_gpu_local` envoyait a vLLM la CLE du YAML ("nemotron") au lieu du
   `model_id` ("nemotron-lightning") : 404 a chaque appel.
2. `sophie_chat_service` lisait `response["content"]` sans regarder
   `response["success"]` : le 404 devenait un 200 avec une reponse vide.
"""
import asyncio
import json

import httpx
import pytest

from app.services.llm_router_service import LLMRouterService, LLMRequest, ProviderType


def _routeur():
    r = LLMRouterService.__new__(LLMRouterService)
    r.providers = {
        "gpu_nemotron": {
            "type": ProviderType.LOCAL,
            "base_url": "http://127.0.0.1:18084/v1",
            "timeout_seconds": 5,
            "models": {"nemotron": {"model_id": "nemotron-lightning", "reasoning": False}},
        }
    }
    r.profile = "test_gpu_complet"
    return r


def test_vllm_recoit_le_model_id_pas_la_cle(monkeypatch):
    envoye = {}

    class _Rep:
        status_code = 200
        text = ""
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1}}

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None, **k):
            envoye.update(json or {})
            return _Rep()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    req = LLMRequest(prompt="x", agent_type="sophie", user_id=1, max_tokens=50)
    resp = asyncio.run(_routeur()._call_gpu_local(req, "nemotron", "gpu_nemotron"))
    assert resp.success, resp.error
    assert envoye["model"] == "nemotron-lightning", envoye.get("model")
    assert envoye["model"] != "nemotron"


def test_sophie_chat_ne_rend_pas_un_200_vide(monkeypatch):
    """Controle : un echec LLM doit sortir en success=False avec le motif, pas en message vide."""
    from app.services import sophie_chat_service as scs
    monkeypatch.setattr(scs, "generate_llm_response",
                        lambda **k: {"success": False, "content": "", "error": "HTTP 404 : model absent",
                                     "model": "nemotron"})
    svc = scs.SophieChatService.__new__(scs.SophieChatService)
    svc.db = None
    monkeypatch.setattr(svc, "get_project_context", lambda *a, **k: {"project": {}}, raising=False)
    monkeypatch.setattr(svc, "get_conversation_history", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(svc, "_resolve_subscription_tier", lambda *a, **k: "free", raising=False)
    monkeypatch.setattr(svc, "_build_system_prompt", lambda *a, **k: "sys", raising=False)
    monkeypatch.setattr(svc, "_save_message", lambda *a, **k: None, raising=False)
    result = asyncio.run(svc.chat(project_id=1, user_message="bonjour", user_id=1))
    assert result["success"] is False
    assert "404" in result.get("error", "")
