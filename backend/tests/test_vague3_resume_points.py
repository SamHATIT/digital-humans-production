"""
VAGUE 3 — reprise d'execution (SPEC_VAGUE3, arbitrages Sam du 23/08).

§3.5 — une valeur de `resume_from` inconnue doit **faire echouer l'appel**,
pas retomber dans la branche generique.

C'est la cause commune des douze defauts : `execute_workflow` ne reconnaissait
que cinq valeurs et laissait tout le reste tomber dans « saute la phase 1,
rejoue a partir de la phase 2 ». Le WARNING de la vague 2 les a rendues
visibles ; il ne les empeche pas. Un point de reprise faux vaut mieux refuse
que devine.
"""
import pytest

from app.services.pm_orchestrator_service_v2 import (
    BUILD_RESUME_POINTS,
    SDS_RESUME_POINTS,
    PMOrchestratorServiceV2,
)


# --------------------------------------------------------------------------
# §3.5 — refus des valeurs inconnues
# --------------------------------------------------------------------------

#: Les onze valeurs mortes relevees par la specification, plus une invention.
#: Aucune ne doit passer en silence.
VALEURS_MORTES = [
    # validation_gate_routes.py:160 — approbation d'une porte
    "phase5_sds",
    "phase6_export",
    "deploy",
    # validation_gate_routes.py:194 — rejet avec annotations
    "phase4_experts",
    "build",
    # retry_routes.py:67 — reprise apres echec d'un agent
    "phase_ba",
    "phase_architect",
    "phase_data",
    "phase_trainer",
    "phase_qa",
    "phase_devops",
    # execution_routes.py:190 — son effet coincidait avec l'intention, par accident
    "phase2_ba",
    # et une valeur qui n'a jamais existe
    "phase42",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("valeur", VALEURS_MORTES)
async def test_une_valeur_inconnue_est_refusee(db_session, valeur):
    """Le defaut : toutes ces valeurs rejouaient depuis la phase 2 en silence."""
    service = PMOrchestratorServiceV2(db_session)

    with pytest.raises(ValueError) as excinfo:
        await service.execute_workflow(
            execution_id=999999, project_id=999999, resume_from=valeur
        )

    message = str(excinfo.value)
    assert valeur in message, "le refus doit nommer la valeur refusee"


@pytest.mark.asyncio
async def test_le_refus_enonce_les_valeurs_valides(db_session):
    """« un message nommant la valeur et la liste des valeurs valides »."""
    service = PMOrchestratorServiceV2(db_session)

    with pytest.raises(ValueError) as excinfo:
        await service.execute_workflow(
            execution_id=999999, project_id=999999, resume_from="phase_architect"
        )

    message = str(excinfo.value)
    for point in SDS_RESUME_POINTS:
        assert point in message, (
            f"le point de reprise valide {point!r} n'est pas cite dans le refus"
        )


@pytest.mark.asyncio
async def test_une_reprise_build_garde_son_message_propre(db_session):
    """Un point de reprise BUILD n'est pas « inconnu » : il est connu, et il
    n'appartient pas a ce workflow. Le message doit orienter, pas seulement
    refuser."""
    service = PMOrchestratorServiceV2(db_session)

    with pytest.raises(ValueError) as excinfo:
        await service.execute_workflow(
            execution_id=999999, project_id=999999, resume_from="build_tasks"
        )

    message = str(excinfo.value)
    assert "execute_build_task" in message
    assert "build_tasks" in message


@pytest.mark.asyncio
async def test_none_reste_le_demarrage_normal(db_session):
    """Controle negatif : `resume_from=None` n'est pas une valeur inconnue.

    La garde est **avant** le `try:` de `execute_workflow`, deliberement : un
    point de reprise faux est une erreur d'appelant, pas un echec d'execution a
    consigner. Une valeur acceptee traverse la garde et rejoint le chemin
    normal, qui lui capte ses erreurs et rend `{"success": False, ...}`.
    """
    service = PMOrchestratorServiceV2(db_session)

    resultat = await service.execute_workflow(
        execution_id=999999, project_id=999999, resume_from=None
    )

    assert resultat["success"] is False
    assert "Project 999999 not found" in resultat["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize("valeur", sorted(SDS_RESUME_POINTS))
async def test_les_points_valides_passent_la_garde(db_session, valeur):
    """Controle positif : chaque point declare valide doit franchir la garde.

    Il echoue ensuite sur le projet introuvable — donc en `{"success": False}`,
    pas en `ValueError`. C'est la difference qu'on teste : refuse a la porte,
    ou accepte puis echoue plus loin.
    """
    service = PMOrchestratorServiceV2(db_session)

    resultat = await service.execute_workflow(
        execution_id=999999, project_id=999999, resume_from=valeur
    )

    assert resultat["success"] is False
    assert "Project 999999 not found" in resultat["error"], (
        f"{valeur!r} est declare valide mais la garde le refuse"
    )


def test_les_deux_vocabulaires_sont_disjoints():
    """Un meme mot ne peut pas etre a la fois reprise SDS et reprise BUILD."""
    assert SDS_RESUME_POINTS & BUILD_RESUME_POINTS == frozenset()
