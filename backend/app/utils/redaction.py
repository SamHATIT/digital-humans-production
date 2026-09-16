"""Expurgation des secrets dans les sorties — SEC-15 (audit Astra L269).

Trois sorties fuyaient : la reponse et le journal des erreurs de validation
(corps complet de la requete), le journal de `GitService` (URL authentifiee),
et le resultat complet de `sf org display --json` stocke comme livrable puis
envoye dans un prompt.

Ce module ne contient que des primitives sans etat, utilisables partout :

* `expurger` — masque des secrets connus **et** les motifs qui trahissent un
  secret meme quand l'appelant a oublie de le nommer (`https://x@hote`,
  `Bearer ...`, cles `sk-ant-`/`ghp_`/`glpat-`). L'appelant honnete oublie ;
  le motif, non.
* `filtrer_resultat_org_salesforce` — **liste blanche** des champs d'org
  utiles a l'analyse. Un champ inconnu est retire : c'est ce qui distingue
  ce filtre d'une liste noire, qui laisserait passer le champ ajoute par une
  future version du CLI.
* `expurger_arguments` — pour les lignes de commande journalisees.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

MASQUE = "***"

#: Champs d'org Salesforce conserves. `sf org display --json` rend aussi
#: `accessToken`, `refreshToken`, `clientId`, `clientSecret`, `password`,
#: `sfdxAuthUrl` — aucun n'a d'utilite pour une analyse d'architecture.
CHAMPS_ORG_AUTORISES = (
    "id",
    "orgId",
    "username",
    "alias",
    "instanceUrl",
    "loginUrl",
    "instanceApiVersion",
    "apiVersion",
    "isSandbox",
    "isScratch",
    "isDevHub",
    "status",
    "expirationDate",
    "createdDate",
    "edition",
    "orgName",
    "trailExpirationDate",
    "devHubUsername",
    "connectedStatus",
)

_MOTIFS = (
    # https://<secret>@hote  et  https://user:<secret>@hote
    re.compile(r"(?P<avant>[a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s@]+@"),
    re.compile(r"(?i)(?P<avant>\bbearer\s+)[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)(?P<avant>\b(?:token|api[_-]?key|secret|password|passwd)\b\s*[=:]\s*)\S+"),
    re.compile(r"(?P<avant>)\bsk-ant-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?P<avant>)\bgh[pousr]_[A-Za-z0-9]{8,}"),
    re.compile(r"(?P<avant>)\bglpat-[A-Za-z0-9_-]{8,}"),
    re.compile(r"(?P<avant>)\bxox[baprs]-[A-Za-z0-9-]{8,}"),
)


def expurger(texte: Any, secrets: Optional[Iterable[Optional[str]]] = None) -> str:
    """Rend `texte` publiable : secrets connus masques, motifs masques."""
    sortie = texte if isinstance(texte, str) else str(texte)

    for secret in secrets or ():
        if secret and len(str(secret)) >= 4:
            sortie = sortie.replace(str(secret), MASQUE)

    for motif in _MOTIFS:
        sortie = motif.sub(lambda m: f"{m.group('avant')}{MASQUE}", sortie)

    # L'URL authentifiee perd son `@` avec le premier motif : on le remet
    # pour que la ligne reste lisible (https://***@github.com/…).
    sortie = re.sub(
        r"(?P<sch>[a-zA-Z][a-zA-Z0-9+.-]*://)" + re.escape(MASQUE) + r"(?![@])",
        lambda m: f"{m.group('sch')}{MASQUE}@",
        sortie,
    )
    return sortie


def expurger_arguments(args: Sequence[Any], secrets: Optional[Iterable[Optional[str]]] = None) -> List[str]:
    """Version liste, pour journaliser une ligne de commande."""
    return [expurger(a, secrets) for a in args]


def filtrer_resultat_org_salesforce(brut: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Ne garde que les champs d'org utiles — liste blanche.

    Le resultat de `sf org display --json` etait copie integralement dans un
    livrable, donc dans un prompt : `accessToken` compris.
    """
    if not isinstance(brut, Mapping):
        return {}
    return {cle: brut[cle] for cle in CHAMPS_ORG_AUTORISES if cle in brut}
