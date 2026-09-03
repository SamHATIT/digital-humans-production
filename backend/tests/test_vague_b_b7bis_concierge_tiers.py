"""
Vague B — lot B7-bis : fermer le point laisse « Ouvert » par B7.

B7 (c9effce) a remplace le bloc de prix en dur du prompt concierge de Sophie
(`backend/prompts/agents/sophie_pm.yaml`) par l'espace reserve
`{{tier_summary}}`, a rendre depuis
`tier_config_service.get_tier_summary_text(db, language)`. Mais
`sophie_concierge_service.py::converse()` ne substituait que
`{{visitor_language}}`, `{{history}}` et `{{user_message}}` (lignes ~243-245) :
le concierge public envoyait la chaine litterale `{{tier_summary}}` au LLM.
Ce fichier le prouve par execution (routeur simule qui capture le prompt
recu), puis verifie le correctif.

Aucune valeur de credits ou de prix n'est ecrite en dur dans les assertions :
elles sont toutes recalculees depuis `tier_config_service.get_tier_summary_text()`
lu directement sur la base jetable, pour le meme `language` que le tour
concierge testé — c'est la fonction de reference elle-meme (deja testee par
B7 pour son propre formatage), pas un chiffre retape ici.
"""
from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest

from app.models.credit import TierConfig
from app.services import sophie_concierge_service as concierge
from app.services import tier_config_service

SEL_TEST = "sel-de-test-lot-b7bis"

_TIER_CONFIG_SEED = [
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
    db_session.add_all([TierConfig(**row) for row in _TIER_CONFIG_SEED])
    db_session.commit()
    return _TIER_CONFIG_SEED


class _RouteurCapture:
    """Faux routeur LLM : enregistre chaque requete recue (dont son prompt)."""

    def __init__(self):
        self.requetes = []

    async def complete(self, request):
        self.requetes.append(request)

        class _Reponse:
            content = 'Bonjour, je suis Sophie. [META]{"intent": "info"}'
            cost_usd = 0.0001
            tokens_in = 10
            tokens_out = 5

        return _Reponse()

    def dernier_prompt(self) -> str:
        return str(self.requetes[-1].prompt)


def _un_tour(db_session, monkeypatch, routeur, language: str, ip: str = "203.0.113.20"):
    monkeypatch.setattr(concierge, "IP_SALT", SEL_TEST)
    monkeypatch.setattr(concierge, "get_llm_router", lambda: routeur)
    asyncio.run(
        concierge.converse(
            db=db_session,
            session_uuid=str(uuid.uuid4()),
            visitor_ip=ip,
            visitor_language=language,
            user_message="Combien coute le tier Pro et combien de credits ?",
        )
    )
    return routeur.dernier_prompt()


# ─────────────────────────────────────────────────────────────────────
# 1. Rouge (avant correctif) / preuve du defaut, puis du correctif
# ─────────────────────────────────────────────────────────────────────

def test_le_tour_concierge_substitue_tier_summary_fr(db_session, monkeypatch, tier_config_seed):
    """Avant correctif : le prompt recu par le routeur contient la chaine
    litterale `{{tier_summary}}` et pas le prix/les credits Pro de
    `tier_config`. Apres correctif : l'inverse.
    """
    routeur = _RouteurCapture()
    prompt = _un_tour(db_session, monkeypatch, routeur, "fr")

    attendu = tier_config_service.get_tier_summary_text(db_session, "fr")

    assert "{{tier_summary}}" not in prompt, (
        "le placeholder litteral {{tier_summary}} a ete envoye au LLM tel quel"
    )
    assert attendu in prompt, (
        "le resume des tiers (calcule depuis tier_config, fr) n'apparait pas "
        "dans le prompt recu par le routeur"
    )
    # Preuve que ce n'est pas un texte muet accidentellement egal : les
    # credits et le prix du tier pro, tels que seedes, doivent etre lisibles
    # dans le resume attendu lui-meme (sinon le test ne prouverait rien).
    ligne_pro = db_session.query(TierConfig).filter_by(tier_name="pro").one()
    assert str(int(ligne_pro.price_eur_monthly)) in attendu
    assert f"{ligne_pro.monthly_credits:,}".replace(",", " ") in attendu


def test_le_tour_concierge_substitue_tier_summary_en(db_session, monkeypatch, tier_config_seed):
    routeur = _RouteurCapture()
    prompt = _un_tour(db_session, monkeypatch, routeur, "en")

    attendu = tier_config_service.get_tier_summary_text(db_session, "en")

    assert "{{tier_summary}}" not in prompt
    assert attendu in prompt


# ─────────────────────────────────────────────────────────────────────
# 2. Controle negatif — la source est la table, pas un texte fige
# ─────────────────────────────────────────────────────────────────────

def test_une_mutation_de_tier_config_est_repercutee_au_tour_suivant(
    db_session, monkeypatch, tier_config_seed
):
    """Le prix Pro change entre deux tours : le second prompt doit refleter
    la nouvelle valeur, et ne plus contenir l'ancien resume."""
    routeur = _RouteurCapture()
    prompt_avant = _un_tour(db_session, monkeypatch, routeur, "fr", ip="203.0.113.21")
    resume_avant = tier_config_service.get_tier_summary_text(db_session, "fr")
    assert resume_avant in prompt_avant

    ligne_pro = db_session.query(TierConfig).filter_by(tier_name="pro").one()
    ligne_pro.price_eur_monthly = Decimal("199.00")
    ligne_pro.monthly_credits = 42424
    db_session.commit()

    resume_apres = tier_config_service.get_tier_summary_text(db_session, "fr")
    assert resume_apres != resume_avant, (
        "la mutation n'a pas change le resume calcule — le test ne prouverait rien"
    )

    routeur2 = _RouteurCapture()
    prompt_apres = _un_tour(db_session, monkeypatch, routeur2, "fr", ip="203.0.113.22")

    assert resume_apres in prompt_apres, (
        "le prompt du tour suivant ne reflete pas la mutation de tier_config"
    )
    assert resume_avant not in prompt_apres, (
        "l'ancien resume (pre-mutation) est encore present — indice d'un cache "
        "ou d'une valeur figee au lieu d'une lecture a chaque tour"
    )


# ─────────────────────────────────────────────────────────────────────
# 3. Controle — la langue du visiteur pilote la langue du resume
# ─────────────────────────────────────────────────────────────────────

def test_la_langue_du_visiteur_pilote_la_langue_du_resume(db_session, monkeypatch, tier_config_seed):
    """`get_tier_summary_text` distingue fr/en sur le prix Pro (`_format_price`)
    et sur la ligne Enterprise, entierement ecrites par la fonction — lu dans
    `tier_config_service.py`. On n'utilise pas la ligne Free/l'unite de
    credits pour cette distinction : le nom de tier ("Free") reste identique
    dans les deux langues (`tier_name.capitalize()`), et la `description`
    lue telle quelle depuis `tier_config` est en francais dans les deux cas
    (seedee ainsi, comme la vraie table depuis la migration 012 — pas
    traduite par la fonction) : "credits/jour cap strict" y apparaitrait meme
    cote anglais, ce qui prouve seulement que la description n'est pas
    traduite, pas que la substitution a echoue.
    """
    routeur_fr = _RouteurCapture()
    prompt_fr = _un_tour(db_session, monkeypatch, routeur_fr, "fr", ip="203.0.113.23")

    routeur_en = _RouteurCapture()
    prompt_en = _un_tour(db_session, monkeypatch, routeur_en, "en", ip="203.0.113.24")

    resume_fr = tier_config_service.get_tier_summary_text(db_session, "fr")
    resume_en = tier_config_service.get_tier_summary_text(db_session, "en")

    def _fragment_prix_pro(resume: str) -> str:
        ligne_pro = next(l for l in resume.splitlines() if l.startswith("- Pro:"))
        return ligne_pro.split(": ", 1)[1].split(",", 1)[0]

    prix_pro_fr = _fragment_prix_pro(resume_fr)
    prix_pro_en = _fragment_prix_pro(resume_en)
    assert prix_pro_fr != prix_pro_en, (
        "le fragment de prix Pro ne differe pas entre fr et en — le test ne "
        "prouverait rien"
    )
    assert prix_pro_fr in prompt_fr and prix_pro_fr not in prompt_en
    assert prix_pro_en in prompt_en and prix_pro_en not in prompt_fr

    ligne_enterprise_fr = resume_fr.splitlines()[-1]
    ligne_enterprise_en = resume_en.splitlines()[-1]
    assert ligne_enterprise_fr != ligne_enterprise_en
    assert ligne_enterprise_fr in prompt_fr and ligne_enterprise_fr not in prompt_en
    assert ligne_enterprise_en in prompt_en and ligne_enterprise_en not in prompt_fr
