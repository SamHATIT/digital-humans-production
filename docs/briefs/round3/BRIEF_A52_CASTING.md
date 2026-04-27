# BRIEF A5.2 — Casting : tunnel de création projet en charte Studio

> **Owner** : Claude Code (autonome, sandbox web)
> **Branche cible** : `feat/platform-studio` (continuer dessus, A5.1 a livré `eab203f`)
> **Estimation** : 1 session longue (~4h équivalent dev humain)
> **Pré-requis** : A5.1 mergée

---

## 1. Cadre stratégique

A5.1 a posé les fondations Studio (palette, typo, layout, login, dashboard).
A5.2 attaque le **premier tunnel narratif** : le Casting, soit la création
d'un nouveau projet — l'ouverture d'une saison théâtrale.

Le Casting est crucial : c'est le **moment où l'utilisateur passe de
visiteur à metteur en scène**. La métaphore Studio doit s'incarner ici.
On n'invite pas l'utilisateur à "remplir un formulaire", on l'invite à
**caster son ensemble** pour le projet.

À la fin de A5.2, un utilisateur peut :
- Démarrer une nouvelle production via une page de bienvenue Studio
- Suivre un wizard à plusieurs étapes (brief produit, contexte client, scope,
  validation business requirements)
- Voir clairement quels agents seront castés, dans quel acte, avec leur
  photo, rôle, tagline (lien direct vers le marketing site acte 2)
- Soumettre, attendre la phase BR validation, et arriver dans le projet
  configuré

Pages cibles refondues en A5.2 :
- `/projects/new` (NewProject.tsx) — page de bienvenue avant wizard
- `/wizard` et `/wizard/:projectId` (ProjectWizard.tsx, 982 lignes legacy) —
  le wizard lui-même
- `/br-validation/:projectId` (BRValidationPage.tsx, 688 lignes legacy) —
  validation business requirements

Pages NON refondues (A5.3 ou A5.4) :
- `/execution/:id`, `/execution/:id/monitor`, `/execution/:id/build` (= A5.3)
- `/projects` listing, `/project/:id`, `/agent-tester`, `/pricing` (= A5.4)

---

## 2. État actuel après A5.1 (rappel)

✓ Design tokens Studio en place (`styles/tokens.css`)
✓ AppShell + StudioHeader + StudioFooter + CreditCounter + LangToggle
✓ LangContext avec hook `useLang()`
✓ LoginPage refondu (split-screen, FR/EN)
✓ Dashboard refondu (hero + état vide 3 CTA + grille projets)
✓ TS strict actif (0 erreur, 0 `@ts-expect-error`)
✓ Polices Cormorant + Inter + JetBrains Mono via Google Fonts
✓ `RedesignedBanner` présent sur 10 pages legacy (à RETIRER quand on refait
  les pages dans A5.2/A5.3/A5.4)

⚠️ **Notes du rapport A5.1 importantes pour A5.2** :
1. **`lib/motion.tsx`** : shim placeholder qui absorbe les props framer-motion
   sans dépendance. Pour A5.2 (Casting), **installer framer-motion v11+** et
   remplacer le shim. Animations fluides indispensables au tunnel narratif.
2. **`/api/billing/balance`** : l'endpoint **existe bel et bien** côté backend
   (`backend/app/api/routes/billing.py:19`, livré en A4 avec tag
   `v2026.04-credits-phase3.1-3.2`). Si CreditCounter fait fallback silencieux,
   c'est probablement un mauvais path d'import API ou un problème de baseUrl.
   À investiguer en début de session A5.2 (5 min).
3. **`/api/executions?status=running`** : à vérifier l'existence côté backend.
   Si absent, créer côté frontend un fallback sur `/api/projects` filtré.

---

## 3. Périmètre A5.2

### 3.1 Installer framer-motion (5 min)

```bash
cd frontend
npm install framer-motion@^11.0.0
```

Puis **supprimer** `frontend/src/lib/motion.tsx` (le shim) et remplacer
tous les imports `from '../lib/motion'` ou `from '@/lib/motion'` par
`from 'framer-motion'`. Vérifier que les pages PM (qui utilisaient le
shim) compilent toujours.

### 3.2 Fix CreditCounter (10 min)

Investiguer pourquoi CreditCounter ne récupère pas le balance :
- Vérifier l'URL exacte appelée (`/api/billing/balance` vs
  `/billing/balance`, baseUrl)
- Vérifier que le token JWT est bien envoyé dans le header
- Tester avec curl : `curl http://localhost:8002/api/billing/balance -H "Authorization: Bearer <token>"`
- Si l'endpoint backend retourne du JSON mais le composant ne l'affiche pas,
  bug de parsing — corriger
- Une fois fixé, l'afficher : `1247 credits` en mono brass + barre fine
  bone-3 indiquant la consommation vs `monthly_quota` du tier

### 3.3 Refondre `/projects/new` — NewProject Studio (30 min)

Page actuelle = ancienne. La nouvelle version est une **page de bienvenue
Studio** courte qui prépare l'utilisateur au Casting.

Layout :
```
┌─────────────────────────────────────────────────┐
│  Header Studio (AppShell)                       │
├─────────────────────────────────────────────────┤
│                                                 │
│   № 02 · CASTING                                │
│   A new production begins.                      │
│   Cormorant ital, 56px                          │
│                                                 │
│   Lede mono : Each project assembles its own   │
│   ensemble. Tell us about your engagement,     │
│   and the studio will compose accordingly.     │
│                                                 │
│   [ ◗ Begin the casting →  ]  (CTA brass mono) │
│                                                 │
│   ────────────────                              │
│                                                 │
│   Recent productions  (3 dernières si exist)   │
│   • LogiFleet — Service Cloud · finished       │
│   • Project X — In casting · 2 days ago        │
│                                                 │
└─────────────────────────────────────────────────┘
```

Le CTA "Begin the casting" envoie sur `/wizard` (route existante).

Bilingue FR/EN :
- EN: "A new production begins." / "Begin the casting"
- FR: "Une nouvelle production commence." / "Commencer le casting"

### 3.4 Refondre `/wizard` — ProjectWizard Studio (~3h)

C'est le **gros morceau du sous-brief**. ProjectWizard.tsx fait actuellement
982 lignes en charte legacy. La nouvelle version est plus narrative,
divisée clairement en **5 actes** (mêmes que les actes du flow site marketing).

#### 3.4.1 Structure générale

5 étapes, navigation type "stepper" + sidebar gauche fixe + contenu droite
qui défile.

```
┌──────────────┬──────────────────────────────────┐
│              │                                  │
│  Sidebar     │   Contenu de l'acte courant      │
│  Studio      │                                  │
│              │   - Eyebrow : ACT II · BRIEF     │
│  ✓ Act I     │   - Titre Cormorant ital 42px    │
│  ◗ Act II    │   - Lede mono                    │
│  · Act III   │                                  │
│  · Act IV    │   [ Form fields Studio ]         │
│  · Act V     │                                  │
│              │   < Previous   Continue → >      │
│              │                                  │
│  Crédits :   │                                  │
│  1247 credit │                                  │
│              │                                  │
└──────────────┴──────────────────────────────────┘
```

#### 3.4.2 Les 5 actes du wizard

**Act I · The opening** (l'ouverture)
*Le projet et son contexte*
- Project name (input texte)
- Industry (dropdown : Logistics, Pharma, Telecom, B2B, Energy, Retail,
  Other)
- Salesforce edition (radio : Enterprise / Unlimited / Other)
- Your role (radio : Salesforce admin / consultant / project lead / other)

**Act II · The brief** (le brief)
*Ce qu'il faut construire*
- Project description (textarea, grand)
- Business goals (textarea avec placeholder : "What outcome should this
  unlock for your business?")
- Constraints / non-goals (textarea optionnel)
- File upload (optional, pour brief PDF) — utiliser composant existant si
  disponible, sinon un drop zone Studio

**Act III · The ensemble** (l'ensemble)
*L'utilisateur découvre quels agents vont être castés*
- Affichage **non-éditable** : les 11 agents par acte avec photos,
  rôles, tagline
- Cohérence visuelle avec le slider acte 2 du marketing site
- Petit texte explicatif : "These eleven specialists will compose your
  Salesforce solution. Each acts in turn ; their work is your project."
- Lien vers le marketing site pour en lire plus : "Read about the ensemble →"

**Act IV · The schedule** (le calendrier)
*Quand et combien*
- Tier de l'utilisateur (info readonly, ex: "Pro tier · 5000 credits/mo")
- Estimated cost in credits (info readonly basée sur API ou estimation
  côté front : SDS ~ 800 credits, BUILD ~ 3500 credits)
- Priority (radio : Standard / Express +20% credits)
- Estimated completion (info : "5-7 working days")

**Act V · Curtain up** (lever de rideau)
*Confirmation et soumission*
- Récapitulatif des 4 actes précédents
- Checkbox "I agree to the terms of service"
- Bouton brass : "◗ Raise the curtain →" qui submit
- Animation de transition vers BR Validation page

#### 3.4.3 Comportements et data

- **Sauvegarde auto draft** côté backend (utiliser endpoint existant si
  disponible, sinon localStorage avec clé `wizard-draft-{userId}`)
- **Validation client** par acte (chaque acte vérifie ses champs avant
  d'autoriser "Continue")
- **Resume URL** : `/wizard/:projectId` doit pouvoir reprendre un draft
  existant
- **Submit final** : POST sur l'endpoint existant
  (`/api/projects` ou `/api/pm-orchestrator/projects` à vérifier dans
  `services/api.ts`), redirige vers `/br-validation/:projectId`

#### 3.4.4 Animations Studio (framer-motion)

- Transition entre actes : slide horizontal 400ms ease-out
- Apparition contenu : fade + translateY 20→0, 320ms
- Stepper : check qui apparaît avec spring quand un acte est complété
- Bouton submit : ripple brass au click, transition vers la page BR

### 3.5 Refondre `/br-validation/:projectId` — BRValidationPage Studio (~1h)

La page de validation Business Requirements arrive après la submission du
wizard. C'est le moment où Sophie (PM) propose un draft de BR à valider
avant de commencer le SDS.

Page actuelle = 688 lignes legacy. Nouvelle version :

```
┌─────────────────────────────────────────────────┐
│  Header Studio                                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  № 03 · INTERMISSION                            │
│  Sophie has read your brief.                    │
│  Cormorant ital                                 │
│                                                 │
│  [ Sophie avatar (Acts I · indigo accent) ]     │
│  + lede : "Here is what I understood. Tell me   │
│   what's right, what's missing, what to refine" │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  BR Document (left)                     │   │
│  │  - Sections collapsibles                │   │
│  │  - Each section editable inline         │   │
│  │  - Add/remove user stories              │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  Sophie's chat (right, sticky)          │   │
│  │  - User: feedback texte                 │   │
│  │  - Sophie: réponses + propositions      │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  [ Decline → Cast someone else ]                │
│  [ Approve and continue → SDS phase ]  (brass)  │
│                                                 │
└─────────────────────────────────────────────────┘
```

Réutiliser autant que possible les composants existants :
- `ChatSidebar.tsx` (307 lignes) — restyler avec les tokens Studio
- `StructuredRenderer.tsx` (343 lignes) — restyler les sections du BR

L'API utilisée est probablement `/api/pm-orchestrator/projects/:id` (ou
similaire). Conserver les contrats d'API existants — **ne pas modifier le
backend**.

### 3.6 Mettre à jour App.tsx

Wrapper les 3 pages refondues dans `<AppShell>` (comme Dashboard en A5.1) :
```tsx
<Route path="/projects/new" element={
  <ProtectedRoute>
    <AppShell>
      <NewProject />
    </AppShell>
  </ProtectedRoute>
} />
<Route path="/wizard" element={...AppShell + ProjectWizard...} />
<Route path="/wizard/:projectId" element={...idem...} />
<Route path="/br-validation/:projectId" element={...AppShell + BRValidationPage...} />
```

**Retirer** le `<RedesignedBanner>` des 3 pages refondues (NewProject,
ProjectWizard, BRValidationPage). Garder le bandeau sur les 7 pages
restantes pour A5.3/A5.4.

### 3.7 Tests visuels & sanity

- `npm run build` : 0 erreur TS
- Test manuel : login → /projects/new → wizard 5 actes → submit → BR validation
- Bilinguisme FR/EN OK sur les 3 pages refondues

---

## 4. Hors périmètre A5.2

❌ Refondre Execution / BuildMonitoring / ProjectDetail / Projects listing /
   AgentTester / Pricing (A5.3 et A5.4)
❌ Modifier le backend
❌ Toucher au site marketing live ou preview Studio
❌ Casser le build TS strict
❌ Casser les routes existantes ou les contrats d'API
❌ Implémenter Stripe en réel
❌ Toucher aux composants `ChatSidebar`, `StructuredRenderer` au-delà de
   leur restyling Studio (pas de refacto structurelle)

---

## 5. Garde-fous

### Tu peux
- Modifier toute page/composant dans le périmètre
- Installer `framer-motion@^11.0.0` (et seulement ça)
- Créer de nouveaux composants Studio (`StudioInput`, `StudioTextarea`,
  `StudioSelect`, `StudioStepper`, `WizardActHeader`, `EnsembleDisplay`...)
- Réorganiser les fichiers dans `frontend/src/` si ça améliore la lisibilité

### Tu ne dois pas
- ❌ Toucher au backend
- ❌ Casser le build TS strict (`npm run build` doit passer, 0 erreur)
- ❌ Utiliser `as any` ou `// @ts-ignore` libéralement (limite 5 occurrences
  documentées)
- ❌ Modifier `services/api.ts` au-delà d'ajouter de nouvelles fonctions
  helpers (les contrats existants sont sacrés)
- ❌ Toucher au worktree Studio (`/var/www/dh-preview/`)

### Pièges connus
1. **framer-motion v11** : la prop `initial={false}` doit être typée
   `Boolean | string | undefined`, pas `false` strict — sinon erreur TS.
2. **Wizard state management** : à 5 étapes avec navigation libre, un bête
   `useState` suffit. Pas besoin de Zustand/Redux.
3. **localStorage draft** : n'enregistrer QUE les inputs utilisateur, pas
   les données dérivées (estimated cost, etc.).
4. **Sophie avatar** : utiliser `frontend/public/avatars/large/sophie.png`
   ou `small/sophie.png` selon disponibilité.
5. **Numérotation actes wizard vs site** : le **site marketing** numérote
   ses sections № 01, № 02, № 03, № 04. Le **wizard** numérote ses étapes
   Act I, Act II, Act III, Act IV, Act V (en romain, comme les actes des
   agents). C'est volontaire — le site est éditorial, le wizard est
   théâtral. Ne pas confondre.

---

## 6. Protocole de rapport

À la fin :
1. Hash du commit poussé sur `feat/platform-studio`
2. Description visuelle de NewProject, du wizard 5 actes, de BRValidation
3. Liste des nouveaux composants Studio créés (avec chemins)
4. Statut `npm run build` (devrait être 0 erreur)
5. Endpoints API utilisés/ajoutés
6. Recommandations pour A5.3 (notamment sur ChatSidebar et components
   d'execution si tu as touché à des choses partagées)
7. Liste des pages legacy avec bandeau restantes (devrait être 7)

---

*Brief produit par : Claude (maître d'œuvre) · 27 avril 2026*
*URL GitHub raw : https://raw.githubusercontent.com/SamHATIT/digital-humans-production/main/docs/briefs/round3/BRIEF_A52_CASTING.md*
