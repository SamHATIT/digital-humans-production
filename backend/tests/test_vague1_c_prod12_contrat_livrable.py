"""
VAGUE 1 / FILE C — PROD-12 : « livrable terminé » n'a pas un contrat unique.

Astra L562, deux mecaniques precises :

1. « Dans `_generate_sds_document`, le chemin renvoye par
   `convert_markdown_to_docx` est ignore : si le convertisseur change de
   format, la route peut pointer un DOCX inexistant. » C'est exactement ce que
   fait le convertisseur quand python-docx n'est pas disponible — il ecrit un
   `.md` et rend **son** chemin, que l'appelant jette au profit du `.docx`
   qu'il avait imagine.
2. « Les routes de telechargement annoncent systematiquement du DOCX, meme
   lorsque la version est HTML/Markdown », et « la decision "livrable present"
   verifie l'extension, pas l'existence du fichier ».
"""
import pytest

from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import (
    PMOrchestratorServiceV2,
    resolve_export_action,
)
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)

DOWNLOAD_URL = "/api/pm-orchestrator/execute/{eid}/download"


@pytest.fixture
def contexte(db_session):
    user = User(
        email="vague1c-prod12@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C PROD-12",
        subscription_tier="pro",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    project = Project(user_id=user.id, name="Projet PROD-12")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm"],
        agent_execution_status={},
        status=ExecutionStatus.COMPLETED,
        execution_state="sds_complete",
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override
    return {"user": user, "project": project, "execution": execution}


# --------------------------------------------------------------------------
# 1. Le chemin rendu est celui qui a ete produit
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_le_chemin_rendu_est_celui_du_convertisseur(
    db_session, contexte, monkeypatch, tmp_path
):
    """Le convertisseur se replie en Markdown quand python-docx manque. Le
    chemin imagine (`.docx`) ne designe alors aucun fichier."""
    reel = tmp_path / "SDS_Exec1.md"

    def _convertisseur_qui_se_replie(markdown, output_path, *a, **kw):
        reel.write_text(markdown, encoding="utf-8")
        return str(reel)

    monkeypatch.setattr(
        "app.services.markdown_to_docx.convert_markdown_to_docx",
        _convertisseur_qui_se_replie,
    )
    monkeypatch.setattr(
        "app.config.settings.OUTPUT_DIR", tmp_path, raising=False
    )

    service = PMOrchestratorServiceV2(db_session)
    chemin = await service._generate_sds_document(
        project=contexte["project"],
        agent_outputs={},
        artifacts={},
        execution_id=contexte["execution"].id,
        sds_markdown="# Un SDS",
    )

    assert chemin == str(reel), (
        f"le chemin rendu ({chemin!r}) n'est pas celui que le convertisseur a "
        f"produit ({str(reel)!r}) — la route pointerait un fichier inexistant"
    )


@pytest.mark.asyncio
async def test_le_chemin_rendu_existe_sur_le_disque(
    db_session, contexte, monkeypatch, tmp_path
):
    """Controle plus fort que le precedent : ce n'est pas la coherence des
    chaines qui compte, c'est le fichier."""
    from pathlib import Path

    def _convertisseur(markdown, output_path, *a, **kw):
        Path(output_path).write_text(markdown, encoding="utf-8")
        return output_path

    monkeypatch.setattr(
        "app.services.markdown_to_docx.convert_markdown_to_docx", _convertisseur
    )
    monkeypatch.setattr("app.config.settings.OUTPUT_DIR", tmp_path, raising=False)

    service = PMOrchestratorServiceV2(db_session)
    chemin = await service._generate_sds_document(
        project=contexte["project"],
        agent_outputs={},
        artifacts={},
        execution_id=contexte["execution"].id,
        sds_markdown="# Un SDS",
    )
    assert Path(chemin).exists(), f"{chemin} n'existe pas"


@pytest.mark.asyncio
async def test_un_convertisseur_qui_ne_produit_rien_est_refuse(
    db_session, contexte, monkeypatch, tmp_path
):
    """Regle 6 : un export qui n'a rien ecrit ne doit pas rendre un chemin
    comme si de rien n'etait. Le repli Markdown reste possible — mais il ecrit
    vraiment un fichier."""
    from pathlib import Path

    def _convertisseur_muet(markdown, output_path, *a, **kw):
        return output_path  # n'ecrit rien

    monkeypatch.setattr(
        "app.services.markdown_to_docx.convert_markdown_to_docx", _convertisseur_muet
    )
    monkeypatch.setattr("app.config.settings.OUTPUT_DIR", tmp_path, raising=False)

    service = PMOrchestratorServiceV2(db_session)
    chemin = await service._generate_sds_document(
        project=contexte["project"],
        agent_outputs={},
        artifacts={},
        execution_id=contexte["execution"].id,
        sds_markdown="# Un SDS",
    )
    assert Path(chemin).exists(), (
        f"{chemin} a ete rendu alors qu'aucun fichier n'a ete ecrit"
    )


# --------------------------------------------------------------------------
# 2. Le telechargement annonce ce qu'il envoie
# --------------------------------------------------------------------------

def test_le_telechargement_annonce_le_format_reel(
    client, db_session, contexte, tmp_path
):
    """« Les routes de telechargement annoncent systematiquement du DOCX, meme
    lorsque la version est HTML/Markdown. » Le client enregistre alors un .docx
    que Word refuse d'ouvrir."""
    fichier = tmp_path / "SDS_Exec.md"
    fichier.write_text("# Un SDS", encoding="utf-8")
    contexte["execution"].sds_document_path = str(fichier)
    db_session.commit()

    r = client.get(DOWNLOAD_URL.format(eid=contexte["execution"].id))
    assert r.status_code == 200, r.text
    type_annonce = r.headers["content-type"]
    assert "wordprocessingml" not in type_annonce, (
        f"un fichier Markdown est annonce comme du DOCX : {type_annonce}"
    )
    assert ".md" in r.headers.get("content-disposition", ""), (
        f"le nom propose ne porte pas la bonne extension : "
        f"{r.headers.get('content-disposition')}"
    )


def test_le_telechargement_d_un_docx_reste_un_docx(
    client, db_session, contexte, tmp_path
):
    """Controle negatif : le cas nominal ne change pas."""
    fichier = tmp_path / "SDS_Exec.docx"
    fichier.write_bytes(b"PK\x03\x04 pas un vrai docx mais un vrai fichier")
    contexte["execution"].sds_document_path = str(fichier)
    db_session.commit()

    r = client.get(DOWNLOAD_URL.format(eid=contexte["execution"].id))
    assert r.status_code == 200, r.text
    assert "wordprocessingml" in r.headers["content-type"]


def test_un_livrable_annonce_mais_absent_rend_404(client, db_session, contexte):
    """Un chemin en base ne prouve pas un fichier sur le disque. Sans cette
    verification, la route tombe en erreur serveur au lieu de dire ce qui
    manque."""
    contexte["execution"].sds_document_path = "/tmp/dh-inexistant-prod12.docx"
    db_session.commit()

    r = client.get(DOWNLOAD_URL.format(eid=contexte["execution"].id))
    assert r.status_code == 404, r.text
    assert "introuvable" in r.text.lower() or "not available" in r.text.lower()


# --------------------------------------------------------------------------
# 3. « Livrable present » se decide sur le fichier
# --------------------------------------------------------------------------

def test_un_livrable_absent_du_disque_n_est_pas_servi(tmp_path):
    """« La decision "livrable present" verifie l'extension, pas l'existence
    du fichier. » Un export a refaire etait donc servi comme un livrable."""
    absent = str(tmp_path / "jamais_ecrit.docx")
    decision = resolve_export_action(state="sds_complete", sds_document_path=absent)
    assert decision["action"] == "regenerate_export", (
        f"un fichier inexistant est servi comme livrable : {decision}"
    )
    assert decision["reason"]


def test_un_livrable_present_sur_le_disque_est_servi(tmp_path):
    """Controle negatif : le livrable reel se sert toujours, et l'export ne se
    refait pas pour rien (« export seul sans nouveau LLM » suppose d'abord de
    ne pas exporter ce qui existe)."""
    present = tmp_path / "SDS.docx"
    present.write_bytes(b"un vrai fichier")
    decision = resolve_export_action(
        state="sds_complete", sds_document_path=str(present)
    )
    assert decision["action"] == "serve"
    assert decision["path"] == str(present)


def test_la_decision_peut_etre_prise_sans_toucher_au_disque():
    """La fonction reste utilisable comme decision pure — c'est ainsi que les
    tests de la vague 3 l'emploient, et que la route la joue a blanc."""
    decision = resolve_export_action(
        state="sds_complete", sds_document_path="/x/sds.docx", fichier_present=True
    )
    assert decision["action"] == "serve"
    decision = resolve_export_action(
        state="sds_complete", sds_document_path="/x/sds.md", fichier_present=True
    )
    assert decision["action"] == "regenerate_export"
