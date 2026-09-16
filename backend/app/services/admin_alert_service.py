"""Alerte administrateur (VAGUE 1 / FILE C — GL-10).

Le 15/09, le RAG documentaire est tombé (`429 credit_balance_exhausted`) et
personne ne l'a su avant le soir : 146 requêtes échouées, quatre SDS produits
sans corpus. Règle posée par Sam le jour même : **l'exploitant doit le savoir
dans la minute**, avec l'exécution concernée et la cause ; **le client ne voit
rien** ; l'exécution est marquée `degraded` pour pouvoir être rejouée.

Trois canaux, par ordre de fiabilité décroissante :

1. le **journal**, en ERROR — toujours écrit, c'est le canal qui ne tombe pas ;
2. **Telegram**, si `TELEGRAM_BOT_TOKEN` et `TELEGRAM_CHAT_ID` sont posés ;
3. le **tableau de bord admin**, qui lit les mêmes alertes en base.

Une alerte ne fait jamais échouer son appelant : signaler une panne ne doit pas
en provoquer une seconde.

Ce module n'est pas un canal client. Rien de ce qu'il écrit ne doit remonter
dans une réponse d'API, un prompt ou un livrable.
"""
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request
from typing import Dict, Optional

logger = logging.getLogger(__name__)

#: Fenêtre de silence par clé de déduplication. Le 15/09, la même panne a
#: produit 146 échecs : une alerte par échec rendrait le canal illisible, et
#: une alerte noyée est une alerte perdue.
FENETRE_DEDUPLICATION_S = 900

_verrou = threading.Lock()
_dernieres_alertes: Dict[str, float] = {}


def reinitialiser_deduplication() -> None:
    """Vide la mémoire de déduplication (tests, ou reprise après incident)."""
    with _verrou:
        _dernieres_alertes.clear()


def _doit_alerter(cle: Optional[str]) -> bool:
    if not cle:
        return True
    maintenant = time.monotonic()
    with _verrou:
        precedente = _dernieres_alertes.get(cle)
        if precedente is not None and (maintenant - precedente) < FENETRE_DEDUPLICATION_S:
            return False
        _dernieres_alertes[cle] = maintenant
    return True


def _envoyer_telegram(sujet: str, corps: str, timeout: float = 5.0) -> bool:
    """Transport Telegram. Rend False s'il n'est pas configuré.

    Aucun envoi n'est *tenté* sans jeton ni destinataire : une tentative
    sortante depuis la suite de tests serait refusée et comptée (vague 0).
    """
    jeton = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    destinataire = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    if not jeton or not destinataire or jeton.startswith("dh-test-fake-"):
        return False

    donnees = urllib.parse.urlencode(
        {"chat_id": destinataire, "text": f"{sujet}\n\n{corps}"}
    ).encode()
    url = f"https://api.telegram.org/bot{jeton}/sendMessage"
    with urllib.request.urlopen(url, donnees, timeout=timeout) as reponse:
        return 200 <= reponse.status < 300


def alerter_admin(
    sujet: str,
    corps: str,
    *,
    cle_deduplication: Optional[str] = None,
    execution_id: Optional[int] = None,
    categorie: str = "operation",
) -> bool:
    """Signale un incident d'exploitation. Rend True si Telegram a accepté.

    Le journal reçoit l'alerte dans tous les cas, y compris quand le transport
    n'est pas configuré : un dispositif d'alerte inerte doit le dire, pas se
    taire (règle 6).
    """
    if not _doit_alerter(cle_deduplication):
        logger.info(
            "[ALERTE ADMIN] %s — déjà signalée dans les %s dernières secondes, "
            "pas de nouvel envoi (clé %s)",
            sujet,
            FENETRE_DEDUPLICATION_S,
            cle_deduplication,
        )
        return False

    logger.error("[ALERTE ADMIN] %s — %s", sujet, corps)
    _persister(sujet, corps, categorie=categorie, execution_id=execution_id)

    try:
        envoye = _envoyer_telegram(sujet, corps)
    except Exception as e:
        logger.error("[ALERTE ADMIN] Transport Telegram en échec : %s", e)
        return False

    if not envoye:
        logger.error(
            "[ALERTE ADMIN] Telegram non configuré (TELEGRAM_BOT_TOKEN / "
            "TELEGRAM_CHAT_ID) : cette alerte n'existe que dans le journal et "
            "le tableau de bord."
        )
    return envoye


def _persister(
    sujet: str, corps: str, *, categorie: str, execution_id: Optional[int]
) -> None:
    """Écrit l'alerte là où le tableau de bord admin la lira.

    Le stockage dédié n'existe pas encore (AS-10, vague 2) : en attendant,
    l'alerte est écrite dans le journal d'audit, déjà consulté par l'admin, et
    l'exécution concernée porte sa propre marque `degraded`. On ne prétend pas
    disposer d'un canal que l'on n'a pas.
    """
    try:
        from app.services.audit_service import ActionCategory, ActorType, audit_service

        audit_service.log(
            actor_type=ActorType.SYSTEM,
            actor_id="admin_alert",
            action=ActionCategory.EXECUTION_FAIL,
            entity_type="alerte",
            entity_id=categorie,
            execution_id=execution_id,
            success="false",
            error_message=f"{sujet} — {corps}"[:2000],
            extra_data={"sujet": sujet, "corps": corps[:2000], "categorie": categorie},
        )
    except Exception as e:
        logger.warning("[ALERTE ADMIN] Journal d'audit indisponible : %s", e)
