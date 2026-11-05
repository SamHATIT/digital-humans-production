"""Garde serveur unique des ecritures BUILD et Salesforce.

Vague 1 / file A — BILL-05 (audit Astra L701) et SEC-08 (L159).

**Pourquoi un module, et pas une porte de plus sur chaque route.** BILL-05 ne
dit pas « il manque une verification » mais « les portes sont posees chemin
par chemin, et les chemins secondaires n'en portent aucune » : validation de
porte, retry, upload, snapshot SDS, analyse de CR, worker. Une garde par
route reproduit le defaut au premier chemin ajoute. Les appelants passent
donc tous par les trois fonctions ci-dessous.

**Deux questions distinctes**, volontairement separees :

1. *Ce compte a-t-il droit au BUILD ?* — `ensure_build_write_allowed` (objet
   utilisateur, cote route) et `ensure_build_write_allowed_for_execution`
   (identifiant, cote worker, qui ne recoit pas d'objet `User` et doit
   revalider au demarrage du job).
2. *Cette plateforme a-t-elle le droit d'ecrire dans une org Salesforce ?* —
   `ensure_salesforce_write_allowed`, posee au **point d'ecriture** des
   services, pas dans les routes. Perimetre decide par Sam le 15/09 : Free +
   Pro ouverts, BUILD ferme — donc *aucune* ecriture Salesforce.

**Refus par defaut.** Un profil illisible, un palier inconnu, une execution
introuvable ou un reglage absent donnent un refus, jamais un passage (regle
« jamais de repli silencieux » : `require_feature` et
`BuildEnabledMiddleware` ont tous deux ete inertes en production).

**Un alias n'est pas une preuve.** SEC-08 : `org_est_productive` declarait
une org non productive des qu'elle voyait `--` dans une chaine fournie par
l'appelant. Ici, la seule preuve acceptee est un resultat d'org **obtenu
d'une source Salesforce authentifiee** (`sf org display --json`), portant un
`isSandbox` booleen vrai et un identifiant d'org. Le jour ou les ecritures
Team rouvriront, c'est cette preuve qu'il faudra fournir.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import Any, Mapping, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Code stable, cite par les tests et les journaux. Ne pas le reformuler sans
# mettre a jour les appelants : c'est lui qui distingue « refuse par la garde »
# d'un echec quelconque du CLI.
CODE_REFUS_ECRITURE_SALESFORCE = "salesforce_writes_disabled"

#: Capacite requise pour toute ecriture BUILD (cf. app/models/subscription.py).
CAPACITE_BUILD = "build_phase"

#: Reglage d'ouverture des ecritures Salesforce. Absent = ferme.
VARIABLE_ECRITURES_SALESFORCE = "DH_SALESFORCE_WRITES_ENABLED"

#: Orgs de test declarees par l'exploitant (05/11/2026), par IDENTIFIANT d'org
#: Salesforce (15 ou 18 caracteres, separes par des virgules). Pour les
#: Developer Edition, qui repondent `IsSandbox = false` comme une production :
#: le CRM de Sam en est une. Seul l'identifiant LU dans l'org fait foi — jamais
#: un alias ou un nom d'utilisateur. Absent = aucune org de test declaree.
VARIABLE_ORGS_DE_TEST = "DH_SALESFORCE_TEST_ORG_IDS"

#: Requete de preuve : lue dans l'org elle-meme, avec ses identifiants.
REQUETE_PREUVE_ORG = "SELECT Id, IsSandbox FROM Organization"


class SalesforceWritesDisabled(RuntimeError):
    """Les ecritures Salesforce sont fermees sur cette plateforme."""


class SalesforceOrgNonVerifiee(RuntimeError):
    """L'org visee n'est pas prouvee non productive par une source authentifiee."""


# ---------------------------------------------------------------------------
# 1. Droit du compte au BUILD
# ---------------------------------------------------------------------------

def ensure_build_write_allowed(user: Any) -> None:
    """Leve 401/403 si `user` ne peut pas declencher une ecriture BUILD.

    Delegue a `ensure_feature`, source unique de la frontiere payante, pour
    ne pas creer une seconde definition du droit qui pourrait diverger.
    """
    from app.utils.feature_access import ensure_feature

    ensure_feature(user, CAPACITE_BUILD)


def ensure_build_write_allowed_for_execution(execution_id: int, db: Session) -> None:
    """Meme controle, a partir d'une execution — chemin du worker.

    Le job ARQ ne porte que des identifiants : il relit le proprietaire en
    base au demarrage, car le palier a pu changer entre l'enfilage et
    l'execution (« un ancien Team retrograde Pro relance un BUILD en
    attente », BILL-05). Une execution ou un proprietaire introuvable est un
    refus : un job orphelin ne s'execute pas « par defaut ».
    """
    from app.models.execution import Execution
    from app.models.project import Project
    from app.models.user import User

    proprietaire = (
        db.query(User)
        .join(Project, Project.user_id == User.id)
        .join(Execution, Execution.project_id == Project.id)
        .filter(Execution.id == execution_id)
        .first()
    )
    if proprietaire is None:
        logger.error(
            "[BuildGuard] execution %s : proprietaire introuvable — ecriture BUILD refusee",
            execution_id,
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "build_owner_unknown",
                "message": (
                    f"Execution {execution_id} : proprietaire introuvable, "
                    f"ecriture BUILD refusee."
                ),
            },
        )
    ensure_build_write_allowed(proprietaire)


# ---------------------------------------------------------------------------
# 2. Droit de la plateforme a ecrire dans une org Salesforce
# ---------------------------------------------------------------------------

def _ecritures_salesforce_activees() -> bool:
    """Vrai seulement sur une valeur d'activation explicite et reconnue.

    Une valeur non reconnue n'est pas « peut-etre oui » : elle est refusee,
    et elle est journalisee pour que l'exploitant voie sa faute de frappe.
    """
    brut = os.environ.get(VARIABLE_ECRITURES_SALESFORCE)
    if brut is None or brut == "":
        return False
    valeur = brut.strip().lower()
    if valeur in {"1", "true", "yes", "on"}:
        return True
    if valeur in {"0", "false", "no", "off"}:
        return False
    logger.error(
        "[BuildGuard] %s=%r n'est pas une valeur reconnue — ecritures Salesforce "
        "maintenues fermees",
        VARIABLE_ECRITURES_SALESFORCE, brut,
    )
    return False


def _orgs_de_test_declarees() -> frozenset:
    """Identifiants (15 premiers caracteres) des orgs de test declarees."""
    brut = os.environ.get(VARIABLE_ORGS_DE_TEST) or ""
    ids = set()
    for morceau in brut.split(","):
        m = morceau.strip()
        if not m:
            continue
        if len(m) not in (15, 18) or not m.startswith("00D"):
            logger.error(
                "[BuildGuard] %s : %r n'est pas un identifiant d'org — ignore",
                VARIABLE_ORGS_DE_TEST, m,
            )
            continue
        ids.add(m[:15])
    return frozenset(ids)


def _preuve_est_non_productive(preuve: Optional[Mapping[str, Any]]) -> bool:
    """Une org n'est non productive que si une source authentifiee le dit.

    Deux preuves acceptees, toutes deux rattachees a un identifiant d'org :
    - `isSandbox` **booleen** vrai (une chaine « true » ou « peut-etre » ne
      prouve rien : elle peut venir d'un formulaire) ;
    - ou l'identifiant figure dans les orgs de test declarees par
      l'exploitant (`DH_SALESFORCE_TEST_ORG_IDS`), pour les Developer Edition.
    """
    if not isinstance(preuve, Mapping):
        return False
    identifiant = preuve.get("organizationId") or preuve.get("orgId") or preuve.get("id")
    if not isinstance(identifiant, str) or not identifiant:
        return False
    if preuve.get("isSandbox") is True:
        return True
    return identifiant[:15] in _orgs_de_test_declarees()


def obtenir_preuve_org(cible: str, executer=subprocess.run) -> Optional[dict]:
    """Lit dans l'org elle-meme son identifiant et `IsSandbox`.

    C'est la « source Salesforce authentifiee » qu'exigeait SEC-08 : la
    requete passe par les identifiants du CLI pour `cible`. Echec (CLI absent,
    org inconnue, reponse illisible) = None, journalise : la garde refusera.
    """
    try:
        sortie = executer(
            ["sf", "data", "query", "--target-org", cible,
             "--query", REQUETE_PREUVE_ORG, "--json"],
            capture_output=True, text=True, timeout=60,
        )
        donnees = json.loads(sortie.stdout or "{}")
        enregistrements = (donnees.get("result") or {}).get("records") or []
        if len(enregistrements) != 1:
            raise ValueError(
                f"reponse sans enregistrement Organization unique "
                f"({donnees.get('message') or donnees.get('name') or 'vide'})"
            )
        org = enregistrements[0]
        return {"organizationId": org.get("Id"), "isSandbox": org.get("IsSandbox")}
    except Exception as e:  # noqa: BLE001 — toute panne = pas de preuve
        logger.error("[BuildGuard] preuve d'org impossible pour %r : %s", cible, e)
        return None


def ensure_salesforce_write_allowed(
    cible: str,
    preuve_org: Optional[Mapping[str, Any]] = None,
) -> None:
    """Leve avant toute ecriture dans une org Salesforce.

    Deux verrous successifs :

    1. Les ecritures sont fermees pour l'ouverture Free + Pro
       (`SalesforceWritesDisabled`). C'est le cas nominal au 16/09.
    2. Si elles sont rouvertes, l'org doit etre prouvee non productive par un
       resultat d'org authentifie (`SalesforceOrgNonVerifiee`). L'alias ou le
       nom d'utilisateur fournis par l'appelant ne valent pas preuve — c'est
       exactement ce que SEC-08 reprochait a `org_est_productive`.
    """
    if not _ecritures_salesforce_activees():
        logger.warning(
            "[BuildGuard] ecriture Salesforce refusee vers %r (%s)",
            cible, CODE_REFUS_ECRITURE_SALESFORCE,
        )
        raise SalesforceWritesDisabled(
            f"{CODE_REFUS_ECRITURE_SALESFORCE} : les ecritures Salesforce sont "
            f"desactivees sur cette plateforme (ouverture Free + Pro, BUILD "
            f"ferme — decision du 15/09). Cible refusee : {cible!r}. Pour les "
            f"rouvrir : {VARIABLE_ECRITURES_SALESFORCE}=true, et fournir une "
            f"preuve d'org non productive."
        )

    if preuve_org is None:
        preuve_org = obtenir_preuve_org(cible)

    if not _preuve_est_non_productive(preuve_org):
        raise SalesforceOrgNonVerifiee(
            f"Deploiement refuse vers {cible!r} : aucune preuve authentifiee que "
            f"cette org n'est pas une production. Un alias ou un nom "
            f"d'utilisateur ne sont pas des preuves (SEC-08) ; fournissez le "
            f"resultat de `sf org display --json` avec isSandbox=true et "
            f"l'identifiant de l'org."
        )
