# B5 — Newsletter Studio · Synthèse de design

**Branche** : `claude/newsletter-studio-covers-Emso5`
**Livrable associé** : `round2bis/newsletter-studio-mockup.html`
**Statut** : 🟦 design produit, en attente validation Sam

---

## 1. Décisions Q1 → Q5

### Q1 — Combien d'articles par newsletter ?

**Recommandation : 1 à 3 articles, séparés par hairlines brass.**

- Le node N8N filtre déjà les articles publiés sur la semaine. La cadence éditoriale Studio
  vise **1 article/semaine** mais la réalité — vacances, doublons, dispatches LogiFleet —
  produit ponctuellement 0, 2 ou 3 publications.
- Le mockup gère les 3 cas en gardant le même rythme visuel :
  - `0 article` → la newsletter ne part pas (court-circuit `Has Articles?` du workflow,
    aucune adaptation nécessaire). Le mockup ne traite donc pas ce cas.
  - `1 article` → le bloc unique respire entre la hairline du hero et celle du colophon,
    plus éditorial.
  - `2-3 articles` → séparés par une hairline `rgba(200,169,126,0.18)` (brass à 18 %),
    légèrement plus chaude que la hairline neutre de structure
    `rgba(245,242,236,0.08)`. C'est la signature.
- **Cap dur à 3** : au-delà, le node N8N tronque et insère une mention
  *"+ N more in The Journal →"* (geste éditorial assumé, pas une case "voir tout").

### Q2 — Logo / wordmark

**Recommandation : reprendre le wordmark `Digital·Humans` du site preview Mod 14 — pas de mark séparé.**

- La newsletter est un dispatch éditorial, pas une carte de visite. Le wordmark seul,
  posé en Cormorant Garamond italique 22 px sur le ras gauche, suffit à signer.
- Pas d'image PNG/SVG dans le header : tous les clients mail ne chargent pas les images
  par défaut (Gmail désactive jusqu'à validation expéditeur). Le wordmark texte est
  toujours visible.
- Le `·` est le **middle dot Unicode `U+00B7`** (`&middot;` en HTML), **pas** un point centré
  custom. Cohérent avec le site (Mod 13 a déjà adopté le caractère natif).
- Si plus tard Sam veut un mark : prévoir un `<img>` mono-couleur bone (≤ 32×32) en option,
  mais pas maintenant.

### Q3 — Mode clair / mode sombre

**Recommandation : dark uniquement au lancement.**

- La charte Studio est dark-first (ink `#0A0A0B` partout). La news doit s'aligner.
- `<meta name="color-scheme" content="dark">` + `<meta name="supported-color-schemes" content="dark">`
  signalent aux clients qui supportent (Apple Mail, Outlook web récent) qu'on assume le dark.
- **Risque connu** : Gmail web, en thème clair par défaut côté utilisateur, peut
  contraster mal. Mitigation : pas de `prefers-color-scheme` dynamique (filtré par Gmail
  de toute façon), mais on garde le contraste élevé bone `#F5F2EC` sur ink `#0A0A0B`
  (ratio 17.4:1, AAA confortable).
- Mode clair envisagé en V2 si retours utilisateurs. Pas avant.

### Q4 — Couleur de la rubrique dans la métadonnée

**Recommandation : brass `#C8A97E` uniformément sur la ligne `RUBRIC · BY AUTHOR`. Couleur d'agent réservée au site.**

- Trois options testées (cf. mockup) :
  - **Couleur d'agent** (violet Sophie, orange Marcus, etc.) → trop coloré, casse
    l'austérité de la charte newsletter. Bonne idée pour le site (Mod 14) où l'agent
    est vu en grand cerclé de sa couleur, mauvaise idée ici où c'est juste une ligne.
  - **Brass** → noble, cohérent, sépare clairement la métadonnée de la copy bone.
    **Choix retenu.**
  - **bone-4** (`#76716A`) → trop fade. Le brass apporte la chaleur sans bruit.
- Conséquence : le brass est porté par 4 éléments dans la newsletter (eyebrow week,
  rubric/author, CTA "Read in The Journal →", hairlines de séparation entre articles).
  Cohérent et économe.
- La métadonnée secondaire (`4 MIN READ · APR 21`) reste en bone-4 — elle est annexe.

### Q5 — CTA de fin

**Recommandation : un seul CTA principal `Read all in The Journal →`, suivi d'un footer utilitaire bone-4 trois liens : `Brief us · The Journal · View on web` puis `Unsubscribe · Preferences`.**

- Le CTA principal est **après le colophon**, en brass mono — c'est l'invitation
  éditoriale, pas une boîte verte qui crie "CLIQUEZ".
- Le footer utilitaire est **discret en bone-4** — il existe pour la conformité
  (RGPD impose un lien désabo) et pour les routines (préférences, vue web). Il n'a pas
  à concurrencer visuellement le CTA principal.
- L'adresse postale (`Digital·Humans · Paris · digital-humans.fr`) en bone-5
  (`#56524C`) clôt le mail, encore plus discrète. À enrichir avec mention SIREN si Sam
  veut.

---

## 2. Anatomie finale validée

```
40px ── header  : wordmark gauche · "№ Week NN · YYYY" droite (brass mono)
24px
──── hairline neutre ────
48px ── hero    : eyebrow mono bone-4 · h1 Cormorant 36px ital · deck Cormorant 18px ital bone-3
40px
──── hairline neutre ────
40px ── article : cover 16:10 · meta brass · meta bone-4 · h2 28px ital · body Inter 15 · CTA brass
40px
──── hairline brass ────
   (répété pour articles 2 et 3 si présents)
──── hairline brass ────
40px ── colophon : eyebrow · pitch Cormorant ital · CTA "Read all in The Journal →"
40px
──── hairline neutre ────
24px ── footer  : 3 liens utilitaires · 2 liens conformité · adresse postale (tous bone-4/5 mono)
48px
```

Largeur totale : **600 px**. Padding latéral : **48 px** (laisse 504 px de zone live, ratio 16:10 propre pour les covers).

### Palette appliquée (rappel rapide)

| Token | Hex | Usage |
|---|---|---|
| `--ink` | `#0A0A0B` | Background principal |
| `--ink-2` | `#141416` | Réservé pour les blocs en relief — non utilisé dans la news (qui reste plate) |
| `--bone` | `#F5F2EC` | Texte principal (titres, body) |
| `--bone-3` | `#B8B2A6` | Texte secondaire (excerpts, deck) |
| `--bone-4` | `#76716A` | Méta (read time, footer) |
| `--bone-5` | `#56524C` | Adresse postale, copyright |
| `--brass` | `#C8A97E` | Eyebrow, rubric, CTA principal, hairlines de séparation entre articles |
| Hairline neutre | `rgba(245,242,236,0.08)` | Structure (header → hero → articles → colophon → footer) |
| Hairline brass | `rgba(200,169,126,0.18)` | Séparation entre articles |

---

## 3. Spec d'implémentation pour le node N8N `Generate Newsletter HTML`

Le mockup `round2bis/newsletter-studio-mockup.html` est **directement adaptable** en JS
template literal. Voici la structure attendue dans le node après patch :

### Données d'entrée (déjà fournies par les nodes en amont)

`items[0].json` contient :
- `week_label` (string) → ex. `"Semaine 17 · 2026"` — actuellement utilisé par l'ancien node, **garder**
- `week_number` (int) → à dériver de `week_label` ou ré-injecter par `Init Week`
- `year` (int) → idem
- `total_articles` (int)
- `test_mode` (bool)
- `posts[]` (array Ghost) avec :
  - `title`, `slug`, `custom_excerpt`, `excerpt`, `published_at`, `feature_image`, `reading_time`
  - `tags[]` (l'agent est dans un tag dont `name` matche un agent connu)
  - `authors[]` (rarement renseigné côté Ghost, on s'appuie sur le tag agent)

### Mapping post Ghost → variable mockup

```js
const RUBRIC_BY_AGENT = {
  'Sophie Chen':     'Dispatches',
  'Olivia Parker':   'Field Notes',
  'Emma Rodriguez':  'Archive',
  'Marcus Johnson':  'Manifesto',
  'Diego Martinez':  'Craft Notes',
  'Zara Thompson':   'Craft Notes',
  'Raj Patel':       'Field Notes',
  'Aisha Okonkwo':   'Archive',
  'Elena Vasquez':   'Craft Notes',
  'Jordan Blake':    'Field Notes',
  'Lucas Fernandez': 'Manifesto',
};

function articleVars(post) {
  const agentTag = (post.tags || []).find(t => RUBRIC_BY_AGENT[t.name]);
  const author   = agentTag?.name || 'Digital·Humans';
  const rubric   = (RUBRIC_BY_AGENT[author] || 'Field Notes').toUpperCase();
  const date     = new Date(post.published_at);
  const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }).toUpperCase();
  const readTime = `${post.reading_time || 4} MIN READ`;
  const cover    = post.feature_image || `https://digital-humans.fr/assets/covers/default-${(agentTag?.slug || 'studio')}.jpg`;
  const title    = post.title.replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const excerpt  = ((post.custom_excerpt || post.excerpt || '').substring(0, 220)).replace(/\s+\S*$/, '…');
  const url      = `https://digital-humans.fr/journal/${post.slug}`;
  return { rubric, author: author.toUpperCase(), readTime, monthDay, cover, title, excerpt, url };
}
```

### Construction du HTML

Repartir intégralement du mockup HTML — copier-coller, et remplacer les blocs en dur par
des interpolations. **Trois zones variables** :

1. **Header** : `№ Week ${weekNumber} · ${year}`
2. **Hero** : `eyebrow` (ex. `Field notes · ${dateRangeLabel}`) — calculé depuis
   `Init Week`. `hero_title` reste fixe `"This week<br>from the studio."`. `hero_deck` est
   généré côté workflow par un appel LLM (Sophie en mode résumé, 1-2 phrases) — **à
   ajouter en V2**, pour l'instant garder un `deck` statique avec mention du nombre
   d'articles : `"${total_articles} ${total_articles>1 ? 'field notes' : 'field note'} from the writers' room. Read at your pace."`
3. **Articles** : boucle sur `posts.slice(0, 3)`. Pour chaque article, injecter le bloc
   complet (cover + meta + title + excerpt + CTA), entrecoupé de hairlines brass.

Si `posts.length > 3` :
```js
const overflow = posts.length - 3;
articlesHtml += `
  <tr>
    <td style="padding:32px 48px 40px 48px;text-align:center;">
      <p style="margin:0;font-family:'JetBrains Mono',Menlo,Monaco,monospace;font-size:11px;font-weight:500;letter-spacing:0.16em;text-transform:uppercase;">
        <a href="https://digital-humans.fr/journal" style="color:#C8A97E;text-decoration:none;border-bottom:1px solid rgba(200,169,126,0.3);padding-bottom:2px;">+ ${overflow} more in The Journal →</a>
      </p>
    </td>
  </tr>`;
```

### Test mode

Le banner test reste utile mais doit être restylé Studio. Remplacer l'ancien jaune Tailwind
`#FEF3C7 / #92400E` par :

```html
<tr>
  <td style="padding:14px 48px;background-color:#1A1612;border-bottom:1px solid rgba(200,169,126,0.18);">
    <p style="margin:0;font-family:'JetBrains Mono',Menlo,Monaco,monospace;font-size:10px;font-weight:500;letter-spacing:0.18em;text-transform:uppercase;color:#C8A97E;text-align:center;">
      Test mode · Sent only to shatit@gmail.com
    </p>
  </td>
</tr>
```

### Subject line

Garder un format mono-style :
```js
const subject = `№ Week ${weekNumber} · ${posts.length === 1 ? posts[0].title : 'This week from the studio'}`;
```

### Variables Mustache à ne PAS interpoler côté JS

- `{{unsubscribe_url}}` reste tel quel dans le HTML : N8N l'interpole avant l'envoi via
  `Send Newsletter`. Vérifier que le node `emailSend` fait bien la substitution (test
  mode permet de valider).

---

## 4. Compatibilité clients mail

| Client | Statut attendu | Notes |
|---|---|---|
| Gmail web (desktop) | ✅ | Cible n°1. Tables, fonts Google, hairlines OK. |
| Gmail mobile (iOS/Android) | ✅ | Idem. Cover image responsive (`width:100%;max-width:504px`). |
| Apple Mail (macOS, iOS) | ✅ | Support `color-scheme` dark, fonts Google chargées. |
| Outlook web (Office 365) | ✅ | Tables OK, peut bloquer Google Fonts → fallback Georgia/Menlo prend le relais, lisible. |
| Outlook desktop Windows (Word engine) | ⚠️ acceptable | Fonts Google bloquées, fallback Georgia OK. Rendering parfois légèrement décalé sur les hairlines. **À tester avant prod.** |
| Outlook.com | ✅ | Alignement avec Outlook web. |
| Yahoo Mail | ✅ | Comme Gmail. |
| ProtonMail | ✅ | Bloque les fonts externes par défaut → fallback. Tables OK. |

**Tests à exécuter par Sam avant validation prod** :
1. Ouvrir le mockup local dans Chrome / Safari → check rendu desktop.
2. Lancer le test mode N8N (Sous-tâche 2) → recevoir l'email sur `shatit@gmail.com`.
3. Ouvrir l'email reçu dans :
   - Gmail web (Chrome)
   - Apple Mail iPhone
   - **Si possible** : Outlook desktop (le rendering Word casse parfois les
     `border-collapse` — un check rapide rassure).

---

## 5. Hand-off vers la sous-tâche 2 (patch N8N)

Une fois ce mockup validé par Sam, Claude Code :

1. Backup le node actuel (export workflow JSON depuis SQLite).
2. Réécrit le code JS de `Generate Newsletter HTML` en suivant la spec ci-dessus.
3. Lance le test mode et envoie à `shatit@gmail.com`.
4. Itère si besoin (typiquement : ajustements de padding pour tablettes ou bug d'image
   non chargée par défaut Gmail).
5. Commit le workflow modifié dans `n8n/workflows/blog-newsletter.studio.json`.

**Workflow live inchangé tant que Sam n'a pas dit go.**

---

*Synthèse produite par Claude Code · 26 avril 2026*
