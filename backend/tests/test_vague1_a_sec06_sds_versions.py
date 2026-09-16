"""Vague 1 / file A — SEC-06 (rapport Astra L127).

Les snapshots SDS etaient ecrits dans un repertoire commun sous
`SDS_<nom_projet>_v<n>.html`, **sans identifiant de client ni de projet** :
deux projets homonymes a la meme version designaient le meme fichier. Le
second ecrasait le premier, et le premier client lisait ensuite le document
du second malgre un controle SQL de propriete correct.

Deux snapshots concurrents du meme projet calculaient aussi le meme
`max(version)+1`, sans contrainte unique pour l'empecher.

Le controle porte sur le CONTENU RENDU au premier client, pas sur le code
de retour : c'est la fuite qui est en jeu.
"""
import shutil
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.main import app
from app.models.execution import Execution
from app.models.project import Project
from app.models.sds_version import SDSVersion
from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)

NOM_PARTAGE = "Refonte CRM"
SECRET_A = "SECRET DU CLIENT A : marge 42%"
SECRET_B = "SECRET DU CLIENT B : marge 13%"


def _tenant(db, suffix: str):
    user = User(
        email=f"sec06-{suffix}@example.test",
        hashed_password="pas-un-vrai-hash",
        name=f"SEC06 {suffix}",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Meme nom de projet des deux cotes : c'est la condition du defaut.
    project = Project(user_id=user.id, name=NOM_PARTAGE)
    db.add(project)
    db.commit()
    db.refresh(project)

    execution = Execution(project_id=project.id, user_id=user.id)
    db.add(execution)
    db.commit()
    db.refresh(execution)

    return {"user": user, "project": project, "execution": execution}


@pytest.fixture(autouse=True)
def _repertoire_de_sortie_vierge():
    """`db_session` recree la base a chaque test : les identifiants de projet
    repartent a 1. Les snapshots du test precedent porteraient donc le meme
    chemin, et l'ecriture exclusive (voulue) les refuserait. On repart d'un
    repertoire vide — c'est un artefact de test, pas un contournement du
    correctif : c'est justement parce qu'on n'ecrase plus rien."""
    dossier = Path(settings.OUTPUT_DIR) / "projects"
    shutil.rmtree(dossier, ignore_errors=True)
    yield
    shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture
def tenants(db_session):
    return {"a": _tenant(db_session, "a"), "b": _tenant(db_session, "b")}


def _authentifier(user: User):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


def _creer_snapshot(client, tenant, html: str):
    """La route fait `from build_sds import build_sds` DANS son corps : on
    substitue le module entier dans sys.modules, sinon le vrai moteur de
    rendu Jinja est appele (mesure : 500, 'None' has no attribute strftime)."""
    faux = types.ModuleType("build_sds")
    faux.build_sds = lambda _execution_id: html
    with patch.dict(sys.modules, {"build_sds": faux}):
        return client.post(
            f"/api/projects/{tenant['project'].id}/sds-versions",
            json={"execution_id": tenant["execution"].id},
        )


def test_deux_clients_homonymes_n_ecrivent_pas_le_meme_fichier(client, db_session, tenants):
    a, b = tenants["a"], tenants["b"]

    _authentifier(a["user"])
    reponse_a = _creer_snapshot(client, a, f"<html><body>{SECRET_A}</body></html>")
    assert reponse_a.status_code == 201, reponse_a.text

    _authentifier(b["user"])
    reponse_b = _creer_snapshot(client, b, f"<html><body>{SECRET_B}</body></html>")
    assert reponse_b.status_code == 201, reponse_b.text

    chemin_a = db_session.query(SDSVersion).filter(
        SDSVersion.project_id == a["project"].id
    ).one().file_path
    chemin_b = db_session.query(SDSVersion).filter(
        SDSVersion.project_id == b["project"].id
    ).one().file_path
    assert chemin_a != chemin_b, f"meme fichier pour deux clients : {chemin_a}"


def test_le_client_a_relit_bien_son_propre_document(client, db_session, tenants):
    """Le coeur du constat : apres le snapshot de B, A doit relire SON texte."""
    a, b = tenants["a"], tenants["b"]

    _authentifier(a["user"])
    assert _creer_snapshot(client, a, f"<html><body>{SECRET_A}</body></html>").status_code == 201

    _authentifier(b["user"])
    assert _creer_snapshot(client, b, f"<html><body>{SECRET_B}</body></html>").status_code == 201

    _authentifier(a["user"])
    vue = client.get(f"/api/projects/{a['project'].id}/sds-versions/1/view")
    assert vue.status_code == 200, vue.text
    assert SECRET_A in vue.text
    assert SECRET_B not in vue.text, "le client A lit le document du client B"


def test_controle_negatif_le_proprietaire_lit_ses_deux_versions(client, db_session, tenants):
    """Sans ce controle, un chemin rendu unique par un alea a chaque LECTURE
    passerait aussi le test precedent."""
    a = tenants["a"]
    _authentifier(a["user"])

    assert _creer_snapshot(client, a, "<html><body>version un</body></html>").status_code == 201
    assert _creer_snapshot(client, a, "<html><body>version deux</body></html>").status_code == 201

    v1 = client.get(f"/api/projects/{a['project'].id}/sds-versions/1/view")
    v2 = client.get(f"/api/projects/{a['project'].id}/sds-versions/2/view")
    assert v1.status_code == 200 and "version un" in v1.text, v1.text
    assert v2.status_code == 200 and "version deux" in v2.text, v2.text


def test_un_couple_projet_version_ne_peut_pas_exister_deux_fois(db_session, tenants):
    """Deux snapshots concurrents calculent le meme max(version)+1 : seule une
    contrainte unique en base empeche le doublon."""
    a = tenants["a"]
    for _ in range(2):
        db_session.add(SDSVersion(
            project_id=a["project"].id,
            execution_id=a["execution"].id,
            version_number=1,
            file_path="/tmp/peu-importe.html",
            file_name="peu-importe.html",
            file_size=1,
        ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_controle_negatif_deux_projets_peuvent_avoir_la_version_1(db_session, tenants):
    a, b = tenants["a"], tenants["b"]
    for tenant in (a, b):
        db_session.add(SDSVersion(
            project_id=tenant["project"].id,
            execution_id=tenant["execution"].id,
            version_number=1,
            file_path=f"/tmp/projet-{tenant['project'].id}.html",
            file_name="sds.html",
            file_size=1,
        ))
    db_session.commit()
    assert db_session.query(SDSVersion).count() == 2
