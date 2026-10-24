"""Disponibilite des fournisseurs LLM : alerte admin, message client.

Vague 2 / file B — GL-25 et « fournisseur local injoignable » (backlog
go-live §2 et §5).

- 17/09 : solde Anthropic epuise ; un echange Pro rendait au client un
  HTTP 502 portant le message brut du fournisseur (« Your credit balance is
  too low… »). Personne n'etait prevenu.
- 15/09 : solde OpenAI (embeddings) epuise, panne silencieuse (GL-10).
- 30/09 : tunnel vers le Spark tombe (redemarrage d'une box) : le Free
  (`gpu_nemotron`) ne repondait plus.

Regles (Sam, 15/09) : l'exploitant le sait dans la minute ; le client lit
« service momentanement indisponible », jamais la cause interne ; aucun
repli silencieux vers un modele payant (le routeur n'en fait pas : voir
`fallback_chain` du profil, verifie par les tests de la file B).

Une alerte part a la PREMIERE indisponibilite constatee d'un fournisseur et
a son RETOUR ; une panne qui dure ne produit pas d'autre alerte. L'etat est
celui du processus (le backend et le worker alertent chacun une fois).

Ce module ne connait pas de seuil de solde : ni Anthropic ni OpenAI
n'exposent le solde prepaye a une cle d'API standard (je ne l'ai pas
verifie au-dela de la documentation connue ; voir le rapport). La panne est
constatee a la premiere requete refusee pour solde.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

CAUSE_SOLDE = "solde_epuise"
CAUSE_INJOIGNABLE = "injoignable"
CAUSE_MODELE_ABSENT = "modele_absent"

#: Ce que lit le client. Pas de nom de fournisseur, pas de cause interne.
MESSAGE_CLIENT = (
    "Le service est momentanément indisponible. Notre équipe a été prévenue ; "
    "merci de réessayer dans quelques minutes."
)

_MOTIFS_SOLDE = (
    "credit balance is too low",       # Anthropic, 400 (mesure du 17/09)
    "insufficient_quota",              # OpenAI, 429
    "exceeded your current quota",     # OpenAI, 429 (message)
    "credit_balance_exhausted",        # libelle du 15/09 (GL-10)
    "billing_hard_limit_reached",      # OpenAI
)
_MOTIFS_INJOIGNABLE = (
    "connecterror",
    "connecttimeout",
    "connection refused",
    "errno 111",
    "all connection attempts failed",
    "name or service not known",
    "failed to establish a new connection",
    "apiconnectionerror",
    "connection error",
    "remoteprotocolerror",
    "server disconnected",
    "readtimeout",
    "writetimeout",
    "pooltimeout",
    "readerror",
    "timed out",
)

_LIBELLES = {
    CAUSE_SOLDE: "solde épuisé",
    CAUSE_INJOIGNABLE: "injoignable",
    CAUSE_MODELE_ABSENT: "modèle absent",
}


def nom_fournisseur(provider_str: Optional[str]) -> str:
    return (provider_str or "inconnu").split("/", 1)[0] or "inconnu"


def est_local(provider_str: Optional[str]) -> bool:
    nom = nom_fournisseur(provider_str)
    return nom == "local" or nom.startswith("gpu_")


def classer_erreur(erreur: Optional[str], fournisseur: Optional[str] = None) -> Optional[str]:
    """Cause de disponibilite reconnue dans un message d'erreur, ou None.

    Reprise 3 de la revue (vague 2 / file B) : le routeur (`_call_gpu_local`,
    file C) ne transmet que `str(e)[:200]`, sans le nom de la classe. Or
    httpx rend une chaine VIDE pour `ReadTimeout` / `ConnectTimeout` et
    certaines coupures : un Spark fige derriere un tunnel ouvert donnait
    `error=''`, classe None, donc 503 sans alerte. Pour un fournisseur LOCAL,
    une erreur vide ou un HTTP 502/503/504 du relais est donc une
    indisponibilite. Le diff propose a la file C (rapport §6) ajoute le nom de
    la classe au message ; les deux formes sont reconnues.
    """
    texte = (erreur or "").lower()
    if any(m in texte for m in _MOTIFS_SOLDE):
        return CAUSE_SOLDE
    if any(m in texte for m in _MOTIFS_INJOIGNABLE):
        return CAUSE_INJOIGNABLE
    if est_local(fournisseur):
        if not texte.strip():
            return CAUSE_INJOIGNABLE
        if re.match(r"\s*http 50[234]\b", texte):
            return CAUSE_INJOIGNABLE
    return None


# ---------------------------------------------------------------------------
# Etat par fournisseur : panne -> alerte une fois ; retour -> alerte une fois
# ---------------------------------------------------------------------------

#: Reprise 2 de la revue : un envoi refuse par Telegram n'est plus tenu pour
#: fait ; il est retente a l'occurrence suivante, au plus une fois par
#: DELAI_NOUVELLE_TENTATIVE_S (pas de rafale pendant une panne qui dure).
DELAI_NOUVELLE_TENTATIVE_S = 60.0
_horloge: Callable[[], float] = time.monotonic

_verrou = threading.Lock()
_pannes: Dict[str, Dict] = {}
#: Retours constates dont l'annonce a ete refusee : retentes au succes suivant.
_retours_en_attente: Dict[str, Dict] = {}


def reinitialiser() -> None:
    """Oublie les pannes connues (tests)."""
    with _verrou:
        _pannes.clear()
        _retours_en_attente.clear()


def etat() -> Dict[str, Dict]:
    with _verrou:
        return {k: dict(v) for k, v in _pannes.items()}


def _alerter(sujet: str, corps: str) -> bool:
    """Rend True s'il n'y a plus rien a faire : Telegram a accepte, ou Telegram
    n'est pas configure (le journal et le tableau de bord sont alors les seuls
    canaux, deja ecrits). False = Telegram configure mais refus : a retenter."""
    from app.services import admin_alert_service

    if admin_alert_service.alerter_admin(sujet, corps, categorie="fournisseur_llm"):
        return True
    return not admin_alert_service.telegram_configure()


def signaler_panne(fournisseur: str, cause: str, detail: str, *, origine: str) -> bool:
    """Rend True si une alerte a ete tentee (nouvelle panne, ou nouvel essai
    d'une alerte refusee)."""
    maintenant = time.time()
    instant = _horloge()
    with _verrou:
        _retours_en_attente.pop(fournisseur, None)
        connue = _pannes.get(fournisseur)
        if connue is not None and connue["cause"] == cause:
            connue["occurrences"] += 1
            if connue["alertee"] or instant - connue["tentative"] < DELAI_NOUVELLE_TENTATIVE_S:
                return False
            connue["tentative"] = instant
            etat_panne = connue
        else:
            etat_panne = {"cause": cause, "depuis": maintenant, "occurrences": 1,
                          "alertee": False, "tentative": instant}
            _pannes[fournisseur] = etat_panne
    libelle = _LIBELLES.get(cause, cause)
    consigne = {
        CAUSE_SOLDE: "Recharger le compte du fournisseur. Les clients des paliers servis "
                     "par ce fournisseur recoivent « service momentanement indisponible ».",
        CAUSE_INJOIGNABLE: "Verifier le service et le tunnel. Aucun repli vers un autre "
                           "fournisseur n'est fait : le client recoit « service "
                           "momentanement indisponible ».",
        CAUSE_MODELE_ABSENT: "Le serveur repond mais ne sert pas le modele attendu : "
                             "verifier le model_id du YAML et le service.",
    }.get(cause, "")
    accepte = _alerter(
        f"Fournisseur LLM {fournisseur} : {libelle}",
        f"Constate par {origine}.\nCause : {detail[:1500]}\n{consigne}",
    )
    with _verrou:
        etat_panne["alertee"] = accepte
    return True


def signaler_retablissement(fournisseur: str, *, origine: str) -> bool:
    """Rend True si une annonce de retour a ete tentee (retour constate, ou
    nouvel essai d'une annonce refusee)."""
    instant = _horloge()
    with _verrou:
        connue = _pannes.pop(fournisseur, None)
        if connue is not None:
            retour = {"panne": connue, "fin": time.time(), "tentative": instant}
        else:
            retour = _retours_en_attente.get(fournisseur)
            if retour is None or instant - retour["tentative"] < DELAI_NOUVELLE_TENTATIVE_S:
                return False
            retour["tentative"] = instant
    panne = retour["panne"]
    duree = int(retour["fin"] - panne["depuis"])
    accepte = _alerter(
        f"Fournisseur LLM {fournisseur} : rétabli",
        f"Constate par {origine}. Panne ({_LIBELLES.get(panne['cause'], panne['cause'])}) "
        f"pendant {duree} s, {panne['occurrences']} occurrence(s)."
        + ("" if panne.get("alertee") else " (l'alerte de panne n'avait pas pu partir)"),
    )
    with _verrou:
        if accepte:
            _retours_en_attente.pop(fournisseur, None)
        else:
            _retours_en_attente[fournisseur] = retour
    return True


def signaler_echec_appel(provider_str: Optional[str], erreur: str, *, origine: str) -> Optional[str]:
    """Un appel a echoue : alerte si la cause est une indisponibilite connue.
    Rend la cause reconnue (ou None)."""
    cause = classer_erreur(erreur, provider_str)
    if cause is not None:
        signaler_panne(nom_fournisseur(provider_str), cause, erreur, origine=origine)
    return cause


def signaler_succes_appel(provider_str: Optional[str], *, origine: str) -> None:
    if provider_str:
        signaler_retablissement(nom_fournisseur(provider_str), origine=origine)


# ---------------------------------------------------------------------------
# Sonde periodique des fournisseurs LOCAUX effectivement servis
# ---------------------------------------------------------------------------

def _chaines_fournisseur(valeur) -> List[str]:
    if isinstance(valeur, str):
        return [valeur] if "/" in valeur else []
    if isinstance(valeur, dict):
        out: List[str] = []
        for cle, v in valeur.items():
            if isinstance(cle, str) and "/" in cle:
                out.append(cle)
            out.extend(_chaines_fournisseur(v))
        return out
    if isinstance(valeur, (list, tuple)):
        out = []
        for v in valeur:
            out.extend(_chaines_fournisseur(v))
        return out
    return []


def fournisseurs_locaux_servis(routeur) -> List[str]:
    """Fournisseurs LOCAUX cites par le profil actif (defauts, surcharges de
    palier, chaine de repli). Les fournisseurs declares mais non routes
    (calibration) ne sont ni sondes ni alertes."""
    from app.services.llm_router_service import ProviderType

    profil = (routeur.config.get("profiles") or {}).get(routeur.profile) or {}
    noms = []
    for chaine in _chaines_fournisseur(profil):
        nom = nom_fournisseur(chaine)
        p = routeur.providers.get(nom)
        if p and p.get("type") == ProviderType.LOCAL and nom not in noms:
            noms.append(nom)
    return noms


def sonder_fournisseurs_locaux_servis(
    routeur=None, *, get: Optional[Callable] = None, delai_s: float = 5.0
) -> Dict[str, Optional[str]]:
    """GET <base_url>/models sur chaque fournisseur local servi. Alerte a la
    premiere panne et au retour (via signaler_panne / signaler_retablissement).
    Rend {fournisseur: cause ou None}."""
    if routeur is None:
        from app.services.llm_router_service import get_llm_router

        routeur = get_llm_router()
    if get is None:
        import httpx

        get = httpx.get
    resultats: Dict[str, Optional[str]] = {}
    for nom in fournisseurs_locaux_servis(routeur):
        p = routeur.providers[nom]
        base = (p.get("base_url") or "").rstrip("/")
        attendus = [m.get("model_id") for m in (p.get("models") or {}).values()]
        try:
            r = get(f"{base}/models", timeout=delai_s)
            r.raise_for_status()
            servis = [m.get("id") for m in r.json().get("data", [])]
        except Exception as e:
            detail = f"{base} injoignable ({type(e).__name__}: {e})"
            signaler_panne(nom, CAUSE_INJOIGNABLE, detail, origine="sonde periodique")
            resultats[nom] = CAUSE_INJOIGNABLE
            continue
        manquants = [m for m in attendus if m not in servis]
        if manquants:
            detail = f"{base}/models ne sert pas {manquants} (servis : {servis})"
            signaler_panne(nom, CAUSE_MODELE_ABSENT, detail, origine="sonde periodique")
            resultats[nom] = CAUSE_MODELE_ABSENT
            continue
        signaler_retablissement(nom, origine="sonde periodique")
        resultats[nom] = None
    return resultats
