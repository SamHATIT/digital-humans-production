"""
SF Admin Service - BUILD v2
Transforme les plans JSON Raj en fichiers XML et déploie via SFDX CLI.
"""
import logging
import json
import tempfile
import subprocess
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DeployResult:
    """Résultat d'un déploiement."""
    success: bool
    components_deployed: int = 0
    components_failed: int = 0
    errors: List[str] = field(default_factory=list)
    created_components: List[Dict[str, str]] = field(default_factory=list)
    deploy_id: Optional[str] = None


# ── FIX-SUFFIXE-002 (08/08/2026) ──────────────────────────────────────────
# Le code ajoutait `__c` a TOUT objet qui n'en avait pas, sans verifier s'il
# s'agissait d'un objet standard. Le WBS disait bien `Lead` ; le deploiement
# demandait `Lead__c`, et Salesforce repondait "Entity 'Lead__c' not found"
# pour chacun des 8 champs. Deux executions perdues le 08/08 avant de trouver.
#
# Les objets standard sont livres par la plateforme et ne portent JAMAIS le
# suffixe. Seuls les objets crees le portent — ainsi que tous les champs
# personnalises, y compris ceux poses sur un objet standard.
STANDARD_OBJECTS = {
    "account", "contact", "lead", "opportunity", "case", "user", "task",
    "event", "campaign", "campaignmember", "contract", "order", "orderitem",
    "product2", "pricebook2", "pricebookentry", "quote", "quotelineitem",
    "asset", "solution", "note", "attachment", "contentdocument",
    "contentversion", "group", "profile", "permissionset", "recordtype",
    "report", "dashboard", "opportunitylineitem", "opportunitycontactrole",
    "idea", "entitlement", "serviceappointment", "workorder", "individual",
}



# ══════════════════════════════════════════════════════════════════════════
# GARDE-PROD-001 (08/08/2026) — RÈGLE ABSOLUE, POSÉE PAR SAM
#
# Digital·Humans ne déploie JAMAIS en production. Jamais. La livraison
# s'arrête au sandbox ; c'est ensuite le client, ou un agent Agentforce chez
# lui, qui promeut vers la production. C'est une règle commerciale ET
# contractuelle : le tier Team s'arrête explicitement au sandbox.
#
# L'enjeu n'est pas théorique. Casser la production d'un grand compte, même
# une heure, coûterait infiniment plus que tout ce que la plateforme peut
# rapporter — et détruirait la confiance qui est notre seul actif.
#
# Ce garde-fou est une LISTE BLANCHE, pas une liste noire : on ne déploie que
# si l'org est identifiable comme non-productive. Dans le doute, on refuse.
# Une liste noire laisserait passer tout ce qu'on n'aurait pas prévu.
# ══════════════════════════════════════════════════════════════════════════

MARQUEURS_NON_PRODUCTION = (
    ".sandbox.my.salesforce.com",      # sandbox nommé
    "--",                              # suffixe de sandbox dans le nom d'utilisateur
    ".develop.my.salesforce.com",      # org de développement
    "-dev-ed.",                        # Developer Edition
    ".scratch.my.salesforce.com",      # org éphémère
    "test.salesforce.com",             # point d'entrée des sandbox
    "orgfarm-",                        # orgs de démonstration Salesforce
)


def org_est_productive(cible: str, instance_url: str = "") -> bool:
    """Vrai si la cible ressemble à une PRODUCTION.

    Liste blanche : tout ce qui ne porte aucun marqueur de non-production est
    traité comme une production, donc refusé. Dans le doute, on refuse.
    """
    empreinte = f"{cible or ''} {instance_url or ''}".lower()
    for marqueur in MARQUEURS_NON_PRODUCTION:
        if marqueur in empreinte:
            return False
    return True


# ── FIX-ACTIVITY-001 (08/08/2026) ─────────────────────────────────────────
# Task et Event partagent leurs champs personnalises via l'objet conteneur
# Activity : un champ deploye sur Activity apparait sur les deux. Le deployer
# directement sur Task echoue avec "Enumeration ou ID de l'entite : valeur
# incorrecte pour le champ de liste de selection restreinte : Task".
ACTIVITY_CONTAINER = {"task", "event"}


def normaliser_objet(nom: str) -> str:
    """Renvoie l'API name correct d'un objet Salesforce.

    Ajoute `__c` uniquement si l'objet est PERSONNALISE. Un objet standard
    perd le suffixe s'il l'a recu a tort en amont.
    """
    if not nom:
        return nom
    base = nom[:-3] if nom.endswith("__c") else nom
    if base.lower() in ACTIVITY_CONTAINER:
        return "Activity"   # les champs de Task/Event vivent sur Activity
    if base.lower() in STANDARD_OBJECTS:
        return base
    return base + "__c"


class SFAdminService:
    """
    Service d'administration Salesforce pour le BUILD v2.
    Transforme les plans JSON de Raj en métadonnées XML et déploie via SFDX.
    
    Workflow:
    1. Reçoit un plan JSON (liste d'opérations)
    2. Génère les fichiers XML dans la bonne structure SFDX
    3. Appelle `sf project deploy start`
    4. Retourne le résultat
    """
    
    API_VERSION = "59.0"
    
    # Mapping field_type vers Salesforce FieldType
    FIELD_TYPE_MAPPING = {
        "Text": "Text",
        "TextArea": "TextArea",
        "LongTextArea": "LongTextArea",
        "RichTextArea": "Html",
        "Number": "Number",
        "Currency": "Currency",
        "Percent": "Percent",
        "Date": "Date",
        "DateTime": "DateTime",
        "Checkbox": "Checkbox",
        "Email": "Email",
        "Phone": "Phone",
        "Url": "Url",
        "Picklist": "Picklist",
        "MultiselectPicklist": "MultiselectPicklist",
        "Lookup": "Lookup",
        "MasterDetail": "MasterDetail",
        "Formula": "Text",
        "AutoNumber": "AutoNumber",
    }
    
    def __init__(self, target_org: str):
        """
        Args:
            target_org: Username ou alias de l'org cible SFDX
        """
        self.target_org = target_org
        self.created_components: List[Dict[str, str]] = []
        logger.info(f"[SFAdmin] Initialized for org: {target_org}")
    
    def execute_plan(self, plan: Dict[str, Any]) -> DeployResult:
        """
        Exécute un plan JSON complet.
        
        Args:
            plan: Plan JSON avec liste d'operations
            
        Returns:
            DeployResult avec succès/échec
        """
        operations = plan.get("operations", [])
        
        if not operations:
            logger.warning("[SFAdmin] Empty plan, nothing to deploy")
            return DeployResult(success=True, components_deployed=0)
        
        logger.info(f"[SFAdmin] Executing plan with {len(operations)} operations")
        
        # Créer répertoire temporaire avec structure SFDX
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. Générer les fichiers XML
                self._generate_metadata_files(operations, temp_dir)
                
                # 2. Créer sfdx-project.json
                self._create_sfdx_project(temp_dir)
                
                # 3. Déployer via SFDX
                result = self._deploy_via_sfdx(temp_dir)
                
                return result
                
            except Exception as e:
                logger.error(f"[SFAdmin] Plan execution failed: {e}")
                return DeployResult(success=False, errors=[str(e)])
    
    def _generate_metadata_files(self, operations: List[Dict], temp_dir: str) -> None:
        """Génère les fichiers XML pour chaque opération."""
        
        # Trier par order
        sorted_ops = sorted(operations, key=lambda x: x.get("order", 0))
        
        # Regrouper par objet pour générer object + fields ensemble
        objects_data: Dict[str, Dict] = {}
        
        for op in sorted_ops:
            op_type = op.get("type", "")
            
            if op_type == "create_object":
                api_name = op.get("api_name", "")
                if not api_name.endswith("__c"):
                    api_name = f"{api_name}__c"
                objects_data[api_name] = {"object": op, "fields": []}
                
            elif op_type == "create_field":
                obj_name = op.get("object", "")
                obj_name = normaliser_objet(obj_name)
                if obj_name not in objects_data:
                    objects_data[obj_name] = {"object": None, "fields": []}
                objects_data[obj_name]["fields"].append(op)
                
            elif op_type == "create_validation_rule":
                self._generate_validation_rule(op, temp_dir)
                
            elif op_type == "create_record_type":
                # Record types sont inclus dans l'objet
                obj_name = op.get("object", "")
                obj_name = normaliser_objet(obj_name)
                if obj_name not in objects_data:
                    objects_data[obj_name] = {"object": None, "fields": [], "record_types": []}
                if "record_types" not in objects_data[obj_name]:
                    objects_data[obj_name]["record_types"] = []
                objects_data[obj_name]["record_types"].append(op)
            
            # Phase 1: List Views
            elif op_type == "create_list_view":
                self._generate_list_view(op, temp_dir)
            
            # Phase 4: Automation
            elif op_type == "create_flow":
                self._generate_flow(op, temp_dir)
            
            elif op_type == "create_approval_process":
                self._generate_approval_process(op, temp_dir)
            
            # Phase 5: Security
            elif op_type == "create_permission_set":
                self._generate_permission_set(op, temp_dir)
            
            elif op_type == "create_page_layout":
                self._generate_page_layout(op, temp_dir)
            
            elif op_type == "create_sharing_rule":
                self._generate_sharing_rule(op, temp_dir)
        
        # Générer les fichiers pour chaque objet
        for obj_name, data in objects_data.items():
            self._generate_object_metadata(obj_name, data, temp_dir)
    
    def _generate_object_metadata(self, obj_name: str, data: Dict, temp_dir: str) -> None:
        """Génère les fichiers metadata pour un objet et ses champs."""
        
        # Créer structure de répertoires
        obj_dir = Path(temp_dir) / "force-app" / "main" / "default" / "objects" / obj_name
        fields_dir = obj_dir / "fields"
        fields_dir.mkdir(parents=True, exist_ok=True)
        
        # Générer object-meta.xml si on a la définition de l'objet
        if data.get("object"):
            obj_op = data["object"]
            obj_xml = self._object_to_xml(obj_op)
            obj_file = obj_dir / f"{obj_name}.object-meta.xml"
            obj_file.write_text(obj_xml, encoding="utf-8")
            logger.info(f"[SFAdmin] Generated: {obj_file.name}")
            self.created_components.append({"type": "CustomObject", "name": obj_name})
        
        # Générer field-meta.xml pour chaque champ
        for field_op in data.get("fields", []):
            field_name = field_op.get("api_name", "")
            if not field_name.endswith("__c"):
                field_name = f"{field_name}__c"
            
            field_xml = self._field_to_xml(field_op)
            field_file = fields_dir / f"{field_name}.field-meta.xml"
            field_file.write_text(field_xml, encoding="utf-8")
            logger.info(f"[SFAdmin] Generated: {field_file.name}")
            self.created_components.append({"type": "CustomField", "name": f"{obj_name}.{field_name}"})
    
    def _object_to_xml(self, op: Dict) -> str:
        """Convertit une opération create_object en XML."""
        api_name = op.get("api_name", "")
        label = op.get("label", api_name.replace("__c", ""))
        plural_label = op.get("plural_label", f"{label}s")
        description = op.get("description", "")
        sharing_model = op.get("sharing_model", "ReadWrite")
        
        # Name field
        name_field_type = op.get("name_field_type", "Text")
        name_field_format = op.get("name_field_format", op.get("auto_number_format", ""))
        
        if name_field_type == "AutoNumber":
            name_field_xml = f"""    <nameField>
        <displayFormat>{name_field_format or f'{api_name[:3].upper()}-{{0000}}'}</displayFormat>
        <label>{label} Name</label>
        <type>AutoNumber</type>
    </nameField>"""
        else:
            name_field_xml = f"""    <nameField>
        <label>{label} Name</label>
        <type>Text</type>
    </nameField>"""
        
        description_xml = f"\n    <description>{description}</description>" if description else ""
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
    <deploymentStatus>Deployed</deploymentStatus>
    <label>{label}</label>
    <pluralLabel>{plural_label}</pluralLabel>{description_xml}
    <sharingModel>{sharing_model}</sharingModel>
{name_field_xml}
    <enableActivities>true</enableActivities>
    <enableReports>true</enableReports>
</CustomObject>"""
        
        return xml
    
    def _field_to_xml(self, op: Dict) -> str:
        """Convertit une opération create_field en XML."""
        field_name = op.get("api_name", "")
        if not field_name.endswith("__c"):
            field_name = f"{field_name}__c"
        
        label = op.get("label", field_name.replace("__c", ""))
        field_type = op.get("field_type", "Text")
        sf_type = self.FIELD_TYPE_MAPPING.get(field_type, "Text")
        description = op.get("description", "")
        required = op.get("required", False)
        
        # Construire le XML selon le type
        type_specific = ""
        
        if sf_type == "Text":
            length = op.get("length", 255)
            type_specific = f"\n    <length>{length}</length>"
            
        elif sf_type == "TextArea":
            type_specific = ""
            
        elif sf_type == "LongTextArea":
            length = op.get("length", 32768)
            visible_lines = op.get("visible_lines", 5)
            type_specific = f"\n    <length>{length}</length>\n    <visibleLines>{visible_lines}</visibleLines>"
            
        elif sf_type == "Number":
            precision = op.get("precision", 18)
            scale = op.get("scale", 0)
            type_specific = f"\n    <precision>{precision}</precision>\n    <scale>{scale}</scale>"
            
        elif sf_type == "Currency":
            precision = op.get("precision", 18)
            scale = op.get("scale", 2)
            type_specific = f"\n    <precision>{precision}</precision>\n    <scale>{scale}</scale>"
            
        elif sf_type == "Percent":
            precision = op.get("precision", 18)
            scale = op.get("scale", 2)
            type_specific = f"\n    <precision>{precision}</precision>\n    <scale>{scale}</scale>"
            
        elif sf_type == "Picklist" or sf_type == "MultiselectPicklist":
            # ── FIX-PICKLIST-001 (08/08/2026) ──────────────────────────────
            # Raj produit `values` avec des objets {api_name, label, default} ;
            # ce generateur ne lisait que `picklist_values` avec des chaines.
            # Les deux ne se rencontraient jamais, donc aucun <valueSet> n'etait
            # emis et Salesforce refusait : "You must specify either picklist,
            # globalPicklist, or valueSet". Les deux formats sont acceptes.
            values = op.get("values") or op.get("picklist_values") or []
            lignes = []
            for v in values:
                if isinstance(v, dict):
                    plein = v.get("api_name") or v.get("fullName") or v.get("value") or ""
                    lib = v.get("label") or plein
                    defaut = "true" if v.get("default") else "false"
                else:
                    plein = str(v); lib = plein; defaut = "false"
                if not plein:
                    continue
                lignes.append(
                    "            <value>\n"
                    f"                <fullName>{plein}</fullName>\n"
                    f"                <default>{defaut}</default>\n"
                    f"                <label>{lib}</label>\n"
                    "            </value>"
                )
            if lignes:
                values_xml = "\n".join(lignes)
                tri = "false" if sf_type == "MultiselectPicklist" else "false"
                type_specific = f"""
    <valueSet>
        <restricted>true</restricted>
        <valueSetDefinition>
            <sorted>{tri}</sorted>
{values_xml}
        </valueSetDefinition>
    </valueSet>"""
                if sf_type == "MultiselectPicklist":
                    type_specific += "\n    <visibleLines>4</visibleLines>"
            else:
                # Sans valeurs, Salesforce refuse le champ. On le signale au
                # lieu de produire un XML qui echouera au deploiement.
                logger.warning(
                    f"[SFAdmin] Picklist {field_name} sans valeurs — "
                    f"champ ignore (Salesforce exige un valueSet)"
                )
                return None

        elif sf_type == "Checkbox":
            # ── FIX-CHECKBOX-001 (08/08/2026) ──────────────────────────────
            # Salesforce EXIGE defaultValue sur une case a cocher :
            # "Must specify 'defaultValue' for a CustomField of type Checkbox".
            # Aucune branche ne traitait ce type, donc rien n'etait emis.
            defaut = op.get("default_value", op.get("defaultValue", False))
            defaut = "true" if defaut in (True, "true", "True", 1) else "false"
            type_specific = f"\n    <defaultValue>{defaut}</defaultValue>"

        elif sf_type == "Lookup":
            ref_to = op.get("reference_to", "")
            relationship_name = op.get("relationship_name", field_name.replace("__c", ""))
            type_specific = f"\n    <referenceTo>{ref_to}</referenceTo>\n    <relationshipName>{relationship_name}</relationshipName>"
            
        elif sf_type == "MasterDetail":
            ref_to = op.get("reference_to", "")
            relationship_name = op.get("relationship_name", field_name.replace("__c", ""))
            type_specific = f"\n    <referenceTo>{ref_to}</referenceTo>\n    <relationshipName>{relationship_name}</relationshipName>\n    <reparentableMasterDetail>false</reparentableMasterDetail>\n    <writeRequiresMasterRead>false</writeRequiresMasterRead>"
        
        description_xml = f"\n    <description>{description}</description>" if description else ""
        required_xml = f"\n    <required>{str(required).lower()}</required>"
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{field_name}</fullName>
    <label>{label}</label>
    <type>{sf_type}</type>{type_specific}{description_xml}{required_xml}
</CustomField>"""
        
        return xml
    
    def _generate_validation_rule(self, op: Dict, temp_dir: str) -> None:
        """Génère un fichier validation rule."""
        obj_name = op.get("object", "")
        if not obj_name.endswith("__c"):
            obj_name = f"{obj_name}__c"
        
        rule_name = op.get("api_name", op.get("name", ""))
        
        # Créer répertoire
        vr_dir = Path(temp_dir) / "force-app" / "main" / "default" / "objects" / obj_name / "validationRules"
        vr_dir.mkdir(parents=True, exist_ok=True)
        
        active = op.get("active", True)
        error_condition = op.get("error_condition_formula", op.get("formula", "false"))
        error_message = op.get("error_message", "Validation error")
        
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ValidationRule xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{rule_name}</fullName>
    <active>{str(active).lower()}</active>
    <errorConditionFormula>{error_condition}</errorConditionFormula>
    <errorMessage>{error_message}</errorMessage>
</ValidationRule>"""
        
        vr_file = vr_dir / f"{rule_name}.validationRule-meta.xml"
        vr_file.write_text(xml, encoding="utf-8")
        logger.info(f"[SFAdmin] Generated: {vr_file.name}")
        self.created_components.append({"type": "ValidationRule", "name": f"{obj_name}.{rule_name}"})
    
    def _create_sfdx_project(self, temp_dir: str) -> None:
        """Crée le fichier sfdx-project.json."""
        project_json = {
            "packageDirectories": [{"path": "force-app", "default": True}],
            "sourceApiVersion": self.API_VERSION
        }
        
        project_file = Path(temp_dir) / "sfdx-project.json"
        project_file.write_text(json.dumps(project_json, indent=2), encoding="utf-8")
        logger.info("[SFAdmin] Created sfdx-project.json")
    
    def _deploy_via_sfdx(self, temp_dir: str) -> DeployResult:
        """Déploie les métadonnées via SFDX CLI."""

        # ── GARDE-PROD-001 : refus absolu de déployer en production ──
        instance = getattr(self, "instance_url", "") or ""
        if org_est_productive(self.target_org, instance):
            message = (
                f"DÉPLOIEMENT REFUSÉ — la cible '{self.target_org}' n'est pas "
                f"identifiable comme un sandbox ou une org de développement. "
                f"Digital·Humans ne déploie jamais en production : la livraison "
                f"s'arrête au sandbox, le client promeut ensuite lui-même. "
                f"Si cette org est bien un sandbox, ajoutez son marqueur à "
                f"MARQUEURS_NON_PRODUCTION plutôt que de contourner ce garde-fou."
            )
            logger.error(f"[SFAdmin] {message}")
            return DeployResult(
                success=False,
                errors=[message],
                components_deployed=0,
            )
        logger.info(
            f"[SFAdmin] Cible vérifiée non-productive : {self.target_org}"
        )

        # ── VALIDATION-XML-001 (08/08/2026) ────────────────────────────────
        # Angle mort identifie par Sam : Elena relit le PLAN de Raj, mais le XML
        # est genere APRES sa revue. Les quatre echecs du 08/08 vivaient tous
        # dans cet interstice — trop tard pour Elena, trop tot pour Salesforce.
        # On valide donc le XML AVANT de deployer : "--dry-run" fait verifier
        # les metadonnees par Salesforce sans rien ecrire. Cout : un aller-retour
        # reseau, aucun appel de modele. Si la validation echoue, on renvoie
        # l'erreur telle quelle sans avoir touche a l'org.
        cmd_validation = [
            "sf", "project", "deploy", "start",
            "--source-dir", "force-app",
            "--target-org", self.target_org,
            "--dry-run",
            "--json",
        ]
        try:
            v = subprocess.run(
                cmd_validation, cwd=temp_dir, capture_output=True,
                text=True, timeout=600,
            )
            if v.returncode != 0:
                detail = json.loads(v.stdout or "{}") if v.stdout else {}
                erreurs = []
                for e in (detail.get("result", {}).get("details", {})
                          .get("componentFailures", []) or []):
                    erreurs.append(
                        f"{e.get('fullName','?')}: {e.get('problem','?')}"
                    )
                if not erreurs:
                    erreurs = [(v.stderr or v.stdout or "validation echouee")[:400]]
                logger.error(f"[SFAdmin] Validation XML echouee : {erreurs[:5]}")
                return DeployResult(
                    success=False,
                    errors=["VALIDATION AVANT DEPLOIEMENT — rien n'a ete ecrit dans l'org."]
                           + erreurs,
                    components_deployed=0,
                )
            logger.info("[SFAdmin] Validation XML reussie — deploiement autorise")
        except subprocess.TimeoutExpired:
            logger.warning("[SFAdmin] Validation XML expiree — on tente le deploiement")
        except Exception as e:
            logger.warning(f"[SFAdmin] Validation XML impossible ({e}) — on tente le deploiement")

        cmd = [
            "sf", "project", "deploy", "start",
            "--source-dir", "force-app",
            "--target-org", self.target_org,
            "--json"
        ]
        
        logger.info(f"[SFAdmin] Deploying from {temp_dir}")
        logger.info(f"[SFAdmin] Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=temp_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Parse JSON response
            try:
                response = json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.error(f"[SFAdmin] Invalid JSON response: {result.stdout[:500]}")
                return DeployResult(
                    success=False,
                    errors=[f"Invalid SFDX response: {result.stderr or result.stdout[:200]}"]
                )
            
            if response.get("status") == 0 and response.get("result", {}).get("success"):
                deploy_result = response["result"]
                
                return DeployResult(
                    success=True,
                    components_deployed=deploy_result.get("numberComponentsDeployed", 0),
                    components_failed=deploy_result.get("numberComponentErrors", 0),
                    created_components=self.created_components,
                    deploy_id=deploy_result.get("id")
                )
            else:
                # Extract errors
                errors = []
                deploy_result = response.get("result", {})
                
                for failure in deploy_result.get("details", {}).get("componentFailures", []):
                    errors.append(f"{failure.get('fullName')}: {failure.get('problem')}")
                
                if not errors:
                    errors = [response.get("message", "Unknown deployment error")]
                
                logger.error(f"[SFAdmin] Deployment failed: {errors}")
                
                return DeployResult(
                    success=False,
                    components_deployed=deploy_result.get("numberComponentsDeployed", 0),
                    components_failed=deploy_result.get("numberComponentErrors", 0),
                    errors=errors
                )
                
        except subprocess.TimeoutExpired:
            return DeployResult(success=False, errors=["Deployment timeout (120s)"])
        except Exception as e:
            return DeployResult(success=False, errors=[str(e)])


    # ═══════════════════════════════════════════════════════════════
    # OPÉRATIONS PHASE 1 SUPPLÉMENTAIRES
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_list_view(self, op: Dict, temp_dir: str) -> None:
        """Génère un ListView pour un objet."""
        obj_name = op.get("object", "")
        if not obj_name.endswith("__c"):
            obj_name = f"{obj_name}__c"
        
        api_name = op.get("api_name", "All")
        label = op.get("label", api_name)
        columns = op.get("columns", [])
        filter_scope = op.get("filter_scope", "Everything")
        
        # Filtrer "Name" - pour custom objects, utiliser OBJECT_NAME au lieu de Name
        # Le champ Name standard n'est pas accessible directement dans les ListViews custom
        filtered_columns = [col for col in columns if col.upper() != "NAME"]
        
        list_views_dir = Path(temp_dir) / "force-app" / "main" / "default" / "objects" / obj_name / "listViews"
        list_views_dir.mkdir(parents=True, exist_ok=True)
        
        columns_xml = "\n".join([f"    <columns>{col}</columns>" for col in filtered_columns])
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<ListView xmlns="http://soap.sforce.com/2006/04/metadata">
    <fullName>{api_name}</fullName>
    <label>{label}</label>
{columns_xml}
    <filterScope>{filter_scope}</filterScope>
</ListView>'''
        
        filepath = list_views_dir / f"{api_name}.listView-meta.xml"
        filepath.write_text(xml_content)
        self.created_components.append({"type": "ListView", "name": f"{obj_name}.{api_name}"})
        logger.info(f"[SFAdmin] Generated ListView: {obj_name}.{api_name}")

    # ═══════════════════════════════════════════════════════════════
    # OPÉRATIONS PHASE 4 (AUTOMATION)
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_flow(self, op: Dict, temp_dir: str) -> None:
        """Génère un Flow (structure de base)."""
        api_name = op.get("api_name", "")
        flow_type = op.get("flow_type", "AutoLaunchedFlow")
        description = op.get("description", "")
        
        flows_dir = Path(temp_dir) / "force-app" / "main" / "default" / "flows"
        flows_dir.mkdir(parents=True, exist_ok=True)
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<Flow xmlns="http://soap.sforce.com/2006/04/metadata">
    <apiVersion>59.0</apiVersion>
    <description>{description}</description>
    <interviewLabel>{api_name}</interviewLabel>
    <label>{op.get("label", api_name)}</label>
    <processType>{flow_type}</processType>
    <status>Draft</status>
</Flow>'''
        
        filepath = flows_dir / f"{api_name}.flow-meta.xml"
        filepath.write_text(xml_content)
        self.created_components.append({"type": "Flow", "name": api_name})
        logger.info(f"[SFAdmin] Generated Flow: {api_name} ({flow_type})")

    def _generate_approval_process(self, op: Dict, temp_dir: str) -> None:
        """Génère un Approval Process."""
        obj_name = op.get("object", "")
        api_name = op.get("api_name", "")
        entry_criteria = op.get("entry_criteria", "true")
        
        approvals_dir = Path(temp_dir) / "force-app" / "main" / "default" / "approvalProcesses"
        approvals_dir.mkdir(parents=True, exist_ok=True)
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<ApprovalProcess xmlns="http://soap.sforce.com/2006/04/metadata">
    <active>false</active>
    <allowRecall>true</allowRecall>
    <allowedSubmitters>
        <type>owner</type>
    </allowedSubmitters>
    <description>{op.get("description", "")}</description>
    <entryCriteria>
        <formula>{entry_criteria}</formula>
    </entryCriteria>
    <finalApprovalRecordLock>true</finalApprovalRecordLock>
    <finalRejectionRecordLock>false</finalRejectionRecordLock>
    <label>{op.get("label", api_name)}</label>
    <showApprovalHistory>true</showApprovalHistory>
</ApprovalProcess>'''
        
        filepath = approvals_dir / f"{obj_name}.{api_name}.approvalProcess-meta.xml"
        filepath.write_text(xml_content)
        self.created_components.append({"type": "ApprovalProcess", "name": f"{obj_name}.{api_name}"})
        logger.info(f"[SFAdmin] Generated ApprovalProcess: {obj_name}.{api_name}")

    # ═══════════════════════════════════════════════════════════════
    # OPÉRATIONS PHASE 5 (SECURITY)
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_permission_set(self, op: Dict, temp_dir: str) -> None:
        """Génère un Permission Set."""
        api_name = op.get("api_name", "")
        label = op.get("label", api_name)
        description = op.get("description", "")
        object_permissions = op.get("object_permissions", [])
        field_permissions = op.get("field_permissions", [])
        
        perm_sets_dir = Path(temp_dir) / "force-app" / "main" / "default" / "permissionsets"
        perm_sets_dir.mkdir(parents=True, exist_ok=True)
        
        obj_perms_xml = ""
        for obj_perm in object_permissions:
            obj_perms_xml += f'''
    <objectPermissions>
        <allowCreate>{str(obj_perm.get("allowCreate", True)).lower()}</allowCreate>
        <allowDelete>{str(obj_perm.get("allowDelete", False)).lower()}</allowDelete>
        <allowEdit>{str(obj_perm.get("allowEdit", True)).lower()}</allowEdit>
        <allowRead>{str(obj_perm.get("allowRead", True)).lower()}</allowRead>
        <modifyAllRecords>{str(obj_perm.get("modifyAllRecords", False)).lower()}</modifyAllRecords>
        <object>{obj_perm.get("object", "")}</object>
        <viewAllRecords>{str(obj_perm.get("viewAllRecords", False)).lower()}</viewAllRecords>
    </objectPermissions>'''
        
        field_perms_xml = ""
        for field_perm in field_permissions:
            field_perms_xml += f'''
    <fieldPermissions>
        <editable>{str(field_perm.get("editable", True)).lower()}</editable>
        <field>{field_perm.get("field", "")}</field>
        <readable>{str(field_perm.get("readable", True)).lower()}</readable>
    </fieldPermissions>'''
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<PermissionSet xmlns="http://soap.sforce.com/2006/04/metadata">
    <description>{description}</description>
    <hasActivationRequired>false</hasActivationRequired>
    <label>{label}</label>{obj_perms_xml}{field_perms_xml}
</PermissionSet>'''
        
        filepath = perm_sets_dir / f"{api_name}.permissionset-meta.xml"
        filepath.write_text(xml_content)
        self.created_components.append({"type": "PermissionSet", "name": api_name})
        logger.info(f"[SFAdmin] Generated PermissionSet: {api_name}")

    def _generate_page_layout(self, op: Dict, temp_dir: str) -> None:
        """Génère un Page Layout."""
        obj_name = op.get("object", "")
        if not obj_name.endswith("__c"):
            obj_name = f"{obj_name}__c"
        
        api_name = op.get("api_name", f"{obj_name}-Layout")
        sections = op.get("sections", [])
        
        layouts_dir = Path(temp_dir) / "force-app" / "main" / "default" / "layouts"
        layouts_dir.mkdir(parents=True, exist_ok=True)
        
        sections_xml = ""
        for section in sections:
            section_label = section.get("label", "Information")
            fields = section.get("fields", [])
            
            items_xml = ""
            # Renamed loop var from `field` to `field_name` to avoid shadowing
            # `dataclasses.field` imported at top of module (ruff F402).
            for field_name in fields:
                # Name field doit être Readonly pour les custom objects
                behavior = "Readonly" if field_name.upper() == "NAME" else "Edit"
                items_xml += f'''
            <layoutItems>
                <behavior>{behavior}</behavior>
                <field>{field_name}</field>
            </layoutItems>'''
            
            sections_xml += f'''
    <layoutSections>
        <customLabel>true</customLabel>
        <detailHeading>true</detailHeading>
        <editHeading>true</editHeading>
        <label>{section_label}</label>
        <layoutColumns>{items_xml}
        </layoutColumns>
        <layoutColumns/>
        <style>TwoColumnsLeftToRight</style>
    </layoutSections>'''
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<Layout xmlns="http://soap.sforce.com/2006/04/metadata">{sections_xml}
    <showEmailCheckbox>false</showEmailCheckbox>
    <showRunAssignmentRulesCheckbox>false</showRunAssignmentRulesCheckbox>
    <showSubmitAndAttachButton>false</showSubmitAndAttachButton>
</Layout>'''
        
        filepath = layouts_dir / f"{obj_name}-{api_name}.layout-meta.xml"
        filepath.write_text(xml_content)
        self.created_components.append({"type": "Layout", "name": f"{obj_name}-{api_name}"})
        logger.info(f"[SFAdmin] Generated Layout: {obj_name}-{api_name}")

    def _generate_sharing_rule(self, op: Dict, temp_dir: str) -> None:
        """Génère une Sharing Rule."""
        obj_name = op.get("object", "")
        if not obj_name.endswith("__c"):
            obj_name = f"{obj_name}__c"
        
        api_name = op.get("api_name", "")
        access_level = op.get("access_level", "Read")
        
        sharing_dir = Path(temp_dir) / "force-app" / "main" / "default" / "sharingRules"
        sharing_dir.mkdir(parents=True, exist_ok=True)
        
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<SharingRules xmlns="http://soap.sforce.com/2006/04/metadata">
    <sharingCriteriaRules>
        <fullName>{api_name}</fullName>
        <accessLevel>{access_level}</accessLevel>
        <label>{op.get("label", api_name)}</label>
        <sharedTo>
            <allInternalUsers></allInternalUsers>
        </sharedTo>
    </sharingCriteriaRules>
</SharingRules>'''
        
        filepath = sharing_dir / f"{obj_name}.sharingRules-meta.xml"
        filepath.write_text(xml_content)
        self.created_components.append({"type": "SharingRule", "name": f"{obj_name}.{api_name}"})
        logger.info(f"[SFAdmin] Generated SharingRule: {obj_name}.{api_name}")


# Factory function pour créer le service depuis un project_id
async def create_sf_admin_service(project_id: int, db) -> Optional[SFAdminService]:
    """
    Crée un SFAdminService pour un projet.
    
    Args:
        project_id: ID du projet
        db: Session DB
        
    Returns:
        SFAdminService configuré ou None si pas de config SF
    """
    from sqlalchemy import text
    
    result = db.execute(
        text("SELECT sf_username FROM projects WHERE id = :id"),
        {"id": project_id}
    ).fetchone()
    
    if not result or not result.sf_username:
        logger.warning(f"[SFAdmin] No Salesforce config for project {project_id}")
        return None
    
    return SFAdminService(target_org=result.sf_username)
