"""Tarifs des modèles réellement servis (BILL-08, vague 1 / file B)

Revision ID: 016_tarifs_modeles_servis
Revises: 015_free_50_credits_jour
Create Date: 2026-09-16

Mesure du 16/09 (identifiants `model_id` de config/llm_routing.yaml croisés
avec les lignes `model_pricing` créées par les migrations) :

    SERVIS SANS LIGNE DE TARIF : claude-haiku-4-5-20251001, claude-opus-5,
    claude-sonnet-5, deepseek-v4-*, glm-5-3-flash-260828, gpt-4o,
    gpt-4o-mini, mistral*, muse-glimmer

Les trois modèles Anthropic du profil `cloud` — les seuls que ce profil
route — n'ont AUCUNE ligne de tarif. Jusqu'ici le repli par sous-chaîne de
`_resolve_pricing` les tarifait au tarif d'une version antérieure
(`claude-sonnet-5` facturé au tarif de `claude-sonnet-4-6`) et écrivait cette
version antérieure dans `credit_transactions.model_used` : le grand livre ne
disait pas ce qui avait été servi (BILL-08, audit Astra L754).

Ce repli est supprimé par le correctif : un modèle servi non listé est
désormais refusé. Cette migration fournit donc les **alias explicites vers un
tarif versionné** que BILL-08 demande, sans quoi tout appel cloud serait
refusé. Les tarifs sont ceux des lignes de même famille (008/010) : aucun
changement de prix, seulement un nom exact.

`requires_opt_in` de `claude-opus-5` est posé à **false** : la migration 010 a
explicitement ouvert Opus au palier Pro pour Marcus (« vitrine technique du
SDS »), et le produit n'a aucun mécanisme de recueil de consentement. Le
correctif applique désormais cette colonne (elle n'était lue nulle part) : la
laisser à `true` refuserait toute exécution Pro et Team, dont l'orchestrateur
tourne en Opus sur le profil cloud. À rebasculer à `true` le jour où un
consentement explicite existe — une ligne de SQL suffit, le code l'applique.

Les modèles locaux/GPU servis (muse-glimmer, deepseek-v4-*, glm-5-3-*) restent
sans tarif : leurs lignes ont été ajoutées à la main sur le VPS le 15/09 pour
la calibration (GL-08) et le choix de les conserver n'est pas tranché. Tant
qu'ils n'ont pas de ligne, ils sont refusés — ce qui est l'objet du correctif :
pas de tarification par ressemblance. `nemotron-lightning` (parcours Free) est
tarifé depuis la migration 014 et n'est pas concerné.

Idempotente (INSERT … ON CONFLICT DO UPDATE), réversible (DELETE des trois
lignes ajoutées).
"""
from alembic import op

revision = "016_tarifs_modeles_servis"
down_revision = "015_free_50_credits_jour"
branch_labels = None
depends_on = None


# (model_name, crédits/1k entrée, crédits/1k sortie, paliers, opt-in requis)
# Tarifs repris à l'identique des lignes de même famille (008, 010).
_LIGNES = [
    ("claude-haiku-4-5-20251001", "0.300", "1.500", "free,pro,team", "false"),
    ("claude-sonnet-5",           "1.000", "5.000", "pro,team",      "false"),
    ("claude-opus-5",             "5.000", "25.000", "pro,team",     "false"),
]


def upgrade() -> None:
    for nom, entree, sortie, paliers, opt_in in _LIGNES:
        op.execute(
            "INSERT INTO model_pricing "
            "(model_name, credits_per_1k_input, credits_per_1k_output, "
            " allowed_tiers, requires_opt_in, is_active, updated_at) "
            f"VALUES ('{nom}', {entree}, {sortie}, '{paliers}', {opt_in}, true, now()) "
            "ON CONFLICT (model_name) DO UPDATE SET "
            "credits_per_1k_input = EXCLUDED.credits_per_1k_input, "
            "credits_per_1k_output = EXCLUDED.credits_per_1k_output, "
            "allowed_tiers = EXCLUDED.allowed_tiers, "
            "requires_opt_in = EXCLUDED.requires_opt_in, "
            "is_active = true, updated_at = now()"
        )


def downgrade() -> None:
    noms = ", ".join(f"'{nom}'" for nom, *_ in _LIGNES)
    op.execute(f"DELETE FROM model_pricing WHERE model_name IN ({noms})")
