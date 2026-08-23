# `backend/migrations/` — MORT. Ne rien ajouter ici.

**VAGUE 2 / LOT 3 — audit croisé du 21/08/2026 (`kim:PROD-05`).**

Les quatre fichiers `.sql` de ce répertoire sont des migrations manuelles,
écrites avant qu'Alembic ne soit en place. Elles **doublonnent** les révisions
de `backend/alembic/versions/` :

| Fichier | Doublonne |
|---|---|
| `006_execution_state_machine.sql` | `alembic/versions/006_add_configurable_validation_gates.py` et suivantes |
| `freemium_and_environments.sql` | `005_add_environments_git_tables.py`, `009_realign_freemium_tiers.py` |
| `wbs_task_types.sql` | `001_add_pm_orchestrator_tables.py` |
| `wizard_phase5.sql` | `004_add_project_config_fields.py`, `005_add_environments_git_tables.py` |

## Pourquoi c'est un défaut et pas une redondance inoffensive

Deux sources pour un même schéma, dont une seule tient `alembic_version`.
Appliquer un `.sql` d'ici **n'avance pas** le pointeur de révision : le prochain
`alembic upgrade head` rejoue alors une migration déjà appliquée et échoue sur
un objet qui existe déjà. C'est l'incident que PROD-05 annonce, et il ne se
manifeste qu'au déploiement suivant, loin de sa cause.

## La seule source de vérité : Alembic

```bash
cd backend
alembic current          # où en est la base
alembic upgrade head     # appliquer
alembic revision -m "..." # créer une révision
```

`alembic.ini` a été corrigé le 23/08 (`script_location` relatif) : l'outil
fonctionne depuis l'hôte comme depuis le conteneur.

## Pourquoi les fichiers sont conservés

Ils documentent l'état du schéma avant Alembic et servent de référence
historique pour les bases créées à la main avant l'automatisation. Les
supprimer ferait perdre cette trace sans rien gagner. **Ils ne doivent pas être
exécutés.** Un test le rappelle : `tests/test_vague2_lot3_migrations_mortes.py`.

## Sur une base créée par l'ancien `create_all`

`alembic_version` y est vide et le premier `alembic upgrade head` échouera. La
marche à suivre est dans `docs/audit-20260821/EXECUTION.md` §6.4 :
`alembic stamp <rev>` d'abord.
