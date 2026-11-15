"""REPRISE-BUILD-001 — une phase deja deployee n'est pas refaite a la relance.

BUILD exec 185 (15/11/2026) : apres l'echec de la phase 2, la relance a
regenere la phase 1. Raj n'etant pas deterministe, le nouveau plan
redeclarait une liste de valeurs deja deployee sous d'autres noms d'API, et
Salesforce a refuse (« Duplicate label: Économie »). La phase deployee est
desormais reprise telle quelle : son registre est recharge pour les phases
suivantes, rien n'est regenere ni redeploye.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.services.phased_build_executor import PhasedBuildExecutor

SNAPSHOT_PHASE1 = {"operations": [
    {"type": "create_object", "api_name": "Market_Signal__c"},
    {"type": "create_field", "object": "Market_Signal__c", "api_name": "Signal_Type__c"},
]}

TACHES = [
    {"task_id": "TASK-004", "task_type": "dev_data_model", "assigned_agent": "admin", "name": "Modele"},
    {"task_id": "TASK-020", "task_type": "dev_apex", "assigned_agent": "apex", "name": "Apex"},
]


def _executeur(phases_deployees, taches_terminees=True):
    ex = PhasedBuildExecutor(project_id=1, execution_id=185, db=MagicMock())
    ex.jordan_service = MagicMock()
    ex.jordan_service.generate_final_package_xml = AsyncMock(return_value={})
    ex._charger_phases_deployees = MagicMock(return_value=phases_deployees)
    ex._taches_toutes_terminees = MagicMock(return_value=taches_terminees)
    ex._update_phase_status = AsyncMock()
    ex._sauver_phase_deployee = MagicMock()
    ex.group_tasks_by_phase = MagicMock(return_value={1: [TACHES[0]], 2: [TACHES[1]]})
    vus = []

    async def _phase(conf, taches):
        vus.append(conf["phase"])
        return {"success": True, "deployed_components": [], "aggregated_snapshot": {"operations": []}}
    ex.execute_phase = _phase
    return ex, vus


def test_phase_deployee_reprise_sans_regeneration():
    ex, vus = _executeur({1: SNAPSHOT_PHASE1})
    res = asyncio.run(ex.execute_build(TACHES))
    assert vus == [2], "la phase 1 deja deployee ne doit pas etre regeneree"
    assert res["phases_completed"] == 2 and res["success"]
    assert res["phase_results"][1]["reprise"] == "deja_deployee"
    assert "Market_Signal__c" in ex.context_registry.generated_objects, \
        "le registre de la phase 1 doit etre recharge pour Diego"
    ex._sauver_phase_deployee.assert_called_once_with(2, {"operations": []})


def test_phase_refaite_si_taches_non_terminees():
    ex, vus = _executeur({1: SNAPSHOT_PHASE1}, taches_terminees=False)
    asyncio.run(ex.execute_build(TACHES))
    assert vus == [1, 2]


def test_sans_sauvegarde_tout_est_execute():
    ex, vus = _executeur({})
    asyncio.run(ex.execute_build(TACHES))
    assert vus == [1, 2]


def test_champs_d_objet_standard_visibles_dans_le_contexte():
    from app.services.phase_context_registry import PhaseContextRegistry
    r = PhaseContextRegistry()
    r.register_batch_output(1, {"operations": [
        {"type": "create_field", "object": "Lead", "api_name": "Score__c"}]})
    assert "Score__c" in r.get_full_data_model()
