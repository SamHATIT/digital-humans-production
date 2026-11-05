"""Cache Anthropic du prompt systeme : eligibilite lue dans llm_routing.yaml (05/11/2026).

Avant : liste en dur dans le code, Marcus seul. Ces tests chargent le VRAI
fichier de routage, pas une copie, pour que la config livree soit celle testee.
"""
from pathlib import Path

import yaml

from app.services.llm_router_service import _should_cache_system

CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "config" / "llm_routing.yaml").read_text(encoding="utf-8")
)


def test_marcus_pro_reste_en_cache():
    assert _should_cache_system("marcus", "pro", CONFIG) is True


def test_olivia_et_emma_pro_sont_desormais_en_cache():
    # rouge avant le 05/11 : seuls les architectes etaient eligibles
    assert _should_cache_system("olivia", "pro", CONFIG) is True
    assert _should_cache_system("research_analyst", "pro", CONFIG) is True


def test_agents_build_team_en_cache():
    assert _should_cache_system("diego", "team", CONFIG) is True
    assert _should_cache_system("jordan", "team", CONFIG) is True


def test_free_jamais_en_cache():
    assert _should_cache_system("olivia", "free", CONFIG) is False
    assert _should_cache_system("marcus", None, CONFIG) is False


def test_agent_inconnu_refuse_et_signale(caplog):
    assert _should_cache_system("agent_fantome", "pro", CONFIG) is False
    assert "agent_fantome" in caplog.text


def test_section_absente_desactive_et_signale(caplog):
    sans = {k: v for k, v in CONFIG.items() if k != "prompt_caching"}
    assert _should_cache_system("marcus", "pro", sans) is False
    assert "prompt_caching" in caplog.text
