"""Vague B / lot B3 — RGPD : trace du consentement CGV a l'inscription

Revision ID: 013_consent_cgv_users
Revises: 012_pro_79eur_15000_credits
Create Date: 2026-09-03

Contexte
--------
`docs/vague-b/MISSION.md` (B3) : l'inscription (chemin reel du frontend,
`signup-request` + `signup-confirm`, et `/register` legacy) doit desormais
exiger un consentement CGV explicite, non pre-coche, et en garder la preuve :
date, version du texte accepte, et empreinte (jamais l'IP brute) de qui l'a
donne. Meme regle de hachage que `chat_logs.ip_hash`
(`sophie_concierge_service._hash_ip` : SHA-256(ip + CHAT_IP_SALT), aucun
defaut public au sel).

Ce que cette migration change
------------------------------
Ajoute trois colonnes a `users`, toutes nullables (les comptes existants
n'ont pas ce consentement trace retroactivement — on ne fabrique pas une
preuve qui n'existe pas) :
  - consent_cgv_at    TIMESTAMPTZ  : date/heure du consentement.
  - consent_version   VARCHAR(16)  : identifiant du texte CGV accepte.
  - consent_ip_hash   VARCHAR(64)  : SHA-256 hex (64 caracteres) de l'IP+sel.

Idempotente (colonnes ajoutees seulement si absentes, meme pattern que
007_backfill_project_conversations_agent_id.py) : si le schema a deja ete
cree par `Base.metadata.create_all()` a partir du modele modifie (bac a
sable de test), l'upgrade ne doit pas echouer sur une colonne deja
presente.

Identifiant de revision : "013_consent_cgv_users" fait 21 caracteres,
sous la limite de 32 caracteres d'`alembic_version.version_num`
(mesuree via `\\d alembic_version` — cf. piege documente par 012).

Jamais executee sur la base de production par cet agent (perimetre B3) :
produite et testee sur `digital_humans_test_b3` uniquement.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "013_consent_cgv_users"
down_revision = "012_pro_79eur_15000_credits"
branch_labels = None
depends_on = None


# Colonnes construites par une fabrique (pas des sa.Column partages) : un
# objet Column ne peut etre attache qu'a une seule Table. Ce fichier est
# rejoue plusieurs fois dans le meme process lors du test upgrade/downgrade/
# upgrade (voir preuve dans le rapport du lot), il faut donc une instance
# neuve a chaque appel d'upgrade().
def _new_columns():
    return (
        ("consent_cgv_at", lambda: sa.Column("consent_cgv_at", sa.DateTime(timezone=True), nullable=True)),
        ("consent_version", lambda: sa.Column("consent_version", sa.String(length=16), nullable=True)),
        ("consent_ip_hash", lambda: sa.Column("consent_ip_hash", sa.String(length=64), nullable=True)),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("users")}
    for name, make_column in _new_columns():
        if name not in existing_columns:
            op.add_column("users", make_column())


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("users")}
    for name, _make_column in _new_columns():
        if name in existing_columns:
            op.drop_column("users", name)
