"""Generation XML de Raj — defauts trouves par le BUILD de l'execution 185
(15/11/2026, projet 122, org sandbox-build).

La validation a blanc de Salesforce a refuse la phase 1 pour des defauts du
generateur, pas du plan : formule non echappee, objets standards suffixes en
`__c`, type de metadonnees `__mdt__c`, champs d'activite sur `Activity__c`,
enregistrements de metadonnees et onglet abandonnes sans trace. Les 53
operations du plan rejouees apres correctif passent la validation a blanc
de Salesforce (53/53, 0 erreur).
"""
import glob
import xml.dom.minidom
from pathlib import Path

import pytest

from app.services.sf_admin_service import SFAdminService, normaliser_objet


@pytest.fixture
def paquet(tmp_path):
    def _generer(ops):
        svc = SFAdminService("sandbox-build")
        svc._generate_metadata_files(ops, str(tmp_path))
        return svc, tmp_path / "force-app" / "main" / "default"
    return _generer


def _tous_bien_formes(racine):
    fichiers = glob.glob(str(racine) + "/**/*.xml", recursive=True)
    for f in fichiers:
        xml.dom.minidom.parse(f)   # leve si mal forme
    return fichiers


class TestNormaliserObjet:
    @pytest.mark.parametrize("nom,attendu", [
        ("Lead", "Lead"), ("Lead__c", "Lead"), ("Opportunity", "Opportunity"),
        ("Market_Signal", "Market_Signal__c"), ("Market_Signal__c", "Market_Signal__c"),
        ("Lead_Scoring_Rule__mdt", "Lead_Scoring_Rule__mdt"),
        ("Evenement__e", "Evenement__e"),
        ("Task", "Activity"), ("Event", "Activity"), ("Activity", "Activity"),
    ])
    def test_nom_api(self, nom, attendu):
        assert normaliser_objet(nom) == attendu


class TestReglesDeValidation:
    def test_formule_echappee_et_objet_standard_conserve(self, paquet):
        svc, racine = paquet([{
            "order": 1, "type": "create_validation_rule", "object": "Lead",
            "api_name": "Score_Entre_0_Et_100", "active": True,
            "formula": "AND(NOT(ISBLANK(Score__c)), OR(Score__c < 0, Score__c > 100))",
            "error_message": "Le score doit être compris entre 0 & 100.",
            "error_field": "Score__c",
        }])
        f = racine / "objects" / "Lead" / "validationRules" / "Score_Entre_0_Et_100.validationRule-meta.xml"
        assert f.exists(), "la regle doit vivre sous Lead, pas Lead__c"
        doc = xml.dom.minidom.parse(str(f))
        formule = doc.getElementsByTagName("errorConditionFormula")[0].firstChild.data
        assert formule == "AND(NOT(ISBLANK(Score__c)), OR(Score__c < 0, Score__c > 100))"
        assert doc.getElementsByTagName("errorDisplayField")[0].firstChild.data == "Score__c"
        assert not (racine / "objects" / "Lead__c").exists()


class TestMetadonneesPersonnalisees:
    OPS = [
        {"order": 1, "type": "create_object", "api_name": "Lead_Scoring_Rule__mdt",
         "label": "Lead Scoring Rule", "plural_label": "Lead Scoring Rules",
         "object_kind": "CustomMetadataType", "visibility": "Public",
         "description": "Règles <configurables>"},
        {"order": 2, "type": "create_field", "object": "Lead_Scoring_Rule__mdt",
         "api_name": "Criterion_Field__c", "label": "Criterion Field",
         "field_type": "Text", "length": 80, "required": True},
        {"order": 3, "type": "create_custom_metadata_record", "object": "Lead_Scoring_Rule__mdt",
         "developer_name": "Has_Phone", "label": "Has Phone",
         "values": {"Criterion_Field__c": "Phone", "Criterion_Value__c": None,
                    "Score_Points__c": 5, "Is_Active__c": True}},
    ]

    def test_type_sans_suffixe_c_et_xml_dedie(self, paquet):
        svc, racine = paquet(self.OPS)
        obj = racine / "objects" / "Lead_Scoring_Rule__mdt" / "Lead_Scoring_Rule__mdt.object-meta.xml"
        assert obj.exists()
        contenu = obj.read_text()
        assert "<visibility>Public</visibility>" in contenu
        assert "sharingModel" not in contenu and "nameField" not in contenu
        champ = (racine / "objects" / "Lead_Scoring_Rule__mdt" / "fields" / "Criterion_Field__c.field-meta.xml").read_text()
        assert "<fieldManageability>DeveloperControlled</fieldManageability>" in champ
        _tous_bien_formes(racine)

    def test_enregistrement_genere_avec_types(self, paquet):
        svc, racine = paquet(self.OPS)
        f = racine / "customMetadata" / "Lead_Scoring_Rule.Has_Phone.md-meta.xml"
        assert f.exists(), "l'enregistrement etait abandonne sans trace"
        contenu = f.read_text()
        assert '<value xsi:type="xsd:string">Phone</value>' in contenu
        assert '<value xsi:nil="true"/>' in contenu
        assert '<value xsi:type="xsd:double">5</value>' in contenu
        assert '<value xsi:type="xsd:boolean">true</value>' in contenu
        _tous_bien_formes(racine)


class TestChampsEtOnglets:
    def test_champ_d_activite_sur_activity(self, paquet):
        svc, racine = paquet([{"order": 1, "type": "create_field", "object": "Activity",
                               "api_name": "Automation_Source__c", "label": "Automation Source",
                               "field_type": "Text", "length": 100}])
        assert (racine / "objects" / "Activity" / "fields" / "Automation_Source__c.field-meta.xml").exists()

    def test_textes_libres_echappes(self, paquet):
        svc, racine = paquet([{"order": 1, "type": "create_field", "object": "Lead",
                               "api_name": "Source__c", "label": "Source & canal",
                               "field_type": "Picklist", "description": "Valeur < 100 & > 0",
                               "values": [{"api_name": "R&D", "label": "R&D <interne>"}]}])
        _tous_bien_formes(racine)

    def test_onglet_genere(self, paquet):
        svc, racine = paquet([{"order": 1, "type": "create_tab", "object": "Market_Signal__c",
                               "api_name": "Market_Signal__c", "motif": "Custom9: Lightning"}])
        assert "<customObject>true</customObject>" in (racine / "tabs" / "Market_Signal__c.tab-meta.xml").read_text()

    def test_operation_inconnue_tracee(self, paquet):
        svc, _ = paquet([{"order": 1, "type": "create_quelque_chose", "api_name": "X"}])
        assert svc.operations_ignorees == [{"type": "create_quelque_chose", "name": "X"}]
