"""
Vague B — lot B7 : une seule source pour les tiers.

Defaut constate (vague A, confirme par lecture le 03/09) :
  - `frontend/src/pages/Pricing.tsx` porte des chiffres de credits et de prix
    en dur, tous perimes par rapport a `tier_config` : Free "500 credits / mo"
    (reel : 300/jour, colonne `daily_credits_cap`), Team "50 000 credits / mo"
    (reel : 100 000, `monthly_credits`), FAQ "~800 credits" pour un SDS
    (mesure D1, 28/08 : ~1200).
  - `backend/prompts/agents/sophie_pm.yaml` (bloc `concierge.prompt`) annonce
    "e79 / month ... 2 SDS / month" et "e1,490 / month" en dur.
  - `GET /api/subscription/tiers` (`app/api/routes/subscription.py`) existe
    deja et est deja public (aucun `Depends(get_current_user)`, mesure par
    lecture de la route) — mais il lit `TIER_FEATURES`, un dict Python en
    dur dans `app/models/subscription.py`, jamais la table `tier_config`.
    Il n'y a donc PAS de nouveau fichier `public_tiers.py` : cet endpoint est
    reutilise et corrige pour lire `tier_config` (D9), comme demande par la
    mission si l'endpoint public existe deja.

Decision D9 (03/09) : la verite des tiers est la table `tier_config`, lue
par l'API ; plus de chiffre en dur nulle part ailleurs.

Ce fichier etablit, dans l'ordre :
  (a) `test_get_tiers_lit_tier_config_...` — l'API rend les chiffres
      (monthly_credits, daily_credits_cap, price_eur_monthly, description)
      exactement comme seedes dans `tier_config` sur la base jetable, sans
      jeton (endpoint public).
  (a-neg) `test_get_tiers_reflete_une_mutation_...` — le test modifie une
      valeur dans `tier_config` (une valeur volontairement differente de la
      constante `TIER_FEATURES["pro"]["price"] == 79` en dur dans
      `app/models/subscription.py`) et verifie que l'API la reflete : c'est
      la preuve que la source est la table, pas le code. Controle negatif
      inclus dans la meme assertion : la reponse ne vaut jamais 79 (valeur
      TIER_FEATURES) une fois la table mutee a 199.
  (b) `test_pricing_tsx_...` / `test_sophie_pm_yaml_...` — un test source :
      ni `Pricing.tsx` ni `sophie_pm.yaml` ne doivent plus contenir de
      litteral de credits ou de prix. Deux regex : une ciblee (nombre
      accole a "credits"/"credit"/"e"/"EUR", ou quota "N SDS/mois"), une
      generique (tout nombre nu de 3 chiffres ou plus, hors annees). Les
      faux positifs de la seconde ont ete mesures par
      `grep -noE '.{25}[0-9]{3,}.{15}' <fichier>` AVANT tout correctif (voir
      `_ALLOWED_BARE_NUMBERS` ci-dessous) et documentes un par un : aucun
      n'est un prix ni un compte de credits.

(c) Test de rendu frontend (`Pricing.tsx` compare a une reponse API simulee) :
    absent. `frontend/package.json` ne declare aucun script de test
    (`grep -n '"scripts"' -A 15 package.json` : dev/build/lint/preview/deploy
    seulement, ni `vitest` ni `jest` ni `@testing-library/*` en dependance).
    Aucun runner frontend dans ce depot pour l'executer. Retenu : (a) + (b).
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.models.credit import TierConfig
from app.models.subscription import TIER_FEATURES, SubscriptionTier

# ---------------------------------------------------------------------------
# (a) — l'API publique lit tier_config
# ---------------------------------------------------------------------------

# Etat attendu de `tier_config` apres les migrations 008 (seed) + 010 (Pro
# 2 000 -> 15 000 credits) + 012 (Pro 49 -> 79 EUR, description realignee) —
# lu par lecture des trois migrations, pas suppose. Rejoue ici sur la base
# jetable (regle 4 : mesurer, ne pas reprendre d'un document) via
# `Base.metadata.create_all` (fixture `db_session` de conftest.py) : cette
# fixture ne rejoue PAS les migrations de donnees, donc le seed doit etre
# ecrit explicitement — c'est le meme choix que `tests/test_vague_b_b1_credits.py`
# (fixture `socle_credits`).
_TIER_CONFIG_APRES_012 = [
    dict(
        tier_name="free",
        monthly_credits=0,
        daily_credits_cap=300,
        price_eur_monthly=Decimal("0.00"),
        description="Decouverte — Sophie + Olivia, 300 credits/jour cap strict",
    ),
    dict(
        tier_name="pro",
        monthly_credits=15000,
        daily_credits_cap=None,
        price_eur_monthly=Decimal("79.00"),
        description="Equipe complete + upload, Sonnet par defaut, 15000 credits/mois inclus",
    ),
    dict(
        tier_name="team",
        monthly_credits=100000,
        daily_credits_cap=None,
        price_eur_monthly=Decimal("1490.00"),
        description="Sandbox + BUILD + Opus opt-in, 100k credits/mois",
    ),
]


@pytest.fixture
def tier_config_seed(db_session):
    db_session.add_all(
        [TierConfig(**row) for row in _TIER_CONFIG_APRES_012]
    )
    db_session.commit()
    return _TIER_CONFIG_APRES_012


def test_get_tiers_est_public_et_lit_tier_config(client, tier_config_seed):
    """Sans jeton : l'endpoint deja public rend les chiffres de `tier_config`."""
    reponse = client.get("/api/subscription/tiers")
    assert reponse.status_code == 200, reponse.text

    par_tier = {t["tier"]: t for t in reponse.json()["tiers"]}

    assert par_tier["free"]["monthly_credits"] == 0
    assert par_tier["free"]["daily_credits_cap"] == 300
    assert par_tier["free"]["credits"] == 300
    assert par_tier["free"]["credits_period"] == "day"
    assert float(par_tier["free"]["price_eur_monthly"]) == 0.0

    assert par_tier["pro"]["monthly_credits"] == 15000
    assert par_tier["pro"]["daily_credits_cap"] is None
    assert par_tier["pro"]["credits"] == 15000
    assert par_tier["pro"]["credits_period"] == "month"
    assert float(par_tier["pro"]["price_eur_monthly"]) == 79.0
    assert "15000 credits" in par_tier["pro"]["description"]

    assert par_tier["team"]["monthly_credits"] == 100000
    assert float(par_tier["team"]["price_eur_monthly"]) == 1490.0

    # Enterprise n'a pas de ligne dans tier_config (seed 008 : free/pro/team
    # seulement) — reste "sur devis", jamais un chiffre invente.
    assert par_tier["enterprise"]["price_eur_monthly"] is None
    assert par_tier["enterprise"]["monthly_credits"] is None


def test_get_tiers_reflete_une_mutation_de_tier_config_pas_de_tier_features(
    client, db_session, tier_config_seed
):
    """Preuve que la source est la table, pas le code (D9).

    `TIER_FEATURES["pro"]["price"]` vaut 79 en dur dans
    `app/models/subscription.py`. On mute `tier_config.pro.price_eur_monthly`
    a une valeur differente (199) et on verifie que l'API la reflete —
    et ne retombe jamais sur 79.
    """
    valeur_en_dur = TIER_FEATURES[SubscriptionTier.PRO]["price"]
    assert valeur_en_dur == 79, (
        "cette assertion fixe l'hypothese du test : si TIER_FEATURES change, "
        "adapter la valeur de mutation ci-dessous pour qu'elle reste differente"
    )

    ligne_pro = (
        db_session.query(TierConfig).filter_by(tier_name="pro").one()
    )
    ligne_pro.price_eur_monthly = Decimal("199.00")
    ligne_pro.monthly_credits = 42424
    db_session.commit()

    reponse = client.get("/api/subscription/tiers")
    assert reponse.status_code == 200, reponse.text
    pro = next(t for t in reponse.json()["tiers"] if t["tier"] == "pro")

    assert float(pro["price_eur_monthly"]) == 199.0
    assert pro["monthly_credits"] == 42424
    # Controle negatif : la valeur TIER_FEATURES en dur (79) ne doit
    # apparaitre nulle part dans la reponse pour ce champ.
    assert float(pro["price_eur_monthly"]) != valeur_en_dur


# ---------------------------------------------------------------------------
# (b) — test source : plus de litteral de credits ni de prix
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
PRICING_TSX = REPO_ROOT / "frontend" / "src" / "pages" / "Pricing.tsx"
SOPHIE_PM_YAML = REPO_ROOT / "backend" / "prompts" / "agents" / "sophie_pm.yaml"

# Regex A — nombre directement accole a un prix ou des credits :
#   "500 credits", "15 000 crédits", "79€", "€79", "1 490€", "2 SDS / month".
_CREDIT_OR_PRICE = re.compile(
    r"\d[\d.,\s]*\d\s*(cr[ée]dits?|€|eur\b)"
    r"|\d\s*(cr[ée]dits?|€|eur\b)"
    r"|€\s*\d"
    r"|\d+\s*sds\s*/\s*(mois|month)",
    re.IGNORECASE,
)

# Regex B — nombre nu de 3 chiffres ou plus (le garde-fou generique demande
# par la mission, "\d{3,} hors dates").
_BARE_NUMBER = re.compile(r"\b\d{3,}\b")

# Faux positifs mesures le 03/09 sur les fichiers AVANT correctif
# (`grep -noE '.{25}[0-9]{3,}.{15}' <fichier>`), colles ici avec leur
# justification — aucun n'est un prix ni un compte de credits tier_config :
#
#   Pricing.tsx:
#     "100"  -> FEATURES "Max BRs per project" du tier Pro (limite de
#               fonctionnalite portee par TIER_FEATURES/FEATURES front, pas
#               par tier_config — D9 ne couvre que credits/prix).
#     "400"  -> classe Tailwind `text-red-400` / `border-red-400` /
#               `bg-red-400` de la banniere d'erreur de chargement des tiers
#               (nuance de couleur, pas un prix).
#     "001"  -> commentaire `ONBOARDING-001`, identifiant de ticket.
#
#   sophie_pm.yaml:
#     "001"/"002"/"003" -> exemples de format d'identifiant dans les
#               instructions Olivia/Marcus/Emma ("BR-001, BR-002",
#               "ARCH-001", "GAP-001", "WBS-001", "ASIS-001") — jamais un
#               credit ni un prix.
#     "2024"/"2026"     -> dates (exemple de diagramme Gantt Marcus,
#               commentaire d'arbitrage Sam) — exclues comme annees.
#     "8000"/"16000"/"500" -> `max_tokens` de configuration LLM (Olivia,
#               Marcus/consolidator, concierge) — un budget de jetons, pas
#               un credit utilisateur ni un prix.
_ALLOWED_BARE_NUMBERS = {
    PRICING_TSX: {"100", "400", "001"},
    SOPHIE_PM_YAML: {"001", "002", "003", "2024", "2026", "8000", "16000", "500"},
}


def _matches(pattern: re.Pattern, text: str) -> list[str]:
    return [m.group(0) for m in pattern.finditer(text)]


def _bare_number_offenders(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    allowed = _ALLOWED_BARE_NUMBERS.get(path, set())
    return [n for n in _matches(_BARE_NUMBER, text) if n not in allowed]


def test_pricing_tsx_ne_contient_plus_de_credits_ou_prix_en_dur():
    text = PRICING_TSX.read_text(encoding="utf-8")
    offenders = _matches(_CREDIT_OR_PRICE, text)
    assert offenders == [], f"litteraux credits/prix trouves dans Pricing.tsx : {offenders}"


def test_pricing_tsx_pas_de_nombre_nu_non_explique():
    offenders = _bare_number_offenders(PRICING_TSX)
    assert offenders == [], f"nombres non explique dans Pricing.tsx : {offenders}"


def test_sophie_pm_yaml_ne_contient_plus_de_credits_ou_prix_en_dur():
    text = SOPHIE_PM_YAML.read_text(encoding="utf-8")
    offenders = _matches(_CREDIT_OR_PRICE, text)
    assert offenders == [], f"litteraux credits/prix trouves dans sophie_pm.yaml : {offenders}"


def test_sophie_pm_yaml_pas_de_nombre_nu_non_explique():
    offenders = _bare_number_offenders(SOPHIE_PM_YAML)
    assert offenders == [], f"nombres non explique dans sophie_pm.yaml : {offenders}"


def test_sophie_pm_yaml_porte_l_espace_reserve_d_injection():
    """L'injection dynamique (lecture de tier_config au moment de l'appel) se
    ferait dans `sophie_concierge_service.py` (hors perimetre B7 — B1/B8).
    Ce test verifie seulement que le prompt porte l'espace reserve nomme
    attendu par `tier_config_service.get_tier_summary_text()`.
    """
    text = SOPHIE_PM_YAML.read_text(encoding="utf-8")
    assert "{{tier_summary}}" in text
