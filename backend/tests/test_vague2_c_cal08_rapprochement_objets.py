"""
Vague 2 / file C — CAL-08 : Emma et les variantes terminologiques.

Constat du backlog (15/09, exécutions 172 à 175) : la revue de couverture
d'Emma compte comme « manque critique » des objets PRÉSENTS dans la conception
sous un autre nom (`credit_note__c` pour un avoir, `mouvement_points__c`,
`ligne_retour_ecommerce__c`…) ; et « objet Flow manquant » — un Flow n'est pas
un objet. Lu le 24/10 : `calculate_coverage_score` compare les noms en
minuscules, à l'identique (`missing = uc_objects - sd_objects`), et le filtre
SF_INFRA_OBJECTS n'est appliqué qu'au score, pas à la liste des manques.

Le rejeu du brief 117 (Omnichannel Loop, exécution 175) demande un appel réel
à Emma (et Marcus/Olivia en amont) ou les livrables de la base de production,
interdite : aucun des deux ici. La preuve porte sur un jeu de cas CONSTRUIT
d'après les exemples cités par le backlog, avec contrôles négatifs : un vrai
manque doit rester un manque.
"""
from __future__ import annotations

import pytest

from agents.roles.salesforce_research_analyst import (
    calculate_coverage_score,
    generate_coverage_report_programmatic,
)


def _conception(standard=(), custom=()):
    return {
        "data_model": {
            "standard_objects": [{"api_name": a, "label": l} for a, l in standard],
            "custom_objects": [{"api_name": a, "label": l} for a, l in custom],
        },
        "automation_design": {"flows": [], "apex_triggers": []},
        "uc_traceability": {},
    }


def _uc(*objets):
    return [{"id": "UC-1", "sf_objects": list(objets)}]


def _manques(conception, objets):
    return sorted(calculate_coverage_score(conception, _uc(*objets))
                  ["by_category"]["data_model"]["missing"])


# ── Variantes terminologiques : présentes, donc pas des manques ──────────

VARIANTES = [
    # (référence dans les UC, objet de la conception (api, libellé))
    ("credit_note__c", ("Avoir__c", "Avoir")),
    ("Avoir__c", ("Credit_Note__c", "Credit Note")),
    ("mouvement_points__c", ("Loyalty_Point_Transaction__c", "Loyalty Point Transaction")),
    ("ligne_retour_ecommerce__c", ("Return_Line__c", "Return Line")),
    ("actif__c", ("Asset", "Asset")),
    ("Maintenance__c", ("Maintenance_Activity__c", "Maintenance Activity")),
]


@pytest.mark.parametrize("reference,objet", VARIANTES, ids=[v[0] for v in VARIANTES])
def test_une_variante_terminologique_n_est_pas_un_manque(reference, objet):
    standard = [objet] if not objet[0].endswith("__c") else []
    custom = [objet] if objet[0].endswith("__c") else []
    assert _manques(_conception(standard, custom), [reference]) == []


def test_un_renommage_est_dit_comme_tel():
    """« Distinguer manque et renommage » : le rapprochement est restitué."""
    dm = calculate_coverage_score(
        _conception(custom=[("Avoir__c", "Avoir")]), _uc("credit_note__c")
    )["by_category"]["data_model"]
    assert dm["renamed"] == [{"reference": "credit_note__c", "objet": "avoir__c",
                              "methode": dm["renamed"][0]["methode"]}]
    assert dm["score"] == pytest.approx(100.0)


# ── Métadonnées : jamais des objets manquants ────────────────────────────

METADONNEES = ["Flow", "Case_Escalation_Flow", "Report", "Queue", "Dashboard",
               "Omni-Channel Flow", "List View", "Email Template", "Approval Process",
               "Record-Triggered Flow"]


@pytest.mark.parametrize("nom", METADONNEES)
def test_une_metadonnee_n_est_jamais_un_objet_manquant(nom):
    rapport = generate_coverage_report_programmatic(_conception(), _uc(nom))
    assert rapport["by_category"]["data_model"]["missing"] == []
    assert nom.lower() in rapport["by_category"]["data_model"]["non_objects"]
    assert not [g for g in rapport["critical_gaps"] if g["category"] == "DATA_MODEL"]


# ── Contrôles négatifs : un vrai manque reste un manque ──────────────────


@pytest.mark.parametrize("reference,objet", [
    ("Order", ("Order_Line__c", "Order Line")),      # l'en-tête n'est pas la ligne
    ("Facture__c", ("Avoir__c", "Avoir")),           # une facture n'est pas un avoir
    ("Contrat__c", ("Contact", "Contact")),          # proximité d'orthographe ≠ sens
    ("Reservation__c", ("Account", "Account")),
    ("Workflow_Step__c", ("Account", "Account")),    # objet custom, pas une métadonnée
], ids=["en-tete-vs-ligne", "facture-vs-avoir", "contrat-vs-contact", "absent", "custom-workflow"])
def test_controle_negatif_un_vrai_manque_reste_un_manque(reference, objet):
    standard = [objet] if not objet[0].endswith("__c") else []
    custom = [objet] if objet[0].endswith("__c") else []
    assert _manques(_conception(standard, custom), [reference]) == [reference.lower()]


def test_jeu_construit_compte_avant_apres():
    """Le comptage demandé par la mission, sur le jeu construit : 6 variantes +
    10 métadonnées + 5 vrais manques. Attendu : 5 manques, tous vrais."""
    conception = _conception(
        standard=[("Asset", "Asset"), ("Account", "Account"), ("Contact", "Contact")],
        custom=[o for _, o in VARIANTES if o[0].endswith("__c")]
        + [("Order_Line__c", "Order Line")],
    )
    references = [r for r, _ in VARIANTES] + METADONNEES + [
        "Order", "Facture__c", "Contrat__c", "Reservation__c", "Workflow_Step__c"]
    manques = _manques(conception, references)
    assert manques == sorted(["order", "facture__c", "contrat__c", "reservation__c",
                              "workflow_step__c"])
