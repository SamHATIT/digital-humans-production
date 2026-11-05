"""Marcus (as_is) doit recevoir les champs existants de l'org (05/11/2026).

Constat du smoke exec 181 sur sandbox-build : le JSON d'org commencait par le
catalogue `metadata_types` (~43 Ko) et etait coupe a 15 000 caracteres ; les
champs existants (`object_fields`) n'arrivaient jamais. Marcus a conclu
« aucun champ personnalise » alors que neuf existaient.
Jeu construit a l'image de la charge reelle (memes cles, memes tailles).
"""
import json

from agents.roles.salesforce_solution_architect import (
    LIMITE_METADONNEES_AS_IS,
    preparer_metadonnees_as_is,
)


def _charge_reelle():
    types = [{"directoryName": f"type{i}", "inFolder": False, "metaFile": False,
              "suffix": f"t{i}", "xmlName": f"Type{i}", "childXmlNames": ["A", "B"] * 10}
             for i in range(263)]
    champs_lead = [{"name": f"Std{i}", "type": "string", "label": f"Champ {i}"} for i in range(40)]
    champs_lead += [{"name": "Score_Qualification__c", "type": "double", "label": "Score"},
                    {"name": "Tier_Vise__c", "type": "picklist", "label": "Tier vise"}]
    return {"full_metadata": {
        "org_info": {"edition": "Developer Edition"},
        "metadata_types": types,
        "objects": [],
        "installed_packages": [],
        "limits": {},
        "object_fields": {"Lead": champs_lead},
    }}


def test_les_champs_existants_arrivent_a_marcus():
    charge = json.dumps(_charge_reelle())
    assert len(charge) > 40000          # le catalogue seul depassait l'ancienne coupe
    texte = preparer_metadonnees_as_is(charge)
    assert "Score_Qualification__c" in texte and "Tier_Vise__c" in texte


def test_le_catalogue_des_types_est_remplace_par_son_effectif():
    texte = preparer_metadonnees_as_is(json.dumps(_charge_reelle()))
    assert '"metadata_types_count": 263' in texte
    assert "childXmlNames" not in texte


def test_une_coupe_restante_est_dite_dans_le_texte(caplog):
    enorme = {"object_fields": {"Lead": [{"name": "X" * 100}] * 2000}}
    texte = preparer_metadonnees_as_is(json.dumps(enorme))
    assert "TRONQUE" in texte and "omis" in texte
    assert len(texte) < LIMITE_METADONNEES_AS_IS + 200
    assert "tronque" in caplog.text


def test_controle_negatif_un_texte_non_json_passe_tel_quel():
    assert preparer_metadonnees_as_is("pas du json") == "pas du json"


def test_le_prompt_as_is_rendu_contient_les_champs_existants():
    """Rouge avant le 05/11 : coupe a 15 000 caracteres dans le catalogue."""
    import agents.roles.salesforce_solution_architect as marcus
    prompt = marcus.get_as_is_prompt(json.dumps(_charge_reelle()))
    assert "Score_Qualification__c" in prompt
