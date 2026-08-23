"""
Selection des experts SDS par Marcus.

VAGUE 3 / §4 — arbitrages Sam du 23 aout 2026.

**Ce qui existait.** `pm_orchestrator_service_v2` filtrait `ALL_SDS_EXPERTS` sur
`execution.selected_agents`, une colonne JSON renseignee **au lancement** — donc
avant que quiconque ait analyse le projet. Vide, les quatre experts tournaient.
En pratique elle etait toujours vide : les quatre tournaient a chaque fois. Le
mecanisme de selection existait, mais il etait alimente par le mauvais bout.
Un dispositif inerte de plus, meme famille que `BuildEnabledMiddleware` et
`require_feature` avant la vague 1 : present, jamais reellement exerce.

**Ce qui est decide.** C'est Marcus qui decide, a l'issue de la phase 3, au vu
de l'architecture qu'il vient de produire — principe directeur/specialiste : le
directeur decide et delegue.

Cas d'usage donne par Sam : Aisha en migration de donnees sur un projet sans
reprise d'existant. Elle tourne, produit une specification vide de sens, et
consomme des credits sur un livrable que personne ne lira.

**Comment Marcus decide.** Pas par un cinquieme appel LLM : par ce qu'il vient
d'ecrire. Le WBS et l'architecture sont ses livrables ; s'ils ne portent aucune
tache de migration, Marcus a deja decide qu'il n'y a pas de migration. La regle
est donc lue dans ses artefacts — deterministe, gratuite, sans nouveau mode de
panne, et verifiable ligne a ligne. Le jour ou l'on voudra un jugement plus fin
qu'un faisceau de mots-cles, c'est ici que se branchera l'appel dedie ; le
contrat de sortie ne changera pas.

**Ce que la selection n'est pas.** Elle ne remplace pas un choix explicite de
l'utilisateur : `selected_agents` renseigne au lancement fait autorite
(contrainte 4). Et elle ne peut pas ecarter Elena (contrainte 1) : la relecture
qualite systematique est un argument de vente de la solution, pas une etape
optionnelle.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional

#: Les quatre experts de la phase 4, dans l'ordre d'execution.
ALL_SDS_EXPERTS: List[str] = ["data", "trainer", "qa", "devops"]

#: Experts que Marcus ne peut pas ecarter (contrainte 1, arbitrage Sam).
MANDATORY_EXPERTS = frozenset({"qa"})

#: Noms d'agents tels qu'ils apparaissent dans le SDS, lu par un client.
AGENT_DISPLAY_NAMES = {
    "data": "Aisha",
    "trainer": "Lucas",
    "qa": "Elena",
    "devops": "Jordan",
}

#: Signaux qui justifient la presence de chaque expert, cherches dans les
#: artefacts de Marcus (WBS, architecture, ecarts).
#:
#: Volontairement larges : **le faux positif coute un livrable de trop, le faux
#: negatif coute un volet absent du SDS.** Les deux ne se valent pas — un volet
#: manquant se decouvre chez le client.
EXPERT_SIGNALS = {
    "data": (
        r"migration", r"\breprise\b", r"chargement initial", r"bulk\s*api",
        r"\bimport\b", r"\betl\b", r"data\s*loader", r"legacy", r"existant",
        r"historiqu", r"dataload", r"\bmigrat",
    ),
    "trainer": (
        r"formation", r"training", r"adoption", r"conduite du changement",
        r"change management", r"utilisateur final", r"end\s*user",
        r"documentation", r"onboarding", r"accompagnement",
    ),
    "devops": (
        r"deploiement", r"déploiement", r"deployment", r"\bci/?cd\b",
        r"pipeline", r"\bsandbox\b", r"release", r"livraison", r"environnement",
        r"\bsfdx\b", r"package", r"mise en production",
    ),
}

#: Justification rendue au client quand un expert est ecarte.
#: Formulation donnee par Sam :
#:   « Aisha : non intervenue, pas de migration de donnees dans le perimetre de
#:     la demande. »
EXCLUSION_REASONS = {
    "data": (
        "{nom} : non intervenue, pas de migration de donnees dans le perimetre "
        "de la demande."
    ),
    "trainer": (
        "{nom} : non intervenu, pas de volet formation ni de conduite du "
        "changement dans le perimetre de la demande."
    ),
    "devops": (
        "{nom} : non intervenu, pas de chaine de deploiement specifique dans le "
        "perimetre de la demande."
    ),
}


def _texte_des_artefacts(artifacts: Optional[Dict[str, Any]]) -> str:
    """Aplatit les artefacts de Marcus en un texte cherchable.

    On serialise plutot que de parcourir une structure : le WBS, l'architecture
    et les ecarts n'ont pas la meme forme d'une execution a l'autre, et un
    parcours typé raterait le signal des qu'un agent change la forme de sa
    sortie — panne silencieuse, exactement ce qu'on cherche a eviter.
    """
    if not artifacts:
        return ""
    interessants = ("WBS", "ARCHITECTURE", "GAP", "AS_IS")
    morceaux = []
    for cle in interessants:
        valeur = artifacts.get(cle)
        if valeur is None:
            continue
        try:
            morceaux.append(json.dumps(valeur, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            morceaux.append(str(valeur))
    return " ".join(morceaux).lower()


def _experts_demandes_par_l_utilisateur(
    selected_agents: Optional[Iterable[str]],
) -> Optional[List[str]]:
    """Les experts explicitement demandes au lancement, ou `None`.

    `selected_agents=["pm", "ba", "architect"]` n'est **pas** un choix
    d'experts : c'est une selection d'agents de base. L'interpreter comme
    « aucun expert » ecarterait Elena, que l'arbitrage rend inamovible, et
    reproduirait le defaut d'origine — un filtre alimente par le mauvais bout.
    """
    if not selected_agents:
        return None
    demandes = [a for a in ALL_SDS_EXPERTS if a in set(selected_agents)]
    return demandes or None


def select_sds_experts(
    artifacts: Optional[Dict[str, Any]] = None,
    selected_agents: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Decide quels experts SDS doivent tourner en phase 4.

    Args:
        artifacts: les artefacts de l'execution — le WBS, l'architecture et les
            ecarts produits par Marcus en phase 3 portent la decision.
        selected_agents: choix explicite de l'utilisateur au lancement. Prime
            sur Marcus (contrainte 4), sauf sur Elena (contrainte 1).

    Returns:
        dict avec :
          - ``selected``   : liste ordonnee des experts a executer ;
          - ``excluded``   : {agent: justification redigee, nominative} ;
          - ``decided_by`` : ``"user"`` ou ``"architect"`` ;
          - ``signals``    : {agent: signal trouve}, pour la tracabilite.

        Tout expert est soit dans `selected`, soit dans `excluded` : aucun ne
        disparait sans trace. C'est l'objet de la contrainte 3 — une absence
        justifiee est une couverture explicite, un silence ressemble a un oubli.
    """
    demandes = _experts_demandes_par_l_utilisateur(selected_agents)
    texte = _texte_des_artefacts(artifacts)

    retenus: List[str] = []
    signaux: Dict[str, str] = {}

    for agent in ALL_SDS_EXPERTS:
        if agent in MANDATORY_EXPERTS:
            retenus.append(agent)
            signaux[agent] = "expert obligatoire (relecture qualite systematique)"
            continue

        if demandes is not None:
            if agent in demandes:
                retenus.append(agent)
                signaux[agent] = "demande explicitement au lancement"
            continue

        motif = next(
            (m for m in EXPERT_SIGNALS.get(agent, ()) if re.search(m, texte)),
            None,
        )
        if motif:
            retenus.append(agent)
            signaux[agent] = f"signal trouve dans les artefacts de Marcus : {motif}"

    ecartes = {
        agent: EXCLUSION_REASONS[agent].format(nom=AGENT_DISPLAY_NAMES[agent])
        for agent in ALL_SDS_EXPERTS
        if agent not in retenus
    }

    return {
        "selected": retenus,
        "excluded": ecartes,
        "decided_by": "user" if demandes is not None else "architect",
        "signals": signaux,
    }
