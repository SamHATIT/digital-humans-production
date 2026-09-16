"""VAGUE 1 / file D — BILL-07 : « prix correct, produit vendu incorrect ».

Constat d'Astra (06/09, L733). La partie frontend (tableau de comparaison
ecrit a la main, « Illimité » sur donnee absente, CTA Pro qui ouvre un modal)
est couverte par `frontend/tests/tierFeatures.test.ts`. Ce fichier porte la
partie serveur : **ce que l'API annonce au client**.

Deux defauts mesures le 16/09 sur `f78e8ad`, dans la reponse de
`GET /api/subscription/tiers` (endpoint public, lu par la page de tarifs) :

  1. `limitations` du Free contenait « Modèle Haiku uniquement », et celles du
     Pro « Modèles Haiku + Sonnet ». Or `backend/config/llm_routing.yaml`,
     profil `cloud` actif en production depuis le 16/09, route le Free sur
     `gpu_nemotron/nemotron` (bloc `tier_overrides`). Le produit vendu nommait
     donc un modele que le client n'obtient pas.

  2. Nommer un modele de langage au client contredit la regle de sortie que
     porte chaque prompt d'agent du depot (`prompts/agents/sophie_pm.yaml`) :
     « ne fais jamais apparaitre le nom d'un modele de langage, d'un
     fournisseur ou d'un outil interne : le client achete un studio, pas une
     chaine d'outils ». Une limitation publique ne peut pas dire au client ce
     que l'agent a interdiction de lui dire.

Alignement retenu (dit dans le rapport de file) : c'est **le discours** qui est
corrige, pas le routage. Changer le routage du Free pour Sonnet serait une
decision commerciale et un cout, hors mandat de cette file ; retirer le nom du
modele rend l'annonce vraie quel que soit le modele servi.
"""
from __future__ import annotations

import re

import pytest

from app.models.subscription import SubscriptionTier, TIER_FEATURES, get_tier_config

# Noms de modeles et de fournisseurs qui n'ont rien a faire dans une annonce
# commerciale. Ecrits ici parce que c'est precisement ce que le test cherche.
NOMS_DE_MODELES = re.compile(
    r"\b(haiku|sonnet|opus|claude|gpt|nemotron|mistral|llama|gemma|qwen|anthropic|openai)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("tier", list(SubscriptionTier))
def test_aucune_limitation_publique_ne_nomme_un_modele(tier):
    config = get_tier_config(tier)
    for limitation in config.get("limitations", []):
        trouve = NOMS_DE_MODELES.search(limitation)
        assert trouve is None, (
            f"le palier {tier.value} annonce « {limitation} » : le nom de modele "
            f"« {trouve.group(0) if trouve else ''} » est a la fois invendable "
            f"(le routage peut changer) et interdit par la regle de sortie client"
        )


@pytest.mark.parametrize("tier", list(SubscriptionTier))
def test_aucun_nom_de_modele_dans_le_tagline_ni_le_nom(tier):
    config = get_tier_config(tier)
    for champ in ("name", "tagline", "price_display"):
        valeur = str(config.get(champ) or "")
        assert NOMS_DE_MODELES.search(valeur) is None, (
            f"{tier.value}.{champ} nomme un modele : {valeur!r}"
        )


def test_controle_negatif_le_motif_reconnait_bien_un_nom_de_modele():
    """Sans ce controle, un motif casse rendrait les tests ci-dessus verts
    quoi qu'annoncent les paliers (regle 2)."""
    assert NOMS_DE_MODELES.search("Modèle Haiku uniquement") is not None
    assert NOMS_DE_MODELES.search("Modèles Haiku + Sonnet. Pas d'Opus.") is not None
    # et il ne mord pas sur une limitation legitime
    assert NOMS_DE_MODELES.search("Pas de génération de code (BUILD)") is None


def test_les_limitations_du_free_restent_informatives():
    """Retirer le nom du modele ne doit pas vider la liste : le Free a de
    vraies limites, et les taire serait le defaut inverse."""
    limitations = get_tier_config(SubscriptionTier.FREE)["limitations"]
    assert len(limitations) >= 3, limitations
    joint = " ".join(limitations).lower()
    assert "upload" in joint or "fichier" in joint
    assert "mémoire" in joint or "memoire" in joint or "stateless" in joint


def test_la_matrice_du_free_reste_celle_du_serveur():
    """Controle de non-regression : ce test echouerait si on « corrigeait » la
    contradiction en alignant le serveur sur la page de tarifs plutot que
    l'inverse. Le Free est un palier de dialogue, pas un palier SDS."""
    free = TIER_FEATURES[SubscriptionTier.FREE]["features"]
    assert free["chat_sophie"] is True
    assert free["chat_olivia"] is True
    assert free["sds_document"] is False
    assert free["build_phase"] is False
    assert free["max_projects"] == 0


def test_le_pro_ne_porte_ni_build_ni_sfdx_ni_git():
    """Les trois lignes que la page de tarifs annoncait au Pro."""
    pro = TIER_FEATURES[SubscriptionTier.PRO]["features"]
    assert pro["build_phase"] is False
    assert pro["sfdx_deployment"] is False
    assert pro["git_integration"] is False
    assert pro["sds_document"] is True


def test_la_route_publique_sert_la_meme_matrice(client):
    """Ce que le client lit reellement — `GET /api/subscription/tiers`, sans jeton."""
    reponse = client.get("/api/subscription/tiers")
    assert reponse.status_code == 200, reponse.text

    par_tier = {ligne["tier"]: ligne for ligne in reponse.json()["tiers"]}
    assert set(par_tier) >= {"free", "pro", "team", "enterprise"}

    free = par_tier["free"]
    assert free["features"]["sds_document"] is False
    assert free["features"]["max_projects"] == 0
    for limitation in free["limitations"]:
        assert NOMS_DE_MODELES.search(limitation) is None, limitation
