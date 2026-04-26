# BRIEF — Mod 16 — Galerie projets en slider horizontal (REMPLACE le trombinoscope)

> **Owner** : Claude Code (autonome, sur le VPS)
> **Cible** : `/var/www/dh-preview/index.html` (bundle React custom)
> **Estimation** : 1 session
> **Priorité** : 🔴 Mod 15 a livré une version incorrecte (grille statique en plus du trombinoscope, bug images). Mod 16 corrige.

---

## 1. Contexte

Mod 15 a livré une galerie projets `№ 04 · The work` en grille 3×2, **en plus** du trombinoscope (`№ 03 · The ensemble`). Sam a explicité après visualisation que l'intention initiale était :

- **Le trombinoscope est REMPLACÉ par la galerie projets**, pas ajouté à côté
  (les portraits agents sont déjà dans les slides de l'acte 2 — le trombinoscope
   était redondant et prenait de la place)
- **Format slider horizontal** identique à `HowItWorks` (acte 2), pas une grille statique
- **Layout d'une slide** : photo plein format avec titre + industrie en overlay
  (gradient ink bottom-up). Au hover, **flip 3D** vertical (rotateY) qui révèle
  les détails techniques + punchline + CTA SDS au verso

Bug Mod 15 à corriger au passage : la fonction `COVER(id)` appelait `AV(key)`,
mais `AV` re-préfixe automatiquement `'av'` → `R['avCvLogifleet']` ne match
jamais le slug `cvLogifleet` des ext_resources. Solution : COVER doit
accéder directement à `R[key]` sans passer par AV.

---

## 2. État cible après Mod 16

| № | Section | Composant | Source |
|---|---|---|---|
| 01 · The case | 4 promesses | `Benefits` | sections.jsx |
| 02 · The sequence | 5 actes du flow (slider H) | `HowItWorks` | sections.jsx |
| **03 · The work** ← **NOUVEAU** | **6 projets (slider H, flip 3D)** | **`OurWork` (refactorisé)** | avatars.jsx |
| 04 · Correspondence | CTA book demo | `CTA` (re-renumeroté от 05 → 04) | avatars.jsx |
| (footer) | — | `Footer` | avatars.jsx |

**Supprimé** : `OurAgents` (le trombinoscope `№ 03 · The ensemble`)

**Note importante** : la fonction `OurAgents` peut rester définie dans avatars.jsx
(zéro coût) mais **ne doit plus être appelée** dans la composition Site
(module UUID `0fbb2257-1e1...`). De même `<OurAgents lang={lang}/>` doit être
retiré du module Site.

---

## 3. Décisions Sam acceptées (à respecter)

### 3.1 Tagline acte 3
**FR/EN identique** : *"Whatever theatre of work, one rim rule."*

(File la métaphore théâtre du site et justifie le terme "rim rule" qui fait
référence à la règle visuelle des accents agents.)

### 3.2 Numérotage des slides
**Chiffres romains I à VI** (cohérence avec les actes I-V de l'acte 2 du site).

### 3.3 Layout d'une slide

```
┌────────────────────────────────────────────┐
│                                            │
│                                            │
│         [ COVER STUDIO PLEIN FORMAT ]      │
│         (papier crème + ink + brass)       │
│                                            │
│                                            │
│  ▒▒▒▒▒▒ gradient ink↗ bottom 40% ▒▒▒▒▒▒    │
│                                            │
│  III  ·  LOGISTICS · B2B          (mono brass)
│  LogiFleet — Fleet Service Cloud  (Cormorant italique bone)
│                                            │
└────────────────────────────────────────────┘

   ↓ HOVER (flip 3D rotateY 180°, 600ms ease) ↓

┌────────────────────────────────────────────┐
│  III  ·  LOGISTICS · B2B          (mono brass)
│  LogiFleet — Fleet Service Cloud  (Cormorant italique bone)
│                                            │
│  • Service Cloud · Field Service · 320 assets
│  • 12 custom objects · 47 flows · 9 LWC    │
│  • Live in production, week 11 · 0 critical bugs
│                                            │
│  A 320-vehicle fleet brought into Service  │
│  Cloud in eight days. Drivers, dispatch,   │
│  maintenance — one canonical record per    │
│  asset.                                    │
│                                            │
│  READ THE SDS →                            │
└────────────────────────────────────────────┘
```

### 3.4 Animation flip
- `transform: rotateY(180deg)` au verso (au repos), `rotateY(0)` au recto
- Durée 600ms, easing ease (ou cubic-bezier(0.2, 0.8, 0.2, 1))
- `transform-style: preserve-3d` sur le wrapper, `backface-visibility: hidden` sur les deux faces
- Au hover du wrapper `.work-slide` (pas du `.work-flip`), le flip s'inverse
- **Fallback mobile** : touchstart toggle une classe `.flipped` (le hover ne marche pas bien tactile)

### 3.5 Gradient overlay
- En bas, hauteur 40% de la slide
- Background : `linear-gradient(to top, rgba(10,10,11,0.92) 0%, rgba(10,10,11,0.7) 50%, rgba(10,10,11,0) 100%)`
- Le titre + l'eyebrow industrie sont positionnés `position: absolute; bottom: 32px; left: 32px;` au-dessus du gradient

### 3.6 Bug COVER → fix
```js
// AVANT (Mod 15, buggé)
const COVER = id => {
  const key = 'cv' + id.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
  return (typeof AV === 'function' ? AV(key) : null) || ('assets/covers/' + id + '.jpg');
};

// APRÈS (Mod 16, fixé)
const COVER = id => {
  const R = (window.__resources || {});
  const key = 'cv' + id.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
  return R[key] || ('assets/covers/' + id + '.jpg');
};
```

(Pas de re-préfixage `av` — accès direct à `R[key]`.)

---

## 4. Tâches détaillées

### Étape 1 — Préparer la branche et le backup (5 min)

```bash
cd /root/workspace/digital-humans-production
git fetch origin
git checkout main
git pull origin main
git checkout -b claude/preview-mod16-gallery-slider

# Backup pré-Mod 16
cp /var/www/dh-preview/index.html /var/www/dh-preview/index.html.pre-mod16
ls -la /var/www/dh-preview/index.html.pre-mod16
```

### Étape 2 — Lire le bundle et identifier les modules cibles (5 min)

Le pattern est connu (cf. `docs/marketing-site/REPRISE_MEMO.md` et le script
Mod 15 `docs/marketing-site/scripts/dh-mod15.py` qui sert de référence).

UUIDs cibles :
- `b077057a-5a3a-41a8-8f45-fe3c0011a134` — `avatars.jsx` (contient `OurAgents`,
  `OurWork` Mod 15, `CTA`, `Footer`)
- Le module Site (le seul module qui contient `<OurAgents lang={lang}/>` ET
  `<CTA lang={lang}/>` dans son content) — l'identifier dynamiquement au
  scan, pas hardcoder l'UUID (il varie selon les builds).

### Étape 3 — Patcher avatars.jsx (40 min)

#### 3.1 Supprimer le bloc `OurWork` actuel (Mod 15)
Tout entre le commentaire/début `const PROJECTS = [` et la fin de
`function OurWork({lang}) { … }` doit être remplacé par la nouvelle version.

#### 3.2 Nouveau composant `OurWork` (slider horizontal flip 3D)

Code à insérer **avant** `function CTA(`, dans avatars.jsx :

```jsx
const PROJECTS = [
  {
    id: 'logifleet',
    roman: 'I',
    industry: { en: 'LOGISTICS · B2B', fr: 'LOGISTIQUE · B2B' },
    title: { en: 'LogiFleet — Fleet Service Cloud',
             fr: 'LogiFleet — Fleet Service Cloud' },
    punchline: { en: 'A 320-vehicle fleet brought into Service Cloud in eight days. Drivers, dispatch, maintenance — one canonical record per asset.',
                 fr: 'Une flotte de 320 véhicules basculée dans Service Cloud en huit jours. Chauffeurs, dispatch, maintenance — un seul enregistrement canonique par actif.' },
    scope: ['Service Cloud · Field Service · 320 assets',
            '12 custom objects · 47 flows · 9 LWC',
            'Live in production, week 11 · 0 critical bugs'],
    sds_url: 'https://digital-humans.fr/sds-preview/146.html',
  },
  { id: 'pharma', roman: 'II',
    industry: { en: 'PHARMA · CLINICAL TRIALS', fr: 'PHARMA · ESSAIS CLINIQUES' },
    title: { en: 'Clinical Trial Watch', fr: 'Clinical Trial Watch' },
    punchline: { en: 'A regulated trial pipeline turned into a single Salesforce dashboard. Sites, enrolments, deviations — every event audit-trailed.',
                 fr: 'Un pipeline d’essais cliniques régulés transformé en un seul dashboard Salesforce. Sites, recrutements, déviations — chaque événement traçable.' },
    scope: ['Health Cloud · Experience Cloud · 21 CFR Part 11',
            '38 trial sites · 1 200 enrolments tracked',
            'Audit-ready logs, end-to-end'],
    sds_url: null },
  { id: 'telecom', roman: 'III',
    industry: { en: 'TELECOM · CLAIMS', fr: 'TÉLÉCOM · RÉCLAMATIONS' },
    title: { en: 'Claim Resolver', fr: 'Claim Resolver' },
    punchline: { en: '14-day average resolution dropped to 4. Claims triaged by Einstein, dispatched by Sophie, audited by Elena.',
                 fr: 'Délai moyen de résolution passé de 14 à 4 jours. Réclamations triées par Einstein, dispatchées par Sophie, auditées par Elena.' },
    scope: ['Service Cloud · Einstein Bots · Omnichannel',
            '110 000 claims/year · 87% first-touch resolution',
            '−71% AHT, +12 NPS in two quarters'],
    sds_url: null },
  { id: 'b2b-distribution', roman: 'IV',
    industry: { en: 'B2B · DISTRIBUTION', fr: 'B2B · DISTRIBUTION' },
    title: { en: 'Pipeline Tuner', fr: 'Pipeline Tuner' },
    punchline: { en: 'Twelve regional sales pipelines reconciled into one consolidated view. Forecast accuracy up from 68% to 91% in the first quarter.',
                 fr: 'Douze pipelines commerciaux régionaux réconciliés en une vue consolidée. Précision du forecast passée de 68% à 91% au premier trimestre.' },
    scope: ['Sales Cloud · CPQ · Tableau CRM',
            '12 regions · 240 reps · €310M ARR tracked',
            '+23 forecast accuracy points'],
    sds_url: null },
  { id: 'energy', roman: 'V',
    industry: { en: 'ENERGY · GRID', fr: 'ÉNERGIE · RÉSEAU' },
    title: { en: 'Grid Foresight', fr: 'Grid Foresight' },
    punchline: { en: 'High-voltage maintenance scheduling moved from spreadsheets to Salesforce. Outage windows down 38%, asset uptime up 6 points.',
                 fr: 'Planification de la maintenance haute tension basculée des spreadsheets vers Salesforce. Fenêtres de coupure −38%, disponibilité des actifs +6 points.' },
    scope: ['Field Service · Asset 360 · Net Zero Cloud',
            '4 800 high-voltage assets monitored',
            'Predictive maintenance via Einstein Discovery'],
    sds_url: null },
  { id: 'retail', roman: 'VI',
    industry: { en: 'RETAIL · OMNICHANNEL', fr: 'RETAIL · OMNICANAL' },
    title: { en: 'Omnichannel Loop', fr: 'Omnichannel Loop' },
    punchline: { en: 'Fifty stores, one customer record. Loyalty events, returns, e-commerce orders, in-store visits — stitched into a single graph.',
                 fr: 'Cinquante magasins, un seul dossier client. Événements de fidélité, retours, commandes e-commerce, visites en magasin — cousus dans un seul graphe.' },
    scope: ['Commerce Cloud · Marketing Cloud · Loyalty',
            '50 stores · 1.4M customers unified',
            '+18% repeat purchase rate'],
    sds_url: null },
];

const COVER = id => {
  const R = (window.__resources || {});
  const key = 'cv' + id.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
  return R[key] || ('assets/covers/' + id + '.jpg');
};

function OurWork({lang}) {
  const scrollerRef = React.useRef(null);
  const [activeIdx, setActiveIdx] = React.useState(0);

  // Réutilise le pattern de HowItWorks pour la nav slider :
  // useEffect onScroll + rafId pour calculer l'index actif
  React.useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    let rafId = null;
    const onScroll = () => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const w = el.clientWidth;
        const i = Math.round(el.scrollLeft / w);
        const total = PROJECTS.length;
        const clamped = Math.max(0, Math.min(total - 1, i));
        setActiveIdx(clamped);
      });
    };
    el.addEventListener('scroll', onScroll, {passive: true});
    return () => { el.removeEventListener('scroll', onScroll); if (rafId) cancelAnimationFrame(rafId); };
  }, []);

  const goTo = (i) => {
    const el = scrollerRef.current;
    if (!el) return;
    const total = PROJECTS.length;
    const clamped = Math.max(0, Math.min(total - 1, i));
    el.scrollTo({left: clamped * el.clientWidth, behavior: 'smooth'});
  };

  // Touch-toggle pour mobile
  const onSlideTap = (e) => {
    if (window.matchMedia && window.matchMedia('(hover: hover)').matches) return;
    e.currentTarget.classList.toggle('flipped');
  };

  const t = lang === 'en'
    ? { num: '№ 03 · The work',
        title: (<>Whatever theatre of work, <em>one rim rule</em>.</>),
        lede: 'Each engagement is a single Salesforce solution composed by the ensemble. Six are public ; the rest live behind NDAs we are happy to honour.',
        cta: 'Read the SDS',
        soon: 'SDS · coming soon' }
    : { num: '№ 03 · L’atelier',
        title: (<>Quel que soit le théâtre, <em>une seule règle</em>.</>),
        lede: 'Chaque mission est une solution Salesforce composée par l’ensemble. Six sont publiques ; les autres vivent derrière des NDA que nous respectons volontiers.',
        cta: 'Lire le SDS',
        soon: 'SDS · bientôt' };

  const isFirst = activeIdx === 0;
  const isLast = activeIdx === PROJECTS.length - 1;

  return (
    <section id="work" className="block">
      <div className="wrap">
        <div className="section-head">
          <div className="num">{t.num}</div>
          <div>
            <h2>{t.title}</h2>
            <p className="lede">{t.lede}</p>
          </div>
        </div>
        <div className="sequence-container work-sequence">
          <div className="steps work-steps" ref={scrollerRef}>
            {PROJECTS.map((p, i) => (
              <div key={p.id} className="step work-slide" onClick={onSlideTap}>
                <div className="work-flip">
                  <div className="work-face work-face-front">
                    <img className="work-cover-img" src={COVER(p.id)} alt={p.title[lang]} loading="lazy"/>
                    <div className="work-cover-gradient"></div>
                    <div className="work-cover-overlay">
                      <div className="work-eyebrow">
                        <span className="work-roman">{p.roman}</span>
                        <span className="work-sep"> · </span>
                        <span>{p.industry[lang]}</span>
                      </div>
                      <h3 className="work-title">{p.title[lang]}</h3>
                    </div>
                  </div>
                  <div className="work-face work-face-back">
                    <div className="work-eyebrow">
                      <span className="work-roman">{p.roman}</span>
                      <span className="work-sep"> · </span>
                      <span>{p.industry[lang]}</span>
                    </div>
                    <h3 className="work-title">{p.title[lang]}</h3>
                    <ul className="work-scope">
                      {p.scope.map((s, k) => (<li key={k}>{s}</li>))}
                    </ul>
                    <p className="work-punch">{p.punchline[lang]}</p>
                    {p.sds_url
                      ? (<a href={p.sds_url} className="work-cta" target="_blank" rel="noopener">{t.cta}<span className="ar"> →</span></a>)
                      : (<span className="work-soon">{t.soon}</span>)}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <button className="seq-arrow seq-prev" onClick={() => goTo(activeIdx - 1)} disabled={isFirst} aria-label="Previous project">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
          </button>
          <button className="seq-arrow seq-next" onClick={() => goTo(activeIdx + 1)} disabled={isLast} aria-label="Next project">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6"/></svg>
          </button>
        </div>
        <div className="seq-dots" role="tablist" aria-label="Project navigation">
          {PROJECTS.map((p, i) => (
            <button
              key={p.id}
              className={'seq-dot' + (i === activeIdx ? ' active' : '')}
              style={{'--c': 'var(--brass)'}}
              onClick={() => goTo(i)}
              aria-label={'Project ' + p.roman}
              aria-current={i === activeIdx ? 'true' : 'false'}
            />
          ))}
        </div>
      </div>
    </section>
  );
}
```

#### 3.3 Renumeroter `CTA` en `№ 04`

Inverser ce que Mod 15 avait fait :
```diff
-    num: '№ 05 · Correspondence',
+    num: '№ 04 · Correspondence',
…
-    num: '№ 05 · Correspondance',
+    num: '№ 04 · Correspondance',
```

#### 3.4 `Object.assign(window, …)`

Garder `OurWork` dans l'export. **Retirer `OurAgents`** de l'export
**si** `OurAgents` n'est plus utilisé nulle part (recommandé : retirer
de la liste, mais laisser la fonction définie pour permettre un rollback
rapide via le module Site).

### Étape 4 — Patcher le module Site (le composant racine) (15 min)

Identifier dynamiquement le module qui contient `<OurAgents lang={lang}/>` et
`<CTA lang={lang}/>` (cf. fix runtime du Mod 15 qui scanne le manifest).

Dans son content :
- **Supprimer** la ligne `<OurAgents lang={lang}/>` (et son éventuel saut de ligne)
- **Conserver** `<OurWork lang={lang}/>` (déjà injecté en Mod 15)

Composition cible :
```jsx
<Hero lang={lang}/>
<Benefits lang={lang}/>
<HowItWorks lang={lang}/>
<OurWork lang={lang}/>
<CTA lang={lang}/>
```

(Plus de `<OurAgents lang={lang}/>`.)

### Étape 5 — CSS dans le template (30 min)

Le CSS Mod 15 (`/* ===== Mod 15 — № 04 · The work — gallery ===== */`) doit
être **remplacé** par le nouveau bloc CSS Mod 16 (slider horizontal + flip 3D).
Si le Mod 15 a injecté le CSS avant un marker précis, on cherche ce marker
et on remplace tout le bloc Mod 15 par le bloc Mod 16.

```css
/* ===== Mod 16 — № 03 · The work — slider horizontal + flip 3D ===== */

/* Le .work-sequence reprend le squelette de .sequence-container :
   scroll horizontal CSS native (scroll-snap-type: x mandatory),
   slides en pleine width. */
.work-steps {
  /* hérite déjà des règles de .steps (flex, scroll-snap, etc.) */
  /* on peut surcharger si la hauteur des slides projets diffère
     des slides agents */
}

.work-slide {
  /* hérite de .step pour l'organisation slider */
  perspective: 1400px;  /* nécessaire pour le flip 3D */
}

.work-flip {
  position: relative;
  width: 100%;
  aspect-ratio: 4 / 3;  /* ou 16/10 selon ce qui rend mieux — à ajuster */
  transform-style: preserve-3d;
  transition: transform 600ms cubic-bezier(0.2, 0.8, 0.2, 1);
}

/* Hover sur device pointer ; pour mobile, classe .flipped togglée par JS */
@media (hover: hover) {
  .work-slide:hover .work-flip { transform: rotateY(180deg); }
}
.work-slide.flipped .work-flip { transform: rotateY(180deg); }

.work-face {
  position: absolute;
  inset: 0;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
  overflow: hidden;
  background: var(--ink-2);
  border: 1px solid rgba(245, 242, 236, 0.06);
}
.work-face-front {
  /* la cover plein format */
}
.work-face-back {
  transform: rotateY(180deg);
  padding: 40px 36px 36px;
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--brass);
}

.work-cover-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(0.92) contrast(1.02);
}
.work-cover-gradient {
  position: absolute;
  left: 0; right: 0; bottom: 0;
  height: 40%;
  background: linear-gradient(to top,
    rgba(10,10,11,0.92) 0%,
    rgba(10,10,11,0.7) 50%,
    rgba(10,10,11,0) 100%);
  pointer-events: none;
}
.work-cover-overlay {
  position: absolute;
  left: 36px; right: 36px; bottom: 32px;
}
.work-eyebrow {
  font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brass);
  margin-bottom: 14px;
}
.work-roman {
  display: inline-block;
  min-width: 28px;
  font-style: italic;
}
.work-sep { color: var(--brass-3, var(--brass)); }
.work-title {
  font-family: var(--serif, 'Cormorant Garamond', Georgia, serif);
  font-style: italic;
  font-size: 28px;
  font-weight: 500;
  line-height: 1.15;
  color: var(--bone);
  margin: 0;
}

/* Verso : scope + punchline + CTA */
.work-face-back .work-eyebrow { margin-bottom: 14px; }
.work-face-back .work-title { font-size: 24px; margin-bottom: 24px; }
.work-scope {
  list-style: none;
  padding: 0;
  margin: 0 0 22px;
}
.work-scope li {
  font-family: Inter, -apple-system, sans-serif;
  font-size: 13.5px;
  line-height: 1.55;
  color: var(--bone-3);
  margin-bottom: 7px;
  padding-left: 14px;
  position: relative;
}
.work-scope li::before {
  content: '·';
  position: absolute;
  left: 0;
  color: var(--brass);
}
.work-punch {
  font-family: var(--serif, 'Cormorant Garamond', Georgia, serif);
  font-style: italic;
  font-size: 16px;
  line-height: 1.5;
  color: var(--bone-2, var(--bone));
  margin: 0 0 28px;
  flex-grow: 1;
}
.work-cta {
  font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--brass);
  text-decoration: none;
  align-self: flex-start;
}
.work-cta .ar { margin-left: 6px; }
.work-soon {
  font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--bone-4);
}

/* Responsive */
@media (max-width: 760px) {
  .work-title { font-size: 22px; }
  .work-face-back { padding: 28px 24px 24px; }
  .work-face-back .work-title { font-size: 20px; }
}
```

### Étape 6 — Repacking + sanity (15 min)

Suivre le pattern Mod 15 :
1. Re-gziper avatars.jsx + le module Site
2. Re-écrire le manifest
3. Sérialiser le template avec `ensure_ascii=False` + escape `</script>` `</style>`
4. Écrire le bundle final dans `/var/www/dh-preview/index.html`
5. Sanity check via Python (3 sections script présentes, manifest entries, etc.)
6. Smoke HTTP sur `http://72.61.161.222/preview/` (HTTP 200, taille raisonnable, présence de `<OurWork`, absence de `<OurAgents`)

⚠️ **Vérifier au sanity check** :
- Le content du module Site ne contient plus `<OurAgents lang={lang}/>`
- avatars.jsx contient toujours `function OurAgents` (préservé pour rollback,
  juste plus appelé) — sauf si tu décides de le retirer aussi (au choix de
  Claude Code, justifier)
- avatars.jsx contient `function OurWork` avec PROJECTS et `roman` field
- avatars.jsx CTA est `№ 04` (pas `№ 05`)
- COVER ne référence plus `AV(`
- CSS Mod 15 supprimé, CSS Mod 16 présent (chercher `/* ===== Mod 16 —`)

### Étape 7 — Documenter dans REPRISE_MEMO et commit (5 min)

Ajouter à `/var/www/dh-preview/REPRISE_MEMO.md` (ou `docs/marketing-site/REPRISE_MEMO.md`
si c'est là que la version trackée vit) :

```markdown
### Session 26 avril (soir, suite) — Mod 16 (correctif Mod 15)

- **Mod 16** : refonte de la section galerie en **slider horizontal flip 3D**,
  qui **REMPLACE** le trombinoscope `№ 03 · The ensemble`.
  - Numérotation revue : Benefits 01 → Sequence 02 → **Work 03 (nouveau)** → CTA 04
  - 6 slides projets, format slider H identique à HowItWorks
  - Chaque slide : photo cover plein format avec titre + industrie en overlay
    sur gradient ink bottom 40%
  - Hover : flip 3D 600ms (rotateY 180°) qui révèle au verso :
    industrie, scope 3 bullets, punchline ital, CTA Read the SDS
  - Fallback mobile : tap toggle .flipped
  - Bug Mod 15 fixé : COVER accède directement à R[key] (plus de AV() qui
    re-préfixait 'av' et cassait la résolution)
  - Trombinoscope OurAgents retiré de la composition Site (la fonction reste
    définie dans avatars.jsx pour rollback)
  - Tagline Sam validée : "Whatever theatre of work, one rim rule."
```

Et le commit :
```bash
git add docs/marketing-site/scripts/dh-mod16.py  # le script auto-patch s'il existe
git add docs/marketing-site/REPRISE_MEMO.md
git -c user.name="Sam (via Claude)" -c user.email="[email protected]" \
  commit -m "feat(preview): Mod 16 — galerie projets en slider horizontal flip 3D

REMPLACE le trombinoscope № 03 par la galerie projets en slider horizontal,
même squelette que HowItWorks (acte 2). 6 projets en slides, photo cover
plein format avec titre + industrie en overlay (gradient ink bottom 40%).

Au hover : flip 3D rotateY 180° (600ms) qui révèle au verso :
- eyebrow industrie
- titre Cormorant ital
- 3 bullets scope Salesforce (clouds, volumes, résultats)
- punchline narrative
- CTA Read the SDS (LogiFleet linké, 5 autres en SDS · coming soon)

Fallback mobile : tap toggle .flipped.

Numérotation revue :
- 01 Benefits, 02 Sequence, 03 The work (nouveau), 04 Correspondence (CTA)
- OurAgents retiré de la composition Site (mais fonction préservée dans
  avatars.jsx pour rollback)

Bug Mod 15 fixé : COVER accède directement à window.__resources[key] au lieu
de passer par AV() qui re-préfixait 'av' (d'où images cassées Mod 15).

Tagline validée par Sam : 'Whatever theatre of work, one rim rule.'

Backup : /var/www/dh-preview/index.html.pre-mod16"
git push origin claude/preview-mod16-gallery-slider
```

---

## 5. Critères de fin (DoD)

- ✅ Section `№ 03 · The work` visible à la place de l'ancien `№ 03 · The ensemble`
- ✅ `№ 02 · The sequence` (HowItWorks) intact, pas modifié
- ✅ CTA renumérotée à `№ 04 · Correspondence`
- ✅ Plus de `<OurAgents lang={lang}/>` dans la composition Site
- ✅ 6 slides projets, slider horizontal scroll-snap
- ✅ Navigation flèches `<` `>` + dots cliquables
- ✅ Photos covers visibles (pas de placeholder cassé — bug Mod 15 fixé)
- ✅ Hover desktop : flip 3D (rotateY 180°, 600ms)
- ✅ Tap mobile : toggle `.flipped`
- ✅ Verso : industrie + titre + 3 scope + punchline + CTA SDS
- ✅ LogiFleet linké au SDS public ; 5 autres en "SDS · coming soon"
- ✅ Bilingue FR/EN OK
- ✅ Tagline EN : *"Whatever theatre of work, one rim rule."*
- ✅ Tagline FR : *"Quel que soit le théâtre, une seule règle."*
- ✅ Backup `index.html.pre-mod16` créé
- ✅ Section "Mod 16" ajoutée au REPRISE_MEMO

---

## 6. Garde-fous

### Ce que tu peux faire
- Modifier `/var/www/dh-preview/index.html` (avec backup obligatoire)
- Modifier avatars.jsx (UUID `b077057a-…`)
- Modifier le module Site (à identifier dynamiquement par scan du manifest)
- Modifier le CSS dans le template
- Ajuster le `aspect-ratio` ou la hauteur des slides si le 4/3 ne rend pas bien
- Adapter les copies projet si nécessaire (mais pas obligatoire)

### Ce que tu NE DOIS PAS faire
- ❌ Toucher au site live `https://digital-humans.fr/`
- ❌ Modifier `Benefits`, `HowItWorks`, `Footer`, `Hero` (quoi qu'il arrive)
- ❌ Casser le bilinguisme (toute string EN doit avoir son équivalent FR)
- ❌ Retirer la **fonction** `OurAgents` du module avatars.jsx (juste son **appel** dans le module Site) — on garde la définition pour permettre un rollback rapide
- ❌ Faire le mod sans backup `pre-mod16`

### Pièges connus (cf. REPRISE_MEMO §⚠️)
1. Apostrophes typographiques `'` (U+2019) dans toutes les strings JSX
2. Caractère `·` (U+00B7) en UTF-8 direct, `ensure_ascii=False` au dump
3. Escape `</script>` → `<\u002Fscript>` et idem `</style>`
4. Pour le module Site : il est dans le manifest, **pas** dans `__bundler/template`
   (cf. fix runtime Mod 15)

### Si bloqué
- Si le flip 3D rend mal (flicker, anti-aliasing) sur certains navigateurs,
  livrer la version flip et signaler — on regarde ensemble
- Si le hover desktop est trop sensible (flicker quand on bouge la souris
  entre slides), augmenter le `transition-delay` à 80-100ms ou réduire la
  surface hover
- Si `aspect-ratio` 4/3 ne donne pas un bon rendu, essayer 16/10 ou hauteur
  fixe `min-height: 480px`

---

## 7. Protocole de rapport

À la fin :
1. Hash du commit poussé sur `claude/preview-mod16-gallery-slider`
2. Confirmation backup `index.html.pre-mod16` créé
3. Sanity output (bundle taille, manifest entries, sections script présentes)
4. Smoke HTTP : `curl -u preview:a88PtPREkPe9 http://72.61.161.222/preview/ -o /tmp/test.html ; md5sum /tmp/test.html /var/www/dh-preview/index.html` (doivent matcher)
5. Liste des éventuels écarts au brief assumés (et pourquoi)

---

*Brief produit par : Claude (maître d'œuvre) · 26 avril 2026, fin de soirée*
