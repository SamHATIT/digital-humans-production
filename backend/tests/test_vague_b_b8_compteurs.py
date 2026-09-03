"""
Vague B — lot B8, point 1 : les compteurs `chat_logs.tokens_in` / `tokens_out`.

Constat (docs/vague-a/EXECUTION.md §3, verifie par A5 par execution) :
`sophie_concierge_service.py` persiste `getattr(response, "tokens_input",
...)` / `getattr(response, "tokens_output", ...)` alors que `LLMResponse`
(llm_router_service.py) expose `tokens_in` / `tokens_out`. Les deux colonnes
`chat_logs.tokens_in` / `tokens_out` restent donc NULL quel que soit le
volume reellement consomme.

Ce fichier :
  1. Prouve le defaut avec un routeur simule qui renvoie tokens_in=17,
     tokens_out=42 (valeurs distinctes, choisies pour ne jamais pouvoir etre
     confondues entre elles ni avec une somme ou un id).
  2. Apres correctif, verifie que chaque colonne porte la bonne valeur
     (assertions separees — pas sur la somme, pour detecter une inversion
     tokens_in/tokens_out).
  3. Controle negatif : si le routeur ne porte pas les attributs tokens_in /
     tokens_out, le tour ne leve pas d'exception ; il documente ce que le
     code fait alors (colonnes a None, cote appelant a 0).
"""
import asyncio
import uuid

import pytest

from app.services import sophie_concierge_service as concierge
from app.models.chat_log import ChatLog


SEL_TEST = "sel-de-test-lot-b8"


class _RouteurAvecJetons:
    """Faux routeur LLM : renvoie une reponse avec tokens_in/tokens_out distincts."""

    def __init__(self, tokens_in=17, tokens_out=42, avec_jetons=True):
        self._tokens_in = tokens_in
        self._tokens_out = tokens_out
        self._avec_jetons = avec_jetons
        self.requetes = []

    async def complete(self, request):
        self.requetes.append(request)

        if self._avec_jetons:
            class _Reponse:
                content = 'Bonjour, je suis Sophie. [META]{"intent": "info"}'
                cost_usd = 0.000123
                tokens_in = self._tokens_in
                tokens_out = self._tokens_out
            # bind outer values via closure workaround (class body can't
            # reference self directly)
            _Reponse.tokens_in = self._tokens_in
            _Reponse.tokens_out = self._tokens_out
            return _Reponse()
        else:
            # Simule un routeur/fournisseur qui ne rendrait pas les jetons du
            # tout (attribut absent) — pas de tokens_in/tokens_out sur l'objet.
            class _ReponseSansJetons:
                content = 'Bonjour, je suis Sophie. [META]{"intent": "info"}'
                cost_usd = 0.0
            return _ReponseSansJetons()


def _dernier_tour_assistant(db_session, session_uuid):
    return (
        db_session.query(ChatLog)
        .filter(ChatLog.session_uuid == session_uuid, ChatLog.role == "assistant")
        .order_by(ChatLog.created_at.desc())
        .first()
    )


def test_les_jetons_du_routeur_sont_persistes_dans_chat_logs(db_session, monkeypatch):
    """tokens_in=17 et tokens_out=42 doivent arriver, chacun sur sa colonne.

    Avant correctif ce test est rouge : `getattr(response, "tokens_input",
    None)` ne trouve jamais cet attribut sur `_Reponse` (qui porte
    `tokens_in`), donc les deux colonnes restent `None`.
    """
    monkeypatch.setattr(concierge, "IP_SALT", SEL_TEST)
    routeur = _RouteurAvecJetons(tokens_in=17, tokens_out=42)
    monkeypatch.setattr(concierge, "get_llm_router", lambda: routeur)

    session_uuid = str(uuid.uuid4())
    reponse = asyncio.run(
        concierge.converse(
            db=db_session,
            session_uuid=session_uuid,
            visitor_ip="203.0.113.9",
            visitor_language="fr",
            user_message="Combien coute un SDS ?",
        )
    )

    ligne = _dernier_tour_assistant(db_session, session_uuid)
    assert ligne is not None, "aucun tour assistant persiste"

    # Assertions separees par colonne : une inversion tokens_in<->tokens_out
    # ne doit pas passer inapercue derriere une somme.
    assert ligne.tokens_in == 17, f"chat_logs.tokens_in attendu 17, obtenu {ligne.tokens_in}"
    assert ligne.tokens_out == 42, f"chat_logs.tokens_out attendu 42, obtenu {ligne.tokens_out}"

    # La valeur rendue a l'appelant (route HTTP) doit correspondre elle aussi.
    assert reponse.tokens_in == 17
    assert reponse.tokens_out == 42


def test_controle_negatif_pas_de_confusion_entre_tokens_in_et_tokens_out(db_session, monkeypatch):
    """Avec des valeurs distinctes, une inversion se verrait immediatement.

    Ce test rejoue le meme tour avec tokens_in et tokens_out echanges par
    rapport au premier test, pour s'assurer que le code ne fait pas une
    correspondance figee (par exemple toujours coller la premiere valeur
    dans tokens_in). Si le correctif etait "tokens_in = tokens_out du
    routeur", ce test le detecterait.
    """
    monkeypatch.setattr(concierge, "IP_SALT", SEL_TEST)
    routeur = _RouteurAvecJetons(tokens_in=99, tokens_out=3)
    monkeypatch.setattr(concierge, "get_llm_router", lambda: routeur)

    session_uuid = str(uuid.uuid4())
    asyncio.run(
        concierge.converse(
            db=db_session,
            session_uuid=session_uuid,
            visitor_ip="203.0.113.10",
            visitor_language="fr",
            user_message="Et pour un BUILD ?",
        )
    )

    ligne = _dernier_tour_assistant(db_session, session_uuid)
    assert ligne.tokens_in == 99
    assert ligne.tokens_out == 3


def test_routeur_sans_jetons_ne_leve_pas_et_documente_le_repli(db_session, monkeypatch):
    """Si `response` ne porte ni tokens_in ni tokens_out (attribut absent),
    le tour ne doit pas lever d'exception.

    Ce que le code fait, une fois corrige (a verifier, pas a supposer) :
      - `chat_logs.tokens_in` / `tokens_out` (colonnes nullable) recoivent
        `None` — c'est ce que `getattr(response, "tokens_in", None)` rend
        quand l'attribut est absent ;
      - la valeur rendue a l'appelant HTTP (`ConciergeReply.tokens_in` /
        `tokens_out`, champs `int = 0` sans None) recoit `0`.
    """
    monkeypatch.setattr(concierge, "IP_SALT", SEL_TEST)
    routeur = _RouteurAvecJetons(avec_jetons=False)
    monkeypatch.setattr(concierge, "get_llm_router", lambda: routeur)

    session_uuid = str(uuid.uuid4())
    reponse = asyncio.run(
        concierge.converse(
            db=db_session,
            session_uuid=session_uuid,
            visitor_ip="203.0.113.11",
            visitor_language="fr",
            user_message="Un dernier tour sans jetons rendus.",
        )
    )

    ligne = _dernier_tour_assistant(db_session, session_uuid)
    assert ligne is not None
    assert ligne.tokens_in is None, (
        f"attendu None (colonne nullable, attribut absent du routeur), obtenu {ligne.tokens_in}"
    )
    assert ligne.tokens_out is None, (
        f"attendu None (colonne nullable, attribut absent du routeur), obtenu {ligne.tokens_out}"
    )
    assert reponse.tokens_in == 0, (
        f"ConciergeReply.tokens_in n'a pas de defaut None (int=0) ; attendu 0, obtenu {reponse.tokens_in}"
    )
    assert reponse.tokens_out == 0
