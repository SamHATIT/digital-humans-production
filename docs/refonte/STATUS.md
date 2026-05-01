# Refonte doc — État courant

**Dernière mise à jour** : 2026-05-01 (consolidation totale main, post-merge feat/platform-studio + feature/tier-based-routing)

## Phase courante
**Phases 0, 1, 2, 3, 4 terminées + hook post-commit livré et opérationnel.** Refonte doc autonome (rebuild auto à chaque commit qui touche les sources). Doc admin déployée sur https://app.digital-humans.fr/admin/docs/ (auth requise). Prochain : enrichissements éditoriaux à la carte (nouvelles sections, hero par section, etc.) et CI post-N2.

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

## Fait sessions 26 avril -> 1er mai 2026

### Session 27 avril — Sprint A5 Platform Studio (refonte frontend complète)
- ✅ A5.1 Foundation (`eab203f`) : design tokens `tokens.css` ink/bone/brass + 5 acte accents, AppShell + StudioHeader/Footer/Cover, LoginPage refondue, Dashboard refondu (Cormorant italic + № 01 STUDIO + cards productions GD/L/SC).
- ✅ A5.2 Casting (`928aed5`) : ProjectWizard 5-act, NewProject welcome, BR validation Studio, composants StudioInput/Select/Tabs/Stepper.
- ✅ A5.3 Theatre (`1abb6d8` + `03d554c`) : ExecutionMonitoringPage refondue (AgentStage, AgentLivePreview, CurtainOverlay, EnsembleDisplay, ChatSidebarStudio).
- ✅ A5.4 Pages connexes (`4979cd2`) : Projects, ProjectDetail, AgentTester, Pricing refondus + cleanup legacy (Navbar.tsx, App.jsx, main.jsx, pmService.js → AppShell, App.tsx, main.tsx, pmService.ts).
- ✅ Perf (`25598be`) : route-level React.lazy, **bundle initial 1.46 MB → 269 KB (-82%)**.
- ✅ Doc admin déployée (`30f6ea2`) : `/var/www/app-docs/` accessible via `app.digital-humans.fr/admin/docs/` (auth nginx_request_auth via JWT cookie).
- ✅ Fixes BUILD pipeline (`de52d0b`, `018f34e`) : state machine post-SDS débloquée, PhasedBuildExecutor init.

### Session 28 avril — Refactor freemium 4-tier + Sophie concierge public
- ✅ `e538605` + `32223f6` : refactor 3-tier (free/premium/enterprise) → **4-tier (free/pro/team/enterprise)**. Modifs subscription model, llm_routing.yaml, allowed_tiers, quota_credits.
- ✅ `6bbc643` : widget chat public Sophie sur le marketing site. Endpoint `/api/public/concierge/talk` accessible sans auth.
- ✅ `a41c240` : nouvelles sections marketing-site + pricing-billing dans la doc refonte.

### Session 29 avril — Stripe Phase 3 S3.3 + Mod 23 pricing
- ✅ `b8e4f82` : `stripe_service.py` complet (checkout, customer portal, webhooks subscription + invoice). Routes `/billing/checkout`, `/billing/portal`, `/billing/webhook`. Hook signup pour créer Stripe customer auto.
- ✅ `d679652` : **Mod 23** — Section prix UI bundle preview (3 colonnes Free/Pro/Team + Enterprise band, narrative № 04 The pact / Le pacte).
- ✅ `4bc1875` : bump quota Pro 2k → 15k crédits, Opus allowed_tiers='pro,team'.
- ✅ Stripe webhook E2E validé (`3ae9425`).

### Session 1er mai — Sprint 1+2 marketing + tier-routing + merges main
**Tag final** : `v2026.05-may-1-consolidation`

- ✅ **Marketing pre-launch** :
  - Mod 28 Sprint 1 (`cf86231`) : footer mailto, CTAs pricing fonctionnels, 3 routes SPA légales `/cgv` `/legal` `/privacy` avec contenu FR+EN (~3000 lignes).
  - Mod 29 Sprint 2 (`3366d29`) : 700+ lignes CSS responsive + a11y WCAG AA + SEO. **Lighthouse mobile : a11y 86→100, SEO 91→100**.
  - Mod 30 (`18698e5`) : favicon SVG inline, **Best Practices 100/100**.
- ✅ **Tier-based LLM routing 3/3** :
  - Étape 1 (`19c53f9`) : Pro 49€ downgrade Sonnet sauf Marcus.
  - Étape 2 (`c1e1a17`) : auto-resolution tier via `_resolve_tier_for_execution()` + `lru_cache(512)` + invalidation webhook Stripe. Tests E2E 6/6 + 4/4.
  - Étape 3 (`73fe8c5`) : Anthropic prompt caching auto Marcus tier paying. Tests E2E 5/5. **~$1+/SDS économisé**.
- ✅ **SignupPage refondue** (`9dab8cb` sur feat/platform-studio) : 355 lignes pattern A5.1 (Cormorant italic, JetBrains Mono, ink/bone/brass), validation client, i18n FR/EN, register+auto-login.
- ✅ **Bench LLM locaux 30 avr** (`8f8370e`) : `gemma4:26b` MoE seul viable CPU-only (23min Marcus, 7min Diego), denses 24-27B KO timeout.
- ✅ **F823 + F402 lint fixes** (`1281e9a`) : 0 F821 confirmé, 2 vrais bugs latents éliminés.
- ✅ **Merge feat/platform-studio dans main** (`8bc569c`, tag `v2026.05-platform-studio-merged`) : 99 fichiers, +9272/-5521 lignes, **0 conflit**. Refonte Studio désormais dans main.
- ✅ **Merge feature/tier-based-routing dans main** (`2f72f5c`) : 45 fichiers, +54072/-183 lignes (gros volumes = audits Lighthouse JSON + bench LLM + contenu juridique).
- ✅ **frontend_pages.yaml fix** (`48ae96a`) : ajout SignupPage + AppShell post-merge platform-studio (le hook post-commit plantait sur `BuildError: Composants présents dans App.tsx mais absents`).

### Effet structurel
Le code source du studio refondu est désormais **DANS main**. Toute future branche feature partira d'un main brand-coherent. Le bug du 1er mai (commit basé sur du code legacy purple/cyan parce que feat/platform-studio n'était pas mergée) ne peut plus se reproduire.

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
