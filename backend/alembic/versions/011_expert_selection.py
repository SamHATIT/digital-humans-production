"""Vague 3 §4 — selection des experts SDS decidee par Marcus

Revision ID: 011_expert_selection
Revises: 010_pro_tier_marcus_opus
Create Date: 2026-08-23

Arbitrage Sam du 23 aout 2026 (SPEC_VAGUE3 §4).

Contexte
--------
`pm_orchestrator_service_v2` filtrait les quatre experts SDS sur
`executions.selected_agents`, une colonne renseignee **au lancement** — donc
avant que quiconque ait analyse le projet. Vide, les quatre experts tournaient ;
en pratique elle etait toujours vide. Le mecanisme existait mais etait alimente
par le mauvais bout.

C'est desormais Marcus qui decide, en fin de phase 3, au vu de l'architecture
qu'il vient de produire.

Pourquoi une colonne dediee
---------------------------
La contrainte 2 exige que la selection soit **persistee et relue**, pas
recalculee : une reprise en `phase4` qui recalculerait relancerait des experts
que Marcus avait ecartes.

Elle ne peut pas reutiliser `selected_agents` : cette colonne porte l'intention
du client au lancement, qui **prime** sur Marcus (contrainte 4). L'ecraser
effacerait precisement ce qui doit primer sur lui.

Changements DB
--------------
1. `executions.expert_selection` : JSONB, nullable.
   Forme : {"selected": [...], "excluded": {agent: justification},
            "decided_by": "user"|"architect"|"resumed", "signals": {...}}

Nullable et sans defaut : les executions anterieures n'ont pas de decision, et
c'est le cas qu'il faut distinguer — `NULL` signifie « Marcus n'a pas encore
tranche », pas « aucun expert ». Le code retombe alors sur les quatre experts,
comportement historique.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011_expert_selection"
down_revision = "010_pro_tier_marcus_opus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "executions",
        sa.Column("expert_selection", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("executions", "expert_selection")
