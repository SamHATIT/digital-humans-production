"""Consentement Opus — GL-22 (vague 2 / file C).

Le site promet « Opus on opt-in, cost shown before each call ». Décision Sam
du 17/09 : « on ajoute le recueil ». Ce module porte les trois opérations du
dispositif ; le routeur LLM et la route de lancement s'appuient dessus.

1. :func:`estimer` — avant le lancement, le coût en crédits que Marcus
   coûterait s'il était servi par le modèle à opt-in, et ce qu'il coûterait
   avec le modèle de repli.
2. :func:`enregistrer_decision` — trace : utilisateur, exécution, date,
   décision, montant affiché, version du texte de l'écran.
3. :func:`verifier_pour_appel` — avant CHAQUE appel routé vers un modèle à
   opt-in : un consentement accepté existe-t-il pour cette exécution, et le
   cumul mesuré + l'estimation de cet appel tient-il dans le montant accepté ?

Choix « le plus prudent » (mission : la formule, le texte et la durée de
validité ne sont fixés nulle part — à confirmer par Sam) :

  - **portée** : une exécution. Un consentement ne vaut ni pour une autre
    exécution, ni pour le chat, ni dans la durée ;
  - **montant** : plafond. Le montant affiché est celui que l'utilisateur
    accepte ; dès que le cumul des crédits Opus de l'exécution plus
    l'estimation de l'appel suivant le dépasserait, l'appel suivant part sur
    le modèle de repli — annoncé, pas silencieux ;
  - **formule** : ``APPELS_MARCUS_MAX`` appels × l'estimation d'un appel
    (``max_tokens`` de Marcus en entrée ET en sortie, au tarif
    ``model_pricing``) — la même estimation que la réservation BILL-01,
    donc une borne haute, pas une moyenne.

Un repli est **annoncé** : marque ``degraded`` sur l'exécution (motif
``opus_repli_sonnet``, rendue par l'API de progression), avertissement au
journal, et ``avis_repli`` sur la réponse du routeur pour les appels hors
exécution.
"""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.consentement_opus import (
    DECISION_ACCEPTE,
    DECISION_REFUSE,
    DECISIONS,
    ConsentementOpus,
)
from app.models.credit import (
    TRANSACTION_TYPE_CHARGE,
    TRANSACTION_TYPE_RESERVATION,
    CreditTransaction,
)

logger = logging.getLogger(__name__)

#: Version du texte de l'écran de consentement (frontend
#: ``OpusConsentDialog``). À changer avec le texte : la trace dit ce qui a été lu.
TEXTE_VERSION = "gl22-v1-20261024"

#: Appels Marcus d'un SDS, au plus : as_is 1 + design 2 (cœur puis
#: automatisation/UI) + gap 1 + wbs 1 + 2 révisions
#: (``MAX_ARCHITECTURE_REVISIONS`` de pm_orchestrator_service_v2). Lu dans le
#: code le 24/10, non mesuré sur une exécution réelle. Une révision « patch »
#: par section peut faire plus d'appels : ils passent alors sur le repli,
#: annoncé, plutôt que de dépasser le montant accepté.
APPELS_MARCUS_MAX = 7

#: Agent dont le routage décide du consentement à l'écran (Marcus).
AGENT_CONSENTEMENT = "architect"

MOTIF_REPLI = "opus_repli_sonnet"


class ConsentementOpusConfigError(RuntimeError):
    """Un modèle à opt-in est routé sans modèle de repli déclaré
    (``repli_sans_consentement`` du profil, config/llm_routing.yaml). On ne
    devine pas un repli : l'appel est refusé."""


@dataclass
class EstimationOpus:
    requis: bool
    modele: Optional[str] = None
    modele_repli: Optional[str] = None
    credits_par_appel: int = 0
    credits_repli_par_appel: int = 0
    appels_max: int = APPELS_MARCUS_MAX
    credits_estimes: int = 0
    credits_repli_estimes: int = 0
    texte_version: str = TEXTE_VERSION
    raison: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def credits_estimes_appel(pricing, max_tokens: int, caracteres_entree: int = 0) -> int:
    """Estimation d'UN appel, en crédits entiers (borne haute).

    Sortie : ``max_tokens``. Entrée : ``max_tokens`` comme la réservation
    BILL-01, relevé à ``caracteres_entree / 2`` si le prompt est plus long —
    un jeton fait rarement moins de deux caractères ; sans ce relèvement, un
    prompt de 100 000 jetons serait estimé à 32 000.
    """
    from app.services.credit_service import _credits_for_tokens

    entree = max(int(max_tokens), math.ceil(max(0, caracteres_entree) / 2))
    return _credits_for_tokens(pricing, entree, int(max_tokens))


def fournisseur_repli(router, provider_str: str) -> Optional[str]:
    profil = (router.config.get("profiles") or {}).get(router.profile) or {}
    return (profil.get("repli_sans_consentement") or {}).get(provider_str)


def estimer(db: Session, subscription_tier: Optional[str], router=None) -> EstimationOpus:
    """Ce que Marcus coûterait pour une exécution de ce palier.

    ``requis`` est faux quand le modèle routé n'exige pas d'opt-in, ou n'a pas
    de tarif : dans ce dernier cas la réservation BILL-01 refusera l'appel,
    explicitement — on ne demande pas un consentement sur un prix inconnu.
    """
    from app.services.credit_service import CreditService, UnknownModelError
    from app.services.llm_router_service import LLMRequest, get_llm_router

    router = router or get_llm_router()
    fournisseur = router._select_provider(LLMRequest(
        prompt="", agent_type=AGENT_CONSENTEMENT,
        subscription_tier=(subscription_tier or "free")))
    modele = router._get_model_id(fournisseur)
    credits = CreditService(db)
    try:
        tarif = credits._resolve_pricing(modele)
    except UnknownModelError:
        return EstimationOpus(requis=False, modele=modele,
                              raison="modèle sans tarif : l'appel sera refusé à la réservation")
    if not tarif.requires_opt_in:
        return EstimationOpus(requis=False, modele=modele, raison="modèle sans opt-in")

    repli = fournisseur_repli(router, fournisseur)
    if not repli:
        raise ConsentementOpusConfigError(
            f"'{fournisseur}' exige un opt-in mais le profil '{router.profile}' ne "
            f"déclare aucun repli_sans_consentement pour lui (config/llm_routing.yaml)")
    modele_repli = router._get_model_id(repli)
    tarif_repli = credits._resolve_pricing(modele_repli)

    max_tokens = router.get_max_tokens_for_agent(AGENT_CONSENTEMENT)
    par_appel = credits_estimes_appel(tarif, max_tokens)
    par_appel_repli = credits_estimes_appel(tarif_repli, max_tokens)
    return EstimationOpus(
        requis=True,
        modele=tarif.model_name,
        modele_repli=tarif_repli.model_name,
        credits_par_appel=par_appel,
        credits_repli_par_appel=par_appel_repli,
        credits_estimes=par_appel * APPELS_MARCUS_MAX,
        credits_repli_estimes=par_appel_repli * APPELS_MARCUS_MAX,
    )


def annoncer_repli(db: Session, execution_id: int, detail: str) -> None:
    """Marque ``degraded`` sur l'exécution, une fois par détail distinct.
    N'effectue pas le commit : l'appelant le fait."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.models.execution import Execution

    execution = db.get(Execution, execution_id)
    if execution is None:
        raise ValueError(f"exécution {execution_id} introuvable : repli non annonçable")
    marques = list(execution.degraded or [])
    if any(m.get("motif") == MOTIF_REPLI and m.get("detail") == detail for m in marques):
        return
    marques.append({"motif": MOTIF_REPLI, "detail": detail,
                    "at": datetime.now(timezone.utc).isoformat()})
    execution.degraded = marques
    flag_modified(execution, "degraded")


def enregistrer_decision(db: Session, user_id: int, execution_id: int,
                         estimation: EstimationOpus, decision: str) -> ConsentementOpus:
    """Trace la décision (sans commit). Un refus annonce aussitôt le repli."""
    if decision not in DECISIONS:
        raise ValueError(f"décision inconnue {decision!r} : attendu {DECISIONS}")
    ligne = ConsentementOpus(
        user_id=user_id,
        execution_id=execution_id,
        model_name=estimation.modele,
        decision=decision,
        credits_estimes=estimation.credits_estimes if decision == DECISION_ACCEPTE else 0,
        # Reprise R5 : le montant présenté est tracé aussi pour un refus.
        credits_presentes=estimation.credits_estimes,
        texte_version=estimation.texte_version,
    )
    db.add(ligne)
    if decision == DECISION_REFUSE:
        annoncer_repli(db, execution_id, (
            f"Opus refusé par l'utilisateur au lancement : Marcus est servi par "
            f"{estimation.modele_repli}."))
    return ligne


def verifier_pour_appel(db: Session, user_id: Optional[int], execution_id: Optional[int],
                        model_name: str, estimation_appel: int) -> Tuple[bool, str, str]:
    """(autorisé, code, motif). Autorisé seulement sur consentement accepté, de
    ce compte, pour cette exécution, et dans le montant accepté. Le code est
    stable (il sert à n'annoncer un même repli qu'une fois) ; le motif porte
    les chiffres."""
    if not execution_id:
        return False, "sans_execution", "aucune exécution : le consentement Opus se donne par exécution"
    ligne = (db.query(ConsentementOpus)
             .filter_by(execution_id=execution_id, model_name=model_name).first())
    if ligne is None:
        return False, "sans_consentement", "aucun consentement enregistré pour cette exécution"
    if ligne.user_id != user_id:
        return False, "autre_compte", "consentement donné par un autre compte"
    if ligne.decision != DECISION_ACCEPTE:
        return False, "refuse", "Opus refusé par l'utilisateur"
    cumul = (db.query(func.coalesce(func.sum(CreditTransaction.credits_consumed), 0))
             .filter(CreditTransaction.execution_id == execution_id,
                     CreditTransaction.model_used == model_name,
                     CreditTransaction.transaction_type.in_(
                         (TRANSACTION_TYPE_CHARGE, TRANSACTION_TYPE_RESERVATION)))
             .scalar()) or 0
    if cumul + estimation_appel > ligne.credits_estimes:
        return False, "plafond", (f"montant accepté atteint ({int(cumul)} crédits consommés + "
                       f"{estimation_appel} estimés > {ligne.credits_estimes} acceptés)")
    return True, "accepte", "consentement accepté"
