# UI Bugs détectés pendant E2E #144 — à corriger après le test

Date détection : 2026-05-02 lors de l'execution 148 (project 100 "Essais Cliniques E2E #144")

## UI-001 — "No deliverables found for this phase" alors que le deliverable existe en DB
**Phase concernée** : 1 (Sophie/PM), 2 (Olivia/BA), probablement aussi 3 (Marcus) et 4 (Emma)

**Symptôme** : Page `/execution/{id}/monitor` affiche "No deliverables found for this phase" 
sous les sections "Phase X: ... — Deliverables", alors que les deliverables existent en DB.

**Diagnostic préliminaire** :
- `frontend/src/components/DeliverableViewer.tsx:25` mappe correctement les phases :
  - Phase 1 → `['pm_br_extraction', 'br_extraction']`
  - Et types similaires pour les autres phases
- Le deliverable `pm_br_extraction` (id 691) existe en DB pour execution 148
- Le filtre frontend devrait matcher

**Hypothèses** :
1. Fetch n'est pas re-trigger après que la phase termine (timing React)
2. Le filtre par execution_id côté API ne retourne pas le bon set
3. Un problème de cache/invalidation côté frontend
4. Les types attendus pour phases 2/3/4 ne matchent pas les types réels en DB

**À investiguer** :
- Endpoint `/api/executions/{id}/deliverables` ou équivalent — qu'est-ce qu'il retourne ?
- Les deliverable_types réellement saved par chaque agent vs ceux mappés dans `DeliverableViewer.tsx`
- Logs front en devtools network pour voir les calls et leurs réponses

## UI-002 — Elapsed time toujours "—" sur la page monitor
**Symptôme** : Le champ "ELAPSED" reste à "—" même quand l'execution tourne depuis plusieurs minutes.

**Hypothèses** :
1. Le champ lit `started_at` et calcule (now - started_at), mais `started_at` peut être null
2. Le format de date attendu côté front ne matche pas l'output backend
3. Le formatter ne tourne pas (useEffect mal configuré, pas de timer interval)

**À investiguer** :
- `frontend/src/pages/ExecutionMonitoringPage.tsx` — chercher "elapsed" ou "ELAPSED"
- Vérifier si `executions.started_at` est bien populé en DB (vu en DB : `started_at` est bien là)
- Probablement un useEffect manquant qui devrait re-render toutes les secondes

## Priorité
P3 — cosmétique, n'affecte pas le pipeline. À traiter dans le sprint post-E2E #144 / 
pre-launch public Pro/Team (ne pas livrer aux utilisateurs Pro avec ces 2 bugs visibles).

## UI-003 — "First take" reste affiché malgré une révision en cours
**Symptôme** : La sidebar gauche affiche "REVISIONS · first take" même quand l'execution est en train de revise (revision 1, 2, ...).

**Attendu** : Pendant la revision 1, devrait afficher "revision 1" ou "first revision". Pendant rev 2, "revision 2".

**À investiguer** :
- `frontend/src/pages/ExecutionMonitoringPage.tsx` — chercher "first take" / "REVISIONS"
- Probablement basé sur une variable qui n'est pas mise à jour quand `revision_count` change

## UI-004 — Menu sidebar se chevauche / devient illisible au scroll
**Symptôme** : En scrollant la page execution monitor, le panneau sidebar gauche (BOX OFFICE, REVISIONS, STATE, ACTS) se chevauche avec le main content et devient illisible.

**Attendu** : sidebar sticky propre OU défilante avec son propre scroll, sans recouvrement.

**À investiguer** :
- CSS layout dans `ExecutionMonitoringPage.tsx`
- Probablement `position: sticky` avec un mauvais `top` ou un container manquant
