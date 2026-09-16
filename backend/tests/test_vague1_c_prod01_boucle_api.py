"""
VAGUE 1 / FILE C — PROD-01 : un chat Sophie peut immobiliser toute la boucle
API.

Astra L378 : « `chat()` est asynchrone mais attend un appel synchrone. Le
thread cree dans `complete_sync` ne libere pas l'event loop appelante :
celle-ci attend sur `future.result`. Pendant un appel lent, les autres
requetes, sondes et flux de ce processus peuvent etre figes. »

Mesure du 16/09 (file C), lue dans le code :

  `sophie_chat_service.py:196` appelle `generate_llm_response` (synchrone)
  depuis `async def chat`. Ce chemin descend dans
  `llm_router_service.complete_sync:1250`, `future.result(timeout=600)` —
  une attente bloquante de dix minutes au pire, **dans** la boucle.

Un equivalent asynchrone existe pourtant deja et rend la meme forme :
`generate_llm_response_async` -> `LLMRouterService.generate_async`.

Methode de preuve : on n'affirme pas « la boucle est bloquee », on le mesure.
Une tache temoin s'incremente toutes les millisecondes pendant l'appel ; si la
boucle est rendue, elle avance. Le transport LLM est simule (aucun reseau).
"""
import asyncio

import pytest

from app.models.project import Project
from app.models.user import User


@pytest.fixture
def projet(db_session):
    user = User(
        email="vague1c-prod01@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C PROD-01",
        subscription_tier="pro",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    # La description est posee explicitement : un projet sans description fait
    # tomber `_build_system_prompt` (constat annexe, corrige a part).
    project = Project(
        user_id=user.id, name="PROD-01", description="Un projet de test"
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return {"user": user, "project": project}


async def _temoin(compteur, stop):
    """Avance tant que la boucle lui rend la main."""
    while not stop.is_set():
        compteur[0] += 1
        await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_un_appel_sophie_lent_ne_gele_pas_la_boucle(
    db_session, projet, monkeypatch
):
    """Le coeur de PROD-01, mesure et non suppose."""
    from app.services import sophie_chat_service as module

    duree_appel = 0.4

    async def _llm_async(prompt, agent_type="worker", system_prompt=None, **kwargs):
        await asyncio.sleep(duree_appel)
        return {
            "success": True,
            "content": "Bonjour, je suis Sophie.",
            "tokens_used": 12,
            "model": "simule",
        }

    def _llm_sync(*a, **kw):
        # Ce que fait `complete_sync` vu de la boucle : une attente bloquante.
        import time

        time.sleep(duree_appel)
        return {
            "success": True,
            "content": "Bonjour, je suis Sophie.",
            "tokens_used": 12,
            "model": "simule",
        }

    monkeypatch.setattr(module, "generate_llm_response", _llm_sync, raising=False)
    monkeypatch.setattr(
        module, "generate_llm_response_async", _llm_async, raising=False
    )

    service = module.SophieChatService(db_session)

    compteur = [0]
    stop = asyncio.Event()
    temoin = asyncio.create_task(_temoin(compteur, stop))
    await asyncio.sleep(0.01)
    depart = compteur[0]

    try:
        await service.chat(
            project_id=projet["project"].id,
            user_message="Bonjour",
            user_id=projet["user"].id,
        )
    finally:
        stop.set()
        await temoin

    avance = compteur[0] - depart
    assert avance > 20, (
        f"la tache temoin n'a avance que de {avance} pas pendant un appel de "
        f"{duree_appel}s : la boucle d'evenements est restee bloquee. Toutes "
        f"les autres requetes, sondes et flux SSE de ce processus attendaient "
        f"avec elle (PROD-01)."
    )


@pytest.mark.asyncio
async def test_le_chat_rend_toujours_la_reponse_de_sophie(
    db_session, projet, monkeypatch
):
    """Controle negatif : liberer la boucle ne doit rien changer au contrat.
    Une version qui ne ferait plus l'appel passerait le test precedent."""
    from app.services import sophie_chat_service as module

    async def _llm_async(prompt, agent_type="worker", system_prompt=None, **kwargs):
        return {
            "success": True,
            "content": "Bonjour, je suis Sophie.",
            "tokens_used": 12,
            "model": "simule",
        }

    monkeypatch.setattr(
        module, "generate_llm_response_async", _llm_async, raising=False
    )
    monkeypatch.setattr(
        module, "generate_llm_response",
        lambda *a, **kw: pytest.fail("le chemin synchrone est encore emprunte"),
        raising=False,
    )

    service = module.SophieChatService(db_session)
    reponse = await service.chat(
        project_id=projet["project"].id,
        user_message="Bonjour",
        user_id=projet["user"].id,
    )
    assert reponse["message"] == "Bonjour, je suis Sophie."


@pytest.mark.asyncio
async def test_un_echec_llm_reste_un_echec(db_session, projet, monkeypatch):
    """Controle negatif : le garde-fou du 05/09 (« un echec LLM ne doit jamais
    devenir un 200 vide ») doit survivre au passage en asynchrone."""
    from app.services import sophie_chat_service as module

    async def _llm_async(prompt, agent_type="worker", system_prompt=None, **kwargs):
        return {"success": False, "error": "404 du fournisseur", "content": ""}

    monkeypatch.setattr(
        module, "generate_llm_response_async", _llm_async, raising=False
    )

    service = module.SophieChatService(db_session)
    reponse = await service.chat(
        project_id=projet["project"].id,
        user_message="Bonjour",
        user_id=projet["user"].id,
    )

    # `chat()` attrape ses exceptions et rend un dict : c'est ce que la route
    # lit. Ce qui compte est donc que l'echec reste un echec, avec son motif.
    assert reponse["success"] is False, (
        f"un echec LLM rendu comme un succes : {reponse}"
    )
    assert "404" in reponse.get("error", "") or "n a pas pu repondre" in reponse.get(
        "error", ""
    ), f"le motif de l'echec est perdu : {reponse}"


@pytest.mark.asyncio
async def test_un_projet_sans_description_ne_casse_pas_le_chat(
    db_session, projet, monkeypatch
):
    """Constat annexe, rencontre en montant les tests ci-dessus.

    `_build_system_prompt` faisait `project_info.get('description', 'Non
    disponible')[:500]`. Le defaut d'un `.get` ne s'applique QUE si la cle est
    absente : une colonne `description` a NULL — cas d'un projet cree sans
    description, ce que le schema autorise — donnait `None[:500]`, donc un
    TypeError, donc un 500 sur le chat. Le premier message de Sophie tombait
    pour un projet parfaitement valide.
    """
    from app.services import sophie_chat_service as module

    projet["project"].description = None
    db_session.commit()

    async def _llm_async(prompt, agent_type="worker", system_prompt=None, **kwargs):
        return {
            "success": True,
            "content": "Bonjour, je suis Sophie.",
            "tokens_used": 12,
            "model": "simule",
        }

    monkeypatch.setattr(
        module, "generate_llm_response_async", _llm_async, raising=False
    )

    service = module.SophieChatService(db_session)
    reponse = await service.chat(
        project_id=projet["project"].id,
        user_message="Bonjour",
        user_id=projet["user"].id,
    )
    assert reponse["success"] is True, f"chat casse sans description : {reponse}"
