"""Tout modele Anthropic route par llm_routing.yaml doit avoir un tarif credits.

05/11/2026 : sans ligne `model_pricing`, un modele est refuse a la reservation
(`UnknownModelError`). Basculer le YAML sans migration coupait le palier Pro,
et rien ne le signalait avant le premier appel client. Ce test lit le VRAI
YAML et les migrations Alembic : la prochaine bascule echouera ici, pas chez
un client.
"""
import re
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]


def _modeles_anthropic_routes():
    conf = yaml.safe_load((RACINE / "config" / "llm_routing.yaml").read_text(encoding="utf-8"))
    modeles = conf["providers"]["anthropic"]["models"]
    alias_routes = set()
    for profil in conf["profiles"].values():
        if not isinstance(profil, dict):
            continue
        for cible in profil.values():
            if isinstance(cible, str) and cible.startswith("anthropic/"):
                alias_routes.add(cible.split("/", 1)[1])
    return {modeles[a]["model_id"] for a in alias_routes if a in modeles}


def _modeles_tarifes_par_les_migrations():
    texte = "\n".join(p.read_text(encoding="utf-8")
                      for p in (RACINE / "alembic" / "versions").glob("*.py"))
    return set(re.findall(r"claude-[a-z]+-[0-9][0-9a-z.-]*", texte))


def test_chaque_modele_anthropic_route_a_un_tarif_seme_par_migration():
    routes = _modeles_anthropic_routes()
    assert routes, "aucun modele Anthropic route : le test ne prouverait rien"
    manquants = routes - _modeles_tarifes_par_les_migrations()
    assert not manquants, f"modeles routes sans tarif model_pricing : {sorted(manquants)}"


def test_les_modeles_5_5_sont_routes():
    routes = _modeles_anthropic_routes()
    assert "claude-opus-5-5" in routes and "claude-sonnet-5-5" in routes
