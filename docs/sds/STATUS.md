# SDS templating depuis DB — État courant

**Dernière mise à jour** : 2026-04-25 (session Claude+Sam, fin itération 4 — Lot B close)

## Phase courante
**Itération 4 — Lot B (sec-5, 7, 8) close.** 3 sections supplémentaires DB-driven : As-Is Analysis (organization + 20 standard objects), Gap Analysis (99 gaps avec descriptions + agents enrichis là où la ref est vide, summary tables, migration considerations, risk areas), Coverage Report (score + by_category avec missing tronqués + 14 critical gaps). Combiné aux iter 2/3, **8/12 sections** sont maintenant DB-driven (sec-1, 2, 3, 4, 5, 6, 7, 8). Reste 4 sections en HTML "en dur" : sec-9, 10, 11, 12 (cf. Lots C/D).

## Décisions actées
- **Stratégie** : suppression future de la phase 5 Emma SDS Final ($5-10, 10-15 min) au profit d'un assemblage direct depuis `agent_deliverables` via Jinja2.
- **Endpoints cibles** (à construire après templating complet) :
  - `GET /api/executions/{id}/sds.html` → live preview à la volée
  - `POST /api/projects/{id}/sds-versions` → snapshot figé dans `outputs/SDS_<project>_v<n>.html` + row sds_versions
  - `GET /api/projects/{id}/sds-versions/{n}/view` → fichier figé immutable
- **Branche** : `feat/sds-templating` (7 commits, **non encore mergée** sur main).
- **Référence visuelle figée** : `docs/sds/templates/_reference_logifleet_146.html` (md5 `66da5fef6227dd359a610fb8cbf87271`, 476625 bytes) — capture de l'exec 146 produite par l'ancien pipeline phase 5 Emma. Sert de baseline diff.
- **Pattern Jinja2** : un partial par section (`partials/<section>.html.j2`), inclus depuis `sds_shell.html.j2`. Le partial sec-6 contient un macro `render_value` récursif réutilisable pour toute structure JSON arbitraire (utilisé par 6.9 Integration Points).
- **Ordre canonique des clés** : PostgreSQL JSONB ne préserve pas l'ordre d'insertion. Pour reproduire l'ordre logique de la référence, l'ordre est défini explicitement dans le partial (cf. `ordered_keys` dans 6.9).
- **Compensation narrative** : 1 LLM call court Emma pour générer titre + subtitle marketing du hero (l'ancien hero était rédigé par Emma au sein du SDS final). À implémenter quand tout le pipeline templating sera en place. Décision Sam : **option C** validée.
- **Langue** : auto-détection FR/EN selon brief/site (pas de paramètre).
- **Mermaid client-side pour 6.1 ERD** : le shell charge `mermaid@10.9.0` depuis CDN avec config Studio (palette ink/bone/brass). Le partial rend `<pre class="mermaid">{erd_mermaid}</pre>`, mermaid.js convertit en SVG au chargement. Économie 20K chars par exécution vs SVG inline pré-rendu.

## Fait session 25 avril 2026

### Préambule — Migration LLM (sur `main`, mergée)
Avant le chantier templating, migration des modèles LLM par défaut :
- ✅ `bfc0c06` : Opus 4.6 → 4.7 + correction pricing ($5/$25 in/out) + drop `temperature` (déprécié sur Opus 4.7)
- ✅ `99d079b` : Sonnet 4.5 → 4.6 + SSoT model display_name + post-commit hook auto-rebuild docs (versionné dans `tools/git-hooks/post-commit`)
- ✅ `fcb9a66` : rebuild docs avec noms LLM à jour
- ⚠️ Le tokenizer Opus 4.7 utilise 1-1.35× plus de tokens que 4.6, à surveiller pour `MAX_TOTAL_LLM_CALLS=80`.

### Itération 1 — Hero + TOC (commit `d1e5f6e`)
- Setup `tools/build_sds.py` (CLI `--execution-id N [--output] [--check] [--diff-reference]`)
- Setup `tools/lib/collect_sds.py` (collectors PostgreSQL : `collect_execution_metadata`, `collect_coverage`, `collect_toc`, `collect_agents_meta`, `_count_business_requirements`, `_count_use_cases`, `build_render_context`)
- Filtre Jinja2 `humanize` ajouté plus tard en iter 2E (mappings spéciaux : `uc_refs`→`UC refs`, `rate_limits`→`rate limits`, etc.)
- `sds_shell.html.j2` : hero + TOC instrumentés en Jinja2, 12 sections inline en dur
- 14 lignes diff vs référence (toutes cosmétiques : titre marketing FR vs EN, date temps réel, etc.)

### Itération 2 — Solution Design (sec-6) — 13/13 sous-sections ✅
6 commits sur `feat/sds-templating` :

| # | Sous-section | Pattern | Status vs ref |
|---|---|---|---|
| 6.1 | Data Model ERD | Mermaid client-side | ✅ visuel |
| 6.2 | Custom Objects | Table 4 cols | +3 corrections |
| 6.3 | Field Details (17 sous-tables) | Pattern répété + picklists | +nombreuses corrections |
| 6.4 | Relationships | Table 4 cols | OK |
| 6.5 | Security Model (4 sous-tables) | Profiles + Permission Sets + Sharing Rules + OWD | +2 améliorations format |
| 6.6 | Queues | Table 4 cols | 0 diff |
| 6.7 | Reporting | Reports + Dashboards | Tables enrichies |
| 6.8 | Automation Design | Flows + Triggers + Jobs + Events | +3 sous-tables ajoutées |
| 6.9 | Integration Points | k-v vertical avec sous-tables imbriquées récursives | Pixel-near via macro `render_value` |
| 6.10 | UI Components | Apps + Pages + LWC + Quick Actions | +2 sous-tables ajoutées |
| 6.11 | UC Traceability (58 UCs) | Table 2 cols, dictsort | +nombreuses corrections |
| 6.12 | Tech Considerations (10) | Table 3 cols | +5 corrections |
| 6.13 | Risks (8) | Table 4 cols | +2 corrections |

### Découverte transversale : notre rendu DB-driven CORRIGE le HTML de référence
- ~30 corrections d'API names Salesforce (`Vehiclec`, `Sinistrec`, `Maintenance_Activityc`, `Alert_Configurationmdt` → `Vehicle__c`, `Sinistre__c`, etc.) — bug systématique du pipeline original perdant les `__` dans les textes descriptifs (parser markdown qui interprète `_` comme italique).
- 4 sections avec colonnes vides corrigées : OWD (colonne vide → Internal+External), Reports Purpose (vide → Object/Filters/Grouping), Flows Trigger (vide → event+condition), UI Components Purpose (vide → données vraies).
- 5 sous-sections manquantes ajoutées dans 6.8 et 6.10 : Apex Triggers (3), Scheduled Jobs (9), Platform Events (1), LWC Components (13), Quick Actions (6).
- 1 phrase tronquée restaurée (`Plan for Batch Apex migration path…` → `Plan for Batch Apex migration path if fleet exceeds 500 vehicles.`).

### Bug Jinja2 piégé (résolu en iter 2C)
`field.values` se résout vers la **méthode built-in** `dict.values()` avant la clé `'values'` (résolution attribut Python prioritaire). Fix : `field['values']` + `'values' in field` au lieu de `field.values`. **Règle** : utiliser le lookup dict explicite en Jinja2 dès qu'une clé peut entrer en collision avec `keys` / `values` / `items`.

### Stats finales sec-6
- Partial : 116K chars (avant) → 14K chars (après) = **réduction 88%**
- HTML rendu : 474K → 466K (-1.7%, malgré l'enrichissement des sous-tables car perte du SVG monstre de 20K)
- Diff métrique : 287 → 687 lignes (augmentation due aux enrichissements, pas à des régressions — les diffs supplémentaires sont quasi tous des corrections)
- Build time : ~1.2s vs 10-15min phase 5 Emma actuelle, **0 coût LLM**

### Itération 3 — Lot A (sec-1 à sec-4) — 4/4 sections ✅
1 commit sur `feat/sds-templating` :

| # | Section | Pattern | Status vs ref |
|---|---|---|---|
| 1 | Project Overview | Tables simples (project + 7 needs parsés du brief) | 0 diff (pixel-near) |
| 2 | Business Requirements | tbl-expand 25 BRs (id, title, category, priority, stakeholder, metadata.fields/validation_rules/acceptance_criteria/dependencies) + 5 constraints + 8 assumptions | 0 diff (pixel-near) |
| 3 | Use Cases | tbl-expand groupé par BR (24 BRs avec UCs), uc-cards avec actor/trigger/main_flow par UC, total 58 UCs | +53 corrections __c |
| 4 | Use Case Digest | 4.1 Synthesis enrichie (UC IDs croisés depuis uc_data.by_br, Complexity dérivée, Architectural notes) + 4.2 cross-cutting (23 shared objects, 1 integration point, 7 security req) + 4.3 19 recommendations + 4.4 25 data volume estimates | +26 enrichissements (4.1 vide en ref) |

### Bugs collectors corrigés (lot A blocking)
- **`collect_use_cases.by_br` était vide** : code utilisait `br_refs`/`br_id`, mais Olivia produit la clé `parent_br` (string). Fix : support `parent_br` en priorité, fallback sur `br_refs` puis `br_id`. Résultat : 58 UCs distribués sur 24 BRs (2 UCs/BR moyenne).
- **`collect_uc_digest.synthesis_by_br` était vide** : code lisait `synthesis_by_br` (liste), mais Emma produit `by_requirement` (dict {BR-id: {...}}). Fix : transformation dict → liste ordonnée par BR-id avec tri numérique propre. Bonus : `total_use_cases_analyzed` exposé pour le préambule sec-4.

### Filtres Jinja2 ajoutés à `build_sds.py`
- **`dot_join`** : joint une liste avec ` <span class='dot'>·</span> ` en escapant chaque item via un escape minimaliste (`& < >` seulement, pas les apostrophes — pour matcher la ref qui garde `'` brut). Indispensable car `autoescape=False` pour ne pas casser sec-6 (qui contient du HTML formé).
- **`ftrim`** : strip whitespace pour les valeurs DB qui peuvent avoir des espaces parasites (saisie utilisateur dans `projects.name`).

### Stats finales Lot A
- Shell : 7045 → 5282 lignes (**-25%**, -1763 lignes en dur remplacées par 4 includes)
- 4 partials : 33 + 48 + 34 + 53 = **168 lignes Jinja2** rédigées
- Diff total vs ref : 1133 → 977 lignes (réduction par convergence + corrections)
- **Diffs résiduelles dans les sections Lot A** : 0 régression. 79 diffs = 53 corrections __c (sec-3) + 26 enrichissements 4.1 (sec-4) — tous des gains qualitatifs nets.
- Build time : inchangé ~1.2s, **0 coût LLM**

### Itération 4 — Lot B (sec-5, 7, 8) — 3/3 sections ✅
1 commit sur `feat/sds-templating` :

| # | Section | Pattern | Status vs ref |
|---|---|---|---|
| 5 | As-Is Analysis | 5.1 organization en table key-value avec ordre canonique (PostgreSQL JSONB ne preserve pas) + chips pour les listes (permission_sets_standard, profiles_standard) ; 5.2 standard_objects en table 3 cols | 0 diff (pixel-near) |
| 7 | Gap Analysis | 7.1 4 sous-tables summary (totaux, by_category, by_complexity, by_agent — pourcentages calcules) ; 7.2 catalog 99 gaps avec gap_description + assigned_agent enrichis (la ref a les colonnes vides) ; 7.3 migration_considerations en bullets ; 7.4 risk_areas en table 3 cols (structure ref reproduite) | +201 enrichissements (99 gaps × 2 cols vides en ref) |
| 8 | Coverage Report | Preambule score + verdict + scoring_method ; 8.1 by_category avec missing tronques a 8 et "(+N)" pour le reste, "(none)" si vide ; 8.2 critical_gaps en table 4 cols ; preambule 8.2 avec missing_pct = 100 - score calcule | 0 diff (pixel-near apres fix 100.0% → 100% pour scores entiers float) |

### Nouveaux collectors (`tools/lib/collect_sds.py`)
- **`collect_as_is`** : charge `architect_as_is`, retourne `organization` (dict avec edition, api_version, release, custom_objects, apex_classes, apex_triggers, flows, lightning_pages, permission_sets_custom, permission_sets_standard, profiles_standard) + `standard_objects` (list[20] avec name, label, custom_fields_count, description).
- **`collect_gap_analysis`** : charge `architect_gap_analysis`, retourne `summary` (total_gaps, by_category, by_complexity, by_agent, total_effort_days), `gaps` (list[99] avec id, category, complexity, effort_days, gap_description, current_state, target_state, assigned_agent, uc_refs[], dependencies[]), `migration_considerations` (list[7]), `risk_areas` (list[8]).
- `collect_coverage` etait deja en place (iter 1) — reutilise pour sec-8.

### Pieges resolus
- **Bug shell : include sec-6 perdu** lors du remplacement automatique des sec-5/7/8. Mon script awk identifiait les bornes via `<section id='sec-X'>` mais sec-6 etait deja en `{% include %}` (pas de balise `<section>` dans le shell). Donc en remplacant sec-5 par son include, le code suivant jusqu'a sec-7 (incluant l'include sec-6) etait supprime. Fix : restaurer manuellement l'include solution_design.html.j2 entre as_is et gap. **Lecon** : pour les futurs lots, verifier que tous les includes existants sont preserves apres modification du shell.
- **Score 100.0% vs 100%** : `coverage.by_category[*].score` est tantot float (100.0) tantot int (100) selon la categorie. La ref affiche tout en int quand c'est entier. Fix : `{{ score | int if score == score | int else score }}` dans le partial sec-8.
- **Pourcentages de gaps by_agent** : la somme by_agent = 93 (pas 99 = total_gaps), donc 6 gaps n'ont pas d'agent assigne. Pourcentages calcules sur `agent_total = by_agent.values() | sum`, comme la ref.

### Stats finales Lot B
- Shell : 5282 → 4007 lignes (**-24%**, -1275 lignes en dur remplacees par 3 includes)
- 3 partials : 40 + 98 + 39 = **177 lignes Jinja2** redigees
- HTML rendu : 479,915 chars (vs 474,023 ref, delta +5,892 = enrichissements sec-7 + corrections sec-3 + sec-2 fields)
- Diff total vs ref : 977 → 309 hunks (**-67%**) — l'augmentation massive sec-7 (+201) compensee par la fin du HTML dur sur sec-5/7/8
- **Diffs residuelles dans les sections Lot B** : 0 regression. 201 diffs sec-7 = 100% enrichissements (gap_description + assigned_agent), 0 diff sec-5 et sec-8 (pixel-near).
- Build time : ~1.2s (inchange), **0 cout LLM**

## Workflow de référence

```bash
# Modification d'un partial ou collector
vim docs/sds/templates/partials/solution_design.html.j2   # ou tools/lib/collect_sds.py

# Build + diff vs référence
source backend/venv/bin/activate
python3 tools/build_sds.py --execution-id 146 --diff-reference
# → écrit docs/sds/rendered.html, affiche le diff vs _reference_logifleet_146.html

# Preview live (deja deploye sur le VPS pendant la session)
cp docs/sds/rendered.html /var/www/digital-humans.fr/sds-preview/146.html
# → https://digital-humans.fr/sds-preview/146.html

# Commit + push
git add docs/sds/templates/ tools/lib/collect_sds.py tools/build_sds.py
git commit -m "feat(sds): <description>"
git push
```

## Prochaines étapes

### Iter 5 — Lot C (sec-9, 10) — proposé
- Section 9 Data Migration (Aisha, ~1207 lignes en dur — la plus structurée)
- Section 10 Training (Lucas, ~419 lignes en dur)

### Iter 6 — Lot D (sec-11, 12) — proposé
- Section 11 Test Strategy (Elena, ~1316 lignes en dur — la plus volumineuse)
- Section 12 CI/CD Deployment (Jordan, ~347 lignes en dur)

### Bascule API et frontend (à faire en parallèle ou après)
- Endpoint `GET /api/executions/{id}/sds.html` (live preview)
- Endpoint `POST /api/projects/{id}/sds-versions` (snapshot figé)
- Frontend : bouton "Live preview" dans `ProjectDetailPage.tsx`
- Bascule : phase 5 Emma → appel `build_sds`, fin du LLM call SDS
- Compensation narrative : 1 LLM call court Emma pour titre+subtitle marketing du hero (option C validée par Sam)

### Backlog adjacent (non démarré)
- Frontend CSS refonte charte Studio (après bascule SDS)
- Activer adaptive thinking + effort levels Opus 4.7 (recommandation : `effort: "high"` minimum pour Sophie/Olivia/Marcus/Emma, `xhigh` pour Diego/Zara)
- P10 BaseAgent class (ordre migration : Sophie → Lucas → Jordan → Olivia → Aisha → Elena → Zara → Diego → Raj → Marcus → Emma)
- Admin Hub centralisé monitoring services
- Smoke test UC batches ARQ avant redémarrage worker (`feat/uc-batches-arq-jobs` WIP `730848b`)
- P12 consolider .env OpenAI : `backend/.env` + `/opt/digital-humans/rag/.env` à fusionner

## Pièges connus (à relire avant toute modif)
- ⚠️ **PostgreSQL JSONB ne préserve pas l'ordre des clés**. Pour tout rendu k-v vertical (style 6.9), définir un `ordered_keys` explicite dans le partial. Les clés inconnues sont rendues à la fin (defensive).
- ⚠️ **Jinja2 `dict.values` piège** : utiliser `field['values']` et `'values' in field`, jamais `field.values`. Idem pour `keys` et `items`.
- ⚠️ **Mermaid déjà chargé dans le shell** : ne PAS rajouter de `<script>` mermaid.min.js, l'init existe déjà avec la palette Studio.
- ⚠️ **Fichier de référence figé** : `_reference_logifleet_146.html` ne doit JAMAIS être régénéré. C'est notre baseline diff. Si on veut une nouvelle référence, créer un fichier différent.
- ⚠️ **StrictUndefined** : si une clé manque dans le contexte, le rendu plante (mieux qu'un trou silencieux). Si une clé est légitimement optionnelle, utiliser `{% if key %}` avant de l'accéder.
- ⚠️ **Le HTML de référence a des bugs** : ne PAS les copier. Notre rendu DB-driven les corrige (API names `__c`, colonnes vides, sections manquantes). Le diff métrique augmente avec les corrections, c'est normal.
- ⚠️ **Connection PostgreSQL hardcodée dans `collect_sds.py`** : `dbname=digital_humans_db user=digital_humans password=DH_SecurePass2025! host=127.0.0.1`. À déporter dans `.env` quand on bascule en production.
- ⚠️ **Filtre `humanize` à étendre** au fur et à mesure : si une nouvelle clé snake_case ambiguë apparaît (ex: `xx_yy` qui devrait s'afficher autrement que `xx yy`), ajouter un mapping dans `SPECIAL` de `tools/build_sds.py`.

## Environnement de travail
- VPS : `72.61.161.222`, Ubuntu 24.04
- Repo : `/root/workspace/digital-humans-production`
- Branche active : `feat/sds-templating` (7 commits, non mergée)
- Python venv : `backend/venv/` (Jinja2 + psycopg2)
- DB : PostgreSQL `digital_humans_db` (table `agent_deliverables`)
- URL preview : `https://digital-humans.fr/sds-preview/146.html` (notre rendu) / `146-reference.html` (référence)
- Build CLI : `python3 tools/build_sds.py --execution-id 146 --diff-reference`

## Liens
- Référence visuelle : `docs/sds/templates/_reference_logifleet_146.html`
- Shell : `docs/sds/templates/sds_shell.html.j2`
- Partial sec-1 : `docs/sds/templates/partials/project_overview.html.j2`
- Partial sec-2 : `docs/sds/templates/partials/business_requirements.html.j2`
- Partial sec-3 : `docs/sds/templates/partials/use_cases.html.j2`
- Partial sec-4 : `docs/sds/templates/partials/uc_digest.html.j2`
- Partial sec-5 : `docs/sds/templates/partials/as_is_analysis.html.j2`
- Partial sec-6 : `docs/sds/templates/partials/solution_design.html.j2`
- Partial sec-7 : `docs/sds/templates/partials/gap_analysis.html.j2`
- Partial sec-8 : `docs/sds/templates/partials/coverage_report.html.j2`
- Collector : `tools/lib/collect_sds.py`
- Builder : `tools/build_sds.py`
- Status sœur (refonte doc) : `../refonte/STATUS.md`
