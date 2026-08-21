"""
LOT-D — Regressions Business Analyst (Olivia).

Constats couverts :
  - kim:PROD-01  : `_execute` ne construit pas de prompt en mode mono-BR
                   (pas de branche `else` apres `if batch_mode`) -> NameError.
                   L'orchestrateur envoie les BR par lots de 2, donc tout projet
                   a nombre IMPAIR de BR termine sur un lot d'un seul BR.
  - cla:CRASH-03 : `_parse_response` renvoie `parsed_content` / `uc_count`
                   jamais affectes quand la reponse n'est pas au format batch
                   (`{"results": [...]}`) ou quand le json_cleaner est absent
                   -> UnboundLocalError.

Tests purement unitaires : l'appel LLM est mocke, aucune base ni cle API.
"""

import json

import pytest

from agents.roles import salesforce_business_analyst as ba_mod
from agents.roles.salesforce_business_analyst import BusinessAnalystAgent

# Le meme decoupage que pm_orchestrator_service_v2.py (BATCH_SIZE = 2).
BATCH_SIZE = 2

BRS = [
    {
        "id": "BR-001",
        "title": "Creation automatique du compte client",
        "description": "Le systeme doit creer un compte a la signature du devis.",
        "category": "AUTOMATION",
        "stakeholder": "Sales Rep",
    },
    {
        "id": "BR-002",
        "title": "Notification du responsable de secteur",
        "description": "Le responsable recoit une alerte a chaque nouveau compte.",
        "category": "AUTOMATION",
        "stakeholder": "Sales Manager",
    },
    {
        "id": "BR-003",
        "title": "Reporting mensuel des signatures",
        "description": "Un rapport mensuel consolide les devis signes.",
        "category": "REPORTING",
        "stakeholder": "Direction",
    },
]


def _fake_uc(br_id: str, idx: int) -> dict:
    """Un UC minimal mais structurellement complet."""
    num = br_id.split("-")[-1]
    return {
        "id": f"UC-{num}-{idx:02d}",
        "title": f"Use case {idx} de {br_id}",
        "actor": "Sales Rep",
        "trigger": "User clicks Save",
        "main_flow": ["1. User does X", "2. System validates Y"],
        "alt_flows": ["1a. If validation fails: show error"],
        "acceptance_criteria": ["GIVEN X WHEN Y THEN Z"],
        "sf_objects": ["Account"],
        "sf_fields": ["Account.Name"],
        "sf_automation": "Flow",
    }


def _install_fake_llm(monkeypatch, seen_prompts):
    """Mocke `_call_llm` : repond au format demande par le prompt recu.

    Le faux LLM lit le prompt pour savoir quels BR lui sont soumis, exactement
    comme le ferait le vrai. Si le prompt est vide/absent, le test echoue avant
    meme d'arriver ici (c'est le NameError de PROD-01).
    """

    def fake_call_llm(self, prompt, system_prompt, execution_id=0):
        seen_prompts.append(prompt)
        br_ids = [br["id"] for br in BRS if br["id"] in prompt]
        assert br_ids, f"Aucun BR identifiable dans le prompt: {prompt[:200]!r}"
        if len(br_ids) > 1:
            # Format batch attendu par le prompt `generate_batch`.
            payload = {
                "results": [
                    {"parent_br": br_id, "use_cases": [_fake_uc(br_id, 1)]}
                    for br_id in br_ids
                ]
            }
        else:
            # Format mono attendu par le prompt `generate`.
            payload = {
                "parent_br": br_ids[0],
                "use_cases": [_fake_uc(br_ids[0], 1)],
            }
        return (json.dumps(payload), 1200, 800, "claude-test", "anthropic", 0.0012)

    monkeypatch.setattr(BusinessAnalystAgent, "_call_llm", fake_call_llm)
    monkeypatch.setattr(
        BusinessAnalystAgent, "_log_interaction", lambda self, **kwargs: None
    )
    monkeypatch.setattr(
        BusinessAnalystAgent,
        "_get_rag_context",
        lambda self, br, project_id=0: "",
    )


def _run_batch(agent, batch):
    """Reproduit exactement l'appel de pm_orchestrator_service_v2 (l.536-539)."""
    if len(batch) > 1:
        input_data = {"business_requirements": batch}
    else:
        input_data = {"business_requirement": batch[0]}
    return agent.run(
        {
            "mode": "generate_uc",
            "input_content": json.dumps(input_data),
            "execution_id": 0,
            "project_id": 0,
        }
    )


# ---------------------------------------------------------------------------
# CRITERE DE FIN : un SDS a 3 BR produit 3 UC complets
# ---------------------------------------------------------------------------
def test_sds_3_brs_produit_3_uc_complets(monkeypatch):
    """kim:PROD-01 — nombre IMPAIR de BR : le dernier lot ne contient qu'un BR."""
    seen_prompts = []
    _install_fake_llm(monkeypatch, seen_prompts)
    agent = BusinessAnalystAgent()

    ucs_par_br = {}
    for i in range(0, len(BRS), BATCH_SIZE):
        batch = BRS[i : i + BATCH_SIZE]
        result = _run_batch(agent, batch)

        assert result.get("success") is True, (
            f"Lot {[br['id'] for br in batch]} en echec: {result.get('error')!r}"
        )
        content = result["content"]
        assert isinstance(content, dict), f"content non parse: {content!r}"
        assert "parse_error" not in content, content
        for uc in content.get("use_cases", []):
            parent = uc.get("parent_br", content.get("parent_br", result["parent_br"]))
            ucs_par_br.setdefault(parent, []).append(uc)

        assert result["metadata"]["uc_count"] == len(batch), (
            f"uc_count={result['metadata']['uc_count']} pour un lot de {len(batch)} BR"
        )

    assert sorted(ucs_par_br) == ["BR-001", "BR-002", "BR-003"], (
        f"UC manquants pour certains BR: {sorted(ucs_par_br)}"
    )
    for br_id, ucs in ucs_par_br.items():
        assert ucs, f"{br_id} n'a aucun UC"
        for uc in ucs:
            for champ in ("id", "title", "main_flow", "acceptance_criteria"):
                assert uc.get(champ), f"{br_id}: UC incomplet, champ '{champ}' vide"

    # 2 lots => 2 appels LLM ; le second est le lot mono-BR.
    assert len(seen_prompts) == 2, seen_prompts
    assert "BR-003" in seen_prompts[1]
    assert "BR-001" not in seen_prompts[1]


# ---------------------------------------------------------------------------
# kim:PROD-01 — isolation du chemin mono-BR
# ---------------------------------------------------------------------------
def test_mono_br_construit_bien_son_prompt(monkeypatch):
    """Le chemin mono-BR doit construire un prompt (et non lever NameError)."""
    seen_prompts = []
    _install_fake_llm(monkeypatch, seen_prompts)
    agent = BusinessAnalystAgent()

    result = _run_batch(agent, [BRS[2]])

    erreur = result.get("error", "")
    assert "not defined" not in erreur, f"NameError sur le chemin mono-BR: {erreur}"
    assert result.get("success") is True, erreur
    assert len(seen_prompts) == 1
    prompt = seen_prompts[0]
    assert prompt, "prompt vide en mode mono-BR"
    assert "BR-003" in prompt
    # Le prompt mono-BR n'est PAS le prompt batch.
    assert prompt == ba_mod.get_uc_generation_prompt(BRS[2], "")
    assert result["metadata"]["uc_count"] == 1
    assert result["parent_br"] == "BR-003"


# ---------------------------------------------------------------------------
# cla:CRASH-03 — _parse_response hors format batch
# ---------------------------------------------------------------------------
def test_parse_response_format_mono(monkeypatch):
    """Reponse sans cle 'results' : pas d'UnboundLocalError sur uc_count."""
    agent = BusinessAnalystAgent()
    content = json.dumps(
        {"parent_br": "BR-003", "use_cases": [_fake_uc("BR-003", 1), _fake_uc("BR-003", 2)]}
    )
    parsed, uc_count = agent._parse_response(content, "BR-003", ["BR-003"], False)
    assert uc_count == 2
    assert len(parsed["use_cases"]) == 2


def test_parse_response_sans_json_cleaner(monkeypatch):
    """json_cleaner indisponible : erreur propre, pas d'UnboundLocalError."""
    monkeypatch.setattr(ba_mod, "JSON_CLEANER_AVAILABLE", False)
    agent = BusinessAnalystAgent()
    content = json.dumps({"parent_br": "BR-003", "use_cases": [_fake_uc("BR-003", 1)]})
    parsed, uc_count = agent._parse_response(content, "BR-003", ["BR-003"], False)
    assert isinstance(parsed, dict)
    assert uc_count == 1


def test_parse_response_json_invalide():
    """JSON illisible : on retombe sur le contrat (dict, 0), sans exception."""
    agent = BusinessAnalystAgent()
    parsed, uc_count = agent._parse_response(
        "Je suis desole, je ne peux pas repondre.", "BR-003", ["BR-003"], False
    )
    assert uc_count == 0
    assert "raw" in parsed


def test_parse_response_dict_sans_use_cases():
    """Reponse JSON valide mais sans UC : (dict, 0), sans exception."""
    agent = BusinessAnalystAgent()
    parsed, uc_count = agent._parse_response(
        json.dumps({"parent_br": "BR-003"}), "BR-003", ["BR-003"], False
    )
    assert uc_count == 0
    assert isinstance(parsed, dict)
