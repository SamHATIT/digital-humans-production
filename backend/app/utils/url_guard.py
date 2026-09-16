"""Bornage des destinations reseau sortantes — SEC-09 (audit Astra L173).

Le wizard acceptait une URL d'instance Salesforce arbitraire et y envoyait un
bearer : un faux jeton suffisait a faire emettre au serveur une requete vers
la destination de son choix (metadonnees d'instance cloud, services internes),
et le chemin OAuth y envoyait un vrai jeton. Git acceptait des URLs et des
protocoles non bornes.

**La defense ne peut pas etre lexicale.** Refuser la chaine « 127.0.0.1 » ne
sert a rien : `interne.acme.test` peut resoudre en 10.x, et un nom peut
changer de resolution. On valide donc le schema, le port, **et chaque adresse
IP resolue**. Un nom irresoluble est refuse, jamais tente « au cas ou »
(regle « jamais de repli silencieux »).

Ce module ne fait pas de requete : il decide si une requete a le droit de
partir. Les appelants l'invoquent avant leur transport.

**Limite dite.** La validation precede la connexion : entre les deux, la
resolution peut changer (DNS rebinding). Le correctif complet demande une
connexion a l'IP validee, ou un proxy sortant en liste blanche — hors
perimetre de cette vague, et signale comme tel dans le rapport.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Iterable, List, Sequence
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DestinationInterdite(ValueError):
    """La destination demandee n'a pas le droit d'etre jointe."""


#: Seuls schemas acceptes pour un appel sortant applicatif.
SCHEMES_AUTORISES = ("https",)

#: Ports acceptes. 443 seul en pratique ; 8443 tolere pour une instance
#: derriere un frontal non standard.
PORTS_AUTORISES = (443, 8443)

#: Fournisseurs Git supportes (Astra : « limiter les fournisseurs/protocoles »).
HOTES_GIT_AUTORISES = (
    "github.com",
    "www.github.com",
    "gitlab.com",
    "bitbucket.org",
)


def _resoudre(hote: str) -> List[str]:
    """Toutes les adresses d'un hote. Isolee pour etre simulable en test :
    le bac a sable de la vague 0 n'a pas de reseau sortant."""
    infos = socket.getaddrinfo(hote, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


def _adresse_est_publique(brut: str) -> bool:
    try:
        adresse = ipaddress.ip_address(brut)
    except ValueError:
        return False
    if isinstance(adresse, ipaddress.IPv6Address) and adresse.ipv4_mapped:
        adresse = adresse.ipv4_mapped
    return not (
        adresse.is_private
        or adresse.is_loopback
        or adresse.is_link_local
        or adresse.is_multicast
        or adresse.is_reserved
        or adresse.is_unspecified
    )


def valider_url_sortante(
    url: str,
    *,
    hotes_autorises: Sequence[str] | None = None,
    schemes: Iterable[str] = SCHEMES_AUTORISES,
) -> str:
    """Rend l'URL si elle est joignable sans risque, leve sinon."""
    if not url or not isinstance(url, str):
        raise DestinationInterdite("Destination absente.")

    decoupee = urlparse(url.strip())
    scheme = (decoupee.scheme or "").lower()
    if scheme not in tuple(schemes):
        raise DestinationInterdite(
            f"Destination refusee : schema {scheme or '(aucun)'!r} non autorise "
            f"(attendus : {', '.join(schemes)})."
        )

    hote = (decoupee.hostname or "").strip().lower()
    if not hote:
        raise DestinationInterdite("Destination refusee : hote absent de l'URL.")

    if hotes_autorises is not None and hote not in tuple(hotes_autorises):
        raise DestinationInterdite(
            f"Destination refusee : {hote!r} n'est pas un hote supporte "
            f"({', '.join(hotes_autorises)})."
        )

    try:
        port = decoupee.port or 443
    except ValueError as erreur:  # port non numerique
        raise DestinationInterdite(f"Destination refusee : port illisible ({erreur}).")
    if port not in PORTS_AUTORISES:
        raise DestinationInterdite(
            f"Destination refusee : port {port} hors liste ({PORTS_AUTORISES})."
        )

    # Un litteral IP est juge directement ; un nom est resolu.
    try:
        ipaddress.ip_address(hote.strip("[]"))
        adresses = [hote.strip("[]")]
    except ValueError:
        try:
            adresses = _resoudre(hote)
        except OSError as erreur:
            raise DestinationInterdite(
                f"Destination refusee : {hote!r} ne resout pas ({erreur})."
            ) from erreur

    if not adresses:
        raise DestinationInterdite(f"Destination refusee : {hote!r} ne resout vers aucune adresse.")

    for adresse in adresses:
        if not _adresse_est_publique(adresse):
            logger.warning(
                "[UrlGuard] destination refusee : %s resout vers %s", hote, adresse
            )
            raise DestinationInterdite(
                f"Destination refusee : {hote!r} resout vers une adresse non "
                f"publique ({adresse})."
            )

    return url


def valider_url_git(url: str) -> str:
    """Meme controle, restreint aux fournisseurs Git supportes en https."""
    return valider_url_sortante(url, hotes_autorises=HOTES_GIT_AUTORISES)


#: Environnement a poser autour d'un appel a `git` : interdit a git de
#: basculer sur un protocole non prevu (Astra : « poser GIT_ALLOW_PROTOCOL »).
ENV_GIT_PROTOCOLES = {"GIT_ALLOW_PROTOCOL": "https", "GIT_TERMINAL_PROMPT": "0"}
