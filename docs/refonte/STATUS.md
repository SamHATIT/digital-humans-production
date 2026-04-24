# Refonte doc — État courant

**Dernière mise à jour** : 2026-04-24 (session Claude+Sam, Phase 3 scaffolding **déployé et validé**)

## Phase courante
**Phases 0, 1, 2, 3 terminées.** Prochaine : **Phase 4** (backup auto + copy atomique vers `/var/www/` + activation écriture sur `index.html`).

## Décisions actées
- **Framework** : Jinja2 + Python stdlib (pas MkDocs / Hugo). Raison : léger, zéro dépendance neuve, sources de vérité spécifiques au projet.
- **CI** : reportée à post-N2 (après que le hook git local ait fait ses preuves pendant ~1 mois).
- **Branche** : `feature/docs-refonte` (dédiée).
- **Backups auto** : `*.bak.YYYYMMDD_HHMMSS` à conserver 7 jours minimum, auto-générés par `build_docs.py` (Phase 4).
- **Source unique par type** : chaque fait vit à un seul endroit (cf `DOCS_REFONTE_PLAN.md §3`).
- **Validation rebuild** : chaque build doit produire un HTML strictement identique (ou documenté) à la version précédente tant qu'aucune source n'a changé. `split_sections.py` pose la référence byte-à-byte.
- **Pattern B pour Phase 3** (acté session 24 avr) : les partials Jinja2 produisent uniquement les *blocs data* (tables, cartes, timeline). Le rédactionnel des sections (h2, intros, blocs narratifs) reste en HTML brut dans `sections/*.html`. Un marker `<!-- PARTIAL:X -->` signale où injecter le bloc généré. Deux passes dans `build_docs.py` : partial→section, puis section→shell.

## Fait session 24 avril 2026
- ✅ Phases 0+1+2 closes (commit `eb0a803` + update `a4b12ae`)
- ✅ **Phase 3 déployée et validée** :
  - 11 fichiers scaffolding posés (md5 matchés, cf `REPRISE_PHASE3.md`)
  - 6 markers `<!-- PARTIAL:X -->` insérés dans 5 sections (`problems`, `rag`, `infra`, `agents`×2, `journal`)
  - **Bugfix `build_docs.py`** : ajout flag `reindent: bool = True` sur `replace_marker_preserving_indent`, appelé avec `reindent=False` dans `assemble_shell`. Sans ce fix, les sections (déjà indentées à 2 espaces) se voyaient réindentées une deuxième fois par le marker (lui aussi à 2 espaces), produisant un décalage global de +2 espaces sur tout le contenu. PARTIALS gardent le comportement de réindentation (templates à colonne 0).
  - **Build validé** : `index.generated.html` produit (59 135 chars), **268 lignes de diff** contre `index.html`, toutes dans les 4 zones dynamiques attendues :
    - **Agents table** : migration tiers 4→2 (`critical`/`complex` → `orchestrator`/`worker`), rôles depuis registry YAML, formatage multi-ligne Jinja
    - **RAG table** : comptages live (total 91 866 chunks, 6 collections), ligne Total ajoutée
    - **Services table** : statuts live → expose 2 drifts réels :
      - `digital-humans-worker` marqué **inactive** (stop propre le 18 avr 16:18 UTC). Doc manuelle disait "active". → à vérifier si le worker doit être redémarré.
      - `ollama` marqué **active** depuis le 12 avr 12:57 UTC. Doc manuelle disait "OFF désactivé volontairement". → doc obsolète, Ollama tourne bien.
    - **Problems cards** : textes depuis `problems.yaml` (plus détaillés que les résumés manuels), **P12 détecté** (deux fichiers `.env` OpenAI) → count passe de "2 partiels" à "3 partiels", total 13.
  - Aucun diff sur le rédactionnel statique ni sur l'indentation globale.

## Prochaines étapes

### Phase 4 — écriture sur index.html + backup auto + déploiement /var/www
Livrables attendus :
- `build_docs.py` écrit directement dans `index.html` (avec backup `index.html.bak.YYYYMMDD_HHMMSS` avant).
- Option `--deploy` qui copie atomiquement vers `/var/www/digital-humans.fr/docs/refonte/index.html` (cp → tmp → mv).
- Purge backups > 7 jours.
- Smoke test post-build : `curl -I https://digital-humans.fr/docs/refonte/` doit retourner HTTP 200.

### Action courte à décider avec Sam (hors refonte doc)
- **ARQ Worker** : reprise d'un `sudo systemctl start digital-humans-worker` si des exécutions SDS/BUILD sont attendues (sinon laisser off est un choix conscient).

## Questions en attente
_(aucune)_

## Pièges connus (à relire avant toute modif)
- ⚠️ `index.html` existe en 2 exemplaires : `docs/refonte/` (repo) et `/var/www/digital-humans.fr/docs/refonte/`. Toujours synchroniser les 2. **En Phase 3, `build_docs.py` écrit dans `index.generated.html` — `index.html` ne bouge pas. Phase 4 change ça.**
- ⚠️ Deux fichiers `.env` pour clé OpenAI : `backend/.env` + `/opt/digital-humans/rag/.env` (cf `problems.yaml` → P12, maintenant affiché comme "Partiel" dans problems card).
- ⚠️ Ne jamais éditer `index.html` à la main une fois Phase 4 livrée — modifier les sources (`sources/*.yaml` ou `sections/*.html`) puis rebuild.
- ⚠️ Vérifier `curl -I https://digital-humans.fr/docs/refonte/` après chaque déploiement — `HTTP 200` attendu.
- ⚠️ `sections/*.html` et `templates/shell.html` forment un couple : si on change l'indentation du marker `<!-- SECTION:X -->` dans le shell, adapter `split_sections.py` en conséquence. Idem pour les nouveaux `<!-- PARTIAL:X -->` : la regex de `replace_marker_preserving_indent` attend `^[ \t]*<!-- PARTIAL:name -->\n?`.
- ⚠️ `collect_rag_stats()` nécessite que `backend/venv` soit actif (pour chromadb). Sinon `BuildError: Module 'chromadb' indisponible`.
- ⚠️ `AGENT_DOC_META` dans `collect.py` doit rester synchronisé avec `agents_registry.yaml` — garde-fou : `collect_agents()` lève `BuildError` si désynchro.
- ⚠️ **Comportement réindentation `replace_marker_preserving_indent`** : PARTIAL (templates Jinja à colonne 0) → `reindent=True` (défaut). SECTION (fragments déjà indentés par split_sections) → `reindent=False`. Ne pas confondre lors d'ajouts futurs.
- ⚠️ Le partial `problems_status_cards.html.j2` génère du whitespace visible dans le HTML source (artefact Jinja) — cosmétique, rendu navigateur OK.

## Environnement de travail
- VPS : `72.61.161.222`, Ubuntu 24.04
- Repo : `/root/workspace/digital-humans-production`
- Branche : `feature/docs-refonte`
- Python venv : `backend/venv/` (Jinja2 + chromadb disponibles)
- Dernier commit attendu : Phase 3 complète (à poser à la fin de cette session)
