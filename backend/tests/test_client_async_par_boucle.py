"""Client Anthropic async : un par boucle d'evenements (15/11/2026).

Smoke exec 183 : 9 appels « Event loop is closed » — le client async etait
partage entre les boucles que `complete_sync` cree et ferme a chaque appel.
"""
import asyncio
import threading

from app.services.llm_router_service import LLMRouterService


def _routeur():
    r = LLMRouterService.__new__(LLMRouterService)
    crees = []
    def fabrique():
        c = object(); crees.append(c); return c
    r.async_providers = {"anthropic": {"client": "partage", "fabrique": fabrique}}
    return r, crees


def test_meme_boucle_meme_client():
    r, _ = _routeur()
    async def deux():
        return r._client_async_par_boucle("anthropic"), r._client_async_par_boucle("anthropic")
    a, b = asyncio.run(deux())
    assert a is b and a != "partage"


def test_boucles_differentes_clients_differents_y_compris_en_threads():
    """Rouge avant le correctif : toutes les boucles recevaient le meme client."""
    r, crees = _routeur()
    vus = []
    def dans_un_thread():
        async def prendre():
            vus.append(r._client_async_par_boucle("anthropic"))
        asyncio.run(prendre())
    for _ in range(3):
        t = threading.Thread(target=dans_un_thread); t.start(); t.join()
    assert len({id(c) for c in vus}) == 3 and len(crees) == 3


def test_sans_boucle_ou_sans_fabrique_le_client_historique_sert():
    r, _ = _routeur()
    assert r._client_async_par_boucle("anthropic") == "partage"
    r.async_providers = {"openai": {"client": "oa"}}
    async def x():
        return r._client_async_par_boucle("openai")
    assert asyncio.run(x()) == "oa"


def test_l_appel_anthropic_passe_par_le_client_de_la_boucle():
    import inspect
    from app.services import llm_router_service as mod
    source = inspect.getsource(mod.LLMRouterService._call_anthropic)
    assert 'self._client_async_par_boucle("anthropic")' in source
