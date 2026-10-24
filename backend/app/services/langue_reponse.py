"""Langue de réponse des agents en dialogue — vague 2 / file C.

Mesuré le 30/09 : une question posée en anglais au Free, Sophie répond en
français. Cause lue le 24/10 : les prompts de chat (config/agents_registry.yaml,
sophie_chat_service) imposaient « Réponds en français ».

Règle : la réponse suit la langue de la QUESTION ; quand la question ne la dit
pas (« OK ? »), celle de l'INTERFACE ; quand ni l'une ni l'autre n'est connue,
la consigne demande au modèle de suivre la langue du client — elle ne devine
pas le français.

La détection est volontairement simple (mots-outils, accents) et ne connaît
que le français et l'anglais, les deux langues de l'interface. Elle rend
``None`` plutôt que de trancher sur un texte trop court ou mêlé.
"""
from __future__ import annotations

import re
from typing import Optional

LANGUES = ("fr", "en")

_MOTS_FR = frozenset("""
le la les un une des du de et est sont je tu il elle nous vous ils elles que qui quel quelle
quels quelles pour avec sur dans pas ne ce cette ces mon ma mes ton ta tes son sa ses notre
votre leur au aux mais ou donc car comment pourquoi quand bonjour merci oui non très aussi
peux peut veux faire fait suis es sommes êtes être avoir ai as avons avez ont c'est qu'est
""".split())

_MOTS_EN = frozenset("""
the an and is are was were i you he she we they what which who whom for with not this that
these those my your his her our their but or so because how why when hello hi thanks thank
please yes no very also can could would should will do does did be been have has had it's
what's i'm you're of to from about
""".split())

_ACCENTS_FR = re.compile(r"[éèêëàâçùûôîïœ]", re.IGNORECASE)
_MOT = re.compile(r"[a-zA-Zàâçéèêëîïôûùüœ']+")


def detecter_langue(texte: Optional[str]) -> Optional[str]:
    """``"fr"``, ``"en"`` ou ``None`` (indécidable)."""
    if not texte:
        return None
    mots = [m.lower() for m in _MOT.findall(texte)]
    fr = sum(1 for m in mots if m in _MOTS_FR) + len(_ACCENTS_FR.findall(texte))
    en = sum(1 for m in mots if m in _MOTS_EN)
    if fr >= 2 and fr > en:
        return "fr"
    if en >= 2 and en > fr:
        return "en"
    return None


def normaliser_langue(lang: Optional[str]) -> Optional[str]:
    """``fr-FR`` → ``fr`` ; une langue hors interface rend ``None``."""
    if not lang:
        return None
    court = lang.strip().lower().split("-")[0].split("_")[0]
    return court if court in LANGUES else None


def langue_de_reponse(message: Optional[str], langue_interface: Optional[str] = None) -> Optional[str]:
    """La langue de la question prime ; à défaut, celle de l'interface."""
    return detecter_langue(message) or normaliser_langue(langue_interface)


def consigne_langue(langue: Optional[str]) -> str:
    """Consigne ajoutée au prompt système."""
    if langue == "fr":
        return ("LANGUE DE RÉPONSE : Réponds en français, la langue du client. "
                "Garde tels quels les noms d'API Salesforce, le code et les "
                "identifiants techniques.")
    if langue == "en":
        return ("RESPONSE LANGUAGE: Reply in English, the client's language. "
                "Keep Salesforce API names, code and technical identifiers as they are.")
    return ("RESPONSE LANGUAGE / LANGUE DE RÉPONSE: reply in the language of the "
            "client's last message.")


def avec_consigne_langue(system_prompt: Optional[str], message: Optional[str],
                         langue_interface: Optional[str] = None) -> str:
    consigne = consigne_langue(langue_de_reponse(message, langue_interface))
    return f"{system_prompt}\n\n{consigne}" if system_prompt else consigne
