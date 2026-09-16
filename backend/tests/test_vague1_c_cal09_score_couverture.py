"""
VAGUE 1 / FILE C — CAL-09 : « 85,0 % exactement sur les quatre executions
revisees ». Plafond, valeur assignee, ou mesure ?

La mission demande de LIRE le code et de trancher, pas de supposer. Reponse
mesuree : **ni plafond ni valeur assignee**. Le score est une moyenne ponderee,
calculee ligne 261-267 de `agents/roles/salesforce_research_analyst.py` :

    overall = obj*0.20 + auto*0.15 + ui*0.10 + trace*0.55
    return {"overall_score": round(overall, 1), ...}

Aucune borne, aucune constante 85. La preuve est ci-dessous : le meme code rend
92,5 / 10,0 / 0 sur d'autres entrees.

Pourquoi 85,0 revient alors a l'identique ? Parce que trois des quatre
composantes **saturent** :

- `ui_coverage` vaut 100 par defaut quand les UC ne listent aucun composant
  d'interface (`... if uc_ui else 100`) ;
- `obj_coverage` et `uc_coverage` atteignent 100 des que les objets et la
  tracabilite correspondent ;
- `auto_coverage` tombe a 0 des que les automatisations nommees par les UC ne
  se retrouvent pas **a l'identique** dans la conception.

    0.20*100 + 0.15*0 + 0.10*100 + 0.55*100 = 85.0

85,0 n'est donc pas une valeur inventee : c'est la signature d'une seule
composante a zero, et cette composante tombe a zero pour la meme raison que
CAL-08 — un rapprochement par NOM exact, pas par sens. Corriger CAL-08 fera
bouger ce chiffre ; il n'y a rien a corriger dans le calcul lui-meme.
"""
import pytest

from agents.roles.salesforce_research_analyst import (
    generate_coverage_report_programmatic,
)

UC = [
    {"id": "UC-1", "sf_objects": ["Account"], "sf_automation": ["FlowFactureAuto"]},
    {"id": "UC-2", "sf_objects": ["Account"], "sf_automation": ["FlowRelance"]},
]


def _conception(automatisations=None, objets=("Account",), tracabilite=("UC-1", "UC-2")):
    return {
        "data_model": {
            "standard_objects": [{"api_name": o} for o in objets],
            "custom_objects": [],
        },
        "automation_design": {
            "flows": [{"name": n} for n in (automatisations or [])],
            "apex_triggers": [],
        },
        "uc_traceability": {uc: "x" for uc in tracabilite},
    }


def test_le_score_n_est_pas_plafonne_a_85():
    """S'il y avait un plafond, aucune entree ne pourrait le depasser."""
    rapport = generate_coverage_report_programmatic(
        _conception(automatisations=["FlowFactureAuto"]), UC
    )
    assert rapport["overall_score"] > 85.0, (
        f"aucune entree ne depasse 85 : ce serait un plafond. "
        f"Obtenu : {rapport['overall_score']}"
    )


def test_le_score_n_est_pas_une_valeur_assignee():
    """S'il etait assigne, il ne varierait pas avec l'entree."""
    faible = generate_coverage_report_programmatic(
        _conception(objets=(), tracabilite=()), UC
    )["overall_score"]
    vide = generate_coverage_report_programmatic({}, [])["overall_score"]
    assert faible != 85.0 and vide != 85.0, (
        f"le score ne bouge pas avec l'entree : {faible} / {vide}"
    )


def test_85_est_la_signature_d_une_seule_composante_a_zero():
    """Le cas des quatre executions du 15/09, reproduit : les automatisations
    nommees par les UC ne se retrouvent pas a l'identique dans la conception."""
    rapport = generate_coverage_report_programmatic(_conception(), UC)
    assert rapport["overall_score"] == pytest.approx(85.0)
    categories = {k: v["score"] for k, v in rapport["by_category"].items()}
    assert categories["automation"] == pytest.approx(0.0)
    assert categories["data_model"] == pytest.approx(100.0)
    assert categories["uc_traceability"] == pytest.approx(100.0)
    assert categories["ui_components"] == pytest.approx(100)


def test_la_composante_automation_tombe_sur_un_ecart_de_nom():
    """Le lien avec CAL-08 : c'est un rapprochement par nom exact.

    La conception porte le meme flux sous un nom different — un humain dirait
    que le besoin est couvert, le calcul dit 0.
    """
    renomme = generate_coverage_report_programmatic(
        _conception(automatisations=["Flow_Facture_Auto", "Flow_Relance"]), UC
    )
    assert renomme["by_category"]["automation"]["score"] == pytest.approx(0.0), (
        "si ce score n'est plus nul, CAL-08 a ete corrige et ce test doit "
        "etre reecrit — pas supprime"
    )
