"""
Vague 2 / file C — langue des agents et GL-26 (persona).

Langue. Mesuré le 30/09 : une question posée en anglais au Free, Sophie
répond en français. Lu le 24/10 : les onze prompts de chat de
config/agents_registry.yaml finissent par « Réponds en français », et le
prompt du chat projet (sophie_chat_service) aussi. Attendu : la réponse suit
la langue de la question, ou celle de l'interface quand la question ne la
dit pas.

GL-26. Mesuré le 17/09 : interrogée sur son rôle, Olivia répond « En tant que
Project Manager senior » (rôle de Sophie), après un échange avec Sophie. Lu le
24/10 : `/api/studio/chat` étiquette TOUS les tours « assistant » de
l'historique du nom de l'agent courant ; la réponse de Sophie arrive donc dans
le prompt d'Olivia sous « Olivia: En tant que Project Manager senior… ».

Ce qui est prouvé ici : le prompt système et la consigne de langue
EFFECTIVEMENT envoyés au modèle (client LLM bouchonné, aucun appel réseau).
Ce qui ne l'est pas : qu'un modèle réel suive la consigne — cela demande un
appel réel, hors de cette mission (voir le rapport).
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from app.main import app
from app.models.project import Project
from app.models.user import User
from app.services.agents_registry import iter_chat_profiles
from app.utils.dependencies import get_current_user

STUDIO = "/api/studio/chat"

QUESTION_EN = "Hello Sophie, what exactly is your role on this project and what will you deliver?"
QUESTION_FR = "Bonjour Sophie, quel est exactement ton rôle sur ce projet et que vas-tu livrer ?"


@pytest.fixture
def capture(monkeypatch):
    """Bouchon du client LLM : capture le prompt système et le prompt, rend
    un texte fixe. Remplace la fonction appelée par les routes de chat."""
    appels = []

    def _faux(prompt, agent_type="worker", system_prompt=None, **kwargs):
        appels.append({"prompt": prompt, "system_prompt": system_prompt or "",
                       "agent_type": agent_type, "kwargs": kwargs})
        return {"content": "réponse simulée", "success": True, "tokens_used": 1,
                "model": "bouchon", "provider": "bouchon"}

    async def _faux_async(prompt, agent_type="worker", system_prompt=None, **kwargs):
        return _faux(prompt, agent_type=agent_type, system_prompt=system_prompt, **kwargs)

    monkeypatch.setattr("app.services.llm_service.generate_llm_response", _faux)
    monkeypatch.setattr("app.services.sophie_chat_service.generate_llm_response_async",
                        _faux_async)
    return appels


def _compte(db_session, palier="pro"):
    s = uuid.uuid4().hex[:8]
    u = User(email=f"langue-{s}@exemple.test", hashed_password="x",
             name=f"Langue {s}", subscription_tier=palier)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)

    async def _o():
        return u
    app.dependency_overrides[get_current_user] = _o
    return u


# ─────────────────────────────────────────────────────────────────────
# Langue — dialogue Studio (parcours Free mesuré le 30/09)
# ─────────────────────────────────────────────────────────────────────


def test_question_en_anglais_consigne_de_repondre_en_anglais(client, db_session, capture):
    _compte(db_session, "free")
    r = client.post(STUDIO, json={"message": QUESTION_EN, "agent_id": "sophie"})
    assert r.status_code == 200, r.text
    sp = capture[-1]["system_prompt"]
    assert "Réponds en français" not in sp, (
        "le prompt de Sophie impose encore le français à une question en anglais")
    assert "Reply in English" in sp


def test_question_en_francais_consigne_de_repondre_en_francais(client, db_session, capture):
    _compte(db_session, "free")
    r = client.post(STUDIO, json={"message": QUESTION_FR, "agent_id": "sophie"})
    assert r.status_code == 200, r.text
    sp = capture[-1]["system_prompt"]
    assert "Réponds en français" in sp
    assert "Reply in English" not in sp


def test_question_sans_langue_lisible_suit_l_interface(client, db_session, capture):
    _compte(db_session, "free")
    client.post(STUDIO, json={"message": "OK ?", "agent_id": "sophie", "lang": "en"})
    assert "Reply in English" in capture[-1]["system_prompt"]
    client.post(STUDIO, json={"message": "OK ?", "agent_id": "sophie", "lang": "fr"})
    assert "Réponds en français" in capture[-1]["system_prompt"]


def test_controle_negatif_la_question_prime_sur_l_interface(client, db_session, capture):
    """Interface en anglais, question en français : on répond en français.
    Sans ce contrôle, un correctif qui ne lirait que l'interface passerait."""
    _compte(db_session, "free")
    client.post(STUDIO, json={"message": QUESTION_FR, "agent_id": "sophie", "lang": "en"})
    sp = capture[-1]["system_prompt"]
    assert "Réponds en français" in sp and "Reply in English" not in sp


def test_aucun_prompt_de_chat_n_impose_le_francais():
    """Les onze profils du registre : aucun « Réponds en français » en dur."""
    fautifs = [p["agent_id"] for p in iter_chat_profiles()
               if "Réponds en français" in p["system_prompt"]]
    assert fautifs == [], f"prompts qui imposent le français : {fautifs}"


# ─────────────────────────────────────────────────────────────────────
# Langue — chat projet (Sophie, sophie_chat_service) et chat d'exécution
# ─────────────────────────────────────────────────────────────────────


def test_chat_projet_sophie_suit_la_langue_de_la_question(db_session, capture):
    from app.services.sophie_chat_service import SophieChatService

    u = _compte(db_session, "pro")
    p = Project(user_id=u.id, name="Projet langue")
    db_session.add(p)
    db_session.commit()

    svc = SophieChatService(db_session)
    asyncio.run(svc.chat(p.id, QUESTION_EN, user_id=u.id))
    sp_en = capture[-1]["system_prompt"]
    asyncio.run(svc.chat(p.id, QUESTION_FR, user_id=u.id))
    sp_fr = capture[-1]["system_prompt"]

    assert "Réponds en français" not in sp_en and "Reply in English" in sp_en
    assert "Réponds en français" in sp_fr and "Reply in English" not in sp_fr


# ─────────────────────────────────────────────────────────────────────
# GL-26 — chaque agent reçoit son propre prompt, et l'historique dit qui a parlé
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("profil", iter_chat_profiles(), ids=lambda p: p["agent_id"])
def test_chaque_agent_recoit_son_prompt_systeme(client, db_session, capture, profil):
    _compte(db_session, "pro")      # le Pro atteint l'ensemble (chat_full_team)
    r = client.post(STUDIO, json={"message": QUESTION_FR, "agent_id": profil["agent_id"]})
    assert r.status_code == 200, r.text
    sp = capture[-1]["system_prompt"]
    assert sp.startswith(f"Tu es {profil['name']},"), sp[:80]
    autres = [q["name"] for q in iter_chat_profiles()
              if q["agent_id"] != profil["agent_id"] and f"Tu es {q['name']}" in sp]
    assert autres == [], f"le prompt de {profil['name']} contient l'identité de {autres}"
    assert capture[-1]["agent_type"] == profil["agent_type"]


def test_l_historique_attribue_chaque_reponse_a_l_agent_qui_l_a_donnee(
        client, db_session, capture):
    """Échange avec Sophie, puis question à Olivia : la réponse de Sophie doit
    arriver dans le prompt d'Olivia sous « Sophie: », pas sous « Olivia: »."""
    _compte(db_session, "free")
    historique = [
        {"role": "user", "content": "Quel est ton rôle ?"},
        {"role": "assistant", "agent_id": "sophie",
         "content": "En tant que Project Manager senior, je cadre le projet."},
    ]
    r = client.post(STUDIO, json={"message": "Et toi Olivia, quel est ton rôle ?",
                                  "agent_id": "olivia", "history": historique})
    assert r.status_code == 200, r.text
    prompt = capture[-1]["prompt"]
    assert "Sophie: En tant que Project Manager senior" in prompt, prompt
    assert "Olivia: En tant que Project Manager senior" not in prompt, (
        "la réponse de Sophie est attribuée à Olivia dans son propre prompt")
    assert prompt.rstrip().endswith("Olivia:")


def test_controle_negatif_un_tour_sans_agent_n_est_pas_attribue_a_l_agent_courant(
        client, db_session, capture):
    """Un ancien client qui n'envoie pas `agent_id` : on ne sait pas qui a
    parlé, on ne l'attribue donc pas à l'agent courant."""
    _compte(db_session, "free")
    historique = [{"role": "assistant", "content": "Réponse d'origine inconnue."}]
    client.post(STUDIO, json={"message": "Et alors ?", "agent_id": "olivia",
                              "history": historique})
    prompt = capture[-1]["prompt"]
    assert "Olivia: Réponse d'origine inconnue." not in prompt
    assert "Réponse d'origine inconnue." in prompt
