# Protocole de session — Refonte doc Digital Humans

**Pour qui** : Claude (ou humain) reprenant le travail dans une nouvelle conversation.
**Objectif** : Bootstrap d'un contexte opérationnel complet en ≤5 minutes.

---

## Étape 1 — Lecture bootstrap (ordre fixe)

```bash
# 1.1 Contexte projet global (~7 KB)
cat /root/workspace/digital-humans-production/CLAUDE.md

# 1.2 État courant de la refonte doc (~2 KB)
cat /root/workspace/digital-humans-production/docs/refonte/STATUS.md

# 1.3 Plan de la refonte (~14 KB) — à lire SI on touche à la doc, sinon skip
cat /root/workspace/digital-humans-production/docs/refonte/DOCS_REFONTE_PLAN.md

# 1.4 Sources de vérité
ls /root/workspace/digital-humans-production/docs/refonte/sources/
cat /root/workspace/digital-humans-production/docs/refonte/sources/meta.yaml
```

## Étape 2 — Health check

```bash
# Services critiques
systemctl is-active digital-humans-backend digital-humans-frontend postgresql redis-server nginx
# RAG
curl -s http://127.0.0.1:8002/health
# Doc servie
curl -sI https://digital-humans.fr/docs/refonte/ | head -5
```

## Étape 3 — Delta depuis la dernière session

```bash
cd /root/workspace/digital-humans-production
# Commits nouveaux sur main depuis la dernière build de la doc
LAST_BUILD=$(grep "^last_build" docs/refonte/sources/meta.yaml | cut -d: -f2- | tr -d ' "')
git log --oneline --since="$LAST_BUILD" main
# Branche en cours
git branch --show-current
git status --short
```

## Étape 4 — Conventions de la branche

- **Branche de travail** : `feature/docs-refonte`
- **Commits** : préfixer avec `docs(refonte):`
- **Jamais pusher sur main directement** — PR via `gh pr create`
- **Backups** : `index.html.bak.YYYYMMDD_HHMMSS` générés auto par `build_docs.py`

## Étape 5 — Règles de modification

1. **Ne jamais éditer `index.html` à la main** une fois Phase 4 livrée. Toutes les modifs passent par :
   - `sources/*.yaml` pour les données factuelles
   - `sections/*.html` pour les contenus rédactionnels
   - puis `python3 tools/build_docs.py`

2. **Toute modification de source → rebuild + verify** :
   ```bash
   python3 tools/build_docs.py --verify
   ```

3. **Mettre à jour `STATUS.md`** en fin de session avec :
   - Ce qui a été fait
   - Prochaine étape
   - Questions en attente

## Étape 6 — Outils à disposition

| Outil | Usage |
|---|---|
| `tools/build_docs.py` | Regénère index.html depuis les sources (Phase 4+) |
| `tools/doc_status.py` | Affiche l'état de fraîcheur de la doc (Phase 5+) |
| `git log --since=...` | Delta de commits |
| `systemctl`, `journalctl` | Services + logs |
| MCP `Digital Human VPS` | Accès distant non-SSH pour Claude |

## Points durs connus

- **Deux copies du HTML** : `docs/refonte/index.html` (repo) et `/var/www/digital-humans.fr/docs/refonte/index.html` (servi). `build_docs.py` synchronise les deux. Ne jamais éditer `/var/www/` directement.
- **Deux `.env` pour la clé OpenAI** : `backend/.env` (FastAPI) ET `/opt/digital-humans/rag/.env` (fallback rag_service). À synchroniser ensemble. C'est documenté comme dette dans `sources/problems.yaml` sous `P12`.
- **Rebuild atomique** : `build_docs.py` écrit dans un tmp puis `mv` pour éviter un état HTML cassé servi pendant 200ms.

---

## Format d'un `STATUS.md` canonique

Voir `STATUS.md` pour un exemple vivant. Règle : max 40 lignes, pas de narration, format puces/tableaux.
