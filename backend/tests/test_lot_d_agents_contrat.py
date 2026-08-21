"""
LOT-D — Contrat de sortie des agents.

Constats couverts :
  - kim:PROD-03 / cla:CRASH-02 : `_call_llm` sans branche `else` apres
    `if LLM_SERVICE_AVAILABLE` -> retourne None -> l'appelant deballe un tuple
    et leve `TypeError: cannot unpack non-iterable NoneType`, remonte comme
    "echec agent" generique. Agents concernes : ba, pm, devops, trainer.
    Attendu : echec NET et explicite (RuntimeError) au lieu de None.
  - cla:CRASH-04 : `DevOpsAgent.run` declare le mode "deploy" dans VALID_MODES
    mais ne le dispatche jamais -> retourne None.
  - cla:CRASH-05 : `generate_build` (salesforce_admin) jette la valeur
    `cost_usd` renvoyee par le LLM : le cout du mode BUILD n'est pas trace.

Tests purement unitaires : aucun appel LLM reel, aucune base.
"""

import inspect

import pytest

from agents.roles import salesforce_admin as admin_mod
from agents.roles import salesforce_business_analyst as ba_mod
from agents.roles import salesforce_devops as devops_mod
from agents.roles import salesforce_pm as pm_mod
from agents.roles import salesforce_trainer as trainer_mod


# ---------------------------------------------------------------------------
# kim:PROD-03 / cla:CRASH-02 — jamais None quand le llm_service est absent
# ---------------------------------------------------------------------------
CAS_CALL_LLM = [
    ("ba", ba_mod, "BusinessAnalystAgent", {"prompt": "p", "system_prompt": "s"}),
    (
        "pm",
        pm_mod,
        "PMAgent",
        {
            "prompt": "p",
            "system_prompt": "s",
            "max_tokens": 100,
            "temperature": 0.2,
        },
    ),
    ("devops", devops_mod, "DevOpsAgent", {"prompt": "p"}),
    ("trainer", trainer_mod, "TrainerAgent", {"prompt": "p"}),
]


@pytest.mark.parametrize("nom, module, classe, kwargs", CAS_CALL_LLM)
def test_call_llm_echoue_net_sans_llm_service(monkeypatch, nom, module, classe, kwargs):
    """Sans llm_service : RuntimeError explicite, jamais un None silencieux."""
    monkeypatch.setattr(module, "LLM_SERVICE_AVAILABLE", False)
    agent = getattr(module, classe)()

    with pytest.raises(RuntimeError) as exc:
        agent._call_llm(**kwargs)

    assert "llm" in str(exc.value).lower(), str(exc.value)


@pytest.mark.parametrize("nom, module, classe, kwargs", CAS_CALL_LLM)
def test_call_llm_ne_retourne_jamais_none(monkeypatch, nom, module, classe, kwargs):
    """Le contrat est un tuple deballable ; None casserait l'appelant."""
    monkeypatch.setattr(module, "LLM_SERVICE_AVAILABLE", False)
    agent = getattr(module, classe)()
    try:
        resultat = agent._call_llm(**kwargs)
    except RuntimeError:
        return  # echec net : contrat respecte
    assert resultat is not None, f"{classe}._call_llm a retourne None"
    assert isinstance(resultat, tuple)


# ---------------------------------------------------------------------------
# cla:CRASH-04 — DevOpsAgent.run dispatche le mode deploy
# ---------------------------------------------------------------------------
def test_devops_run_dispatche_le_mode_deploy(monkeypatch):
    appels = []

    def faux_deploy(self, input_content, execution_id, project_id):
        appels.append((input_content, execution_id, project_id))
        return {"success": True, "agent_id": "jordan", "mode": "deploy"}

    monkeypatch.setattr(devops_mod.DevOpsAgent, "_execute_deploy", faux_deploy)
    agent = devops_mod.DevOpsAgent()

    resultat = agent.run(
        {
            "mode": "deploy",
            "input_content": '{"task": {"task_id": "T-1"}, "components": []}',
            "execution_id": 7,
            "project_id": 3,
        }
    )

    assert resultat is not None, "run() en mode deploy a retourne None"
    assert resultat.get("success") is True, resultat
    assert len(appels) == 1, "_execute_deploy n'a pas ete appele"
    assert appels[0][1] == 7 and appels[0][2] == 3


def test_devops_run_dispatche_toujours_le_mode_spec(monkeypatch):
    """Non-regression : le mode spec continue de passer par _execute_spec."""
    appels = []
    monkeypatch.setattr(
        devops_mod.DevOpsAgent,
        "_execute_spec",
        lambda self, i, e, p: appels.append((i, e, p)) or {"success": True},
    )
    agent = devops_mod.DevOpsAgent()
    resultat = agent.run({"mode": "spec", "input_content": "texte", "execution_id": 1})
    assert resultat.get("success") is True
    assert len(appels) == 1


def test_devops_tous_les_modes_valides_sont_dispatches():
    """Tout mode declare dans VALID_MODES doit avoir une branche dans run()."""
    source = inspect.getsource(devops_mod.DevOpsAgent.run)
    doc = devops_mod.DevOpsAgent.run.__doc__ or ""
    source = source.replace(doc, "")  # la docstring cite les modes, pas le code
    for mode in devops_mod.DevOpsAgent.VALID_MODES:
        assert f'mode == "{mode}"' in source, (
            f"mode '{mode}' declare dans VALID_MODES mais non dispatche par run()"
        )


# ---------------------------------------------------------------------------
# cla:CRASH-05 — le cout du mode BUILD est trace
# ---------------------------------------------------------------------------
def test_generate_build_trace_le_cout(monkeypatch):
    monkeypatch.setattr(admin_mod, "LLM_SERVICE_AVAILABLE", True)
    monkeypatch.setattr(admin_mod, "LLM_LOGGER_AVAILABLE", False)
    monkeypatch.setattr(
        admin_mod,
        "generate_llm_response",
        lambda **kwargs: {
            "content": "<?xml version='1.0'?>",
            "tokens_used": 500,
            "input_tokens": 200,
            "model": "claude-test",
            "cost_usd": 0.0421,
        },
    )

    resultat = admin_mod.generate_build(
        task={"task_id": "T-1", "name": "Objet Formation", "description": "d"},
        architecture_context="arch",
        execution_id="42",
    )

    assert resultat["metadata"].get("cost_usd") == pytest.approx(0.0421), (
        f"cout non trace dans generate_build: {resultat['metadata']}"
    )
