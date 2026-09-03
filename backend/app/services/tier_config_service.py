"""
Source unique des chiffres de tier — vague B, lot B7.

Decision D9 (03/09, `docs/vague-b/DECISIONS_SAM.md`) : la verite des tiers
(credits, prix) est la table `tier_config`, lue par l'API ; plus de chiffre
en dur ailleurs.

Defaut mesure (vague A, confirme le 03/09) : `frontend/src/pages/Pricing.tsx`
et `backend/prompts/agents/sophie_pm.yaml` portaient des chiffres de credits
et de prix en dur, perimes par rapport a `tier_config` (Free "500/mois" au
lieu de 300/jour reel, Team "50 000" au lieu de 100 000, concierge "e79 /
2 SDS par mois" en commentaire alors que `tier_config.pro.description` dit
"15000 credits/mois inclus" depuis la migration 012). Cause : deux sources
jamais reliees. Ce module en fait une.

Consommateurs :
  - `GET /api/subscription/tiers` (`app/api/routes/subscription.py`),
    endpoint deja public (aucune dependance d'authentification, mesure par
    lecture de la route) — reutilise, corrige pour lire `tier_config` au
    lieu du dict `TIER_FEATURES` en dur.
  - Le prompt concierge de Sophie (`backend/prompts/agents/sophie_pm.yaml`,
    bloc `concierge.prompt`) via `get_tier_summary_text()`, a la place de
    l'espace reserve `{{tier_summary}}`. L'appel effectif de cette fonction
    — remplacer le placeholder par le texte rendu — se ferait dans
    `sophie_concierge_service.py` (`rendered_prompt = rendered_prompt.replace(...)`,
    a cote des trois `.replace()` deja presents pour `{{visitor_language}}`,
    `{{history}}`, `{{user_message}}`). Ce fichier est hors perimetre de B7
    (attribue a B1/B8) : voir `docs/vague-b/EXECUTION.md` section B7,
    « Ouvert », pour la ligne exacte a y ajouter.

`Enterprise` n'a pas de ligne dans `tier_config` (seedee par la migration
008 : free / pro / team seulement — un contrat Enterprise est negocie, pas
un prix catalogue) : son prix reste "sur devis", jamais un chiffre, donc
absent des fonctions ci-dessous.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.credit import TierConfig


def _credits_period(row: TierConfig) -> str:
    """'day' si ce tier est plafonne par jour, 'month' sinon.

    Mesure sur la migration 008 : seule la ligne 'free' porte
    `daily_credits_cap` non NULL (300) ; pro/team n'ont qu'un
    `monthly_credits`.
    """
    return "day" if row.daily_credits_cap is not None else "month"


def _credits_value(row: TierConfig) -> int:
    """Le nombre de credits a afficher pour ce tier, selon son rythme."""
    return row.daily_credits_cap if row.daily_credits_cap is not None else row.monthly_credits


def list_public_tiers(db: Session) -> List[Dict[str, Any]]:
    """Lit `tier_config` (source unique, D9) et rend une liste triee par prix.

    Ne contient aucune valeur ecrite en dur dans ce module : tout vient de
    la ligne SQL.
    """
    rows = db.query(TierConfig).order_by(TierConfig.price_eur_monthly.asc()).all()
    return [
        {
            "tier_name": row.tier_name,
            "monthly_credits": row.monthly_credits,
            "daily_credits_cap": row.daily_credits_cap,
            "credits": _credits_value(row),
            "credits_period": _credits_period(row),
            "price_eur_monthly": float(row.price_eur_monthly),
            "description": row.description,
        }
        for row in rows
    ]


def get_tier_row(db: Session, tier_name: str) -> Optional[Dict[str, Any]]:
    """Une seule ligne de `list_public_tiers`, ou None si le tier n'a pas de
    ligne dans `tier_config` (cas d'Enterprise)."""
    for row in list_public_tiers(db):
        if row["tier_name"] == tier_name:
            return row
    return None


def _format_price(price_eur_monthly: float, language: str) -> str:
    if price_eur_monthly == 0:
        return "Gratuit" if language == "fr" else "Free"
    grouped = f"{price_eur_monthly:,.0f}".replace(",", " ")
    return f"{grouped} €/mois" if language == "fr" else f"€{grouped}/month"


def _format_credits(value: int, period: str, language: str) -> str:
    grouped = f"{value:,}".replace(",", " ")
    if language == "fr":
        unit = "credits/jour" if period == "day" else "credits/mois"
    else:
        unit = "credits/day" if period == "day" else "credits/month"
    return f"{grouped} {unit}"


def get_tier_summary_text(db: Session, language: str = "en") -> str:
    """Resume textuel des tiers, pret a remplacer l'espace reserve
    `{{tier_summary}}` du prompt concierge de Sophie (`sophie_pm.yaml`).

    Source unique : `tier_config` (D9). Aucun chiffre n'est ecrit dans cette
    fonction — seuls le formatage (separateur de milliers, unite, devise)
    et le libelle "Enterprise : sur devis" (qui n'est justement pas un
    chiffre) le sont.
    """
    lignes = []
    for row in list_public_tiers(db):
        prix = _format_price(row["price_eur_monthly"], language)
        credits = _format_credits(row["credits"], row["credits_period"], language)
        nom = row["tier_name"].capitalize()
        description = row["description"] or ""
        lignes.append(f"- {nom}: {prix}, {credits} — {description}")

    if language == "fr":
        lignes.append("- Enterprise : sur devis, on-premise — contacter Sam")
    else:
        lignes.append("- Enterprise: on request, on-premise — contact Sam")
    return "\n".join(lignes)
