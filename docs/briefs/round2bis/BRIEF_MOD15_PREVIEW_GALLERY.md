# BRIEF — Mod 15 — Galerie projets « № 04 · The work » dans le preview Mod 14

> **Owner** : Claude Code (autonome, sur le VPS)
> **Cible** : `/var/www/dh-preview/index.html` (bundle React custom Mod 14)
> **Estimation** : 1 session
> **Priorité** : 🟡 Permet à Sam de juger en contexte les 6 covers Studio générées en B5.3

---

## 1. Contexte court

Le preview Mod 14 (URL `https://digital-humans.fr/preview/`, basic auth `preview:a88PtPREkPe9`) contient la maquette du futur site Studio. État actuel post-Mods 1-14 :

| № | Section | Composant | Fichier source (UUID) |
|---|---|---|---|
| 01 · The case | 4 promesses | `Benefits` | sections.jsx (`6641f2bf-…`) |
| 02 · The sequence | 5 actes du flow | `HowItWorks` | sections.jsx (`6641f2bf-…`) |
| 03 · The ensemble | 11 portraits agents | `OurAgents` | avatars.jsx (`b077057a-…`) |
| **04 · Correspondence** | CTA book a demo | `CTA` | avatars.jsx (`b077057a-…`) |
| (footer) | — | `Footer` | avatars.jsx (`b077057a-…`) |

**Track B5.3 a livré 14 covers Studio** (mergé sur main, tag `v2026.04-covers-studio`). Les 6 covers galerie acte 3 sont dans `assets/covers/` :
- `logifleet.jpg` — fleet management
- `pharma.jpg` — clinical trials
- `telecom.jpg` — claim resolver
- `b2b-distribution.jpg` — pipeline tuner
- `energy.jpg` — grid foresight
- `retail.jpg` — omnichannel loop

**Décision Sam (26 avril, fin de journée)** : ajouter une nouvelle section `№ 04 · The work` au preview pour voir le rendu des covers en série, en contexte. La CTA actuelle (№ 04) devient `№ 05 · Correspondence`.

---

## 2. Objectif Mod 15

### Ajout
Une nouvelle section `OurWork` insérée **entre `OurAgents` (№ 03)** et `CTA`, qui devient la **section 04** du site.

### Renumérotation
La CTA `№ 04 · Correspondence` devient `№ 05 · Correspondence` (FR : `№ 05 · Correspondance`).

### Structure visuelle attendue

D'après le mockup B2 validé sans arbitrage (cf. zip Design du 26 avril matin, fichier `B2 - Gallery Act 3.html`) :

- **Grille 3 × 2** : 3 colonnes × 2 lignes, gap généreux (~32px)
- **6 cards projet**, une par cover
- **Chaque card** :
  - **Cover image** en haut, ratio 16:9 (les covers Gemini sortent en 1376×768, soit 1.79:1, on garde ce ratio)
  - **Méta** sous l'image : industrie + scope (mono small, brass)
  - **Titre projet** : Cormorant italique 22px bone
  - **Punchline** : 1-2 lignes Inter 14px bone-3
- **Hover** : panneau slide-up qui couvre 60-70% de la card (animation `transform: translateY(0)` depuis `translateY(100%)` en 280ms ease-out)
  - Contenu du panneau : industrie (mono uppercase brass) + 2-3 bullets Salesforce scope (clouds utilisés / volumes / résultat clé) + CTA `Read the SDS →` (brass, mono link-style)
  - Pour LogiFleet : lien réel vers `https://digital-humans.fr/sds-preview/146.html`
  - Pour les 5 autres : lien `#` ou `javascript:void(0)` (les SDS ne sont pas encore produits) — on peut afficher un état "Coming soon" en bone-4 à la place du CTA

### Couleurs
Pas de couleur d'agent ici — on est dans une rubrique projets, pas agents. Tous les hover panneaux en `--ink-2` (#141416) avec une **hairline brass top** (1px). Le texte interne suit la palette Studio standard (bone, bone-3, bone-4, brass).

### Données pour les 6 cards

```js
const PROJECTS = [
  {
    id: 'logifleet',
    cover: 'logifleet.jpg',
    industry: { en: 'LOGISTICS · B2B', fr: 'LOGISTIQUE · B2B' },
    title:    { en: 'LogiFleet — Fleet Service Cloud',
                fr: 'LogiFleet — Fleet Service Cloud' },
    punchline:{ en: 'A 320-vehicle fleet brought into Service Cloud in eight days. Drivers, dispatch, maintenance — one canonical record per asset.',
                fr: 'Une flotte de 320 véhicules basculée dans Service Cloud en huit jours. Chauffeurs, dispatch, maintenance — un seul enregistrement canonique par actif.' },
    scope: ['Service Cloud · Field Service · 320 assets', '12 custom objects · 47 flows · 9 LWC', 'Live in production, week 11 · 0 critical bugs'],
    sds_url: 'https://digital-humans.fr/sds-preview/146.html',
  },
  {
    id: 'pharma',
    cover: 'pharma.jpg',
    industry: { en: 'PHARMA · CLINICAL TRIALS', fr: 'PHARMA · ESSAIS CLINIQUES' },
    title:    { en: 'Clinical Trial Watch',
                fr: 'Clinical Trial Watch' },
    punchline:{ en: 'A regulated trial pipeline turned into a single Salesforce dashboard. Sites, enrolments, deviations — every event audit-trailed.',
                fr: "Un pipeline d'essais cliniques régulés transformé en un seul dashboard Salesforce. Sites, recrutements, déviations — chaque événement traçable." },
    scope: ['Health Cloud · Experience Cloud · 21 CFR Part 11', '38 trial sites · 1 200 enrolments tracked', 'Audit-ready logs, end-to-end'],
    sds_url: null, // coming soon
  },
  {
    id: 'telecom',
    cover: 'telecom.jpg',
    industry: { en: 'TELECOM · CLAIMS', fr: 'TÉLÉCOM · RÉCLAMATIONS' },
    title:    { en: 'Claim Resolver',
                fr: 'Claim Resolver' },
    punchline:{ en: '14-day average resolution dropped to 4. Claims triaged by Einstein, dispatched by Sophie, audited by Elena.',
                fr: 'Délai moyen de résolution passé de 14 à 4 jours. Réclamations triées par Einstein, dispatchées par Sophie, auditées par Elena.' },
    scope: ['Service Cloud · Einstein Bots · Omnichannel', '110 000 claims/year · 87% first-touch resolution', '−71% AHT, +12 NPS in two quarters'],
    sds_url: null,
  },
  {
    id: 'b2b-distribution',
    cover: 'b2b-distribution.jpg',
    industry: { en: 'B2B · DISTRIBUTION', fr: 'B2B · DISTRIBUTION' },
    title:    { en: 'Pipeline Tuner',
                fr: 'Pipeline Tuner' },
    punchline:{ en: 'Twelve regional sales pipelines reconciled into one consolidated view. Forecast accuracy up from 68% to 91% in the first quarter.',
                fr: 'Douze pipelines commerciaux régionaux réconciliés en une vue consolidée. Précision du forecast passée de 68% à 91% au premier trimestre.' },
    scope: ['Sales Cloud · CPQ · Tableau CRM', '12 regions · 240 reps · €310M ARR tracked', '+23 forecast accuracy points'],
    sds_url: null,
  },
  {
    id: 'energy',
    cover: 'energy.jpg',
    industry: { en: 'ENERGY · GRID', fr: 'ÉNERGIE · RÉSEAU' },
    title:    { en: 'Grid Foresight',
                fr: 'Grid Foresight' },
    punchline:{ en: 'High-voltage maintenance scheduling moved from spreadsheets to Salesforce. Outage windows down 38%, asset uptime up 6 points.',
                fr: 'Planification de la maintenance haute tension basculée des spreadsheets vers Salesforce. Fenêtres de coupure −38%, disponibilité des actifs +6 points.' },
    scope: ['Field Service · Asset 360 · Net Zero Cloud', '4 800 high-voltage assets monitored', 'Predictive maintenance via Einstein Discovery'],
    sds_url: null,
  },
  {
    id: 'retail',
    cover: 'retail.jpg',
    industry: { en: 'RETAIL · OMNICHANNEL', fr: 'RETAIL · OMNICANAL' },
    title:    { en: 'Omnichannel Loop',
                fr: 'Omnichannel Loop' },
    punchline:{ en: 'Fifty stores, one customer record. Loyalty events, returns, e-commerce orders, in-store visits — stitched into a single graph.',
                fr: 'Cinquante magasins, un seul dossier client. Événements de fidélité, retours, commandes e-commerce, visites en magasin — cousus dans un seul graphe.' },
    scope: ['Commerce Cloud · Marketing Cloud · Loyalty', '50 stores · 1.4M customers unified', '+18% repeat purchase rate'],
    sds_url: null,
  },
];
```

Sam pourra raffiner les copies plus tard — ce qui est important ici c'est la **structure et le rendu visuel**, pas la formulation exacte.

---

## 3. Tâches détaillées

### Étape 1 — Préparer la branche et le backup (5 min)

```bash
cd /root/workspace/digital-humans-production
git fetch origin
git checkout main
git pull origin main
git checkout -b claude/preview-mod15-gallery

# Backup avant Mod 15 (suit la convention pre-modN du REPRISE_MEMO)
cp /var/www/dh-preview/index.html /var/www/dh-preview/index.html.pre-mod15
ls -la /var/www/dh-preview/index.html.pre-mod15
```

### Étape 2 — Décompresser le bundle pour développement (5 min)

Le bundle est un fichier custom décrit dans `/var/www/dh-preview/REPRISE_MEMO.md` (section "Principes techniques"). Il faut :

1. Lire `/var/www/dh-preview/index.html`
2. Parser les 3 sections script :
   - `__bundler/manifest` : JSON `{uuid: {mime, compressed, data: base64}}`
   - `__bundler/ext_resources` : array `[{id, uuid}]`
   - `__bundler/template` : string JSON contenant le HTML complet
3. Décompresser les modules JS : `gzip.decompress(base64.b64decode(data))` quand `compressed: true`
4. Travailler sur les modules en clair, repacker à la fin

UUIDs cibles à modifier :
- `b077057a-5a3a-41a8-8f45-fe3c0011a134` — `avatars.jsx` : ajouter `OurWork` + renuméroter `CTA`
- `__bundler/template` (le HTML englobant) : injecter la balise `<OurWork lang={lang}/>` au bon endroit dans la composition

### Étape 3 — Copier les 6 covers dans le bundle (10 min)

Les covers vivent actuellement dans `assets/covers/` du repo. Pour les inclure dans le bundle :

**Approche recommandée** : ajouter chaque cover comme une entrée du `manifest` avec `compressed: false` (déjà JPEG, pas besoin de regziper).

```python
import base64, json, uuid

for project_id in ['logifleet', 'pharma', 'telecom', 'b2b-distribution', 'energy', 'retail']:
    cover_path = f'assets/covers/{project_id}.jpg'
    cover_data = open(cover_path, 'rb').read()
    cover_b64 = base64.b64encode(cover_data).decode()
    cover_uuid = str(uuid.uuid4())
    manifest[cover_uuid] = {
        "mime": "image/jpeg",
        "compressed": False,
        "data": cover_b64
    }
    # Aussi enregistrer dans ext_resources pour qu'elles soient résolvables
    ext_resources.append({"id": f"cv{project_id.replace('-','_').title()}", "uuid": cover_uuid})
```

Cela suit le même pattern que les avatars agents (cf. mod 12 qui a injecté les 11 photos).

### Étape 4 — Écrire le composant `OurWork` (30 min)

Dans `avatars.jsx` (à décompresser, modifier, recompresser), ajouter avant `function CTA(...)` :

```jsx
const PROJECTS = [/* … cf. data ci-dessus … */];

const COVER = id => {
  const key = 'cv' + id.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
  return R[key] || `../assets/covers/${id}.jpg`;
};

function OurWork({lang}) {
  const t = lang === 'en'
    ? {num: '№ 04 · The work', title: <>Six <em>fields</em>, one rim rule.</>, lede: 'Each engagement is a single Salesforce solution composed by the ensemble. Six are public ; the rest live behind NDAs we are happy to honour.'}
    : {num: '№ 04 · L\u2019atelier', title: <>Six <em>terrains</em>, une règle.</>, lede: 'Chaque mission est une solution Salesforce composée par l\u2019ensemble. Six sont publiques ; les autres vivent derrière des NDA que nous respectons volontiers.'};
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
        <div className="work-grid">
          {PROJECTS.map(p => (
            <article key={p.id} className="work-card">
              <div className="work-cover">
                <img src={COVER(p.id)} alt={p.title[lang]} />
              </div>
              <div className="work-meta">
                <div className="work-industry">{p.industry[lang]}</div>
                <h3 className="work-title">{p.title[lang]}</h3>
                <p className="work-punch">{p.punchline[lang]}</p>
              </div>
              <div className="work-hover">
                <div className="work-hover-industry">{p.industry[lang]}</div>
                <ul className="work-hover-scope">
                  {p.scope.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
                {p.sds_url
                  ? <a href={p.sds_url} className="work-hover-cta" target="_blank" rel="noopener">{lang === 'en' ? 'Read the SDS' : 'Lire le SDS'} <span className="ar">→</span></a>
                  : <span className="work-hover-soon">{lang === 'en' ? 'SDS · coming soon' : 'SDS · bientôt'}</span>}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

// puis CTA renuméroté avec № 05 (cf. étape 5)
```

### Étape 5 — Renuméroter la CTA (5 min)

Dans le même `avatars.jsx`, modifier la fonction `CTA` :

```diff
-    num: '№ 04 · Correspondence',
+    num: '№ 05 · Correspondence',
…
-    num: '№ 04 · Correspondance',
+    num: '№ 05 · Correspondance',
```

### Étape 6 — Ajouter le CSS pour `.work-grid` et `.work-card` (20 min)

Le CSS racine du site est dans la string `__bundler/template` (HTML englobant). Localiser le `<style>` principal et y ajouter :

```css
/* === № 04 · The work — gallery === */
.work-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
  margin-top: 48px;
}
@media (max-width: 900px) {
  .work-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 600px) {
  .work-grid { grid-template-columns: 1fr; }
}
.work-card {
  position: relative;
  background: var(--ink-2);
  border: 1px solid rgba(245, 242, 236, 0.06);
  overflow: hidden;
  transition: border-color 280ms ease;
}
.work-card:hover {
  border-color: var(--brass-3);
}
.work-cover {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: var(--ink);
}
.work-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.work-meta {
  padding: 24px 24px 28px;
}
.work-industry {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brass);
  margin-bottom: 12px;
}
.work-title {
  font-family: 'Cormorant Garamond', Georgia, serif;
  font-style: italic;
  font-size: 22px;
  font-weight: 500;
  line-height: 1.2;
  color: var(--bone);
  margin-bottom: 10px;
}
.work-punch {
  font-family: Inter, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.55;
  color: var(--bone-3);
}
.work-hover {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--ink-2);
  border-top: 1px solid var(--brass);
  padding: 24px;
  transform: translateY(100%);
  transition: transform 280ms ease-out;
  pointer-events: none;
}
.work-card:hover .work-hover {
  transform: translateY(0);
  pointer-events: auto;
}
.work-hover-industry {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brass);
  margin-bottom: 14px;
}
.work-hover-scope {
  list-style: none;
  padding: 0;
  margin: 0 0 18px;
}
.work-hover-scope li {
  font-family: Inter, -apple-system, sans-serif;
  font-size: 13px;
  line-height: 1.55;
  color: var(--bone-3);
  margin-bottom: 6px;
  padding-left: 14px;
  position: relative;
}
.work-hover-scope li::before {
  content: '·';
  position: absolute;
  left: 0;
  color: var(--brass);
}
.work-hover-cta {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--brass);
  text-decoration: none;
}
.work-hover-cta .ar {
  margin-left: 6px;
}
.work-hover-soon {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--bone-4);
}
```

### Étape 7 — Injecter `<OurWork lang={lang}/>` dans le HTML englobant (10 min)

Dans le `__bundler/template` (le HTML qui appelle les composants React via `createRoot.render(...)`), trouver la séquence :
```jsx
<OurAgents lang={lang}/>
<CTA lang={lang}/>
```

et insérer entre les deux :
```jsx
<OurAgents lang={lang}/>
<OurWork lang={lang}/>
<CTA lang={lang}/>
```

S'assurer aussi que le composant `OurWork` est bien exposé sur `window` à la fin de avatars.jsx :
```js
Object.assign(window, {OurAgents, OurWork, CTA, Footer, ENSEMBLE});
```

### Étape 8 — Repacker le bundle et déployer (10 min)

1. Re-gziper avatars.jsx et le re-base64-encoder
2. Reconstruire le manifest avec les 6 nouvelles entrées covers
3. Reconstruire ext_resources avec les 6 nouveaux mappings `cvLogifleet`, `cvPharma`, etc.
4. Re-sérialiser le template (avec **escape critique** `</script>` → `<\u002Fscript>`, cf. piège #3 du REPRISE_MEMO)
5. Réécrire `/var/www/dh-preview/index.html`

⚠️ **Pièges connus** (cf. REPRISE_MEMO sec. ⚠️) :
- Apostrophes ASCII dans les strings JSX → utiliser apostrophe typographique `'` (U+2019)
- `\u00b7` rendu littéralement → utiliser `·` direct (U+00B7) avec `json.dumps(ensure_ascii=False)`
- Escape `</script>` et `</style>` dans le template JSON sérialisé

### Étape 9 — Test visuel + capture (5 min)

```bash
# Vider le cache navigateur n'est pas faisable depuis Claude Code, mais on peut
# vérifier que le HTML modifié parse bien
python3 -c "
import re
src = open('/var/www/dh-preview/index.html').read()
print(f'Size: {len(src)} bytes')
# Sanity : 3 scripts présents
for typ in ['manifest', 'ext_resources', 'template']:
    m = re.search(rf'<script type=\"__bundler/{typ}\"[^>]*>(.*?)</script>', src, re.DOTALL)
    if m: print(f'  {typ}: {len(m.group(1))} chars')
    else: print(f'  {typ}: MISSING')
"

# Test HTTP
curl -sw 'HTTP %{http_code}\n' -o /dev/null -u 'preview:a88PtPREkPe9' \
  https://digital-humans.fr/preview/
```

Sam vérifie visuellement en ouvrant `https://digital-humans.fr/preview/` (basic auth `preview:a88PtPREkPe9`) avec **Ctrl+Shift+R** pour bypass cache.

### Étape 10 — Commit + push (5 min)

```bash
cd /root/workspace/digital-humans-production

# Pas besoin de tracker /var/www/dh-preview/index.html dans le repo (c'est un déploiement local).
# Mais si on a touché à des sources dans le repo (par exemple si avatars.jsx existe en repo),
# les commit. Sinon, juste documenter le mod dans REPRISE_MEMO.md.

# Mettre à jour le mémo
cp /var/www/dh-preview/REPRISE_MEMO.md /tmp/REPRISE_MEMO.md.bak
# Ajouter une section "Mod 15" — voir contenu suggéré ci-dessous

git add docs/refonte/  # si on a mis à jour PARALLEL_TRACKS.md
git -c user.name="Sam (via Claude)" -c user.email="[email protected]" commit -m "feat(preview): Mod 15 — galerie projets № 04 The work avec 6 covers Studio

Ajout d'une nouvelle section OurWork au preview Mod 14 :
- Grille 3×2, 6 projets (logifleet + pharma + telecom + b2b + energy + retail)
- Cards avec cover 16:9 + méta + hover panneau slide-up
- Hover : industrie + 3 bullets scope Salesforce + CTA Read the SDS
- LogiFleet linké au SDS public ; les 5 autres en 'SDS · coming soon'
- CTA renumérotée № 05 · Correspondence

Backup : /var/www/dh-preview/index.html.pre-mod15"
git push origin claude/preview-mod15-gallery
```

---

## 4. Critères de fin (DoD)

- ✅ Section `№ 04 · The work` visible sur le preview entre `№ 03 · The ensemble` et CTA
- ✅ 6 cards projet avec leurs covers réelles
- ✅ Hover panneau slide-up fonctionnel sur chacune
- ✅ LogiFleet linké vers le SDS public
- ✅ Les 5 autres affichent "SDS · coming soon"
- ✅ CTA renumérotée `№ 05 · Correspondence`
- ✅ Bilingue FR/EN OK (le toggle de langue du site les bascule correctement)
- ✅ Responsive : grille 3 colonnes en desktop, 2 colonnes ≤ 900 px, 1 colonne ≤ 600 px
- ✅ Backup `index.html.pre-mod15` en place
- ✅ Section "Mod 15" ajoutée au REPRISE_MEMO.md

---

## 5. Garde-fous

### Ce que tu peux faire
- Modifier `/var/www/dh-preview/index.html` directement (avec backup obligatoire)
- Modifier `avatars.jsx` (UUID `b077057a-…`) pour ajouter `OurWork` et renuméroter `CTA`
- Modifier le `__bundler/template` pour injecter `<OurWork lang={lang}/>`
- Ajouter 6 entrées au `manifest` (covers JPEG) + 6 au `ext_resources`
- Adapter le CSS dans la `<style>` du template
- Adapter les copies projet (titre/punchline/scope) si tu trouves mieux

### Ce que tu NE DOIS PAS faire
- ❌ Toucher au site live `https://digital-humans.fr/` (qui tourne sur `/var/www/digital-humans.fr/`, pas le preview)
- ❌ Modifier les sections déjà validées (`Benefits`, `HowItWorks`, `OurAgents`)
- ❌ Casser le bilinguisme (toute string EN doit avoir son équivalent FR)
- ❌ Charger les covers depuis une URL externe — elles doivent être inlinées dans le bundle (pattern existant)
- ❌ Faire un mod sans backup `pre-mod15`

### Si bloqué
- Si le bundle JSX devient trop complexe à patcher en place, faire les modifs en plusieurs commits incrémentaux (15a, 15b, 15c…)
- Si le CSS hover ne fonctionne pas comme attendu, livrer la version "always shown" en attendant qu'on debug
- Si une cover refuse de charger (taille trop grosse pour le bundle ?), signaler et proposer un downscale via Pillow

---

## 6. Section à ajouter au REPRISE_MEMO

À append à la fin du fichier `/var/www/dh-preview/REPRISE_MEMO.md` :

```markdown
### Session 26 avril (soir) — Mod 15

- **Mod 15** : ajout de la **galerie projets `№ 04 · The work`** entre `OurAgents` et `CTA`.
  - 6 cards projets en grille 3×2 (logifleet, pharma, telecom, b2b-distribution, energy, retail)
  - Covers Studio générées en B5.3 (Gemini 3 Pro Image, palette papier crème + ink + brass)
  - Hover panneau slide-up : industrie + 3 bullets Salesforce scope + CTA Read the SDS
  - LogiFleet linké vers `/sds-preview/146.html` ; les 5 autres en "SDS · coming soon"
  - CTA renumérotée `№ 05 · Correspondence`
  - **Validé par Sam** : [à valider]

### Validation des covers Studio en contexte (objectif Mod 15)

Les 6 covers de B5.3 sortent en palette papier crème + ink + brass (interprétation Gemini de "1920s lithograph"). Le rendu en série dans la galerie sur fond ink #0A0A0B est à juger : effet "œuvres encadrées en galerie sombre" attendu. Si pas satisfaisant après ce Mod, options :
- Régénérer les covers avec un STYLE_TEMPLATE explicitant `dark charcoal background`
- Ou ajuster côté React (filet brass + ombre intérieure pour renforcer l'effet "encadré")
```

---

## 7. Protocole de rapport

À la fin :
1. Hash du commit poussé sur `claude/preview-mod15-gallery`
2. Confirmation du backup `index.html.pre-mod15` créé
3. Tailles des covers injectées (les 6 covers + le bundle final)
4. Liste des éventuels écarts au brief assumés (et pourquoi)
5. Capture conceptuelle ou check HTTP du preview répondant en HTTP 200

---

*Brief produit par : Claude (maître d'œuvre) · 26 avril 2026, fin de soirée*
