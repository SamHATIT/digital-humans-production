# BRIEF A5.1 — Foundation : design tokens, layout, navigation, login, dashboard vide

> **Owner** : Claude Code (autonome, sandbox web)
> **Branche cible** : `feat/platform-studio` (déjà créée par maître d'œuvre)
> **Estimation** : 1 session longue (~3-4h équivalent dev humain)
> **Pré-requis** : aucun (premier sous-brief de A5)

---

## 1. Cadre stratégique

A5.1 pose les **fondations Studio** de la plateforme. Avant d'attaquer les
tunnels narratifs (A5.2 Casting, A5.3 Théâtre) il faut un socle solide :
design tokens corrects, navigation cohérente, auth fonctionnelle, dashboard
prêt à recevoir du contenu.

Aucun écran "complexe" n'est refondu ici (Wizard, Execution, BR Validation
restent **inchangés** en attendant A5.2/A5.3). Mais **tout l'écosystème
visuel** est posé : palette, typo, layout, navigation, états vides.

À la fin de A5.1, un utilisateur qui se connecte voit :
- Une **page de login** Studio (FR/EN, charte ink/bone/brass)
- Un **dashboard** Studio avec : header, navigation, état "no projects",
  compteur crédits live, footer
- Une cohérence visuelle nette avec le site marketing preview Mod 16

A5.1 ne touche PAS aux pages legacy. Si un utilisateur navigue vers
`/wizard`, il voit l'ancienne page (en charte slate/cyan/purple). Ce
ressenti hybride est volontaire et provisoire. A5.2 et A5.3 le résorbent.

---

## 2. État actuel (ce qui existe)

```
frontend/
├── package.json          (React 19 + Vite + Tailwind v4 + TS + react-router 7)
├── tailwind.config.js    (palette legacy slate/cyan/purple)
├── tsconfig.json
├── src/
│   ├── App.tsx           (13 routes, react-router v7, ProtectedRoute)
│   ├── main.tsx
│   ├── App.jsx           ⚠️ DOUBLON à supprimer (legacy)
│   ├── main.jsx          ⚠️ DOUBLON à supprimer (legacy)
│   ├── index.css         (Tailwind v4 + custom keyframes)
│   ├── App.css
│   ├── components/
│   │   ├── Navbar.tsx
│   │   ├── ProtectedRoute.tsx
│   │   ├── ChatSidebar.tsx, WorkflowEditor.tsx, DiffViewer.tsx,
│   │   │   BuildPhasesPanel.tsx, TimelineStepper.tsx,
│   │   │   ExecutionMetrics.tsx, GanttChart.tsx, ArchitectureReviewPanel.tsx,
│   │   │   ValidationGatePanel.tsx, ProjectSettingsModal.tsx, etc.
│   │   └── ui/Avatar.tsx
│   ├── pages/
│   │   ├── LoginPage.tsx          ← À REFONDRE (A5.1)
│   │   ├── Dashboard.tsx          ← À REFONDRE (A5.1)
│   │   ├── Projects.tsx, NewProject.tsx, ProjectWizard.tsx,
│   │   │   ProjectDetailPage.tsx, ExecutionPage.tsx,
│   │   │   ExecutionMonitoringPage.tsx, BuildMonitoringPage.tsx,
│   │   │   BRValidationPage.tsx, AgentTesterPage.tsx,
│   │   │   ProjectDefinitionPage.tsx, Pricing.tsx
│   │   └── pm/PMDialogue.jsx, PRDReview.jsx, UserStoriesBoard.jsx,
│   │      RoadmapPlanning.jsx     ⚠️ .jsx → à convertir en .tsx
│   ├── services/api.ts            (apiCall + auth.login/register/me)
│   ├── hooks/useExecutionProgress.ts
│   ├── lib/, types/, assets/
├── public/avatars/large + small/  (11 portraits agents)
└── dist/                          (build de prod, à ignorer)
```

**Stack confirmée** : React 19, Vite, Tailwind v4 (`@import "tailwindcss"`
dans index.css, pas de plugins), react-router-dom v7, lucide-react, axios,
recharts, mermaid, frappe-gantt.

---

## 3. Périmètre A5.1 (à faire)

### 3.1 Design tokens Studio (priorité 1)

Créer `frontend/src/styles/tokens.css` qui pose les variables CSS Studio
identiques à celles du preview Mod 16 (`/var/www/dh-preview/index.html`).
Référence canonique : la `<style>` du template du preview.

**Palette** :
```css
:root {
  /* Backgrounds */
  --ink:        #0A0A0B;   /* fond principal */
  --ink-2:      #141416;   /* surfaces level 2 (cards, panels) */
  --ink-3:      #1C1C1F;   /* hover surface, dividers low */

  /* Text */
  --bone:       #F5F2EC;   /* texte principal */
  --bone-2:     #E5E1D8;
  --bone-3:     #B5B0A4;   /* texte secondaire */
  --bone-4:     #6F6B62;   /* texte muet, "coming soon" */

  /* Accent dominant */
  --brass:      #C8A97E;
  --brass-2:    #B89968;
  --brass-3:    #8B764D;

  /* Accents acte (5) — pour les agents par acte */
  --indigo:     #6E7DB8;   /* Act I — Direction (Sophie) */
  --plum:       #9B6E94;   /* Act II — Visionaries (Olivia, Emma, Marcus) */
  --terra:      #C57F5C;   /* Act III — Builders (Diego, Zara, Raj) */
  --sage:       #7A9474;   /* Act IV — Guardians (Elena, Jordan) */
  --ochre:      #B88B3F;   /* Act V — Stage (Aisha, Lucas) */
}

/* Typography */
:root {
  --serif: 'Cormorant Garamond', Georgia, 'Times New Roman', serif;
  --sans:  'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --mono:  'JetBrains Mono', 'Menlo', 'Consolas', monospace;
}
```

**Tailwind config** : étendre `tailwind.config.js` pour exposer ces tokens
en classes utilitaires (`bg-ink`, `text-bone`, `border-brass`, etc.).
SUPPRIMER les anciens tokens `pm-primary`, `pm-secondary`, `primary` de la
config legacy. Conserver `success`, `error`, `warning` (utiles pour les
notifications/badges) en alignant les valeurs Studio si possible.

**Polices** : ajouter dans `index.css` les imports Google Fonts
correspondants :
```css
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500;1,600&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
```

### 3.2 Layout principal Studio (`AppShell.tsx`)

Créer `frontend/src/components/layout/AppShell.tsx`, le layout commun à
toutes les pages protégées (post-login). Structure :

```
┌────────────────────────────────────────────────────────────┐
│  StudioHeader  (sticky top, fond ink-2 + hairline brass)   │
├────────────────────────────────────────────────────────────┤
│                                                            │
│                                                            │
│              {children}  (la page courante)               │
│                                                            │
│                                                            │
├────────────────────────────────────────────────────────────┤
│  StudioFooter  (mention légale + crédits + © MMXXVI)      │
└────────────────────────────────────────────────────────────┘
```

Composants enfants :
- `StudioHeader.tsx` : logo "Digital · Humans" Cormorant ital + tagline
  mono "AUTONOMOUS STUDIO · EST MMXXV", nav links (Dashboard, Projects,
  New project), `CreditCounter` (à droite), avatar utilisateur + logout
- `StudioFooter.tsx` : 3 colonnes mono small : copyright + mention légale +
  liens (preview marketing site + Pricing + Logout)
- `CreditCounter.tsx` : composant qui fetch `/api/billing/balance` au
  mount + toutes les 60s, affiche le solde en mono brass avec icône
  étoile/crédit + barre fine de progression vs tier_config.monthly_quota

### 3.3 Refonte LoginPage en charte Studio

`frontend/src/pages/LoginPage.tsx` complètement refait :

- Layout split-screen : **gauche** plein ink avec une cover Studio
  (réutiliser une des covers `/assets/covers/*.jpg` du preview, par exemple
  `logifleet.jpg` ou une nouvelle générée plus tard) en background avec
  gradient ink overlay
- **Droite** : formulaire centré max-width 400px, fond ink-2
  - Logo Cormorant ital "Digital · Humans" en header
  - Eyebrow mono "WELCOME BACK · SIGN IN"
  - Inputs Studio (background `--ink-3`, border `rgba(245,242,236,0.08)`,
    focus border `--brass`, label mono uppercase tracking 0.16em)
  - Bouton primaire Studio : background `--brass`, color `--ink`, hover
    `--brass-2`, mono uppercase tracking 0.14em
  - Lien secondaire "Don't have an account? Request access →" en mono
    bone-3, hover bone
- Toggle FR/EN en haut à droite (réutilise pattern du site marketing)
- État erreur : panneau ink-2 hairline `error` avec icône, mono small

### 3.4 Refonte Dashboard en charte Studio (état vide + état avec projets)

`frontend/src/pages/Dashboard.tsx` :

- Section hero : eyebrow mono "№ 01 · STUDIO", titre Cormorant ital
  "Welcome back, {firstName}." (FR : "Bon retour, {firstName}.")
- **Si zéro projet** : état vide avec 3 cards rangées :
  1. "Cast your first ensemble" → CTA `/wizard`
  2. "Browse the gallery" → lien vers preview marketing (route externe)
  3. "Read the manifesto" → lien vers Ghost `/journal/manifesto`
- **Si projets** : grille de cards projets (même structure que la galerie
  Mod 16 mais en mode "data-driven", chaque card = 1 projet réel de la DB)
  - Cover par défaut : pattern cover Studio générique (à fournir comme
    placeholder, peut être un SVG simple)
  - Méta : eyebrow industrie + titre projet + last activity
  - Click → `/project/:id`
- Section "The work in progress" en bas : timeline horizontale des dernières
  exécutions actives (data-driven via `/api/executions?status=running`)
  → version simplifiée, pas la timeline finale qui sera traitée en A5.3

### 3.5 Routing minimal modifié

Dans `App.tsx`, **ne pas changer les routes**. Juste injecter `<AppShell>`
autour de `Dashboard` (et seulement Dashboard pour ce premier sous-brief) :

```tsx
<Route path="/" element={
  <ProtectedRoute>
    <AppShell>
      <Dashboard />
    </AppShell>
  </ProtectedRoute>
} />
```

Les autres pages restent sans AppShell (style legacy provisoirement).

### 3.6 Migration TS strict

- Activer `"strict": true` dans `tsconfig.json` (et `noImplicitAny`,
  `strictNullChecks`, `noUnusedLocals`, `noUnusedParameters`)
- **Supprimer les doublons** `App.jsx` et `main.jsx`
- **Convertir** `src/pages/pm/*.jsx` en `.tsx` (4 fichiers : PMDialogue,
  PRDReview, UserStoriesBoard, RoadmapPlanning) — typer les props/state
  proprement
- Fixer les erreurs TS qui apparaîtront au build après `strict: true`.
  La plupart sont des `any` à typer ou des `null`-checks à ajouter.
  Prendre le temps d'écrire les types proprement (pas de `: any` opportuniste).

### 3.7 État vide de qualité partout où c'est nécessaire

Dans LoginPage et Dashboard nouvelle version, soigner les états :
- **Loading** : spinner mono, texte "loading…" en mono bone-3
- **Error** : panneau ink-2 hairline error, icône + message + retry
- **Empty** : illustration discrète + texte explicatif + CTA primaire

Jamais de state visuellement "blanc" ou "cassé" — c'est un produit B2B,
chaque transition doit avoir son état soigné.

---

## 4. Hors périmètre A5.1 (à NE PAS faire)

❌ Refondre `/projects`, `/wizard`, `/project/:id`, `/execution/*`,
   `/agent-tester`, `/br-validation`, `/pricing` (= A5.2/A5.3/A5.4)
❌ Toucher au backend (aucune modification de l'API)
❌ Modifier les composants `ChatSidebar`, `WorkflowEditor`, `DiffViewer`,
   `BuildPhasesPanel`, `TimelineStepper`, `ExecutionMetrics`, `GanttChart`,
   `ArchitectureReviewPanel`, `ValidationGatePanel`, `SDSPreview`,
   `ProjectSettingsModal`, `StructuredRenderer`, `MermaidRenderer`,
   `DeliverableViewer`, `AgentThoughtModal`, `SubscriptionBadge`
   (= A5.2 et A5.3)
❌ Changer la structure des routes ou supprimer des routes existantes
❌ Toucher au site marketing live `digital-humans.fr` ou au preview Studio
   (`/var/www/dh-preview/`)
❌ Implémenter Stripe en réel (= phase 3.3+, hors A5)
❌ Implémenter le toggle de langue partout (juste sur LoginPage et
   Dashboard pour ce sous-brief, le reste suivra)

---

## 5. Tâches détaillées

### Étape 1 — Setup branche et tokens (30 min)

```bash
cd /root/workspace/digital-humans-production
git checkout feat/platform-studio
git pull origin feat/platform-studio  # branche déjà créée par maître d'œuvre

# Cleanup doublons
rm frontend/src/App.jsx frontend/src/main.jsx

# Création des fichiers tokens
mkdir -p frontend/src/styles
# créer frontend/src/styles/tokens.css avec le contenu Studio (cf. §3.1)
```

Modifier `tailwind.config.js` pour exposer les tokens :
```js
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: 'var(--ink)', 2: 'var(--ink-2)', 3: 'var(--ink-3)' },
        bone: { DEFAULT: 'var(--bone)', 2: 'var(--bone-2)', 3: 'var(--bone-3)', 4: 'var(--bone-4)' },
        brass: { DEFAULT: 'var(--brass)', 2: 'var(--brass-2)', 3: 'var(--brass-3)' },
        indigo: 'var(--indigo)',
        plum: 'var(--plum)',
        terra: 'var(--terra)',
        sage: 'var(--sage)',
        ochre: 'var(--ochre)',
        success: '#7A9474',  // sage
        error:   '#C25450',
        warning: '#B88B3F',  // ochre
      },
      fontFamily: {
        serif: ['Cormorant Garamond', 'Georgia', 'serif'],
        sans:  ['Inter', '-apple-system', 'sans-serif'],
        mono:  ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        eyebrow: '0.16em',
        cta: '0.14em',
      },
    },
  },
  plugins: [],
}
```

Modifier `frontend/src/index.css` :
- Garder `@import "tailwindcss";` en première ligne
- Ajouter `@import "./styles/tokens.css";`
- Ajouter l'import Google Fonts (cf. §3.1)
- Remplacer le `body { background-color: #0B1120 }` legacy par
  `body { background: var(--ink); color: var(--bone); font-family: var(--sans); }`

### Étape 2 — Layout AppShell (45 min)

Créer ces fichiers (chemins relatifs à `frontend/src/`) :

- `components/layout/AppShell.tsx` — wrapper avec header + main + footer
- `components/layout/StudioHeader.tsx` — header sticky
- `components/layout/StudioFooter.tsx` — footer mono small
- `components/layout/CreditCounter.tsx` — fetch `/api/billing/balance`
  + affiche solde + barre quota
- `components/layout/LangToggle.tsx` — toggle FR/EN (utilise un context
  `LangContext` à créer aussi dans `contexts/LangContext.tsx`)

Tous typés strictement TS (props, state, refs, hooks).

### Étape 3 — Refonte LoginPage (45 min)

Remplacer le contenu de `pages/LoginPage.tsx` par la version Studio (cf. §3.3).
Conserver l'appel `auth.login(email, password)` existant — ne PAS modifier
`services/api.ts`. Conserver la redirection vers `/` après login.

Tester manuellement : connexion fonctionne, redirection OK, FR/EN togglé.

### Étape 4 — Refonte Dashboard (60 min)

Remplacer `pages/Dashboard.tsx` par la version Studio (cf. §3.4).

Pour les data fetch :
- Liste projets : `GET /api/projects` (existe déjà côté backend)
- Exécutions actives : `GET /api/executions?status=running` (à vérifier
  qu'il existe ; sinon, utiliser ce qu'il y a et adapter)

Si une route API manque, **ne PAS l'inventer côté backend** — utiliser ce
qui existe et signaler dans le rapport ce qui manquerait pour la version
finale.

### Étape 5 — TS strict + cleanup .jsx (60 min)

```bash
# Activer strict mode
# Dans tsconfig.json :
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    ...
  }
}

# Convertir les .jsx en .tsx
git mv frontend/src/pages/pm/PMDialogue.jsx frontend/src/pages/pm/PMDialogue.tsx
git mv frontend/src/pages/pm/PRDReview.jsx frontend/src/pages/pm/PRDReview.tsx
git mv frontend/src/pages/pm/UserStoriesBoard.jsx frontend/src/pages/pm/UserStoriesBoard.tsx
git mv frontend/src/pages/pm/RoadmapPlanning.jsx frontend/src/pages/pm/RoadmapPlanning.tsx

# Build pour faire émerger les erreurs TS
cd frontend
npm install  # au cas où
npx tsc --noEmit 2>&1 | tee /tmp/tsc-errors.log

# Itérer pour corriger les erreurs avec types propres
# (pas de `as any`, pas de `// @ts-ignore`)
```

Si certaines erreurs sont structurellement non-corrigeables sans
réécrire un composant entier (par ex. `WorkflowEditor.tsx` est trop
custom et bloque), ajouter `// @ts-expect-error: refactor in A5.2/A5.3`
avec un commentaire explicatif et passer. Limiter à 5 occurrences max
sur tout le repo.

### Étape 6 — Pages legacy : ajouter un visuel "draft" (15 min)

Pour que l'utilisateur comprenne que les pages legacy ne sont pas finies,
ajouter un bandeau discret en haut de chaque page legacy :
```
┌──────────────────────────────────────────────────┐
│ ⚠ This page is being redesigned. New version    │
│   coming in next sprint.                         │
└──────────────────────────────────────────────────┘
```

Bandeau couleur ink-3 + texte bone-3 + icône warning, dismissable.

À ajouter sur : Projects, NewProject, ProjectWizard, ProjectDetailPage,
ExecutionPage, ExecutionMonitoringPage, BuildMonitoringPage, BRValidationPage,
AgentTesterPage, Pricing.

### Étape 7 — Tests visuels + smoke (15 min)

```bash
cd frontend
npm run dev  # vite dev server, port 3000

# tester manuellement :
# - / login : login fonctionne, redirige vers Dashboard
# - / dashboard : header Studio visible, footer présent, état vide ok
# - /projects, /wizard, /pricing : bandeau "redesigned" visible, page legacy en dessous
```

Si toutes les pages s'ouvrent sans erreur console → smoke OK.

### Étape 8 — Commit et push (10 min)

```bash
cd /root/workspace/digital-humans-production
git add frontend/
git status

git -c user.name="Sam (via Claude Code)" -c user.email="[email protected]" \
  commit -m "feat(platform): A5.1 Foundation — design tokens, AppShell, LoginPage, Dashboard

Pose les fondations Studio de la plateforme :

- Design tokens Studio (palette ink/bone/brass + 5 accents acte) dans
  styles/tokens.css, exposés via tailwind.config.js (bg-ink, text-bone,
  border-brass, etc.)
- Polices Cormorant Garamond + Inter + JetBrains Mono via Google Fonts
- AppShell layout (StudioHeader + StudioFooter + CreditCounter + LangToggle)
- LoginPage refait en charte Studio (split-screen avec cover + form ink-2,
  toggle FR/EN, états error soignés)
- Dashboard refait en charte Studio (hero + état vide 3 cards CTA + grille
  projets data-driven + work-in-progress timeline simplifiée)
- TS strict activé (strict:true, noImplicitAny, strictNullChecks)
- 4 fichiers .jsx convertis en .tsx (pages/pm/*)
- Doublons App.jsx et main.jsx supprimés
- Bandeau 'redesigned' ajouté sur les 10 pages legacy non-encore-refondues

Hors périmètre (A5.2/A5.3/A5.4 à venir) :
- Wizard, ExecutionMonitoring, BuildMonitoring, BRValidation, ProjectDetail,
  AgentTester, Pricing — restent en charte legacy avec bandeau
- Aucun composant lourd (WorkflowEditor, ChatSidebar, BuildPhasesPanel,
  TimelineStepper, etc.) refondu

Validation :
- npm run build → 0 erreur TS
- npm run dev → toutes les routes répondent
- Smoke visuel : login fonctionne, dashboard charte Studio, pages legacy
  affichent le bandeau"
git push origin feat/platform-studio
```

---

## 6. Critères de fin (DoD)

- ✅ `frontend/src/styles/tokens.css` existe avec palette Studio complète
- ✅ `tailwind.config.js` expose ink/bone/brass/accents + fontFamily Studio
- ✅ Polices Google Fonts importées dans index.css
- ✅ `App.jsx` et `main.jsx` supprimés
- ✅ 4 fichiers `pages/pm/*.jsx` convertis en `.tsx`
- ✅ `tsconfig.json` strict mode activé
- ✅ `npm run build` retourne 0 erreur TS (avec ≤5 `@ts-expect-error`
  documentés sur composants legacy bloquants)
- ✅ `AppShell.tsx`, `StudioHeader.tsx`, `StudioFooter.tsx`,
  `CreditCounter.tsx`, `LangToggle.tsx`, `LangContext.tsx` créés
- ✅ `LoginPage.tsx` refondu en charte Studio, toggle FR/EN, états
  loading/error soignés
- ✅ `Dashboard.tsx` refondu en charte Studio, AppShell appliqué,
  empty state + projects grid + work-in-progress
- ✅ Pages legacy intactes mais avec bandeau "redesigned"
- ✅ Test manuel : login → redirige Dashboard (visuel Studio), navigation
  vers Projects → bandeau visible, charte legacy
- ✅ Commit + push sur `feat/platform-studio`

---

## 7. Garde-fous

### Ce que tu peux faire
- Modifier tout fichier dans `frontend/`
- Créer de nouveaux fichiers dans `frontend/src/`
- Modifier `tailwind.config.js`, `tsconfig.json`, `vite.config.ts`
  (uniquement si nécessaire et documenté)
- Installer de nouveaux paquets npm si vraiment indispensable (justifier
  dans le rapport, préférer pas)

### Ce que tu NE DOIS PAS faire
- ❌ Toucher au backend (`backend/` est intouchable pour A5.1)
- ❌ Modifier `services/api.ts` (l'auth fonctionne, on ne change rien)
- ❌ Refondre des composants lourds hors périmètre (WorkflowEditor,
  ChatSidebar, BuildPhasesPanel, TimelineStepper, etc.)
- ❌ Modifier les routes existantes (juste injecter `<AppShell>` autour
  de Dashboard)
- ❌ Toucher au preview Studio (`/var/www/dh-preview/`)
- ❌ Toucher au site live `digital-humans.fr`
- ❌ Casser le build TypeScript final (`npm run build` doit passer)
- ❌ Utiliser `as any` ou `// @ts-ignore` libéralement (limite stricte 5
  occurrences `// @ts-expect-error` documentées)

### Pièges connus
1. **Tailwind v4** : la syntaxe est `@import "tailwindcss"` pas
   `@tailwind base/components/utilities` (legacy v3). Vérifier que les
   classes custom (`bg-ink`, `text-bone`) marchent bien après modification
   du config — le watch dev peut nécessiter un restart.
2. **react-router v7** : `<BrowserRouter>` + `<Routes>` + `<Route>` (pas
   `<Switch>` qui était v5). Le pattern actuel marche, ne pas refactor.
3. **Auth flow** : JWT stocké dans localStorage, intercepté par `apiCall`.
   Ne pas casser ce contrat (Bearer header).
4. **Polices Google Fonts** : tester avec et sans connexion (cache CSS).
   En cas de FOUT (Flash of Unstyled Text), utiliser `font-display: swap`
   dans la requête fonts.googleapis.com.
5. **Cover image LoginPage** : la cover Studio est dans `/assets/covers/`
   du repo (root), PAS dans `frontend/public/`. Soit copier la cover en
   `frontend/public/covers/logifleet.jpg`, soit configurer un alias Vite
   pour servir `/covers/*` depuis le repo root. Préférer la copie (plus
   simple, plus reproductible).

### Si bloqué
- Erreur TS impossible à fixer sur composant legacy lourd : `// @ts-expect-error: refactor in A5.X` + commentaire explicatif + passer (limite 5 occurrences)
- Endpoint API manquant (`/api/billing/balance` ou `/api/executions?status=`) : utiliser ce qui existe + ajouter un mock côté frontend + documenter dans le rapport
- `npm install` qui échoue : vérifier la node version (Node 20+ requis pour Vite 5+)
- Impossible de générer une cover placeholder pour les projets sans cover : utiliser un SVG simple Studio en composant React (un cadre brass + monogramme Cormorant) plutôt qu'une image

---

## 8. Protocole de rapport

À la fin de la session, livrer :

1. **Hash du commit** poussé sur `feat/platform-studio`
2. **Capture conceptuelle** : décrire ce que verra le maître d'œuvre quand
   il fera `npm run dev` puis ira sur `/login` puis `/`
3. **Liste des écarts assumés au brief** avec justification (par ex.
   "j'ai ajouté un composant `BlockHeader` réutilisable parce que…")
4. **Liste des `// @ts-expect-error` posés** avec fichier:ligne et raison
5. **Statut `npm run build`** : nombre d'erreurs TS finales (devrait être 0)
6. **Endpoints API utilisés** : liste avec statut "fonctionne" ou "à créer"
7. **Pages legacy avec bandeau "redesigned"** : confirmation des 10 pages
8. **Recommandations pour A5.2** : si tu as identifié des choses qui vont
   être problématiques pour le sous-brief suivant (par ex. WorkflowEditor
   qui partage du code avec ProjectWizard), les signaler ici

---

## 9. Workflow d'exécution

1. Maître d'œuvre fournit ce brief à Claude Code (URL GitHub raw)
2. Claude Code travaille en sandbox web (pas d'accès VPS direct)
3. Claude Code commit + push sur `feat/platform-studio`
4. **Maître d'œuvre exécute côté VPS** :
   - `cd /root/workspace/digital-humans-production`
   - `git fetch origin && git checkout feat/platform-studio && git pull`
   - `cd frontend && npm install && npm run build` (sanity)
   - `npm run dev &` (test visuel sur port 3000 depuis l'IP du VPS)
   - Capture les écarts visuels, signale à Sam
5. **Sam valide visuellement** ou demande ajustements (Mod 17 si besoin)
6. Quand A5.1 validé : on enchaîne sur A5.2 Casting

---

*Brief produit par : Claude (maître d'œuvre) · 27 avril 2026*
*Branche cible : `feat/platform-studio` (créée le 27 avr, basée sur main commit `3282eec`)*
*URL GitHub raw : https://raw.githubusercontent.com/SamHATIT/digital-humans-production/main/docs/briefs/round3/BRIEF_A51_FOUNDATION.md*
