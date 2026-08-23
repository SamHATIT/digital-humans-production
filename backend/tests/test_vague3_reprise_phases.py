"""
VAGUE 3 — §3.1 : ajouter les points de reprise `phase2_5` et `phase3`.

La regle retenue par Sam : « on garde ce qui est termine correctement, et on
reprend a la suite du dernier qui a reussi. »

Le defaut : `execute_workflow` ne connaissait aucun point d'entree entre
`phase2` et `phase4`. Si Marcus echouait a son quatrieme appel — le cas le plus
couteux et le plus frequent — la seule reprise disponible etait `phase2`, qui
**refait tous les UC d'Olivia**. Un echec de Marcus detruisait le travail
d'Olivia.

  `phase2_5` — les UC d'Olivia sont conserves, le digest d'Emma est refait.
  `phase3`   — UC et digest conserves, Marcus reprend ses quatre appels.

Methode de preuve : `_run_agent` est le point de passage unique de tous les
appels d'agents. On l'instrumente pour enregistrer qui est appele, et on arrete
la course a l'entree de Marcus. Ce qui compte n'est pas que l'execution aille au
bout, c'est **qui a ete rappele et qui ne l'a pas ete**.
"""
import json

import pytest

from app.models.agent import Agent
from app.models.agent_deliverable import AgentDeliverable
from app.models.business_requirement import BusinessRequirement
from app.models.deliverable_item import DeliverableItem
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import (
    SDS_RESUME_POINTS,
    PMOrchestratorServiceV2,
)


class ArretControle(Exception):
    """Leve pour stopper la course des qu'on a vu ce qu'on voulait voir."""


# --------------------------------------------------------------------------
# Montage : une execution qui a deja produit BR, UC et digest
# --------------------------------------------------------------------------

@pytest.fixture
def execution_avancee(db_session):
    """Un projet dont les phases 1, 2 et 2.5 ont reussi.

    C'est l'etat exact d'une execution qui echoue en phase 3 : tout l'amont est
    en base, et c'est precisement ce que la reprise doit conserver.
    """
    # `agent_deliverables.agent_id` est NOT NULL et pointe `agents.id`. Sans ces
    # lignes, `_save_deliverable` insere NULL, l'INSERT casse, et son try/except
    # avale l'erreur : le livrable est perdu en silence. Voir la note du rapport
    # de vague 3 — le repli documente par `resolve_agent_pk` (« on retombe sur
    # le comportement legacy NULL ») ne peut pas fonctionner sur une colonne
    # NOT NULL.
    from app.services.agent_pk_resolver import reset_cache

    reset_cache()
    for nom in ("Sophie", "Olivia", "Emma", "Marcus", "Aisha", "Lucas", "Elena", "Jordan"):
        db_session.add(Agent(name=nom, description=f"Agent {nom}"))
    db_session.commit()

    user = User(
        email="vague3-reprise@example.test",
        hashed_password="not-a-real-hash",
        name="Vague3",
        subscription_tier="team",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    project = Project(
        user_id=user.id,
        name="Projet reprise",
        description="Un projet avec de l'amont deja produit",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba", "architect"],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    # Phase 1 : deux BR valides
    for idx in range(2):
        db_session.add(
            BusinessRequirement(
                project_id=project.id,
                execution_id=execution.id,
                br_id=f"BR-{idx + 1:03d}",
                requirement=f"Exigence metier numero {idx + 1}",
                order_index=idx,
            )
        )

    # Phase 2 : trois UC produits par Olivia, en base
    for idx in range(3):
        db_session.add(
            DeliverableItem(
                execution_id=execution.id,
                agent_id="ba",
                parent_ref="BR-001",
                item_id=f"UC-001-{idx + 1:02d}",
                item_type="use_case",
                content_parsed={"title": f"Cas d'usage {idx + 1}"},
                content_raw="{}",
                parse_success=True,
            )
        )

    # Phase 2.5 : le digest d'Emma, en base
    emma_pk = db_session.query(Agent).filter(Agent.name == "Emma").first().id
    db_session.add(
        AgentDeliverable(
            execution_id=execution.id,
            agent_id=emma_pk,
            deliverable_type="research_analyst_uc_digest",
            # Forme reelle d'un digest d'Emma : `is_digest_valid` exige
            # `by_requirement` et refuse tout ce qui porte `raw`/`parse_error`.
            content=json.dumps(
                {
                    "content": {
                        "by_requirement": {
                            "BR-001": {
                                "summary": "SYNTHESE EMMA DEJA PRODUITE",
                                "use_cases": ["UC-001-01", "UC-001-02"],
                            }
                        },
                        "total_use_cases": 3,
                    },
                    "metadata": {"tokens_used": 4242},
                }
            ),
        )
    )

    db_session.commit()
    db_session.refresh(execution)
    return {"user": user, "project": project, "execution": execution}


@pytest.fixture
def agents_traces(monkeypatch):
    """Enregistre les appels d'agents et arrete la course a l'entree de Marcus."""
    appels = []

    async def _faux_run_agent(self, agent_id, mode=None, input_data=None, **kwargs):
        appels.append(agent_id)
        if agent_id == "architect":
            raise ArretControle("Marcus atteint — on a vu ce qu'il fallait voir")
        return {
            "success": True,
            "output": {
                "content": {"digest": "digest recalcule"},
                "metadata": {"tokens_used": 1},
            },
        }

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_agent", _faux_run_agent)

    async def _pas_de_metadata_sf(self, execution_id, project=None):
        return {"success": False, "error": "test", "full_metadata": {}, "summary": {}}

    monkeypatch.setattr(
        PMOrchestratorServiceV2, "_get_salesforce_metadata", _pas_de_metadata_sf
    )
    return appels


async def _reprendre(db_session, contexte, resume_from):
    service = PMOrchestratorServiceV2(db_session)
    return await service.execute_workflow(
        execution_id=contexte["execution"].id,
        project_id=contexte["project"].id,
        selected_agents=["pm", "ba", "architect"],
        resume_from=resume_from,
    )


# --------------------------------------------------------------------------
# Les deux points de reprise sont reconnus
# --------------------------------------------------------------------------

def test_phase2_5_et_phase3_sont_des_points_de_reprise():
    """Sans eux, un echec de Marcus detruit le travail d'Olivia."""
    assert "phase2_5" in SDS_RESUME_POINTS
    assert "phase3" in SDS_RESUME_POINTS


# --------------------------------------------------------------------------
# phase2_5 — les UC sont conserves, le digest est refait
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase2_5_ne_rappelle_pas_olivia(db_session, execution_avancee, agents_traces):
    """Le gain principal : les UC deja produits ne sont pas repayes."""
    await _reprendre(db_session, execution_avancee, "phase2_5")

    assert "ba" not in agents_traces, (
        f"Olivia a ete rappelee alors que ses UC sont en base : {agents_traces}"
    )


@pytest.mark.asyncio
async def test_phase2_5_rappelle_bien_emma(db_session, execution_avancee, agents_traces):
    """Controle positif : c'est le digest qu'on refait, sinon la reprise ne
    servirait a rien."""
    await _reprendre(db_session, execution_avancee, "phase2_5")

    assert "research_analyst" in agents_traces, (
        f"Emma n'a pas ete rappelee : {agents_traces}"
    )


@pytest.mark.asyncio
async def test_phase2_5_atteint_marcus(db_session, execution_avancee, agents_traces):
    """La reprise doit continuer la chaine, pas s'arreter au digest."""
    await _reprendre(db_session, execution_avancee, "phase2_5")

    assert "architect" in agents_traces, (
        f"la chaine ne se poursuit pas jusqu'a Marcus : {agents_traces}"
    )


@pytest.mark.asyncio
async def test_phase2_5_refuse_de_partir_sans_uc(db_session, execution_avancee, agents_traces):
    """Regle 5 — pas de repli silencieux. Reprendre en phase 2.5 sans UC en base
    n'a pas de sens : Emma analyserait le vide et Marcus concevrait sur du vent.
    Il faut le dire, pas produire un SDS creux."""
    db_session.query(DeliverableItem).filter(
        DeliverableItem.execution_id == execution_avancee["execution"].id
    ).delete()
    db_session.commit()

    resultat = await _reprendre(db_session, execution_avancee, "phase2_5")

    assert resultat["success"] is False
    assert "use case" in resultat["error"].lower() or "uc" in resultat["error"].lower()
    assert "research_analyst" not in agents_traces


# --------------------------------------------------------------------------
# phase3 — UC et digest conserves, Marcus seul reprend
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase3_ne_rappelle_ni_olivia_ni_emma(db_session, execution_avancee, agents_traces):
    """Le cas nomme par la specification : Marcus echoue a son 4e appel. Avant,
    la seule reprise possible etait `phase2` — donc tous les UC repayes."""
    await _reprendre(db_session, execution_avancee, "phase3")

    assert "ba" not in agents_traces, f"Olivia rappelee : {agents_traces}"
    assert "research_analyst" not in agents_traces, (
        f"Emma rappelee alors que son digest est en base : {agents_traces}"
    )


@pytest.mark.asyncio
async def test_phase3_atteint_marcus(db_session, execution_avancee, agents_traces):
    await _reprendre(db_session, execution_avancee, "phase3")

    assert agents_traces == ["architect"], (
        f"seul Marcus devait etre appele : {agents_traces}"
    )


@pytest.mark.asyncio
async def test_phase3_relit_le_digest_en_base(db_session, execution_avancee, monkeypatch):
    """Marcus doit recevoir le digest d'Emma **relu**, pas un dictionnaire vide.

    Sans cette relecture, la reprise `phase3` serait pire que `phase2` : Marcus
    concevrait sans la synthese des UC, en silence.
    """
    recus = {}

    async def _capture(self, agent_id, mode=None, input_data=None, **kwargs):
        if agent_id == "architect":
            recus["input_data"] = input_data
            raise ArretControle("capture faite")
        return {"success": True, "output": {"content": {}, "metadata": {}}}

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_agent", _capture)

    async def _pas_de_metadata_sf(self, execution_id, project=None):
        return {"success": False, "error": "test", "full_metadata": {}, "summary": {}}

    monkeypatch.setattr(
        PMOrchestratorServiceV2, "_get_salesforce_metadata", _pas_de_metadata_sf
    )

    await _reprendre(db_session, execution_avancee, "phase3")

    charge = json.dumps(recus.get("input_data", {}), ensure_ascii=False)
    assert "SYNTHESE EMMA DEJA PRODUITE" in charge, (
        "le digest d'Emma n'a pas ete relu depuis la base — Marcus concevrait "
        f"sans la synthese des UC. Recu : {charge[:400]}"
    )


@pytest.mark.asyncio
async def test_phase3_sans_digest_le_dit_et_continue_sur_les_uc_bruts(
    db_session, execution_avancee, agents_traces, caplog
):
    """Regle 5 sur un cas limite : reprendre en `phase3` alors qu'aucun digest
    n'est en base.

    Continuer est le bon choix — Marcus sait travailler sur les UC bruts, c'est
    le repli deja prevu quand Emma echoue. Mais le taire ne l'est pas : sans
    trace, un SDS de moindre qualite serait indistinguable d'un SDS nominal.
    """
    db_session.query(AgentDeliverable).filter(
        AgentDeliverable.execution_id == execution_avancee["execution"].id
    ).delete()
    db_session.commit()

    with caplog.at_level("WARNING"):
        await _reprendre(db_session, execution_avancee, "phase3")

    assert "architect" in agents_traces, "Marcus doit tout de meme travailler"
    assert any(
        "AUCUN digest" in r.message or "aucun digest" in r.message.lower()
        for r in caplog.records
    ), "l'absence de digest doit laisser une trace"


@pytest.mark.asyncio
async def test_phase3_refuse_de_partir_sans_uc(db_session, execution_avancee, agents_traces):
    """Meme regle qu'en phase 2.5 : sans UC, il n'y a rien a concevoir."""
    db_session.query(DeliverableItem).filter(
        DeliverableItem.execution_id == execution_avancee["execution"].id
    ).delete()
    db_session.commit()

    resultat = await _reprendre(db_session, execution_avancee, "phase3")

    assert resultat["success"] is False
    assert "architect" not in agents_traces


# --------------------------------------------------------------------------
# Non-regression : le demarrage normal appelle toujours tout le monde
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_un_demarrage_normal_repart_de_sophie(
    db_session, execution_avancee, agents_traces
):
    """Controle de non-regression : sans `resume_from`, rien n'est saute.

    La course s'arrete a la porte de validation des BR — comportement normal et
    voulu quand `ba` est dans `selected_agents` : le client valide les BR avant
    qu'Olivia ne travaille. Ce qui compte ici est que Sophie ait bien ete
    rappelee, donc qu'aucune phase n'ait ete sautee.
    """
    resultat = await _reprendre(db_session, execution_avancee, None)

    assert agents_traces == ["pm"], (
        f"Sophie doit ouvrir la marche, et seule : {agents_traces}"
    )
    assert resultat["status"] == "waiting_br_validation"


@pytest.mark.asyncio
async def test_phase2_rejoue_bien_olivia(db_session, execution_avancee, agents_traces):
    """Controle de non-regression sur le point de reprise existant : `phase2`
    doit continuer de rappeler Olivia. C'est la reprise couteuse que `phase2_5`
    et `phase3` viennent eviter, pas remplacer."""
    await _reprendre(db_session, execution_avancee, "phase2")

    assert "ba" in agents_traces, f"Olivia doit etre rejouee en phase2 : {agents_traces}"
    assert "pm" not in agents_traces, "la phase 1 doit rester sautee"


# --------------------------------------------------------------------------
# §3.1 — la reprise automatique (BUG-010) applique la meme regle
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_reprise_apres_olivia_ne_rejoue_pas_olivia(
    db_session, execution_avancee, agents_traces
):
    """`checkpoint_map` disait `phase2_ba -> phase2`, commentaire a l'appui :
    « re-run Phase 2 (UCs in DB, safe to redo) ». Sans danger, oui — mais
    entierement repaye. Olivia a fini : on reprend a la suite, pas a elle."""
    execution_avancee["execution"].last_completed_phase = "phase2_ba"
    db_session.commit()

    await _reprendre(db_session, execution_avancee, None)

    assert "ba" not in agents_traces, (
        f"Olivia rejouee alors que son checkpoint est pose : {agents_traces}"
    )
    assert "research_analyst" in agents_traces, (
        f"la reprise doit repartir d'Emma : {agents_traces}"
    )


@pytest.mark.asyncio
async def test_auto_reprise_apres_emma_ne_rejoue_ni_olivia_ni_emma(
    db_session, execution_avancee, agents_traces
):
    """`phase2_5_emma -> phase2` refaisait les deux. Emma a fini : Marcus suit."""
    execution_avancee["execution"].last_completed_phase = "phase2_5_emma"
    db_session.commit()

    await _reprendre(db_session, execution_avancee, None)

    assert agents_traces == ["architect"], (
        f"seul Marcus devait reprendre : {agents_traces}"
    )


@pytest.mark.asyncio
async def test_auto_reprise_apres_sophie_repart_d_olivia(
    db_session, execution_avancee, agents_traces
):
    """Controle de non-regression : `phase1_pm -> phase2` reste juste."""
    execution_avancee["execution"].last_completed_phase = "phase1_pm"
    db_session.commit()

    await _reprendre(db_session, execution_avancee, None)

    assert "pm" not in agents_traces, "Sophie a fini, elle ne doit pas rejouer"
    assert "ba" in agents_traces, f"Olivia doit reprendre : {agents_traces}"


def test_tous_les_points_de_la_carte_de_reprise_sont_valides(db_session):
    """Garde-fou : depuis §3.5 une valeur inconnue leve. Une entree fausse dans
    `checkpoint_map` ferait donc echouer toute reprise automatique, au lieu de
    degrader en silence. Le contrat doit etre verifie, pas suppose."""
    import inspect

    from app.services import pm_orchestrator_service_v2 as module

    source = inspect.getsource(module.PMOrchestratorServiceV2.execute_workflow)
    debut = source.index("checkpoint_map = {")
    fin = source.index("}", debut)
    bloc = source[debut:fin]

    valeurs = set()
    for ligne in bloc.splitlines()[1:]:
        if ":" not in ligne:
            continue
        valeur = ligne.split(":", 1)[1].split("#")[0].strip().rstrip(",").strip()
        if valeur and valeur != "None":
            valeurs.add(valeur.strip('"').strip("'"))

    assert valeurs, "carte de reprise introuvable"
    inconnues = valeurs - SDS_RESUME_POINTS
    assert not inconnues, (
        f"checkpoint_map pointe des valeurs que execute_workflow refuse : "
        f"{sorted(inconnues)}"
    )
