# Plan de refonte de la documentation `docs/refonte/`

**Auteur·e·s** : Sam + Claude (session 24 avril 2026)
**Statut** : PROPOSÉ
**Contexte** : La doc HTML a dérivé de 2,5 mois (dernière édition manuelle 14 fév, vs nombreux changements 18 avril Session 3 + RAG ingest 24 avril). On veut qu'elle reste à jour sans gymnastique humaine.

---

## 1. Diagnostic

### Pourquoi la doc dérive

1. **Sources dupliquées** — les mêmes informations sont écrites à plusieurs endroits :
   - Stats RAG : dans `index.html` (×6 occurrences) + dans `CLAUDE.md` + dans `CHANGELOG.md`
   - Liste agents : `index.html` + `agents_registry.yaml` + `CLAUDE.md`
   - Statut des problèmes P0-P11 : `index.html` + `CHANGELOG.md` + mémoire Claude
2. **Mise à jour manuelle** après chaque sprint → oubliée dès qu'on travaille sous pression
3. **Mono-fichier 1100 lignes** → toute modification nécessite de recharger le gros HTML, avec risque de casser le HTML
4. **Pas de validation** — on ne sait jamais si la doc servie publiquement est cohérente avec le code
5. **Deux copies manuelles** (`docs/refonte/` repo + `/var/www/.../refonte/`) synchronisées à la main

### Ce qui marche et qu'il faut préserver

- HTML single-file : léger, pas de framework lourd, autonome (Mermaid CDN unique)
- Design et navigation UI propres
- Diagrammes Mermaid interactifs bien intégrés
- URL publique stable `https://digital-humans.fr/docs/refonte/`

---

## 2. Principes directeurs

| # | Principe | Implication |
|---|---|---|
| 1 | **Single Source of Truth (SSoT)** | Chaque fait existe à UN seul endroit. Les autres le référencent ou le génèrent. |
| 2 | **Build-time, pas runtime** | La doc reste statique (HTML servi par nginx) mais assemblée par un script. Pas de backend. |
| 3 | **Fail loud** | Si une source manque ou est incohérente, le build échoue bruyamment. Pas de silence. |
| 4 | **Idempotent** | `python3 tools/build_docs.py` doit pouvoir tourner 10 fois sans effet secondaire. |
| 5 | **Format lisible** | Les fichiers sources (YAML/MD) restent lisibles par un humain sans outil. |
| 6 | **Autorégénération après commit** | Hook git post-commit regen. Si quelqu'un oublie, CI le rattrape. |

---

## 3. Architecture cible

### Sources de vérité (fichiers existants, à documenter formellement comme SSoT)

| Section doc | Source de vérité | Type |
|---|---|---|
| Liste des 11 agents + rôles + modèles LLM | `backend/config/agents_registry.yaml` | YAML structuré (existe) |
| Profiles LLM (cloud/on-premise/freemium) | `backend/config/llm_routing.yaml` | YAML structuré (existe) |
| Stats RAG (chunks, collections, dim) | `chromadb` live query | API (existe) |
| Services actifs + statuts | `systemctl list-units` | Probe shell (existe) |
| Timeline / Journal | `CHANGELOG.md` + `git log` | Markdown + shell (existe) |
| Problèmes P0-P11 (statut, fix commit) | **À créer** : `docs/refonte/sources/problems.yaml` | YAML à produire |
| Stack technique (versions) | **À créer** : `docs/refonte/sources/stack.yaml` | YAML à produire |
| ADRs (décisions d'architecture) | `docs/ADR-*.md` | Markdown (existe) |

### Sections rédactionnelles (restent manuelles, dans fichiers dédiés)

Ces sections demandent de la narration — pas d'auto-génération pertinente :
- Vue d'ensemble (intro)
- Architecture (diagrammes Mermaid)
- Flux SDS et BUILD (diagrammes séquence)
- HITL & Chat Multi-Agent
- Base de données (tables)
- API Reference (volatile, auto-gen risqué — OpenAPI JSON direct meilleur choix à terme)
- Frontend (pages / composants)
- Plan de refonte (narratif)

Chacune est stockée comme fragment HTML ou Markdown dans `docs/refonte/sections/`.

### Arborescence proposée

```
docs/refonte/
├── index.html                          ← généré, ne plus éditer à la main
├── DOCS_REFONTE_PLAN.md                ← ce document
├── SESSION_PROTOCOL.md                 ← comment reprendre entre conversations
├── sources/                            ← SSoT pour sections dynamiques
│   ├── problems.yaml                   ← P0-P11 statuts
│   ├── stack.yaml                      ← versions Python, Node, Postgres, etc.
│   └── meta.yaml                       ← "dernière build", "version doc", etc.
├── sections/                           ← fragments rédactionnels manuels
│   ├── overview.html
│   ├── architecture.html               (avec mermaid)
│   ├── sds-build.html                  (avec mermaid)
│   ├── hitl-chat.html
│   ├── database.html
│   ├── api-reference.html
│   ├── frontend.html
│   └── refonte-plan.html
├── templates/
│   ├── shell.html                      ← head + nav + footer, placeholder {{ BODY }}
│   ├── partials/
│   │   ├── agents.html.j2              ← Jinja2 depuis agents_registry.yaml
│   │   ├── llm-profiles.html.j2        ← Jinja2 depuis llm_routing.yaml
│   │   ├── rag-stats.html.j2           ← depuis probe ChromaDB
│   │   ├── services.html.j2            ← depuis systemctl
│   │   ├── problems.html.j2            ← depuis problems.yaml
│   │   └── timeline.html.j2            ← depuis CHANGELOG.md + git log
└── archive/
    └── index.html.pre-refonte-20260424 ← backup avant refonte

tools/
├── build_docs.py                       ← script de build principal
├── doc_status.py                       ← bootstrap de contexte pour Claude
└── lib/
    ├── collect.py                      ← fonctions de collecte (chroma, yaml, git)
    └── render.py                       ← rendu Jinja2
```

---

## 4. Phases d'exécution

### Phase 0 — Préparation (15 min, cette session)

**Livrables**
- [x] Ce document (`DOCS_REFONTE_PLAN.md`) committé dans le repo
- [ ] `SESSION_PROTOCOL.md` créé (comment reprendre dans une nouvelle conversation)
- [ ] Branche git `feature/docs-refonte` créée

**Bloquant** : Validation de Sam sur la direction générale avant de coder quoi que ce soit.

### Phase 1 — SSoT explicites (1h)

Créer les sources YAML manquantes, en extrayant les données de la doc HTML actuelle.

**Livrables**
- `docs/refonte/sources/problems.yaml` — P0 à P11 avec statut, commit fix, date
- `docs/refonte/sources/stack.yaml` — versions (Python, Node, Postgres, Redis, Ollama…)
- `docs/refonte/sources/meta.yaml` — titre site, date dernière build auto

**Format exemple (problems.yaml)** :

```yaml
version: 1
problems:
  - id: P0
    title: "async def → sync def (event loop blocking)"
    status: fixed                    # fixed | partial | planned
    fixed_in:
      - commit: 7aa5db9
        date: 2026-02-14
        sprint: "S0 + A-7/A-8"
    description: "Routes FastAPI async avec SQLAlchemy sync bloquaient l'event loop."

  - id: P4
    title: "Fat controller pm_orchestrator"
    status: partial
    description: "Service reste à ~3396 lignes après split initial."
    next_action: "Décomposer en handlers par phase (SDS/BUILD)."

  - id: P11
    title: "RAG health silencieux"
    status: fixed
    fixed_in:
      - commit: e4388f4
        date: 2026-04-18
        sprint: "A-10"
    description: "RAG outages remontés en ERROR + health check startup."
```

### Phase 2 — Split sections rédactionnelles (1h)

Découper `index.html` actuel en fragments `sections/*.html` + un `templates/shell.html` commun.

**Livrables**
- `templates/shell.html` — head, nav, script, placeholder `{{ BODY }}`
- `sections/*.html` — 9 fragments (overview, architecture, sds-build, hitl-chat, database, api-reference, frontend, refonte-plan, journal)

Ces fragments restent en HTML pur (pas de Jinja) pour les rédactionnels statiques.

**Validation** : `build_docs.py --sections-only` doit produire un HTML identique à l'actuel (diff vide après strip whitespace).

### Phase 3 — Collectors + templates dynamiques (2h)

Implémenter `tools/lib/collect.py` avec 6 fonctions :

```python
def collect_agents() -> dict:         # agents_registry.yaml
def collect_llm_profiles() -> dict:   # llm_routing.yaml
def collect_rag_stats() -> dict:      # chromadb.PersistentClient().list_collections()
def collect_services() -> list:       # systemctl list-units --type=service
def collect_problems() -> list:       # sources/problems.yaml
def collect_timeline() -> list:       # CHANGELOG.md + git log --since
```

Chacune documentée avec :
- Format d'entrée (chemin fichier ou commande shell)
- Format de sortie (dataclass ou dict typé)
- Ce qui se passe en cas d'indisponibilité (raise BuildError)

**Livrables**
- `tools/lib/collect.py` (6 fonctions + tests unitaires)
- `templates/partials/*.html.j2` (6 templates Jinja2)

### Phase 4 — Build script + validation (30 min)

```bash
tools/build_docs.py                    # build + copy vers /var/www
tools/build_docs.py --dry-run          # build → /tmp, pas de copy
tools/build_docs.py --verify           # build + parse HTML + compare
tools/build_docs.py --diff             # montre diff vs version actuellement servie
```

**Livrable**
- `tools/build_docs.py` avec CLI propre
- Validation HTML intégrée (html.parser)
- Copie atomique vers `/var/www/digital-humans.fr/docs/refonte/` (write tmp → mv)

### Phase 5 — Automatisation (30 min)

Deux leviers, en chaîne :

**5a. Git hook post-commit local**

```bash
# .git/hooks/post-commit
#!/bin/bash
if git diff HEAD~1 --name-only | grep -qE "(backend/config/.*\.yaml|CHANGELOG\.md|docs/refonte/sources|docs/refonte/sections)"; then
    echo "→ Docs source changed, rebuilding..."
    python3 tools/build_docs.py --verify
fi
```

**5b. Badge fraîcheur dans le HTML généré**

Le footer du HTML contient :
```html
<footer>
  Dernier build : 2026-04-24 12:34:56 UTC · commit abc1234 · 91,866 chunks
</footer>
```

Si le badge affiche une date trop ancienne, c'est un signal visuel qu'il faut rebuild.

**5c. (Optionnel, plus tard) CI GitHub Actions**

Job `docs-check` qui :
1. Clone le repo
2. Lance `build_docs.py --verify`
3. Compare avec la version servie (via curl digital-humans.fr)
4. Fail si divergence

### Phase 6 — Session protocol (15 min)

Document `SESSION_PROTOCOL.md` pour qu'une nouvelle conversation Claude puisse bootstraper en 3 minutes :

```markdown
## Bootstrap rapide (3 minutes)

1. Lire ces fichiers dans l'ordre :
   - `CLAUDE.md` (contexte projet, 7 KB)
   - `CHANGELOG.md` (last 50 lignes — les changements récents)
   - `docs/refonte/sources/problems.yaml`
   - `docs/refonte/STATUS.md` (état courant)

2. Lancer `python3 tools/doc_status.py` qui affiche :
   - Dernière build de la doc + delta commits
   - Sources modifiées non encore propagées
   - Tests E2E récents
   - Services UP/DOWN

3. Si doc stale, lancer `tools/build_docs.py --verify` AVANT toute modification.
```

---

## 5. Automatisation — niveaux d'ambition

| Niveau | Effort | Bénéfice | Recommandation |
|---|---|---|---|
| **N0** (actuel) | 0 | Manuel, dérive inévitable | À quitter |
| **N1** Phases 0-4 | ~5h | Build en une commande, sources séparées, validation HTML | ✅ **Minimum viable** |
| **N2** + Phase 5 | +1h | Autorégénération après commit, badge fraîcheur | ✅ **Recommandé** |
| **N3** + CI GitHub | +1h | Doc ne peut pas dériver sans qu'un check échoue | Plus tard |
| **N4** OpenAPI-driven API ref | +2h | API Reference toujours à jour depuis FastAPI directement | Nice to have |

---

## 6. Recommandation d'ordre d'exécution

### Cette conversation (aujourd'hui)
- [x] Phase 0 : ce document + `SESSION_PROTOCOL.md` + branche git
- [ ] Phase 1 : les 3 fichiers `sources/*.yaml` créés à partir du contenu actuel
- Total : ~1h30

### Prochaine session
- Phase 2 : split `index.html` en fragments
- Phase 3 : collectors + templates Jinja2
- Première exécution réussie de `build_docs.py`
- Total : ~3h

### Session +2
- Phase 4 : validation, CLI propre, modes diff/verify
- Phase 5 : hook git + badge + test en conditions réelles
- Total : ~1h30

### Total enveloppe
**~6h sur 3 sessions** pour passer de N0 à N2. Amortissement dès la 1ère mise à jour évitée (qui prend aujourd'hui 30 min à 1h manuellement + risque de dérive).

---

## 7. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| `build_docs.py` casse en prod | Moyenne | Haut (doc inaccessible) | Écriture atomique (tmp → mv), backup auto avant chaque build |
| `agents_registry.yaml` divergent du code | Basse | Moyen | Test unitaire au build qui importe `agents_registry.py` et compare |
| Hook git oublié sur un clone neuf | Haute | Faible | README rappelle `git config core.hooksPath .githooks` + script `make install-hooks` |
| Auto-gen de timeline trop verbeuse (git log fleuve) | Haute | Moyen | Filtrer sur commit messages taggés (`feat:`, `fix:`, `refactor:` uniquement) + limite de 20 dernières entrées |
| Drift entre `CHANGELOG.md` et réalité des commits | Moyenne | Faible | `CHANGELOG.md` reste rédactionnel (prime sur git log) ; git log est le fallback |

---

## 8. Décisions à prendre par Sam

1. **OK sur la direction générale ?** (SSoT, build-time, hybrid auto-gen / rédactionnel)
2. **OK sur le choix Jinja2 + Python stdlib** (vs Hugo, MkDocs, Docusaurus) ?
3. **OK sur le scope N2** (pas de CI pour l'instant) ?
4. **Branche git dédiée** `feature/docs-refonte` ou direct sur `main` ?
5. **Niveau de sparité souhaitée** entre sessions : faut-il que je documente chaque micro-décision, ou confiance sur jugement ?

---

_Ce document est lui-même un artefact de la refonte : il sera bientôt lié depuis `index.html` et versionné comme les autres fichiers_ `docs/refonte/`.
