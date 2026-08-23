"""
VAGUE 3 — §4 : selection des experts SDS par Marcus.

Ce qui existait : `pm_orchestrator_service_v2.py:2108` filtrait `ALL_SDS_EXPERTS`
sur `selected_agents`, une colonne JSON de `executions` — donc **un choix fait
au lancement, avant que quiconque ait analyse le projet**. Vide, les quatre
experts tournent. En pratique, les quatre tournent a chaque fois : le mecanisme
existait mais etait alimente par le mauvais bout. Un dispositif inerte de plus,
meme famille que `BuildEnabledMiddleware` avant la vague 1.

Ce qui est decide (arbitrages Sam) :

  1. **Marcus decide**, a l'issue de la phase 3, au vu de l'architecture qu'il
     vient de produire. Principe directeur/specialiste.
  2. **Elena (`qa`) est inamovible** — la relecture qualite systematique est un
     argument de vente, pas une etape optionnelle. Le perimetre de decision de
     Marcus porte sur `data`, `trainer` et `devops`.
  3. **La selection est persistee**, et relue par une reprise en `phase4`.
  4. **Un expert ecarte est justifie dans le SDS**, pas absent.
  5. **Un choix explicite de l'utilisateur reste prioritaire.**

Cas d'usage donne par Sam : Aisha en migration de donnees sur un projet sans
reprise d'existant. Elle tourne, produit une specification vide de sens, et
consomme des credits sur un livrable que personne ne lira.
"""
import pytest

from app.services.expert_selection import (
    ALL_SDS_EXPERTS,
    MANDATORY_EXPERTS,
    select_sds_experts,
)


# --------------------------------------------------------------------------
# Les invariants
# --------------------------------------------------------------------------

def test_elena_est_inamovible():
    """Arbitrage Sam : Marcus ne peut pas ecarter la QA."""
    assert "qa" in MANDATORY_EXPERTS
    assert MANDATORY_EXPERTS <= set(ALL_SDS_EXPERTS)


def test_marcus_ne_decide_que_de_trois_experts():
    """Son perimetre : data, trainer, devops."""
    assert set(ALL_SDS_EXPERTS) - MANDATORY_EXPERTS == {"data", "trainer", "devops"}


@pytest.mark.parametrize("artefacts", [{}, {"WBS": {}}, {"ARCHITECTURE": {}}])
def test_elena_survit_a_tout(artefacts):
    """Meme sans aucun signal, meme sur un projet vide."""
    choix = select_sds_experts(artefacts)
    assert "qa" in choix["selected"]
    assert "qa" not in choix["excluded"]


# --------------------------------------------------------------------------
# Le cas d'usage de Sam : Aisha sans migration de donnees
# --------------------------------------------------------------------------

def _wbs(*intitules):
    return {
        "WBS": {
            "content": {
                "phases": [
                    {"name": "Phase 1", "tasks": [{"name": n} for n in intitules]}
                ]
            }
        }
    }


def test_aisha_est_ecartee_sans_migration_de_donnees():
    """Le cas nomme : elle tournait, produisait une specification vide de sens,
    et consommait des credits sur un livrable que personne ne lira."""
    choix = select_sds_experts(_wbs("Creer le trigger Account", "Ecran LWC"))
    assert "data" in choix["excluded"]
    assert "data" not in choix["selected"]


def test_aisha_est_retenue_quand_il_y_a_de_la_migration():
    """Controle positif : le mecanisme doit ecarter, pas exclure par defaut."""
    choix = select_sds_experts(
        _wbs("Migration des donnees Compte depuis l'ancien CRM", "Trigger")
    )
    assert "data" in choix["selected"]
    assert "data" not in choix["excluded"]


@pytest.mark.parametrize(
    "intitule",
    [
        "Reprise de l'existant Contacts",
        "Chargement initial via Bulk API",
        "Data migration from legacy system",
        "Import des historiques",
    ],
)
def test_les_signaux_de_migration_sont_reconnus(intitule):
    choix = select_sds_experts(_wbs(intitule))
    assert "data" in choix["selected"], f"{intitule!r} n'a pas ete reconnu"


# --------------------------------------------------------------------------
# Chaque exclusion porte sa justification (contrainte 3)
# --------------------------------------------------------------------------

def test_chaque_expert_ecarte_a_une_raison_redigee():
    """« Une absence justifiee est une couverture explicite. Un silence ne dit
    rien et ressemble a un oubli. »"""
    choix = select_sds_experts(_wbs("Trigger Account"))
    assert choix["excluded"], "le cas doit ecarter au moins un expert"
    for agent, raison in choix["excluded"].items():
        assert isinstance(raison, str) and len(raison) > 20, (
            f"{agent} est ecarte sans justification redigee : {raison!r}"
        )


def test_la_justification_suit_la_formulation_de_sam():
    """Formulation attendue : « Aisha : non intervenue, pas de migration de
    donnees dans le perimetre de la demande. »"""
    choix = select_sds_experts(_wbs("Trigger Account"))
    raison = choix["excluded"]["data"]
    assert "non intervenue" in raison.lower()
    assert "migration" in raison.lower()


def test_les_justifications_nomment_l_agent_pas_son_identifiant():
    """Le SDS est lu par un client : « Aisha », pas « data »."""
    choix = select_sds_experts(_wbs("Trigger Account"))
    assert "Aisha" in choix["excluded"]["data"]


# --------------------------------------------------------------------------
# Contrainte 5 — le choix explicite de l'utilisateur prime
# --------------------------------------------------------------------------

def test_un_choix_utilisateur_prime_sur_marcus():
    """« Si `selected_agents` est renseigne au lancement, il fait autorite. »"""
    choix = select_sds_experts(
        _wbs("Trigger Account"),  # aucun signal de migration
        selected_agents=["pm", "ba", "architect", "data"],
    )
    assert "data" in choix["selected"], "l'utilisateur a demande Aisha"
    assert choix["decided_by"] == "user"


def test_un_choix_utilisateur_ne_peut_pas_ecarter_elena():
    """Les deux contraintes se croisent : l'utilisateur prime, sauf sur Elena."""
    choix = select_sds_experts(
        _wbs("Migration des donnees"),
        selected_agents=["pm", "ba", "architect", "data"],
    )
    assert "qa" in choix["selected"]


def test_sans_choix_utilisateur_c_est_marcus():
    choix = select_sds_experts(_wbs("Trigger Account"))
    assert choix["decided_by"] == "architect"


def test_un_selected_agents_sans_expert_laisse_la_main_a_marcus():
    """`selected_agents=["pm","ba"]` n'est pas un choix d'experts : c'est une
    selection d'agents de base. L'interpreter comme « aucun expert » ecarterait
    Elena, que l'arbitrage rend inamovible."""
    choix = select_sds_experts(
        _wbs("Migration des donnees"), selected_agents=["pm", "ba", "architect"]
    )
    assert "qa" in choix["selected"]
    assert choix["decided_by"] == "architect"


# --------------------------------------------------------------------------
# La decision est complete et lisible
# --------------------------------------------------------------------------

def test_tout_expert_est_soit_retenu_soit_justifie():
    """Aucun expert ne doit disparaitre sans trace — c'est tout l'objet de la
    contrainte 3."""
    for artefacts in (_wbs("Trigger"), _wbs("Migration des donnees"), {}):
        choix = select_sds_experts(artefacts)
        couverts = set(choix["selected"]) | set(choix["excluded"])
        assert couverts == set(ALL_SDS_EXPERTS), (
            f"experts sans decision : {set(ALL_SDS_EXPERTS) - couverts}"
        )
