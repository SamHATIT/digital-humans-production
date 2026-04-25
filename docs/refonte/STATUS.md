# Refonte doc — État courant

**Dernière mise à jour** : 2026-04-25 (session Claude+Sam, post-LLM migration + nouveau chantier SDS templating démarré)

## Phase courante
**Phases 0, 1, 2, 3, 4 terminées.** Refonte doc livrée. Prochain : enrichissements éditoriaux à la carte (nouvelles sections, hero par section, etc.) et hook git local optionnel (post-N2).

## Décisions actées
- **Framework** : Jinja2 + Python stdlib. Léger, zéro dépendance neuve, SSoT projet.
- **CI** : reportée post-N2 (après que le hook git local ait fait ses preuves pendant ~1 mois).
- **Branche** : `feature/docs-refonte`.
- **Backups auto** : `index.html.bak.YYYYMMDD_HHMMSS`, rétention 7 jours par défaut (paramétrable via `--purge-days`), ignorés par git (`*.bak*`).
- **Source unique par type** : chaque fait vit à un seul endroit.
- **Pattern B pour Phase 3** : partials Jinja2 produisent les blocs *data*, rédactionnel reste dans `sections/*.html`, markers `<!-- PARTIAL:X -->`.
- **Charte Studio** (Lot A + Lot B session 2) : palette noir/bone/brass, fonts Cormorant + Inter + JetBrains Mono, navigation scroll continu + TOC sticky scroll-spy, tableaux expandables, mode print inversé.
- **Phase 4 — déploiement** : `build_docs.py` écrit direct dans `index.html` (repo) avec backup préalable, purge auto > 7j ; flag `--deploy` pour copie atomique vers `/var/www` + smoke test HTTP ; flag `--dry-run` pour preview dans `index.generated.html` sans toucher la baseline.

## Fait session 24 avril 2026
- ✅ Phases 0+1+2 closes (commits `eb0a803` + `a4b12ae`)
- ✅ Phase 3 — collectors + Jinja2 partials + build_docs.py Pattern B (commit `79fb79c`)
- ✅ Charte Studio Lot A + Lot B (commit `cb2961f`) : palette, fonts, layout reading (260px TOC sticky + scroll-spy), 3 partials en tbl-expand, mode print inversé
- ✅ Mermaid useMaxWidth + fullwidth (commit `72b5caa`) : les 5 diagrammes (flowchart LR/TB, stateDiagram) occupent toute la largeur disponible
- ✅ **Phase 4 livrée** :
  - `build_docs.py` refactoré : argparse avec 5 flags (`--strict`, `--dry-run`, `--deploy`, `--no-backup`, `--purge-days`)
  - **Mode normal** : backup → atomic write dans `index.html` → purge > 7j. Testé : backup créé (`index.html.bak.20260424_141731`), md5 identique post-write, purge a supprimé 1 backup de février (> 7j).
  - **Mode `--dry-run`** : écrit dans `index.generated.html` sans toucher la baseline. Testé : `index.html` intact, diff rapporté.
  - **Mode `--deploy`** : build normal + backup `/var/www` + atomic write vers `/var/www/.../index.html` + purge /var/www + smoke test `curl -sI`. Testé : HTTP 200 sur `https://digital-humans.fr/docs/refonte/`, md5 identique repo ↔ /var/www.
  - **Atomic write** via `tempfile.mkstemp` dans le même FS puis `os.replace()` — pas de fichier partiel visible par Nginx.
  - `index.generated.html` ajouté au `.gitignore`.
  - Baseline repo promue : `docs/refonte/index.html` contient maintenant la charte Studio validée visuellement.

## Fait session 25 avril 2026

### Migration LLM (sur `main`, mergée)
- ✅ `bfc0c06` : Opus 4.6 → 4.7 + correction pricing $5/$25 in/out + drop `temperature` (déprécié sur Opus 4.7)
- ✅ `99d079b` : Sonnet 4.5 → 4.6 + SSoT `model display_name` + post-commit hook auto-rebuild docs (versionné dans `tools/git-hooks/post-commit`)
- ✅ `fcb9a66` : rebuild `index.html` avec noms LLM à jour dans les sections statiques

⚠️ Le tokenizer Opus 4.7 utilise 1-1.35× plus de tokens qu'Opus 4.6, à surveiller pour `MAX_TOTAL_LLM_CALLS=80`.

### Nouveau chantier — SDS templating depuis DB
Démarré sur la branche **`feat/sds-templating`** (non mergée). Objectif : remplacer la phase 5 Emma SDS Final ($5-10 / 10-15 min) par un assemblage Jinja2 templaté à partir des deliverables persistés en PostgreSQL.

Itération 2 close : 13/13 sous-sections de la section 6 Solution Design instrumentées DB-driven. Build ~1.2s, 0 coût LLM.

📄 **Status dédié** : `docs/sds/STATUS.md` (151 lignes — décisions actées, sessions, workflow, prochaines étapes, pièges connus).

## Workflow de référence (pour Sam, futur-Claude, etc.)

```bash
# Modification d'une source (yaml, section, template, partial)
vim docs/refonte/sources/problems.yaml   # ou sections/, templates/partials/, templates/shell.html

# Preview sans impact (optionnel)
source backend/venv/bin/activate
python3 tools/build_docs.py --dry-run
# → écrit index.generated.html, affiche le diff vs index.html

# Build + commit quand satisfait
python3 tools/build_docs.py
# → backup auto, write index.html, purge > 7j
git add docs/refonte/
git commit -m "docs: <description>"
git push

# Déploiement sur /var/www (après push, généralement)
python3 tools/build_docs.py --deploy
# → rebuild + backup /var/www + atomic copy + smoke test HTTP 200
```

## Prochaines étapes (backlog, pas urgent)

### Enrichissements éditoriaux à la carte
- **Hero par section** : certaines sections mériteraient un eyebrow mono + titre italique brass en tête (pattern Studio), pas juste le `<h2>` qui hérite du CSS global.
- **Nouvelles sections** : si le produit évolue, ajouter `sections/xxx.html` + entrée dans shell.html (marker + TOC).
- **Diagrammes Mermaid supplémentaires** : chaque concept clé gagnerait à avoir son schéma (ex: state machine BUILD, flow HITL, etc.).
- **`.section h2::before`** : ajouter un contenu (nom de section court en mono) pour évoquer les `act` du Studio.

### Infrastructure doc
- **Hook git post-commit** : lancer automatiquement `build_docs.py --deploy` après chaque commit qui touche `docs/refonte/`. Simple hook bash local, zéro config serveur.
- **Scheduler `rebuild-on-drift`** : cron quotidien qui lance `build_docs.py --deploy` pour que les stats live (RAG counts, services) soient rafraîchies même sans édition.
- **CI post-N2** : une fois que le hook local a fait ses preuves ~1 mois, migrer vers GitHub Actions (build + deploy via SSH).

## Questions en attente
_(aucune)_

## Pièges connus (à relire avant toute modif)
- ⚠️ `index.html` existe en 2 exemplaires : `docs/refonte/` (repo) et `/var/www/digital-humans.fr/docs/refonte/`. Synchronisés via `build_docs.py --deploy`.
- ⚠️ Deux fichiers `.env` pour clé OpenAI (cf `problems.yaml` → P12).
- ⚠️ Ne jamais éditer `index.html` à la main. Toujours modifier les sources (`sources/*.yaml`, `sections/*.html`, `templates/shell.html`, `templates/partials/*.j2`) puis rebuild.
- ⚠️ `build_docs.py` nécessite `backend/venv` actif (pour `chromadb` dans `collect_rag_stats()`).
- ⚠️ `AGENT_DOC_META` dans `collect.py` synchronisé avec `agents_registry.yaml` (garde-fou BuildError).
- ⚠️ `replace_marker_preserving_indent` : PARTIAL → `reindent=True` (défaut). SECTION → `reindent=False`. Ne pas confondre.
- ⚠️ Nouveau shell Studio : sections toutes visibles en scroll continu. Scroll-spy dépend de `.section[id]`.
- ⚠️ Les `<br/>` dans les diagrammes Mermaid (syntaxe Mermaid, pas HTML) peuvent être flaggés par des parsers HTML stricts — ignorer.
- ⚠️ `--deploy` ne respecte PAS `--no-backup` pour `/var/www` (le backup /var/www est toujours créé avant écrasement, c'est le filet de sécurité prod).
- ⚠️ `atomic_write` nécessite que le tmpfile soit dans le MÊME filesystem que la destination (sinon `os.replace` n'est pas atomique). C'est garanti par `tempfile.mkstemp(dir=dst.parent)`.

## Environnement de travail
- VPS : `72.61.161.222`, Ubuntu 24.04
- Repo : `/root/workspace/digital-humans-production`
- Deploy : `/var/www/digital-humans.fr/docs/refonte/`
- Branche : `feature/docs-refonte`
- Python venv : `backend/venv/` (Jinja2 + chromadb)
- URL live : `https://digital-humans.fr/docs/refonte/`
