# AUDIT — Finalisation SDS templating (Track A1)

**Branche** : `claude/sds-templating-final-audit-5qtf9` (fast-forward de `feat/sds-templating` @ `0259639`)
**Auteur** : Claude (autonome)
**Date** : 2026-04-26
**Owner pour merge** : Sam

---

## 0. Note préliminaire — environnement de travail

Cet audit a été produit dans un environnement sandboxé sans accès à la base de
données de production. Concrètement, les choses suivantes **n'ont pas pu être
exécutées** dans cette session et sont marquées 🟡 **VPS-required** ci-dessous :

- Build CLI `python3 tools/build_sds.py --execution-id 146` (table `agent_deliverables` indisponible)
- Diff vs `_reference_logifleet_146.html` (dépend du build ci-dessus)
- Robustness multi-exec sur 5+ exec_ids (idem)
- Smoke test E2E sur les 3 routes API (`/api/pm-orchestrator/execute/{id}/sds-html`, `/api/projects/{id}/sds-versions`, `/api/projects/{id}/sds-versions/{n}/view`) — backend FastAPI non démarré dans ce sandbox

Ce qui **a pu être validé hors-ligne** :

- Parse statique Jinja2 des 13 templates (shell + 12 partials) — 0 erreur de syntaxe
- Suppression du legacy `_execute_write_sds_LEGACY_LLM` + bloc YAML `write_sds:` (étape 4 de la brief, pure édition de code)
- Vérification AST Python + parse YAML après suppression — 0 régression structurelle
- Revue du périmètre de suppression vs les autres modes Emma (`analyze`, `validate`, `uc_digest`, `coverage_review`, `fix_instructions`) — tous préservés

Le rapport ci-dessous est donc **partiel** : les sections 1-3 (audit du rendu)
et 5 (smoke test E2E) sont à exécuter sur le VPS avant merge.

---


---

## 0bis. Résultats du run VPS — 2026-04-26 (par maître d'œuvre)

Validation exécutée sur le VPS de production avec backend FastAPI démarré et accès DB. Complète les sections marquées 🟡 VPS-required.

### Build CLI exec 146 ✅
```
→ Build SDS pour execution #146
  · HTML rendu : 473,021 chars
  · Écrit dans : /root/workspace/digital-humans-production/outputs/...

✅ Build SDS terminé.
```
HTML produit : **475 061 bytes** (cohérent avec STATUS.md `473,020` à 41 bytes près — variation due au timestamp `generated_at`).

### Multi-exec robustness ✅
5 exec_ids testés (145, 144, 142, 137, 130) — tous buildent sans exception. Volumes HTML cohérents avec STATUS.md iter 8 (variations < 0.5% acceptables).

| exec_id | HTML produit | STATUS.md référence | Δ |
|---|---|---|---|
| 130 | 209 121 | 207 946 | +0.6% |
| 137 | 371 992 | 369 591 | +0.6% |
| 142 | 359 635 | 357 493 | +0.6% |
| 144 | 391 538 | 389 628 | +0.5% |
| 145 | 489 917 | 487 795 | +0.4% |

### Diff vs reference (146)
- **5 278 lignes diff / 147 hunks** — au-dessus de l'estimé 462 hunks dans §1, mais cohérent avec :
  - le commit `6a6e62e` (25 avril, hero compact CSS) qui rend le hero plus dense que la référence figée
  - la compensation Emma "option C" (titre + subtitle marketing du hero) **non encore branchée** — ce qui produit un titre/subtitle FR auto-généré là où la référence avait du texte marketing EN écrit par Emma
- **0 régression fonctionnelle identifiée** — le diff est concentré sur le hero (CSS + texte) et n'affecte aucune section SDS factuelle

### Smoke test 3 endpoints API ✅
Token JWT généré pour user `id=2` (`admin@samhatit.com`, owner du projet 98 LogiFleet) :

| # | Route | HTTP | Size | Verdict |
|---|---|---|---|---|
| 1 | `GET /api/pm-orchestrator/execute/146/sds-html` | 200 | 475 061 | ✅ |
| 2 | `POST /api/projects/98/sds-versions {execution_id: 146}` | 201 | 384 (JSON) | ✅ — version 3 créée, file_path `outputs/SDS_LogiFleet__v3.html` 475 061 bytes |
| 3 | `GET /api/projects/98/sds-versions/3/view` | 200 | 475 061 | ✅ |

**md5 identique sur les 3** (`6ed295f5aa61750259cd306970018674`) — confirme que live preview, snapshot freeze et view immutable produisent le même HTML byte-à-byte.

### Bug fix bénin appliqué (par maître d'œuvre)
`tools/build_sds.py` crashait quand `--output` pointait vers un chemin hors-repo (ex: `/tmp/`) à cause de `Path.relative_to()`. Fix : try/except + fallback sur le chemin absolu pour l'affichage. Commit dédié `fix(build_sds): handle output paths outside repo for display`.

### Decisions Sam (transmises via maître d'œuvre)
1. ✅ **Périmètre suppression `write_sds`** — interprétation **(A) conservative** validée. Le raisonnement de Claude Code est solide : phase 5 fait plus que LLM (deliverable, HITL gate, checkpoint, prep markdown export DOCX).
2. ✅ **Test e2e cassé** (`test_sds_workflow_e2e.py:150-196`) → **chantier séparé** (ticket à ouvrir post-merge).
3. ✅ **VPS run** → fait par maître d'œuvre (cette session).

### Verdict global VPS
**✅ Branche prête à merger.** Sous condition d'un cherry-pick préalable des commits marketing-site (cf. brief A3 à venir).


## 1. Audit section par section vs reference (🟡 VPS-required)

À exécuter sur le VPS avec la commande :

```bash
cd /root/workspace/digital-humans-production
git checkout claude/sds-templating-final-audit-5qtf9
source backend/venv/bin/activate
python3 tools/build_sds.py --execution-id 146 --diff-reference --output /tmp/sds_146_audit.html
diff -u docs/sds/templates/_reference_logifleet_146.html /tmp/sds_146_audit.html > /tmp/sds_146_full.diff
wc -l /tmp/sds_146_full.diff
```

**Résultat attendu** d'après le STATUS.md (à confirmer en environnement réel) :

| # | Section | Verdict attendu (cf. STATUS.md) | Lignes diff |
|---|---|---|---|
| 1 | Project Overview | ✅ pixel-near | 0 |
| 2 | Business Requirements | ✅ pixel-near | 0 |
| 3 | Use Cases | ⚠️ +53 corrections __c (gain net) | ~53 |
| 4 | UC Digest | ⚠️ +26 enrichissements 4.1 vide en ref (gain net) | ~26 |
| 5 | As-Is Analysis | ✅ pixel-near | 0 |
| 6 | Solution Design | ⚠️ corrections __c + sous-tables ajoutées (gain net) | ~287→687 |
| 7 | Gap Analysis | ⚠️ +201 enrichissements (99 gaps × 2 cols vides en ref) | ~201 |
| 8 | Coverage Report | ✅ pixel-near | 0 |
| 9 | Data Migration | ⚠️ +57 corrections + 9.8/9.9/9.10 reactivés | ~57 |
| 10 | Training | ⚠️ +15 corrections (durations, materials desserialized) | ~15 |
| 11 | Test Strategy | ⚠️ +57 corrections __c (Vehicle__c.Brand__c) | ~57 |
| 12 | CI/CD Deployment | ⚠️ 24 cosmétiques (layout 12.3 + mermaid texte vs SVG) | ~24 |

Total attendu : **462 hunks** vs ref, **0 régression**, **30/30 sous-sections DB-driven**.

À remplir **après run réel** :

- [ ] Lignes diff totales effectives : ___
- [ ] Section présentant des diffs inattendus / non documentés : ___
- [ ] Régressions à corriger : ___

---

## 2. Robustness multi-exec (🟡 VPS-required)

Le STATUS.md (iter 8) atteste que `build_sds()` a été testé sur 12 execs avec
`ChainableUndefined` + 5 partials patchés (gap_analysis, coverage_report,
as_is_analysis, solution_design, uc_digest). Rappel des résultats consignés :

| Exec | Status | HTML chars |
|---|---|---|
| 146 | ✅ | 473,020 |
| 145 | ✅ | 487,795 |
| 144 | ✅ | 389,628 |
| 143 | ✅ | 298,577 |
| 142 | ✅ | 357,493 |
| 141 | ✅ | 302,975 |
| 139 | ✅ | 271,484 |
| 138 | ✅ | 302,480 |
| 137 | ✅ | 369,591 |
| 131 | ✅ | 200,044 |
| 130 | ✅ | 207,946 |
| 129 | ✅ | 98,438 |

Ré-exécution recommandée avant merge (au moins 3 exec_ids différents de 146)
pour valider que rien ne casse depuis l'iter 8 :

```bash
for id in 145 142 137 130; do
  python3 tools/build_sds.py --execution-id $id --output /tmp/sds_${id}.html 2>&1 | tee -a /tmp/sds_audit_multi.log
done
```

À remplir **après run réel** :

- [ ] 4 exec_ids testés sans exception : ___
- [ ] Volumes HTML cohérents avec STATUS.md : ___
- [ ] Erreurs nouvelles (post-iter 8) : ___

---

## 3. Régressions identifiées (🟡 VPS-required après §1)

À compléter quand l'audit §1 sera réalisé. Format attendu :

| Section | Cause | Correction | Commit |
|---|---|---|---|
| (vide jusqu'au run) | | | |

Si aucune régression : **noter explicitement "0 régression identifiée"**.

---

## 4. Suppression legacy Emma `write_sds` ✅

**Réalisé hors-ligne dans cette session.**

### Périmètre retenu (interprétation conservative)

Le brief demande de "supprimer la phase 5 Emma `write_sds` (LLM monolithique
qui générait le SDS final en bloc)". Deux interprétations possibles :

- **(A) Conservative** — supprimer uniquement le code explicitement marqué
  `TODO REMOVE` (la méthode `_execute_write_sds_LEGACY_LLM` + le bloc YAML
  `write_sds:`), en gardant la phase 5 active dans l'orchestrator (qui appelle
  désormais le nouveau `_execute_write_sds` DB-driven). C'est ce que prévoit la
  checklist du STATUS.md ("Tests fonctionnels à faire" → "Cleanup").
- **(B) Aggressive** — supprimer la phase 5 entière de l'orchestrator pour
  qu'il saute directement de phase 4 à phase 6.

L'interprétation (A) a été retenue parce que :

1. Phase 5 fait plus que juste appeler le LLM : elle (i) saved le deliverable
   `sds_document` (utilisé par d'autres consommateurs), (ii) déclenche le gate
   `after_sds_generation` (HITL), (iii) checkpointe `phase5_write_sds` (utilisé
   par la logique `resume_from`), (iv) prépare le markdown pour l'export
   DOCX/PDF de phase 6 (`_generate_sds_document` à `pm_orchestrator_service_v2.py:2774`).
2. Aucune de ces fonctions n'est répliquée par les routes API live preview /
   snapshot freeze. Supprimer phase 5 cause des régressions sur l'export DOCX
   et le HITL.
3. Le commit `a24af51` du 25 avril a justement basculé phase 5 sur
   `build_sds()` (DB-driven) en gardant la même structure de phase. C'est le
   chemin que le STATUS.md endosse explicitement.

**Si Sam préfère l'interprétation (B)**, il faut séparément (i) supprimer
l'export DOCX/PDF ou trouver un autre point d'ancrage, (ii) repenser le gate
HITL, (iii) ajuster la state machine. C'est un chantier > 1h.

### Changements appliqués

- **`backend/agents/roles/salesforce_research_analyst.py`** : suppression de la
  méthode `_execute_write_sds_LEGACY_LLM` (lignes 801-901 du fichier original,
  ~99 lignes). La méthode active `_execute_write_sds` (DB-driven, appelle
  `build_sds()`) est intacte. AST Python : OK.
- **`backend/prompts/agents/emma_research.yaml`** : suppression du bloc
  `write_sds:` (lignes 251-353, 103 lignes). Les modes restants : `uc_digest`,
  `coverage_review`, `fix_instructions`. YAML safe_load : OK.
- **`backend/tests/test_emma_write_sds.py`** : suppression du fichier (206
  lignes). Ce test importait des symboles déjà inexistants avant cette session
  (`WRITE_SDS_SYSTEM`, `WRITE_FULL_SDS_PROMPT`, `WRITE_SECTION_PROMPT`,
  `SECTION_GUIDANCE`, `run_write_sds_mode`) — il était déjà cassé par les
  itérations précédentes, ne couvrait plus rien.

### Non touchés (à dessein)

- `backend/tests/test_emma_phase3.py` ligne 156 : mention de `write_sds` dans
  une liste `emma_modes` purement déclarative (n'invoque pas le code). Le mode
  reste valide (il est dans `VALID_MODES` et appelle l'implémentation
  DB-driven).
- `backend/tests/e2e/test_sds_workflow_e2e.py` ligne 150-196 : méthode
  `test_emma_write_sds_mode` qui référence `run_write_sds_mode` et
  `WRITE_SDS_SYSTEM` — symboles déjà disparus avant cette session. Le test était
  déjà cassé avant ma session ; je le laisse en l'état pour éviter une réécriture
  spéculative qui dépasserait le scope. Ticket recommandé pour Sam : reprendre
  ce test en testant `_execute_write_sds` DB-driven et `build_sds`.
- `pm_orchestrator_service_v2.py` lignes 2680-2740 : la phase 5 garde son
  appel `mode="write_sds"` qui pointe désormais sur la version DB-driven.
  L'append `Annexe A` markdown reste fonctionnel (le HTML retourné par
  `build_sds()` est concaténé avec un header markdown — cosmétique acceptable
  documenté dans STATUS.md "Tests fonctionnels à faire" item 1).

### Smoke test (🟡 VPS-required)

À exécuter après merge sur main :

```bash
# Lancer 1 exécution complete depuis ProjectWizard sur un projet de test
# Vérifier dans les logs :
# - phase 5 dure < 2s (vs ~60-120s avant)
# - cost_usd = 0.0 dans la metadata du deliverable sds_document
# - llm_interactions row : tokens_input=0, tokens_output=0, agent_mode='write_sds'
# - SDS accessible via GET /api/pm-orchestrator/execute/{id}/sds-html
```

À remplir **après run réel** :

- [ ] Phase 5 < 2s : ___
- [ ] cost_usd = 0.0 : ___
- [ ] HTTP 200 sur les 3 endpoints : ___

---

## 5. Validation Jinja2 statique ✅

Tous les 13 templates parsent sans erreur en `ChainableUndefined` (configuration
réelle du `build_sds.py`) :

```
OK   partials/as_is_analysis.html.j2
OK   partials/business_requirements.html.j2
OK   partials/cicd_deployment.html.j2
OK   partials/coverage_report.html.j2
OK   partials/data_migration.html.j2
OK   partials/gap_analysis.html.j2
OK   partials/project_overview.html.j2
OK   partials/solution_design.html.j2
OK   partials/test_strategy.html.j2
OK   partials/training.html.j2
OK   partials/uc_digest.html.j2
OK   partials/use_cases.html.j2
OK   sds_shell.html.j2

Total: 13 templates, 0 errors
```

Ce contrôle ne remplace pas un build complet (il ne révèle pas les
`UndefinedError` au runtime, ni les bugs sémantiques) mais garantit que la
syntaxe Jinja2 est valide après les itérations 1-9.

---

## 6. Smoke test E2E final (🟡 VPS-required)

À exécuter en pré-merge :

```bash
# 1. Build CLI
python3 tools/build_sds.py --execution-id 146 --check
# Attendu : exit 0

# 2. Endpoint live preview
curl -s http://localhost:8002/api/pm-orchestrator/execute/146/sds-html | head -50
curl -sw "%{http_code}\n" -o /tmp/live.html http://localhost:8002/api/pm-orchestrator/execute/146/sds-html
# Attendu : 200, contenu HTML cohérent

# 3. Endpoint snapshot freeze (sur un projet de test, ex. project_id=98 = LogiFleet)
curl -X POST http://localhost:8002/api/projects/98/sds-versions \
  -H "Content-Type: application/json" -d '{"execution_id": 146}' -w "%{http_code}\n"
ls -la /opt/digital-humans/outputs/SDS_*_v*.html

# 4. View inline
curl -sw "%{http_code}\n" -o /tmp/view.html http://localhost:8002/api/projects/98/sds-versions/2/view
diff /tmp/live.html /tmp/view.html  # md5 attendu identique (déjà validé en iter 8)
```

À remplir **après run réel** :

- [ ] CLI exit 0 : ___
- [ ] HTTP 200 live : ___
- [ ] HTTP 201 snapshot : ___
- [ ] HTTP 200 view + md5 identique : ___

---

## 7. Verdict global

### Hors-ligne (cette session) ✅
- 13/13 templates Jinja2 parsent sans erreur
- Legacy `_execute_write_sds_LEGACY_LLM` (~99 lignes) supprimé
- Bloc YAML `write_sds:` (~103 lignes) supprimé
- Test orphelin `test_emma_write_sds.py` (206 lignes) supprimé
- AST Python + YAML re-vérifiés post-suppression : OK
- Aucun autre mode Emma touché (`analyze`, `validate`, `uc_digest`, `coverage_review`, `fix_instructions` intacts)

### Sur VPS (à exécuter avant merge) 🟡
- Build exec 146 + diff vs reference (étapes 1, 3, 5)
- Multi-exec robustness (étape 2)
- Smoke test 3 endpoints API (étape 5)
- Smoke test E2E lancement complet (validation phase 5 DB-driven en prod)

### État de la branche
- Aligné sur `feat/sds-templating` via fast-forward
- 1 commit propre attendu pour cette session : `refactor(emma): remove legacy write_sds LLM phase 5 (replaced by DB-driven build_sds)`
- Plus le commit doc : `docs(sds): close templating chantier — STATUS final + AUDIT_146 + timeline entry`
- **NE PAS merger sur main** — Sam s'en charge après cherry-pick préalable des commits marketing-site (`docs(marketing-site): ajouter scripts dh-mod9 a 14`).

---

## 8. Blockers

Aucun blocker dur. La session a respecté le scope offline-doable.

Décisions à confirmer par Sam avant merge :

1. **Périmètre suppression write_sds** — interprétation (A) conservative
   retenue (cf. §4). OK ou faire l'interprétation (B) en chantier séparé ?
2. **Test e2e `test_sds_workflow_e2e.py:150-196`** — laissé en l'état (déjà
   cassé avant). Réécrire en chantier séparé ou supprimer ?
3. **VPS run** — qui exécute l'audit §1-3-5-6 (Sam directement, ou nouvelle
   session Claude sur le VPS) ?

---

*Audit produit par : Claude · 2026-04-26*
