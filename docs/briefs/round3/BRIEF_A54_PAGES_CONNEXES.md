# BRIEF A5.4 — Pages connexes : Projects listing, ProjectDetail, AgentTester, Pricing + cleanup final

> **Owner** : Claude Code (autonome, sandbox web)
> **Branche cible** : `feat/platform-studio` (continuer dessus, après A5.3)
> **Estimation** : 1 session longue (~4h équivalent dev humain)
> **Pré-requis** : A5.3 mergée (Théâtre + composants partagés restylés)

---

## 1. Cadre stratégique

A5.4 ferme le sprint A5 en refondant les **4 pages restantes** et en
nettoyant tout ce qui reste de l'héritage legacy (bandeau "redesigned",
Navbar legacy non utilisée, imports orphelins).

À la fin de A5.4, **toute la plateforme** est en charte Studio. Plus aucun
bandeau "redesigned" nulle part. Plus aucune page en palette
slate/cyan/purple. La cohérence visuelle plateforme ↔ site marketing
preview Mod 16 est complète.

A5.4 inclut aussi une décision commerciale importante : la page Pricing
est **refondée selon la nouvelle nomenclature freemium** validée par Sam
en Round 1 :
- ❌ Plus de Free / Premium / Enterprise (3 tiers anciens)
- ✅ **Free / Pro 49€/mois / Team 1490€+/mois + Enterprise sur devis**
  (3 tiers + 1 commercial)

Pages cibles refondues :
- `/projects` (Projects.tsx, 180 lignes — listing)
- `/project/:projectId` (ProjectDetailPage.tsx, **752 lignes** — hub projet)
- `/agent-tester` (AgentTesterPage.tsx, 338 lignes — outil dev/admin)
- `/pricing` (Pricing.tsx, 250 lignes — **refonte commerciale + visuelle**)

---

## 2. État après A5.3 (rappel anticipé)

✓ Toute la fondation Studio (A5.1)
✓ Wizard 5 actes + BR Validation refondus (A5.2)
✓ Théâtre SDS et BUILD refondus (A5.3)
✓ Composants partagés restylés en Studio :
   ChatSidebarStudio, StructuredRenderer Studio, DeliverableViewer Studio,
   ArchitectureReviewPanel Studio, ValidationGatePanel Studio,
   ProjectSettingsModal Studio, MermaidRenderer, AgentThoughtModal Studio,
   SDSPreview Studio
✓ framer-motion v11 en place, getAgentAccent() utilitaire dispo
✓ CreditCounter fonctionne (endpoint billing identifié)
⚠️ Reste 4 pages legacy avec bandeau : Projects, ProjectDetail, AgentTester,
   Pricing
⚠️ `Navbar.tsx` legacy encore importé sur certaines pages restantes

---

## 3. Périmètre A5.4

### 3.1 Refondre `/projects` — Projects listing Studio (~30 min)

`Projects.tsx` (180 lignes legacy) liste les projets de l'utilisateur en
cards avec actions delete/open.

Nouvelle version Studio reprend **le pattern de la grille Dashboard
(A5.1)** mais avec plus d'infos par card :

```
┌────────────────────────────────────────────────────────┐
│  Header Studio                                         │
├────────────────────────────────────────────────────────┤
│                                                        │
│  № 02 · THE WORKS                                      │
│  Your productions to date.                             │
│  Cormorant ital                                        │
│                                                        │
│  [ + Begin a new production ]   (CTA brass top right)  │
│                                                        │
│  Filters mono : [All] [In casting] [Live] [Archived]   │
│                                                        │
│  ┌──────────┬──────────┬──────────┐                    │
│  │ Card     │ Card     │ Card     │                    │
│  │ project  │ project  │ project  │                    │
│  └──────────┴──────────┴──────────┘                    │
│  ┌──────────┬──────────┬──────────┐                    │
│  │ Card     │ Card     │ Card     │                    │
│  └──────────┴──────────┴──────────┘                    │
│                                                        │
└────────────────────────────────────────────────────────┘
```

Card projet :
- Cover Studio (StudioPlaceholderCover ou cover de projet si dispo)
- Eyebrow mono : industrie ou status (`IN CASTING`, `SDS PHASE`, `BUILD PHASE`,
  `LIVE`, `ARCHIVED`)
- Titre Cormorant ital : nom du projet
- Méta mono small : created_at, current phase, last activity
- Hover : panneau slide-up avec actions (Open · Settings · Archive · Delete)
- Bordure hairline brass au hover

Réutiliser `StudioPlaceholderCover` créé en A5.1.

États :
- **Loading** : skeleton de cards (3 placeholders ink-2 avec shimmer brass)
- **Empty** : copie "No productions yet. Cast your first ensemble." + CTA
- **Error** : panneau Studio cohérent

### 3.2 Refondre `/project/:projectId` — Project Detail Studio (~2h)

**LE gros morceau de A5.4** (752 lignes legacy). C'est un hub de gestion
de projet : versions SDS, change requests, chat, settings, démarrage BUILD,
notifications.

#### 3.2.1 Layout général

```
┌───────────────────────────────────────────────────────────┐
│  Header Studio                                            │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  № 03 · LogiFleet — Service Cloud                         │
│  Eyebrow mono : LOGISTICS · LIVE · created 12 days ago    │
│                                                           │
│  Tabs Studio :                                            │
│  [ Overview ] [ Deliverables ] [ Change requests ] [ ⚙ ] │
│                                                           │
│  ─────────────────────────────                            │
│                                                           │
│  TAB OVERVIEW (default) :                                 │
│  ┌────────────────────┬───────────────────────────────┐   │
│  │  PROJECT STATE     │  RECENT ACTIVITY              │   │
│  │  - Phase: BUILD    │  - Sophie added a CR (1d)     │   │
│  │  - Health: nominal │  - Diego completed Apex (2d)  │   │
│  │  - Credits used   │  - SDS v2.3 approved (5d)     │   │
│  │    1 240 / 5 000   │                               │   │
│  │  - Next milestone  │                               │   │
│  │    Apex tests Tue  │                               │   │
│  └────────────────────┴───────────────────────────────┘   │
│                                                           │
│  CTA selon phase :                                        │
│  - SDS approved → [ ◗ Begin BUILD phase → ]               │
│  - BUILD finished → [ ◗ Download deliverable → ]          │
│  - LIVE → [ ◗ Request a change → ]                        │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

#### 3.2.2 Tabs détaillés

**Overview** (défaut) : carte de santé du projet, dernière activité, CTA
contextuel selon la phase.

**Deliverables** : liste des livrables produits (BR, RDD, Architecture, SDS
versions, ZIP BUILD). Chaque item :
- Icône type (doc, zip, schema)
- Titre + version + date
- CTA "View" → ouvre dans `DeliverableViewer Studio` (déjà restylé en A5.3)
- CTA "Download" → si applicable

**Change requests** : la liste des CRs (active + historique). Chaque CR :
- Statut (open / under review / approved / declined / live)
- Auteur + date
- Description courte
- Click → expand inline avec full description + chat associé
- Bouton "+ New change request" en haut → ouvre modal `ChangeRequestModal Studio`

**Settings** (icône ⚙) : modal `ProjectSettingsModal Studio` (déjà restylé
en A5.3). Pas un tab à proprement parler, ouvre une modal au-dessus du
contenu courant.

#### 3.2.3 Composants à créer/réutiliser

**Nouveaux** :
- `ProjectHealthCard.tsx` : card "Project state" du tab Overview
- `ProjectActivityFeed.tsx` : feed mono "Recent activity"
- `DeliverableCard.tsx` : item de liste pour le tab Deliverables
- `ChangeRequestCard.tsx` : item expandable pour le tab Change requests
- `ChangeRequestModal.tsx` : nouveau CR
- `StudioTabs.tsx` : composant tabs réutilisable Studio (mono uppercase
  tracking 0.16em, soulignement brass animé)

**Réutilisés** :
- `DeliverableViewer Studio` (de A5.3)
- `ChatSidebarStudio` (de A5.3)
- `ProjectSettingsModal Studio` (de A5.3)
- `StructuredRenderer Studio` (de A5.3)

#### 3.2.4 Données

Conserver les contrats API existants (`/api/projects/:id`,
`/api/projects/:id/sds-versions`, `/api/projects/:id/change-requests`,
`/api/projects/:id/messages` etc.). Ne pas modifier le backend.

Si certains endpoints sont incohérents ou manquants, signaler dans le
rapport plutôt que de les inventer.

### 3.3 Refondre `/agent-tester` — AgentTester Studio (~45 min)

`AgentTesterPage.tsx` (338 lignes) est un outil dev/admin pour tester un
agent en isolation. Pas critique pour l'utilisateur final mais utilisé
en interne par Sam et l'équipe.

Nouvelle version Studio :

```
┌──────────────────────────────────────────────────┐
│  Header Studio                                   │
├──────────────────────────────────────────────────┤
│                                                  │
│  № 09 · AGENT TESTER                             │
│  Test an ensemble member in isolation.           │
│  Cormorant ital                                  │
│                                                  │
│  ┌──────────────┬────────────────────────────┐   │
│  │ AGENT PICKER │  AGENT DETAIL              │   │
│  │  ◗ Sophie    │  [ Avatar large ]          │   │
│  │  · Olivia    │  Name + role + tagline     │   │
│  │  · Emma      │                            │   │
│  │  · Marcus    │  Capabilities (mono list)  │   │
│  │  · Diego     │                            │   │
│  │  · Zara      │  TASK INPUT                │   │
│  │  · Raj       │  [ textarea ink-3 ]        │   │
│  │  · Elena     │                            │   │
│  │  · Jordan    │  SF org (dropdown)         │   │
│  │  · Aisha     │  [ Run task ]   (brass)    │   │
│  │  · Lucas     │                            │   │
│  └──────────────┴────────────────────────────┘   │
│                                                  │
│  LIVE LOG (under, full width)                    │
│  Mono small, fond ink-2, hairline brass          │
│  [12:34:56] Sophie: starting analysis...         │
│  [12:34:58] Sophie: BR extracted, 14 stories     │
│                                                  │
└──────────────────────────────────────────────────┘
```

Réutiliser le **mapping accent acte** (getAgentAccent) pour colorer
chaque agent dans le picker selon son acte.

Le live log est probablement déjà streamé via SSE ou polling — conserver
le mécanisme existant.

### 3.4 Refondre `/pricing` — Pricing Studio + REFONTE COMMERCIALE (~45 min)

**ATTENTION** : Pricing n'est pas qu'un re-styling, c'est aussi une
**refonte de la nomenclature commerciale**. La version actuelle propose
Free / Premium / Enterprise (3 tiers) ; la nouvelle nomenclature validée
par Sam en Round 1 est :

| Tier | Prix | Cible |
|---|---|---|
| **Free** | 0 € | Découverte, 1 projet, SDS uniquement, ZDR |
| **Pro** | 49 €/mois | Indépendants, consultants, jusqu'à 5 projets, SDS+BUILD |
| **Team** | 1 490 €/mois | Équipes, projets illimités, support prioritaire |
| **Enterprise** | sur devis | Grands comptes, déploiement on-premise, SLA |

#### 3.4.1 Crédits par tier (à confirmer avec backend, voir tier_config)

Reprendre les valeurs de `tier_config` dans la base PostgreSQL
(seed manuel fait en A4) — Claude Code n'a pas besoin de modifier
ces valeurs, juste les afficher correctement.

Si Claude Code ne peut pas accéder à la DB, afficher les valeurs cibles
suivantes (à valider plus tard par Sam) :
- Free : 500 credits/mois
- Pro : 5 000 credits/mois
- Team : 50 000 credits/mois
- Enterprise : illimité (sur devis)

#### 3.4.2 Layout Studio

```
┌─────────────────────────────────────────────────────────────┐
│  Header Studio                                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  № 09 · PRICING                                             │
│  A studio for every scale.                                  │
│  Cormorant ital                                             │
│                                                             │
│  Lede : From a single Salesforce admin to a full team,     │
│  pick the cast that fits your studio.                       │
│                                                             │
│  ┌──────────┬──────────┬──────────┬──────────┐              │
│  │   FREE   │   PRO    │   TEAM   │   ENT    │              │
│  │   0 €    │  49 €/mo │ 1 490€/mo│ on demand│              │
│  │          │          │          │          │              │
│  │  500     │  5 000   │ 50 000   │  unltd   │              │
│  │ credits  │ credits  │ credits  │ credits  │              │
│  │          │          │          │          │              │
│  │ 1 project│5 projects│   ∞      │   ∞      │              │
│  │          │          │          │          │              │
│  │ SDS only │SDS +BUILD│SDS +BUILD│SDS +BUILD│              │
│  │   ZDR    │  + Git   │   + SLA  │ + on-prem│              │
│  │          │          │          │          │              │
│  │ [Sign up]│[Subscribe│[Contact] │[Contact] │              │
│  │ (mono)   │] (brass) │ (mono)   │ (mono)   │              │
│  └──────────┴──────────┴──────────┴──────────┘              │
│                                                             │
│  Card "Pro" mise en avant (border brass, badge "POPULAR")   │
│                                                             │
│  ──── Comparison table mono ────                            │
│  Liste exhaustive features × tiers (✓ / valeur / ✗)         │
│                                                             │
│  FAQ accordion mono (3-4 questions clés)                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

#### 3.4.3 Tableau comparatif détaillé

Reprendre la structure existante de `Pricing.tsx` (le tableau features ×
tiers), juste **changer les colonnes** : `free` / `premium` / `enterprise`
deviennent `free` / `pro` / `team` / `enterprise`.

Liste de features bilingue FR/EN à mettre à jour :

```ts
const FEATURES = [
  // SDS Phase
  { en: 'Business Requirements extraction', fr: 'Extraction des Business Requirements', free: true, pro: true, team: true, enterprise: true },
  { en: 'Use Cases generation', fr: 'Génération des Use Cases', free: true, pro: true, team: true, enterprise: true },
  { en: 'Solution Design', fr: 'Solution Design', free: true, pro: true, team: true, enterprise: true },
  { en: 'SDS Document (Word/PDF)', fr: 'Document SDS (Word/PDF)', free: true, pro: true, team: true, enterprise: true },
  { en: 'Max BRs per project', fr: 'BRs max par projet', free: '30', pro: '100', team: 'Unlimited', enterprise: 'Unlimited' },
  { en: 'Max projects', fr: 'Projets max', free: '1', pro: '5', team: 'Unlimited', enterprise: 'Unlimited' },
  // BUILD Phase
  { en: 'BUILD Phase (code generation)', fr: 'Phase BUILD (génération de code)', free: false, pro: true, team: true, enterprise: true },
  { en: 'SFDX Deployment', fr: 'Déploiement SFDX', free: false, pro: true, team: true, enterprise: true },
  { en: 'Git integration', fr: 'Intégration Git', free: false, pro: true, team: true, enterprise: true },
  { en: 'Multi-environments', fr: 'Multi-environnements', free: false, pro: false, team: true, enterprise: true },
  // Advanced
  { en: 'Custom templates', fr: 'Templates personnalisés', free: false, pro: false, team: true, enterprise: true },
  { en: 'Priority support', fr: 'Support prioritaire', free: false, pro: true, team: true, enterprise: true },
  { en: 'Zero data retention', fr: 'Zero data retention', free: true, pro: false, team: false, enterprise: true },
  { en: 'On-premise deployment', fr: 'Déploiement on-premise', free: false, pro: false, team: false, enterprise: true },
  { en: 'SLA + dedicated support', fr: 'SLA + support dédié', free: false, pro: false, team: false, enterprise: true },
];
```

Sam pourra ajuster cette liste plus tard. Le critère est : structure
correcte + les 4 tiers + bilingue.

#### 3.4.4 CTAs

- **Free** : `Sign up free →` → `/login` (création de compte)
- **Pro** : `Subscribe →` → pour l'instant, ouvre une modal "Coming soon —
  subscribe to be notified" (Stripe pas encore en prod, validé Sam)
- **Team** : `Talk to us →` → `mailto:[email protected]?subject=Team plan`
- **Enterprise** : `Talk to us →` → `mailto:[email protected]?subject=Enterprise plan`

#### 3.4.5 Page accessible publiquement

`/pricing` est dans les **routes publiques** de App.tsx (déjà). Ne pas la
mettre derrière `<ProtectedRoute>`. Mais la wrapper dans un AppShell léger
(juste header simple sans CreditCounter quand non connecté).

Créer un variant `<AppShell variant="public">` qui n'affiche pas
CreditCounter et a des CTAs login/signup à droite au lieu de logout.

### 3.5 Cleanup final du sprint A5 (~15 min)

Le sprint A5 ferme proprement :

1. **Retirer `RedesignedBanner` de toutes les pages** — il ne reste plus
   aucune page legacy après A5.4
2. **Supprimer `components/RedesignedBanner.tsx`** lui-même (composant
   plus utilisé)
3. **Retirer `Navbar.tsx` legacy** s'il n'est plus utilisé (vérifier que
   plus aucune page n'importe `Navbar`). S'il est encore importé, finir
   la migration vers `StudioHeader`.
4. **Retirer le shim `lib/motion.tsx`** si pas déjà fait en A5.2
5. **Audit `npm prune`** — retirer les dépendances qui ne sont plus
   utilisées (potentiellement les vieilles deps liées au design legacy)
6. **Vérifier `tailwind.config.js`** — si des couleurs legacy
   (`pm-primary`, `pm-secondary`, `primary` du mode legacy) traînent
   encore, les retirer

### 3.6 Tests visuels & sanity finaux

- `npm run build` : 0 erreur TS strict
- Test manuel parcours complet :
  1. Visiter `/pricing` (non connecté) → version Studio publique
  2. Click "Sign up free" → `/login` Studio
  3. Login → Dashboard Studio
  4. Click "+ Begin production" → `/projects/new` Studio
  5. Wizard 5 actes → submit → BR validation
  6. Approve → execution → curtain rises → monitor SDS
  7. SDS approved → BUILD phase → monitor BUILD
  8. Build finished → download
  9. Aller sur `/projects` → listing Studio cohérent
  10. Click sur un projet → ProjectDetail Studio
  11. Tabs Overview / Deliverables / Change requests / Settings tous fonctionnels
  12. Aller sur `/agent-tester` → outil dev Studio
  13. Aucun bandeau "redesigned" nulle part

- Cohérence visuelle plateforme ↔ site marketing preview Mod 16
- Bilinguisme FR/EN sur toutes les pages refondues

### 3.7 Mettre à jour App.tsx

Wrapper les 4 pages refondues dans `<AppShell>` :
- `/projects` (protected)
- `/project/:projectId` (protected)
- `/agent-tester` (protected)
- `/pricing` (PUBLIC — utiliser `<AppShell variant="public">`)

---

## 4. Hors périmètre A5.4

❌ Implémenter Stripe en réel (= Phase 3.3 future, hors A5)
❌ Modifier le backend (aucune modification)
❌ Toucher au site marketing live ou preview Studio
❌ Toucher aux tier_config en DB (juste les afficher correctement)
❌ Casser le build TS strict
❌ Refacto structurel des composants A5.3 (ChatSidebarStudio, etc.) — juste
   les utiliser tels quels

---

## 5. Garde-fous

### Tu peux
- Refondre les 4 pages cibles
- Créer de nouveaux composants Studio (`StudioTabs`, `ProjectHealthCard`,
  `ProjectActivityFeed`, `DeliverableCard`, `ChangeRequestCard`,
  `ChangeRequestModal`)
- Créer la variante `<AppShell variant="public">` pour `/pricing`
- Faire le cleanup final (retirer RedesignedBanner, Navbar legacy, shim
  motion résiduel s'il en reste)

### Tu ne dois pas
- ❌ Modifier le backend
- ❌ Implémenter Stripe en réel (juste préparer les CTAs avec modal
  "Coming soon")
- ❌ Casser le build TS strict
- ❌ Modifier les contrats `services/api.ts` au-delà d'ajouter de nouvelles
  fonctions helpers
- ❌ Casser la cohérence visuelle avec ce qui a été fait en A5.1/A5.2/A5.3
- ❌ Modifier le `tier_config` en DB

### Pièges connus
1. **Pricing public** : `<AppShell variant="public">` ne doit PAS faire
   d'appels API protégés (CreditCounter retire), mais doit garder
   StudioFooter et le toggle FR/EN.
2. **ProjectDetailPage 752 lignes** : trop gros pour un seul fichier après
   refacto. Casser en sous-composants par tab (ProjectOverviewTab,
   ProjectDeliverablesTab, ProjectChangeRequestsTab) pour rester lisible.
3. **Modal "Coming soon" Pro tier** : sobre, juste une note Studio
   (Cormorant ital + bouton "Notify me" qui ouvre un mailto). Pas de
   formulaire d'attente complexe — pas le moment.
4. **Mailto** : utiliser `[email protected]` comme adresse par défaut
   (à confirmer par Sam si autre).
5. **AgentTester accent acte** : utiliser getAgentAccent() de A5.3 pour
   le picker d'agents — chaque agent dans la liste a sa couleur d'acte.
6. **Tableau comparatif Pricing** : 4 colonnes au lieu de 3, faire
   attention au responsive (mobile : passer en accordion par tier).
7. **Cleanup imports** : après suppression de RedesignedBanner et Navbar,
   faire un `grep -r "RedesignedBanner\|Navbar"` pour s'assurer qu'aucun
   import orphelin ne casse le build.

---

## 6. Protocole de rapport

À la fin :
1. Hash du commit poussé sur `feat/platform-studio`
2. Description visuelle de Projects, ProjectDetail (4 tabs), AgentTester,
   Pricing (4 tiers + tableau)
3. Liste des nouveaux composants créés (chemins)
4. Liste des composants/fichiers SUPPRIMÉS (RedesignedBanner, Navbar legacy,
   etc.)
5. Statut `npm run build` (0 erreur TS attendue)
6. Endpoints API utilisés (avec statut fonctionne / problème / à créer)
7. Confirmation : 0 page legacy restante, 0 bandeau "redesigned" nulle part
8. **Recommandations finales pour Sam** :
   - Listes des décisions à confirmer (mails commercial,
     valeurs tier_config si différentes)
   - Décisions techniques à challenger (par ex. le bundle reste lourd ?)
   - Idées d'amélioration post-A5 qui sont sorties pendant la refonte

---

## 7. Fin du sprint A5

À la fin de A5.4 :
- **Toute la plateforme** est en charte Studio
- **0 page legacy** restante
- **0 bandeau "redesigned"** nulle part
- **TS strict** actif sur tout le frontend
- **0 dépendance morte** dans package.json
- Le sprint A5 (4 sous-briefs) est complet → on peut merger
  `feat/platform-studio` sur `main` après validation Sam et tagger
  `v2026.04-platform-studio` (et planifier la bascule prod en Phase 2 du
  master plan)

---

*Brief produit par : Claude (maître d'œuvre) · 27 avril 2026*
*URL GitHub raw : https://raw.githubusercontent.com/SamHATIT/digital-humans-production/main/docs/briefs/round3/BRIEF_A54_PAGES_CONNEXES.md*
