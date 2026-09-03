# Arbitrage — chemin prod vs test_lot_e (B9)

## Le défaut, ligne par ligne

`backend/tests/test_lot_e_secrets_and_paths.py` (avant correctif, ligne 25) :

```python
FORBIDDEN_PREFIXES = ("/opt/digital-humans", "/var/lib/digital-humans", "/root/workspace")
```

`test_no_machine_specific_default_path` (10 paramétrisations) et
`test_sf_admin_persist_dir_defaults_to_settings` testaient
`not value.startswith(FORBIDDEN_PREFIXES)` sur la valeur *effective* de dix
attributs de `Settings`. La docstring de la fonction disait autre chose :
« every configured path is derived from the checkout, not from /opt ». Les
deux ne coïncident que si le checkout ne vit jamais sous `/root/workspace`.
Sur le VPS il y vit (`/root/workspace/digital-humans-production`, `CLAUDE.md`
ligne 9) — un chemin **légitimement dérivé du checkout**
(`Path(__file__).resolve().parent.parent.parent`, `backend/app/config.py`
lignes 97-99) s'est fait rejeter parce qu'il partage un préfixe avec la
racine machine sur laquelle Sam héberge tous ses dépôts.

Assertion réellement vérifiée : « ne commence pas par une des trois chaînes
listées ». Ce que la docstring promet : « dérive du checkout ». Ce sont deux
choses différentes, et la deuxième n'implique pas la première dès que le
checkout partage un segment de chemin avec un des préfixes interdits.

## Reproduction exécutée (règle 10, dans les deux sens)

Copie physique du worktree sous `/root/workspace/digital-humans-production-b9/`
(un lien symbolique ne suffit pas : `Path.resolve()` déréférence les liens et
aurait ramené `__file__` sous `/home/user/...`, masquant le défaut).

**Avant correctif**, depuis ce chemin :
```
$ cd /root/workspace/digital-humans-production-b9/backend && venv/bin/python -m pytest tests/test_lot_e_secrets_and_paths.py -v
FAILED …test_no_machine_specific_default_path[PROJECT_ROOT]
FAILED …test_no_machine_specific_default_path[BACKEND_ROOT]
FAILED …test_no_machine_specific_default_path[OUTPUT_DIR]
FAILED …test_no_machine_specific_default_path[METADATA_DIR]
FAILED …test_no_machine_specific_default_path[CHROMA_PATH]
FAILED …test_no_machine_specific_default_path[LLM_CONFIG_PATH]
FAILED …test_no_machine_specific_default_path[DELIVERABLES_DIR]
FAILED …test_no_machine_specific_default_path[SFDX_PROJECT_PATH]
FAILED …test_no_machine_specific_default_path[FORCE_APP_PATH]
FAILED …test_no_machine_specific_default_path[AGENTS_DIR]
FAILED …test_sf_admin_persist_dir_defaults_to_settings
11 failed, 14 passed, 26 warnings in 0.38s
```
11 échecs — exactement le chiffre du VPS du 03/09 cité dans la mission.
Cause confirmée in situ : `settings.PROJECT_ROOT` valait
`/root/workspace/digital-humans-production-b9`, et les neuf autres attributs
en dérivent tous, donc partagent le préfixe interdit.

**Après correctif**, même chemin, même commande : `27 passed` (voir
`docs/vague-b/EXECUTION.md` pour la sortie complète et le détail du commit).

## Les deux options

### Option A — proposée, implémentée

Le test vérifie que chaque chemin **dérive du checkout** au lieu de vérifier
l'absence d'un préfixe fixe. Concrètement (voir le commit) : pour chaque
attribut, on construit un `Settings` frais avec la variable `DH_<ATTR>`
correspondante supprimée (donc sa *valeur par défaut*, celle écrite en dur
dans `app/config.py`, pas celle qu'un `.env` d'exploitation choisit), et on
vérifie `Path(valeur).resolve().is_relative_to(PROJECT_ROOT.resolve())`.

Ce que ça change de comportement :
- Une valeur par défaut est acceptée **si et seulement si elle est sous le
  checkout courant, quel que soit son préfixe** — `/home/user/wt/b9`,
  `/root/workspace/digital-humans-production`, ou n'importe quel autre
  répertoire dans lequel `git clone` a été lancé.
- Une **surcharge explicite** via `DH_CHROMA_PATH`, `DH_DELIVERABLES_DIR`,
  etc. — documentée et commentée dans `backend/.env.example` lignes 93-98
  pointant vers `/opt/digital-humans/...` et `/var/lib/digital-humans/...` —
  n'est plus jugée : c'est une décision d'exploitant assumée, pas un chemin
  laissé en dur dans le code. C'est un choix délibéré : le test porte sur ce
  que le code *propose par défaut*, pas sur où l'opérateur choisit de faire
  vivre ses données.

Ce que A perd, et comment A le compense :
- **Perdu** : la détection d'un chemin machine copié tel quel dans une valeur
  par défaut, si par malheur ce chemin machine se trouvait être sous le
  checkout actuel au moment du test (cas dégénéré : un développeur travaille
  directement dans `/opt/digital-humans/...`). Cas non observé, hautement
  improbable, mais réel en théorie.
- **Compensé** : `is_relative_to(PROJECT_ROOT)` est une règle structurelle,
  pas une liste de noms — elle rejette *tout* défaut hors checkout, y compris
  des machines et des préfixes qui n'existent pas encore aujourd'hui,
  contrairement à `FORBIDDEN_PREFIXES` qui n'attrape que les trois chaînes
  écrites dedans. Un contrôle négatif permanent (test
  `test_no_machine_specific_default_path_rejects_a_real_machine_path`) force
  le défaut de `CHROMA_PATH` vers `/opt/digital-humans/rag/chromadb_data` et
  vérifie que la règle le rejette toujours — la détection du cas réel qui a
  motivé P2 (`/opt/digital-humans/rag` en dur) est donc prouvée, pas
  supposée. `test_no_hardcoded_absolute_path_in_source` (inchangé) couvre
  l'autre moitié du risque : un chemin machine recopié tel quel *dans le texte
  source* de `config.py`, `sf_admin_service.py`, `encryption.py` — orthogonal
  à la question d'où vit le checkout, donc conservé sans modification.

### Option B — chiffrée, non retenue

Déménager la prod hors de `/root/workspace`. Recherche exhaustive
(`grep -rln "/root/workspace/digital-humans-production"`, hors `__pycache__`
et hors la page générée `docs/refonte/sections/`) : **84 fichiers, 153
occurrences**. Détail des points opérationnels (pas de la doc pure) :

| Fichier:ligne | Nature |
|---|---|
| `backend/digital-humans-worker.service:9` | `WorkingDirectory=` du service ARQ |
| `backend/digital-humans-worker.service:13` | `Environment="PYTHONPATH=..."` |
| `backend/app/api/routes/journal_webhook.py:24` | `BUILD_SCRIPT = Path("/root/workspace/.../scripts/journal/build.py")` — **code applicatif**, hors périmètre B9 (voir « Ouvert » dans `EXECUTION.md`) |
| `scripts/journal/regen/regen_covers.py:26` | `ENV = Path("/root/workspace/.../.env")` |
| `scripts/blog_api.py:27` | chemin du script `blog_generator.py` appelé en subprocess |
| `scripts/blog_generator.py:28` | `env_file = "/root/workspace/.../.env"` |
| `tools/split_sections.py:19` | `ROOT = Path("/root/workspace/digital-humans-production")` |
| `n8n/workflows/blog-generate.json:19` | commande `cd /root/workspace/... && python3 blog_generator.py` dans un nœud n8n |
| `n8n/workflows/README-studio-patch.md:75,122,139,186` | procédure et chemin de fichier JSON |
| `docs/refonte/sources/meta.yaml:14,23` | `repo_path`, `output_path_repo` du générateur de docs |
| `CLAUDE.md:9,128,155` | chemin VPS documenté, commande `cd`, commande de sauvegarde (`cd /root/workspace && tar -czf backups/... digital-humans-production/`) |
| `.claude/CLAUDE.md:11` | chemin du repo |
| `.claude/skills/digital-humans-context/ARCHITECTURE.md:333` | `cwd=` d'exemple |
| `.claude/skills/digital-humans-context/REFACTOR-ASSIGNMENTS.md:170` | exemple de code cité (`PROJECT_ROOT: Path = Path("/root/workspace/digital-humans-production")`) |
| `backend/tests/` — 14 fichiers hors `__pycache__` | `sys.path.insert(0, '/root/workspace/.../backend')` et/ou `open('/root/workspace/.../backend/app/...')` dans des tests existants (dont `test_emma_phase3.py`, l'un des 4 rouges antérieurs déjà connus) |
| ~65 fichiers restants | documentation historique (`docs/audits/`, `docs/briefs/`, `docs/archives/`, `SESSION_HANDOFF_*.md`, `PUSH_TO_GITHUB.md`, etc.) — coût de relecture, pas de risque d'exécution |

Coût de B, en plus des 84 fichiers : régénérer la sauvegarde de référence, le
watchdog (`scripts/dh-watchdog.sh` pointe déjà vers un autre répertoire,
`/root/workspace/dh-comite/.env`, à vérifier séparément s'il dépend d'un
chemin frère), et deux services système (backend, frontend) qui ne sont
**pas** trackés dans ce dépôt — leurs unités `systemd` ne sont pas
grep-ables ici, donc non chiffrés, à vérifier directement sur le VPS avant
toute décision.

## Recommandation

Option A. Elle répare l'assertion pour qu'elle vérifie ce que sa docstring
promet déjà, sans toucher un seul fichier de prod, de service, ou de script —
84 fichiers économisés contre 2 fichiers modifiés (le test, ce document).
