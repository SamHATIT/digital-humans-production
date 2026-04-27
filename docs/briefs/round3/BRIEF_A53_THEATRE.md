# BRIEF A5.3 — Théâtre : monitoring d'exécution en charte Studio

> **Owner** : Claude Code (autonome, sandbox web)
> **Branche cible** : `feat/platform-studio` (continuer dessus, après A5.2)
> **Estimation** : 1 session longue (~5h équivalent dev humain — c'est le plus gros sous-brief)
> **Pré-requis** : A5.2 mergée (Wizard + BR Validation refondus)

---

## 1. Cadre stratégique

A5.1 a posé les fondations. A5.2 a livré le tunnel d'entrée (Casting).
A5.3 attaque le **deuxième tunnel narratif et le plus important** : le
Théâtre, soit le **monitoring en temps réel de l'exécution** des agents
sur un projet.

Le Théâtre est le **moment de vérité** du produit. C'est ici que
l'utilisateur voit son ensemble travailler. Il n'observe pas un script
qui tourne en arrière-plan, il **assiste à une représentation théâtrale
narrée**.

À la fin de A5.3, un utilisateur peut :
- Suivre une exécution SDS en cours (Sophie → Olivia → Emma → Marcus → Sophie)
- Voir un **stepper Studio** qui montre l'acte en cours, avec accent agent
  (indigo/plum/terra/sage/ochre)
- Lire une **timeline narrative** des actions des agents (au lieu d'un log
  technique)
- Interagir avec l'agent en cours via une **chat sidebar restylée** (HITL :
  human-in-the-loop)
- Visualiser les **livrables intermédiaires** au fur et à mesure (BR, RDD,
  Architecture, SDS final)
- Suivre une exécution BUILD avec le même paradigme (Diego/Zara/Raj se
  succèdent)

Pages cibles refondues en A5.3 :
- `/execution/:projectId` (ExecutionPage.tsx) — page d'entrée d'une exécution
- `/execution/:executionId/monitor` (ExecutionMonitoringPage.tsx, **935
  lignes legacy**) — le monitoring SDS en cours
- `/execution/:executionId/build` (BuildMonitoringPage.tsx, **475 lignes
  legacy**) — le monitoring BUILD en cours

Pages NON refondues (A5.4) :
- `/projects` listing, `/project/:id`, `/agent-tester`, `/pricing`

---

## 2. État après A5.2 (rappel anticipé)

✓ Toute la fondation Studio (A5.1)
✓ Wizard 5 actes refondu en charte Studio
✓ BR Validation refondue
✓ framer-motion v11 installé, shim retiré
✓ CreditCounter fonctionne (endpoint billing identifié)
✓ Composants Studio communs créés en A5.2 : `StudioInput`, `StudioTextarea`,
  `StudioSelect`, `StudioStepper`, `WizardActHeader`, etc.
⚠️ Reste 7 pages legacy avec bandeau "redesigned"

---

## 3. Périmètre A5.3

### 3.1 Refondre ExecutionPage (entrée vers monitoring) (~1h)

`/execution/:projectId` est la page qui arrive après l'approbation du BR.
Aujourd'hui c'est probablement minimaliste (ou dispatch direct).

Nouvelle version Studio :

```
┌─────────────────────────────────────────────┐
│  Header Studio                              │
├─────────────────────────────────────────────┤
│                                             │
│   № 04 · CURTAIN UP                         │
│   The ensemble takes the stage.             │
│                                             │
│   Project: LogiFleet — Service Cloud        │
│                                             │
│   ┌────────────────┬───────────────────┐    │
│   │  Phase SDS     │  Phase BUILD      │    │
│   │  Status: ready │  Status: pending  │    │
│   │                │                   │    │
│   │  Estimated:    │  Estimated:       │    │
│   │  ~ 800 credits │  ~ 3 500 credits  │    │
│   │                │                   │    │
│   │  [◗ Begin SDS] │  Begins after SDS │    │
│   └────────────────┴───────────────────┘    │
│                                             │
└─────────────────────────────────────────────┘
```

CTA "Begin SDS" → POST sur l'endpoint existant
(`/api/executions/start` ou similaire, à vérifier dans `services/api.ts`).
Une fois lancé, redirige vers `/execution/:id/monitor`.

### 3.2 Refondre ExecutionMonitoringPage — le Théâtre SDS (~3h)

C'est **LE gros morceau de A5.3** (935 lignes legacy).

#### 3.2.1 Layout général

```
┌──────────────────────────────────────────────────────────┐
│  Header Studio                                           │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  № 04 · ACT II — THE BRIEF                               │
│  Olivia is taking notes.                                 │
│  Cormorant ital, accent plum (Act II)                    │
│                                                          │
│  ┌──────────────┬──────────────────────────────────┐     │
│  │              │                                  │     │
│  │  TIMELINE    │  CURRENT AGENT VIEW              │     │
│  │  (left,      │                                  │     │
│  │   sticky)    │  [ Olivia avatar large + name ]  │     │
│  │              │  Role: Solution Architect        │     │
│  │  ✓ Sophie    │  Acting since: 2:14              │     │
│  │  ◗ Olivia    │                                  │     │
│  │  · Emma      │  Currently doing:                │     │
│  │  · Marcus    │  Reviewing the BR for technical  │     │
│  │  · Sophie    │  feasibility                     │     │
│  │              │                                  │     │
│  │              │  Latest output (live):           │     │
│  │  ────        │  [ Document/section preview ]    │     │
│  │              │                                  │     │
│  │  CREDITS     │  ┌──────────────────────────┐    │     │
│  │  Used 124    │  │  Sidebar Chat (HITL)     │    │     │
│  │  Left 1123   │  │  — Olivia: ...           │    │     │
│  │              │  │  — You: ...              │    │     │
│  │              │  │  [ Compose message ]     │    │     │
│  │              │  └──────────────────────────┘    │     │
│  │              │                                  │     │
│  └──────────────┴──────────────────────────────────┘     │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

#### 3.2.2 Composants à créer/refondre

- **`AgentStage.tsx`** (nouveau) — composant qui affiche l'agent en cours
  d'action : avatar large (utiliser `public/avatars/large/{agent}.png`),
  nom, rôle, tagline, accent acte. Pulse animation framer-motion sur le
  cadre brass tant que l'agent est actif.
- **`StudioTimeline.tsx`** (refait depuis `TimelineStepper.tsx` 156 lignes
  legacy) — timeline verticale gauche, chaque step = un agent dans l'ordre
  de la phase SDS (Sophie → Olivia → Emma → Marcus → Sophie). États :
  `pending` (bone-4), `current` (accent acte, pulse), `completed` (brass
  check), `failed` (error icon). Click sur un step passé = voir son livrable.
- **`AgentLivePreview.tsx`** (nouveau) — preview live de ce que l'agent
  produit. Polling endpoint `/api/executions/:id/current-output` (vérifier
  qu'il existe ou utiliser `/api/executions/:id` qui retourne tout).
  Affichage rendu Markdown avec `StructuredRenderer` Studio-skinné.
- **`ChatSidebarStudio.tsx`** (refait depuis `ChatSidebar.tsx` 307 lignes
  legacy) — chat HITL avec l'agent en cours. Fond ink-2, bulles bone/brass,
  composer Studio, attachments si supportés. Bouton "Submit feedback" en
  brass.
- **`ExecutionMetricsStudio.tsx`** (refait depuis `ExecutionMetrics.tsx`
  276 lignes legacy) — sidebar gauche bas avec credits used/left + temps
  écoulé + nombre d'itérations.

#### 3.2.3 Données et flux

L'orchestration backend existe déjà (Sophie pilote, état machine 24 états,
ARQ workers, etc.). Le frontend doit :

- **Polling** : toutes les 2-3s, fetcher `/api/executions/:id` pour
  récupérer l'état (current_agent, completed_agents, current_phase, etc.)
- **WebSocket** (si existant) : utiliser à la place du polling pour
  fluidité. Vérifier `services/api.ts` ou hooks existants comme
  `useExecutionProgress.ts`.
- **HITL** : quand un agent demande un input, le chat sidebar s'active
  (border accent acte qui pulse), notification mono "Olivia is asking
  for your input"
- **Livrables** : quand un livrable est produit (BR, RDD, Architecture,
  SDS), il apparaît dans `AgentLivePreview` ; click → ouvre dans une vue
  fullscreen avec `DeliverableViewer.tsx` (à restyler en Studio aussi)

#### 3.2.4 Animations Studio (framer-motion)

- **Transition d'acte** : quand on passe d'un agent au suivant, le titre
  Cormorant fade-out, le nouveau fade-in en 400ms ease-out, le step
  correspondant dans la timeline glisse vers "current"
- **Curtain rises** : au tout premier chargement de la page (juste après
  click "Begin SDS"), animation de rideau qui se lève — gradient ink qui
  remonte de bas en haut en 1.0s, révélant le théâtre. Stocker dans
  sessionStorage pour ne pas répéter à chaque refresh.
- **Pulse agent actif** : le cadre brass autour de l'avatar de l'agent
  en cours pulse subtilement (opacity 0.6 → 1.0 → 0.6, 2s loop)
- **Apparition livrable** : quand un livrable arrive, fade + slide-up 320ms

### 3.3 Refondre BuildMonitoringPage — le Théâtre BUILD (~1h)

`/execution/:executionId/build` (475 lignes legacy). Mêmes principes que
ExecutionMonitoringPage mais pour la phase BUILD :

- Agents en scène : Diego (Apex), Zara (LWC), Raj (Admin) successivement
- Accent acte : terra (Act III · Builders) pour les 3
- Dashboard de progression : nb de classes Apex générées, nb de LWC, nb de
  configurations Admin
- Composant `BuildPhasesPanel.tsx` (246 lignes) à refondre en Studio
- Possibilité de **télécharger le ZIP final** quand le BUILD est terminé
  (CTA brass "Download deliverable →")

### 3.4 Migrer/refondre les composants partagés (~1h)

Plusieurs composants legacy sont utilisés à la fois par les pages refondues
en A5.2 (BR Validation) et A5.3 (Execution). Les refondre une fois pour
toutes en Studio :

- `ChatSidebar.tsx` → `ChatSidebarStudio.tsx`
- `StructuredRenderer.tsx` → version Studio
- `DeliverableViewer.tsx` → version Studio
- `MermaidRenderer.tsx` (légère modif si besoin de couleurs Studio)
- `AgentThoughtModal.tsx` → version Studio (modal pleine page ink-2 + bone)
- `SDSPreview.tsx` → version Studio (lien vers les SDS HTML publics si dispo,
  sinon viewer interne)
- `ArchitectureReviewPanel.tsx` → version Studio (637 lignes — gros morceau,
  prendre le temps)
- `ValidationGatePanel.tsx` → version Studio (190 lignes — léger)
- `ProjectSettingsModal.tsx` → version Studio (510 lignes)
- `WorkflowEditor.tsx` → à évaluer : si utilisé seulement en legacy, retirer
  ou laisser tel quel ; sinon restyler

Pour chaque restylage : conserver le contrat de props existant. Ne pas
casser les pages legacy qui les utilisent encore (Projects listing,
ProjectDetail) — ces pages seront refondues en A5.4.

### 3.5 Mettre à jour App.tsx

Wrapper les 3 pages d'exécution dans `<AppShell>` :
```tsx
<Route path="/execution/:projectId" element={<AppShell>...</AppShell>} />
<Route path="/execution/:executionId/monitor" element={<AppShell>...</AppShell>} />
<Route path="/execution/:executionId/build" element={<AppShell>...</AppShell>} />
```

**Retirer** le bandeau "redesigned" des 3 pages refondues. Restera 4 pages
legacy avec bandeau pour A5.4 : Projects, ProjectDetail, AgentTester,
Pricing.

### 3.6 Tests visuels & sanity

- `npm run build` : 0 erreur TS
- Test manuel : démarrer un projet → wizard → BR validation → execution
  monitor → curtain rises → suivre les agents → BUILD → download
- Bilinguisme FR/EN OK sur les 3 pages refondues
- Animations fluides (60fps), pas de jank visible

---

## 4. Hors périmètre A5.3

❌ Refondre Projects listing, ProjectDetail, AgentTester, Pricing (= A5.4)
❌ Modifier le backend
❌ Toucher au site marketing live ou preview Studio
❌ Casser le build TS strict
❌ Modifier les routes existantes ou les contrats d'API
❌ Modifier la state machine d'exécution backend (24 états livrés en
   Horizons 2+3)

---

## 5. Garde-fous

### Tu peux
- Refondre tous les composants partagés mentionnés en §3.4
- Créer de nouveaux composants Studio pour le Théâtre
- Optimiser les composants lourds (`ExecutionMonitoringPage` 935 lignes —
  les casser en sous-composants `AgentStage`, `StudioTimeline`, etc.)
- Utiliser framer-motion librement pour les animations
- Ajouter des hooks customs (`useExecutionStream`, `useAgentLive`, etc.)
  dans `frontend/src/hooks/`

### Tu ne dois pas
- ❌ Modifier le backend
- ❌ Casser le build TS strict
- ❌ Casser les pages legacy A5.4 qui consomment encore les composants
  partagés (Projects, ProjectDetail, AgentTester, Pricing) — restyler tout
  en gardant les contrats de props
- ❌ Modifier les contrats `services/api.ts` au-delà d'ajouter de nouvelles
  fonctions helpers
- ❌ Toucher aux fichiers du worktree `/var/www/dh-preview/`

### Pièges connus
1. **Polling vs WebSocket** : si un WebSocket existe déjà côté backend,
   l'utiliser (latence +). Sinon polling 2-3s acceptable pour Round 3.
2. **Avatars** : les fichiers sont dans `frontend/public/avatars/large/` et
   `small/`. Vérifier que les 11 noms existent (sophie, olivia, emma,
   marcus, diego, zara, raj, elena, jordan, aisha, lucas).
3. **Curtain rises** : ne le déclencher QUE la première fois, sinon
   l'utilisateur le verra à chaque refresh = frustrant. Stocker dans
   `sessionStorage` la première vue avec clé `curtain-seen-{executionId}`.
4. **State machine 24 états** : ne pas chercher à les afficher tous dans
   la timeline, c'est trop verbeux. Grouper par agent (5 steps : Sophie →
   Olivia → Emma → Marcus → Sophie). Afficher l'état détaillé dans
   `AgentStage.tsx`.
5. **Accents acte par agent** :
   - Sophie (Act I · Direction) → indigo
   - Olivia, Emma, Marcus (Act II · Visionaries) → plum
   - Diego, Zara, Raj (Act III · Builders) → terra
   - Elena, Jordan (Act IV · Guardians) → sage
   - Aisha, Lucas (Act V · Stage) → ochre
   Créer une util `getAgentAccent(agentId): string` dans `lib/agents.ts`.
6. **DeliverableViewer existe déjà** : ne pas le réécrire from scratch,
   juste restyler. C'est probablement le plus pénible (wrapping de Markdown,
   diagrammes Mermaid, code highlighting).
7. **HITL pulse** : très visible mais pas trop strident. opacity 0.5 → 1
   sur 1.5s loop, pas plus rapide.

---

## 6. Protocole de rapport

À la fin :
1. Hash du commit poussé sur `feat/platform-studio`
2. Description visuelle de ExecutionPage, ExecutionMonitoringPage (Théâtre),
   BuildMonitoringPage
3. Liste des composants restylés avec leurs paths
4. Liste des nouveaux composants créés (`AgentStage`, `StudioTimeline`,
   `AgentLivePreview`, `ChatSidebarStudio`, etc.)
5. Statut `npm run build` (0 erreur TS attendue)
6. Endpoints API utilisés (préciser ceux qui ont posé problème ou qu'il
   faudrait améliorer côté backend)
7. État du polling vs WebSocket (lequel est utilisé, fréquence, perfs)
8. Liste des pages legacy restantes avec bandeau (devrait être 4 :
   Projects, ProjectDetail, AgentTester, Pricing)
9. Recommandations pour A5.4 (notamment sur le listing Projects qui réutilise
   probablement les cards Dashboard)

---

*Brief produit par : Claude (maître d'œuvre) · 27 avril 2026*
*URL GitHub raw : https://raw.githubusercontent.com/SamHATIT/digital-humans-production/main/docs/briefs/round3/BRIEF_A53_THEATRE.md*
