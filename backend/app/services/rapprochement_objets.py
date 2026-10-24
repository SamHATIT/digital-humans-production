"""Rapprochement sémantique des objets — CAL-08 (vague 2 / file C).

Constat (15/09, exécutions 172-175) : la revue de couverture d'Emma comptait
comme « manque critique » des objets présents dans la conception sous un autre
nom (``credit_note__c`` pour un avoir, ``mouvement_points__c``,
``ligne_retour_ecommerce__c``…) et classait « Flow » en objet manquant. Le
calcul comparait les noms en minuscules, à l'identique.

Ce module rapproche une référence (nom cité par un cas d'usage) d'un objet de
la conception, avant de déclarer un manque :

1. **métadonnée** : Flow, Report, Queue, Dashboard, List View… ne sont pas des
   objets ; ils ne sont jamais des objets manquants (``non_objects``). Un nom
   qui finit par ``__c`` est un objet, quoi qu'il contienne ;
2. **identité** : même nom d'API (casse ignorée) ;
3. **normalisation** : préfixe d'espace de noms et suffixe ``__c`` retirés,
   accents, séparateurs et casse ignorés, pluriel simple ;
4. **sens** : mots traduits vers un vocabulaire commun (lexique FR → EN ci-
   dessous, ``avoir`` → ``credit note``), comparés au nom d'API ET au libellé
   de l'objet. Égalité des ensembles de mots ; inclusion seulement si les mots
   en plus sont des qualifiants (canal, marque : ``ligne retour ecommerce`` ⊇
   ``return line``). Tout autre mot en plus change l'objet (reprise R1) :
   ``Order`` n'est pas ``Order_Line__c``, ``ServiceContract`` n'est pas
   ``Contract``, ``Maintenance`` n'est pas ``Maintenance_Activity__c`` — un
   manque à relire vaut mieux qu'un vrai manque masqué.

Ce n'est pas une ressemblance d'orthographe : ``Contrat__c`` n'est pas
``Contact``. Un rapprochement est restitué comme **renommage**, distinct d'un
manque, pour être relu.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

#: Types de métadonnées Salesforce cités par les UC comme s'ils étaient des
#: objets. Comparés sur le nom normalisé (mots séparés par des espaces).
_METADONNEES = (
    "flow", "flows", "record triggered flow", "screen flow", "autolaunched flow",
    "scheduled flow", "omni channel flow", "report", "reports", "report type",
    "dashboard", "dashboards", "queue", "queues", "list view", "list views",
    "email template", "email templates", "approval process", "process builder",
    "workflow", "workflow rule", "validation rule", "permission set",
    "permission set group", "profile", "record type", "page layout",
    "lightning page", "lightning record page", "apex class", "apex trigger",
    "trigger", "lwc", "lightning web component", "assignment rule",
    "escalation rule", "auto response rule", "omni channel routing",
    "routing configuration", "service channel", "presence status",
    "named credential", "custom metadata type", "custom setting", "platform event",
)
#: Suffixes qui font d'un nom propre une métadonnée (``Case_Escalation_Flow``,
#: ``Sales Report``, ``Support Queue``, ``Lead Assignment Rule``). Comparés en
#: fin de nom, mot à mot, au singulier ; un ``__c`` reste un objet.
#: Reprise D1 (revue passe 2) : R1 n'avait gardé que « flow » et des
#: métadonnées nommées redevenaient des objets manquants. « rule » et
#: « template » SEULS restent exclus : Price Rule, Product Rule, Quote
#: Template sont des objets (CPQ). Seules des expressions de type connu.
_SUFFIXES_METADONNEE = (
    ("flow",), ("report",), ("report", "type"), ("dashboard",), ("queue",),
    ("list", "view"), ("email", "template"), ("assignment", "rule"),
    ("escalation", "rule"), ("auto", "response", "rule"), ("validation", "rule"),
    ("workflow", "rule"), ("approval", "process"), ("permission", "set"),
    ("page", "layout"), ("record", "type"),
)

#: Lexique de rapprochement : mot (sans accent, minuscule) → mots communs.
_LEXIQUE: Dict[str, Tuple[str, ...]] = {
    "avoir": ("credit", "note"), "avoirs": ("credit", "note"),
    "memo": ("note",), "facture": ("invoice",), "commande": ("order",),
    "ligne": ("line",), "item": ("line",), "items": ("line",),
    "retour": ("return",), "mouvement": ("transaction",), "movement": ("transaction",),
    "point": ("point",), "points": ("point",), "fidelite": ("loyalty",),
    "actif": ("asset",), "actifs": ("asset",), "compte": ("account",),
    "contrat": ("contract",), "produit": ("product",), "devis": ("quote",),
    "campagne": ("campaign",), "piste": ("lead",), "tache": ("task",),
    "evenement": ("event",), "fournisseur": ("supplier",), "vendor": ("supplier",),
    "livraison": ("delivery",), "expedition": ("shipment",), "paiement": ("payment",),
    "abonnement": ("subscription",), "magasin": ("store",), "boutique": ("store",),
    "shop": ("store",), "entrepot": ("warehouse",), "remboursement": ("refund",),
    "reclamation": ("claim",), "sinistre": ("claim",), "demande": ("request",),
    "rendez": ("appointment",), "vous": (), "vehicule": ("vehicle",),
    "conducteur": ("driver",), "chauffeur": ("driver",), "client": ("customer",),
    "adresse": ("address",), "equipement": ("equipment",), "emplacement": ("location",),
    "projet": ("project",), "ressource": ("resource",), "competence": ("skill",),
    "employe": ("employee",), "agence": ("branch",), "programme": ("program",),
    "membre": ("member",), "niveau": ("tier",), "recompense": ("reward",),
    "canal": ("channel",), "panier": ("cart",), "prix": ("price",),
    "remise": ("discount",), "garantie": ("warranty",), "echeance": ("installment",),
    "compteur": ("meter",), "releve": ("reading",), "tarif": ("rate",),
    "intervention": ("work", "order"), "maintenance": ("maintenance",),
    "activite": ("activity",), "visite": ("visit",), "stock": ("inventory",),
    "e": (), "commerce": ("ecommerce",),
}

#: Mots sans valeur de rapprochement.
_VIDES = frozenset({"de", "du", "des", "la", "le", "les", "d", "l", "of", "the",
                    "a", "an", "et", "and", "c", "custom", "object", "objet", "record"})


def _sans_accent(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte)
                   if not unicodedata.combining(c))


def _mots_bruts(nom: str) -> List[str]:
    """Mots d'un nom d'API ou d'un libellé : espace de noms et suffixe retirés,
    camelCase et séparateurs découpés, accents et casse ignorés."""
    n = _sans_accent(nom or "").strip()
    n = re.sub(r"__(c|mdt|e|x|b|kav|r)$", "", n, flags=re.IGNORECASE)
    if n.count("__") == 1:                       # ns__Objet
        n = n.split("__", 1)[1]
    n = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", n)
    return [m for m in re.split(r"[^A-Za-z0-9]+", n.lower()) if m]


def _singulier(mot: str) -> str:
    return mot[:-1] if len(mot) > 3 and mot.endswith("s") and not mot.endswith("ss") else mot


def cle_normalisee(nom: str) -> str:
    return " ".join(_singulier(m) for m in _mots_bruts(nom))


def concepts(nom: str) -> frozenset:
    out = set()
    for mot in _mots_bruts(nom):
        if mot in _VIDES:
            continue
        traduits = _LEXIQUE.get(mot)
        if traduits is None:
            traduits = _LEXIQUE.get(_singulier(mot), (_singulier(mot),))
        out.update(traduits)
    return frozenset(out)


def est_metadonnee(nom: str) -> bool:
    """Flow, Report, Queue… ne sont pas des objets. Un ``__c`` en est un."""
    if re.search(r"__c$", (nom or "").strip(), flags=re.IGNORECASE):
        return False
    cle = " ".join(_mots_bruts(nom))
    if cle in _METADONNEES:
        return True
    mots = tuple(_singulier(m) for m in cle.split())
    return any(len(mots) > len(suf) and mots[-len(suf):] == suf
               for suf in _SUFFIXES_METADONNEE)


#: Mots qui ne désignent pas un autre objet : un canal, une marque, un
#: préfixe technique. Seuls mots tolérés en plus d'un côté (reprise R1).
_QUALIFIANTS = frozenset({
    "ecommerce", "online", "web", "digital", "sf", "salesforce", "dh", "data", "info",
    "information",
})


def _concepts_compatibles(a: frozenset, b: frozenset) -> bool:
    """Égalité des concepts ; ou inclusion dont les mots en plus sont tous des
    qualifiants (``ligne retour ecommerce`` ⊇ ``return line``).

    Reprise R1 (revue 1) : l'inclusion était acceptée dès que le plus petit
    ensemble avait deux mots, ou pour un mot si le mot en plus ne désignait pas
    un « objet enfant ». Un objet voisin ou enfant présent faisait alors passer
    l'objet demandé pour renommé : ``Credit_Note_Line__c`` ↔ ``Avoir__c``,
    ``Loyalty_Program__c`` ↔ ``Loyalty_Program_Member__c``, ``ServiceContract``
    ↔ ``Contract``, ``Opportunity`` ↔ ``Opportunity_Product__c``. Un mot de
    plus change l'objet ; on préfère montrer un manque à relire que masquer un
    vrai manque.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    petit, grand = (a, b) if len(a) <= len(b) else (b, a)
    return petit <= grand and (grand - petit) <= _QUALIFIANTS


def rapprocher(reference: str, objets: Sequence[Tuple[str, Optional[str]]]) -> Optional[Tuple[str, str]]:
    """(objet de la conception, méthode) ou None. ``objets`` : (api_name, libellé)."""
    ref = (reference or "").strip()
    if not ref:
        return None
    for api, _ in objets:
        if api and api.strip().lower() == ref.lower():
            return api.strip().lower(), "identite"
    cle = cle_normalisee(ref)
    for api, libelle in objets:
        if api and (cle_normalisee(api) == cle or (libelle and cle_normalisee(libelle) == cle)):
            return api.strip().lower(), "normalisation"
    c_ref = concepts(ref)
    for api, libelle in objets:
        if not api:
            continue
        if _concepts_compatibles(c_ref, concepts(api)) or (
                libelle and _concepts_compatibles(c_ref, concepts(libelle))):
            return api.strip().lower(), "sens"
    return None


def classer_references(references: Iterable[str],
                       objets: Sequence[Tuple[str, Optional[str]]]) -> dict:
    """Répartit les références des UC : couvertes, renommées, métadonnées,
    manquantes. Toutes en minuscules, triées."""
    couverts, renommes, non_objets, manquants = set(), [], set(), set()
    for ref in sorted({(r or "").strip() for r in references if (r or "").strip()},
                      key=str.lower):
        if est_metadonnee(ref):
            non_objets.add(ref.lower())
            continue
        trouve = rapprocher(ref, objets)
        if trouve is None:
            manquants.add(ref.lower())
        elif trouve[1] == "identite":
            couverts.add(ref.lower())
        else:
            renommes.append({"reference": ref.lower(), "objet": trouve[0], "methode": trouve[1]})
    return {
        "couverts": sorted(couverts),
        "renommes": renommes,
        "non_objets": sorted(non_objets),
        "manquants": sorted(manquants),
    }
