# SDS templating depuis DB — État courant

**Dernière mise à jour** : 2026-04-25 (session Claude+Sam, fin itération 2)

## Phase courante
**Itération 2 (Solution Design / sec-6) close.** 13/13 sous-sections instrumentées en Jinja2 + DB. Build ~1.2s, 0 coût LLM. Reste 11 sections SDS encore en HTML "en dur" dans le shell.

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

### Iter 3 — Sections 1, 2, 3 (proposé)
Templater **Project Overview + Business Requirements + Use Cases**. Les 2 et 3 sont l'ossature du SDS et représentent ~25 BRs Sophie + 58 UCs Olivia. Une fois fait, on aura **4/12 sections** templatées DB-driven.

### Iter 4 — Sections lourdes (à explorer)
- Section 7 Gap Analysis (Marcus, 81K JSON) — challenge structuré
- Section 11 Test Strategy (Elena, 157K) — la plus volumineuse
- Le helper `render_value` du partial sec-6 sera réutilisé partout où il y a des structures imbriquées

### Iter 5 — Sections moyennes
- Section 4 Use Case Digest (Emma)
- Section 5 As-Is Analysis (Marcus)
- Section 8 Coverage Report (Emma)
- Section 9 Data Migration (Aisha)
- Section 10 Training (Lucas)
- Section 12 CI/CD Deployment (Jordan)

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
- Partial sec-6 : `docs/sds/templates/partials/solution_design.html.j2`
- Collector : `tools/lib/collect_sds.py`
- Builder : `tools/build_sds.py`
- Status sœur (refonte doc) : `../refonte/STATUS.md`
