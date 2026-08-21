## Verdict d’ouverture (5 lignes)

**Non, pas en l’état pour le 1er octobre 2026.**  
Le frontend contient plusieurs défauts **bloquants** : stockage JWT en `localStorage` + exposition XSS, rendu HTML non échappé depuis des contenus agents, et services API legacy cassés qui peuvent provoquer des pannes fonctionnelles silencieuses.  
Il y a aussi des incohérences de contrat (`api.get` utilisé comme Axios, endpoints divergents `/api/...` vs non préfixés) qui rendent une partie du code non fiable en production.  
Le contrôle des paliers est **principalement cosmétique côté frontend** (donc contournable), et je ne peux pas confirmer l’enforcement serveur dans cette passe.  
Avec un correctif ciblé sécurité + contrats API + nettoyage du code mort, le go-live devient réaliste.

---

## Constats

### SEC-01 — **bloquant**
- **Fichier/ligne** : `frontend/src/components/ChatSidebar.tsx` (fonction `formatMarkdownInline`, rendu `dangerouslySetInnerHTML`), ~l.65–73 et ~l.286–289  
- **Scénario réel** : un message agent contenant `<img src=x onerror=fetch('...token...')>` est injecté tel quel dans le DOM. Comme le token est en `localStorage`, compromission de session possible.
- **Correctif** : supprimer `dangerouslySetInnerHTML` et rendre en texte brut ou via sanitizer strict (DOMPurify).
```tsx
<p className="text-sm text-bone-2 whitespace-pre-wrap break-words">{msg.content}</p>
```
- **Effort** : 2h

---

### SEC-02 — **bloquant**
- **Fichier/ligne** : `frontend/src/components/studio/ChatSidebarStudio.tsx` (`inlineFormat` + `dangerouslySetInnerHTML`), ~l.40–48 et ~l.334–336  
- **Scénario réel** : même vecteur XSS dans la version Studio, avec accès chat HITL en prod.
- **Correctif** : idem SEC-01 (texte brut ou sanitizer whitelist).
- **Effort** : 2h

---

### SEC-03 — **bloquant**
- **Fichier/ligne** : `frontend/src/components/SDSPreview.tsx` (`inlineFormat` + `dangerouslySetInnerHTML` dans paragraphes/listes/table), ~l.100–106, 57, 74, 137, 153  
- **Scénario réel** : un SDS contenant HTML malveillant est exécuté à l’ouverture du preview.
- **Correctif** : bannir HTML injection; parser markdown vers composants React sûrs (ou sanitize strict).
- **Effort** : 4h

---

### SEC-04 — **bloquant**
- **Fichier/ligne** : `frontend/src/services/api.ts` (`localStorage` token + cookie JS), ~l.18–31, 36, 67–70  
- **Scénario réel** : toute XSS vole le JWT (`localStorage`) + peut manipuler cookie `token` non HttpOnly.  
- **Correctif** : passer à cookie HttpOnly/Secure/SameSite côté backend + supprimer persistance token côté JS.
- **Effort** : 6h frontend (coordination backend nécessaire, hors périmètre)

---

### REL-01 — **majeur**
- **Fichier/ligne** : `frontend/src/services/deliverableService.js`, `projectsService.js`, `qualityGateService.js` (usage Axios-style `response.data` + `params`)  
- **Scénario réel** : ces services renvoient `undefined` (car `api.get` renvoie déjà JSON), et `params` est ignoré → bugs silencieux.
- **Correctif** : soit supprimer ces services non utilisés, soit les adapter au contrat `apiCall`.
```js
const data = await api.get('/api/...');
return data;
```
- **Effort** : 3h

---

### REL-02 — **majeur**
- **Fichier/ligne** : mêmes services JS legacy (`/deliverables/...`, `/projects/...`, `/quality-gates/...` sans préfixe `/api`)  
- **Scénario réel** : 404 en prod si activés, car le reste du frontend appelle `/api/...`.
- **Correctif** : normaliser tous les endpoints en `/api/...`.
- **Effort** : 2h

---

### REL-03 — **majeur**
- **Fichier/ligne** : `frontend/src/components/SubscriptionBadge.tsx` (tiers `premium/enterprise`) vs pricing (`free/pro/team/enterprise`)  
- **Scénario réel** : gating incohérent, fonctionnalités débloquées/masquées de façon erronée.
- **Correctif** : unifier enum tiers sur `free | pro | team | enterprise`.
- **Effort** : 2h

---

### ARCH-01 — **majeur**
- **Fichier/ligne** : duplication des constantes agents  
  - `src/constants.ts`
  - `src/lib/constants.ts`
  - `src/types/constants.ts`
  - `src/lib/agents.ts`
- **Scénario réel** : divergence progressive (IDs/obligatoires/avatars), régressions métier sur sélection d’agents.
- **Correctif** : conserver `src/lib/agents.ts` comme source unique, retirer/adapter les autres.
- **Effort** : 5h

---

### SEC-05 — **majeur**
- **Fichier/ligne** : `frontend/src/services/api.ts` (`document.cookie = token=...`) ~l.21  
- **Scénario réel** : cookie lisible JS + envoyé large `path=/`; augmente surface de vol/rejeu.
- **Correctif** : ne plus poser ce cookie côté JS; cookie auth doit être émis HttpOnly par serveur.
- **Effort** : 1h frontend

---

### COMPAT-01 — **mineur**
- **Fichier/ligne** : routes déclarées mais pages legacy PM non routées (`src/pages/pm/*`)  
- **Scénario réel** : code mort maintenu, augmente charge cognitive et risques de drift API.
- **Correctif** : marquer explicitement deprecated / exclure build / supprimer après validation.
- **Effort** : 2h

---

## Vérification des correctifs internes P0–P12 (frontend)

- **P4 (partiel contrôleur surdimensionné backend)** : **non vérifiable** dans cette passe frontend.
- **P10 (partiel BaseAgent)** : **non vérifiable** côté frontend.
- **P12 (partiel `.env` clé OpenAI)** : **non vérifiable** côté frontend.
- **P2 (chemins absolus codés en dur)** : **OK côté frontend** (pas de chemins système hardcodés, hors script deploy npm qui est attendu ops).
- **P6 (modèles LLM hardcodés)** : **N/A frontend**.
- **P9 (`safe_content`)** : **N/A frontend**.
- **Point de vigilance réapparu** : malgré P5/P11 côté backend, le frontend affiche parfois les erreurs brutes (`err.message`) directement UI (ex: `ProjectSettingsModal`, `ValidationGatePanel`) — risque d’exposition d’infos internes.

---

## 4) Cohérence des paliers (frontend uniquement)

### TIER-01 — **majeur**
- **Fichier/ligne** : `src/components/SubscriptionBadge.tsx`, `src/pages/Pricing.tsx`, `src/pages/ExecutionPage.tsx`  
- **Constat** : le masquage de fonctionnalités est surtout UI; aucune garantie frontend robuste (normal) et incohérence d’enums (`premium` vs `pro`, `team` absent dans FeatureGate).
- **Risque** : utilisateur peut appeler routes/actions directement via DevTools si backend ne bloque pas.
- **Correctif frontend** : harmoniser les enums et ajouter gardes UI cohérentes.  
- **API backend à vérifier séparément** :  
  - `POST /api/pm-orchestrator/projects/{id}/start-build`  
  - `POST /api/pm-orchestrator/execute`  
  - endpoints BR/SDS/BUILD doivent vérifier tier côté serveur.
- **Effort** : 3h

---

## 5) Passage à l’échelle — jugement

**Verdict frontend : peut tenir la charge UI, mais cassera d’abord sur le coût/rythme des appels backend, pas sur React.**  
Le frontend poll beaucoup (`useExecutionStream` 3s + 10s, multiples écrans), ouvre des panneaux riches (Mermaid, diff, gros JSON), et garde des états lourds en mémoire. Le vrai point de rupture sera backend/LLM, mais côté frontend le premier symptôme sera latence, freeze rendering Mermaid/diff, puis saturation API.

(Je ne chiffre pas infra complète backend ici, hors périmètre demandé frontend-only. Je signale seulement impact côté client.)

---

## 6) Exploitabilité / observabilité manquante

### OPS-01 — **majeur**
- **Fichier/ligne** : global frontend (pas de telemetry structurée)  
- **Scénario réel** : incident UX impossible à diagnostiquer (XSS, API mismatch, crash rendu Mermaid).
- **Correctif** : instrumentation minimale (erreurs globales, route, endpoint, latency).
- **Effort** : 4h

### OPS-02 — **mineur**
- **Fichier/ligne** : multiples `catch {}` silencieux (`ArchitectureReviewPanel`, `ChatSidebar`, etc.)  
- **Scénario réel** : pannes invisibles pour l’éditeur.
- **Correctif** : journaliser au moins en console structurée + toast utilisateur.
- **Effort** : 2h

---

## 7) Dette technique coûteuse

### DEBT-01 — **majeur**
- **Fichier/ligne** : services legacy JS incohérents (`deliverableService.js`, `projectsService.js`, `qualityGateService.js`)  
- **Impact** : réutilisation future dangereuse, faux sentiment de couverture API.
- **Correctif** : purge ou migration TS alignée `services/api.ts`.
- **Effort** : 3h

### DEBT-02 — **majeur**
- **Fichier/ligne** : 4 sources “agents/constants”  
- **Impact** : bugs métier récurrents lors évolutions palier/features.
- **Correctif** : source unique + tests snapshot simples.
- **Effort** : 5h

---

## Ce qui est bien traité (frontend)

- `MermaidRenderer` a `securityLevel: 'strict'` (**bon point**).
- `rel="noopener noreferrer"` présent sur liens externes sensibles.
- Beaucoup de cleanup d’intervalles/effects correctement fait.
- Structuration Studio cohérente et lisible pour itération rapide.

---

## Feuille de route (3 vagues)

### Vague 1 — **avant 1er octobre** (bloquants)
1. Supprimer `dangerouslySetInnerHTML` non sanitizé (SEC-01/02/03).  
2. Couper le token JS cookie + préparer bascule HttpOnly (SEC-04/05).  
3. Désactiver/supprimer services API legacy cassés (REL-01/02).  
4. Harmoniser enums tiers frontend (REL-03/TIER-01).

### Vague 2 — **J+30**
1. Unifier source de vérité agents/constants (DEBT-02).  
2. Ajouter télémétrie erreurs + latence API (OPS-01).  
3. Remplacer `catch {}` silencieux par logs exploitables (OPS-02).

### Vague 3 — **plus tard**
1. Retirer pages PM legacy non routées (COMPAT-01).  
2. Durcir UX paliers (messages explicites, upsell cohérent).  
3. Optimiser rendu gros livrables (virtualisation, lazy Mermaid/diff).