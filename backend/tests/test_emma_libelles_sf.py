"""Emma tolere les champs Salesforce rendus en objet par Olivia (15/11/2026, smoke exec 183)."""
from agents.roles.salesforce_research_analyst import _libelle_sf


def test_chaine_inchangee():
    assert _libelle_sf("Lead.Score__c") == "Lead.Score__c"


def test_objet_avec_champ_devient_objet_point_champ():
    assert _libelle_sf({"object": "Lead", "field": "Score_Qualification__c", "type": "Number"}) == "Lead.Score_Qualification__c"


def test_objet_partiel_ou_inconnu_ne_leve_jamais():
    assert _libelle_sf({"name": "Signal_Marche__c"}) == "Signal_Marche__c"
    assert _libelle_sf({"autre": 1})
    assert _libelle_sf(42) == "42"
