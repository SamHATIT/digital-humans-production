# Refonte doc — État courant

**Dernière mise à jour** : 2026-04-24 (session Claude+Sam, Phase 3 + charte Studio)

## Phase courante
**Phases 0, 1, 2, 3 terminées. Charte Studio portée (Lot A + Lot B).** Prochaine : **Phase 4** (écriture auto sur `index.html` + backup + deploy atomique), puis enrichissements éditoriaux si besoin.

## Décisions actées
- **Framework** : Jinja2 + Python stdlib. Léger, zéro dépendance neuve, SSoT projet.
- **CI** : reportée post-N2.
- **Branche** : `feature/docs-refonte`.
- **Backups auto** : `*.bak.YYYYMMDD_HHMMSS`, 7 jours min, auto-générés par `build_docs.py` en Phase 4.
- **Source unique par type** : chaque fait vit à un seul endroit.
- **Pattern B pour Phase 3** : partials Jinja2 produisent les blocs *data*, rédactionnel reste dans `sections/*.html`, markers `<!-- PARTIAL:X -->`.
- **Charte Studio (acté 24 avr session 2)** : la doc adopte l'esthétique éditoriale Studio (noir `#0A0A0B` + bone `#F5F2EC` + brass `#C8A97E`, serif Cormorant + sans Inter + mono JetBrains, navigation scroll continu + TOC sticky scroll-spy, tableaux expandables, mode print inversé). Cassure volontaire avec le baseline byte-à-byte antérieur : `index.html` dans le repo reste l'ancien layout tant que la nouvelle version n'est pas validée visuellement.

## Fait session 24 avril 2026
- ✅ Phases 0+1+2 closes (commit `eb0a803` + update `a4b12ae`)
- ✅ Phase 3 déployée et validée (commit `79fb79c`) : 11 fichiers scaffolding, 6 markers PARTIAL insérés dans 5 sections, bugfix `build_docs.py` (flag `reindent`), build validé (268 lignes de diff, toutes légitimes)
- ✅ **Charte Studio portée (Lot A + Lot B)** :
  - **Nouveau `shell.html`** (~440 lignes) : palette + fonts Studio, header glass sticky, hero avec halo brass, reading-layout 260px/1fr, TOC sticky scroll-spy (4 groupes : Général / Flux métier / Infrastructure / Refonte 2026), section CTA + footer, scripts (mermaid init thème brass, table toggles, scroll-spy IntersectionObserver), **mode print inversé complet** (thème clair, page-breaks, A4).
  - **Nav : switcher → scroll continu** : suppression de `.section{display:none}`, toutes les sections visibles en scroll unique, TOC `<a href="#id">` + scroll-spy.
  - **3 partials en pattern tbl-expand** : `agents_table` (detail = agent_type→tier, complexity, coût estimé, RAG collections chips, alias), `rag_collections_table` (detail = agents consommateurs chips, statut ChromaDB, note), `infra_services_table` (detail = type, note, commandes diagnostic).
  - **Partials inchangés structurellement** : `problems_status_cards` (cartes), `llm_routing_table` (table simple), `journal_timeline` (timeline CSS). Le nouveau CSS les habille tous correctement.
- ✅ **Build validé post-charte** : 95 806 chars, 0 tag non fermé, 0 marker résiduel, 14 sections présentes, tous éléments Studio présents (header.glass, hero, reading-layout, toc-side, cta, footer, tbl-expand, tbl-row-summary/detail, mermaid thème brass, scroll-spy, table toggles).
- ✅ **Déployé pour visualisation** : `/var/www/digital-humans.fr/docs/refonte/index.html` remplacé (backup `.bak.20260424_HHMMSS` conservé). `https://digital-humans.fr/docs/refonte/` retourne HTTP 200.

## Prochaines étapes

### Phase 4 — auto-écriture sur index.html + deploy atomique
Livrables attendus :
- `build_docs.py` écrit direct dans `index.html` (avec backup `.bak.YYYYMMDD_HHMMSS` avant).
- Option `--deploy` : copie atomique vers `/var/www/digital-humans.fr/docs/refonte/index.html`.
- Purge backups > 7 jours.
- Smoke test post-build : `curl -I` → HTTP 200.

### Tâches annexes
- **Valider visuellement** la nouvelle charte sur `https://digital-humans.fr/docs/refonte/`. Si KO : rollback via `cp index.html.bak.20260424_HHMMSS index.html` dans `/var/www/.../docs/refonte/`.
- Si validé : copier `docs/refonte/index.generated.html` → `docs/refonte/index.html` dans le repo pour que `index.html` (baseline de diff) reflète la nouvelle charte. Jusque-là, le prochain build affichera un diff énorme — c'est attendu.
- Enrichir les sections rédactionnelles avec les éléments Studio : `hero` éventuel par section (eyebrows mono + h2 serif italique), `<p class="note">` pour les asides, etc. — optionnel, à faire progressivement.

## Questions en attente
- Confirmation visuelle Sam sur la charte Studio appliquée (Phase 3 + Lot A + Lot B) avant de promouvoir `index.generated.html` → `index.html` dans le repo.

## Pièges connus (à relire avant toute modif)
- ⚠️ `index.html` existe en 2 exemplaires : `docs/refonte/` (repo) et `/var/www/digital-humans.fr/docs/refonte/`. Actuellement désynchros : le repo garde l'ancienne baseline, `/var/www` a la nouvelle charte pour visualisation.
- ⚠️ Deux fichiers `.env` pour clé OpenAI (cf `problems.yaml` → P12).
- ⚠️ Ne jamais éditer `index.html` à la main une fois Phase 4 livrée — modifier les sources (`sources/*.yaml` ou `sections/*.html` ou `templates/shell.html`) puis rebuild.
- ⚠️ Vérifier `curl -I https://digital-humans.fr/docs/refonte/` → `HTTP 200` après chaque déploiement.
- ⚠️ `sections/*.html` et `templates/shell.html` : si on change l'indentation du marker `<!-- SECTION:X -->` dans le shell, adapter `split_sections.py`. Idem pour `<!-- PARTIAL:X -->` : regex `^[ \t]*<!-- PARTIAL:name -->\n?`.
- ⚠️ `collect_rag_stats()` nécessite `backend/venv` actif (chromadb).
- ⚠️ `AGENT_DOC_META` dans `collect.py` synchronisé avec `agents_registry.yaml` (garde-fou BuildError).
- ⚠️ `replace_marker_preserving_indent` : PARTIAL → `reindent=True` (défaut, templates Jinja à colonne 0). SECTION → `reindent=False` (fragments déjà indentés).
- ⚠️ **Nouveau shell Studio** : les sections sont désormais toutes visibles en scroll continu. Le JS scroll-spy dépend de `.section[id]`. Si on ajoute une section sans `id=`, elle échappe au TOC side.
- ⚠️ Les `<br/>` dans les diagrammes Mermaid (syntaxe Mermaid, pas HTML) sont interprétés comme balises par des parsers HTML stricts — ignorer.

## Environnement de travail
- VPS : `72.61.161.222`, Ubuntu 24.04
- Repo : `/root/workspace/digital-humans-production`
- Branche : `feature/docs-refonte`
- Python venv : `backend/venv/` (Jinja2 + chromadb)
- Dernier commit : `79fb79c` (Phase 3). Prochain : charte Studio (en cours).
