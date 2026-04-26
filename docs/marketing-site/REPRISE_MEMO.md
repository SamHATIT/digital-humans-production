# 🗂️ Mémo de reprise — Digital Humans refonte site

**Dernière session : 26 avril 2026 (Mod 15 — galerie projets « № 04 · The work »)**
**Statut : 6 covers Studio en place, à juger en contexte ; reprise après validation Sam**

---

## ✅ Ce qui est fait (sessions 19 + 25 avril)

### Session 19 avril — Mods 1 à 11
- Mods 1-8 : retouches design générales (hero, navigation, sections benefits, etc.)
- Mod 9 : injection photo Sophie + nouveau layout éditorial Act I (solo)
- Mod 10 : layout unifié pour tous les actes (220×275 px, cerclage agent color via box-shadow `--ac`, filter saturate 0.9 contrast 1.03)
- Mod 11 : tentative alignement droit `step-meta-col` Act I — bug visuel non-effectif (la CSS est injectée mais visuellement rien ne change). **Bug abandonné** (Sam : "on saute, on verra plus tard")

### Session 25 avril — Mods 12 à 14
- **Mod 12** : injection batch des **10 photos restantes** (Olivia, Emma, Marcus, Diego, Zara, Raj, Aisha, Elena, Jordan, Lucas) + enrichissement bilingue des rôles avec taglines narratives + ajout `ac:'#hex'` couleur agent sur chaque entrée. 20/20 patches OK. Bug rencontré : apostrophe ASCII dans `L'Interprete` qui cassait la string JS — fixé en utilisant l'apostrophe typographique `'` (cohérent avec le reste du fichier où il y a 367 occurrences typo).
- **Mod 13** : split du rôle en 2 spans stylisés (label métier en mono petit gris, séparateur `·` en brass, punchline en serif italique). Bug rencontré : `\u00b7` rendu littéralement comme texte JSX au lieu d'être interprété — fixé en utilisant le caractère `·` UTF-8 directement avec `json.dumps(ensure_ascii=False)`.
- **Mod 14** : punchline en bloc séparé (sa propre ligne) au lieu d'inline. **Validé par Sam** : "non, c'est bon. merci."

### Session 26 avril (soir) — Mod 15

- **Mod 15** : ajout de la **galerie projets `№ 04 · The work`** entre `OurAgents` et `CTA`.
  - 6 cards projets en grille 3×2 (logifleet, pharma, telecom, b2b-distribution, energy, retail)
  - Covers Studio générées en B5.3 (Gemini 3 Pro Image, palette papier crème + ink + brass)
  - Hover panneau slide-up : industrie + 3 bullets Salesforce scope + CTA Read the SDS (280ms ease-out)
  - LogiFleet linké vers `/sds-preview/146.html` ; les 5 autres en "SDS · coming soon"
  - CTA renumérotée `№ 05 · Correspondence` / `№ 05 · Correspondance`
  - Composant `OurWork` exposé sur `window` à la fin de `avatars.jsx` (Object.assign)
  - Couvertures inlinées dans le bundle via 6 entrées `manifest` (mime image/jpeg, compressed:false) + 6 entrées `ext_resources` (`cvLogifleet`, `cvPharma`, `cvTelecom`, `cvB2bDistribution`, `cvEnergy`, `cvRetail`)
  - Patch script : `docs/marketing-site/scripts/dh-mod15.py`
  - **Validé par Sam** : [à valider]

#### Validation des covers Studio en contexte (objectif Mod 15)

Les 6 covers de B5.3 sortent en palette papier crème + ink + brass (interprétation Gemini de "1920s lithograph"). Le rendu en série dans la galerie sur fond ink #0A0A0B est à juger : effet "œuvres encadrées en galerie sombre" attendu. Si pas satisfaisant après ce Mod, options :
- Régénérer les covers avec un STYLE_TEMPLATE explicitant `dark charcoal background`
- Ou ajuster côté React (filet brass + ombre intérieure pour renforcer l'effet "encadré")

### Layout actuel des cartes agents (post Mod 14)

```
[ photo 220×275 cerclée couleur agent ]

Agent Name              ← serif 18px bone
APEX DEVELOPER          ← mono 9.5px gris bone-4 0.16em (label métier)
The Pianist             ← serif italique 16.5px bone (signature, sa propre ligne)

Diego writes Apex code… ← hero-line serif italique 13.5px (description)
```

### Mapping complet photo ↔ agent ↔ accent

| Photo | Agent | Accent hex | Rôle EN | Rôle FR |
|---|---|---|---|---|
| `7_15PM` | Sophie Chen | `#8B5CF6` violet | Project Manager · Orchestrator | Chef de projet · Chef d'orchestre |
| `8_25PM` | Olivia Parker | `#3B82F6` bleu | Business Analyst · The Interpreter | Business Analyst · L'Interprete |
| `8_28PM` | Emma Rodriguez | `#06B6D4` cyan | Research Analyst · The Verifier | Research Analyst · La Verificatrice |
| `8_36PM` | Marcus Johnson | `#F97316` orange | Solution Architect · The Builder of Shapes | Architecte Solution · Le Batisseur |
| `8_37PM` | Diego Martinez | `#EF4444` rouge | Apex Developer · The Pianist | Développeur Apex · Le Pianiste |
| `8_41PM` | Zara Thompson | `#22C55E` emerald | LWC Developer · The Painter | Développeuse LWC · La Peintre |
| `8_42PM` | Raj Patel | `#EAB308` amber | Administrator · The No-Code Wizard | Administrateur · Le Magicien No-Code |
| `8_44PM` | Aisha Okonkwo | `#92400E` sienna | Data Specialist · The Curator | Spécialiste Data · La Curatrice |
| `8_44PM_1` | Elena Vasquez | `#6B7280` slate | QA Engineer · The Guardian | Ingénieure QA · La Gardienne |
| `8_45PM` | Jordan Blake | `#1E40AF` indigo | DevOps Engineer · The Stagehand | Ingénieur DevOps · Le Régisseur |
| `8_46PM` | Lucas Fernandez | `#D946EF` magenta | Trainer · The Transmitter | Formateur · Le Transmetteur |
| `8_47PM` | LogiFleet card | — | (carte projet, pour la Galerie) | — |

---

## 🗂️ État de la maquette

**URL** : http://72.61.161.222/preview/
**Auth** : `preview` · `a88PtPREkPe9`
**Fichier** : `/var/www/dh-preview/index.html` (bundle React autonome, ~14.5 MB)

### Backups incrémentaux (rollback en 1 commande)

```bash
# Liste les backups disponibles :
ls -la /var/www/dh-preview/index.html.pre-mod*

# Rollback à un backup donné :
cp /var/www/dh-preview/index.html.pre-modN /var/www/dh-preview/index.html
```

État actuel = post-mod15. Backups disponibles : `pre-mod1` à `pre-mod15` (le backup `pre-mod15` est créé par l'opérateur juste avant `python3 docs/marketing-site/scripts/dh-mod15.py`).

---

## 🧠 Principes techniques du bundle (à rappeler)

- **Format custom** : 3 sections `<script type="...">` à parser et reconstruire :
  - `__bundler/manifest` — JSON des ressources `{uuid: {mime, compressed, data: base64}}` (41 entries actuellement)
  - `__bundler/ext_resources` — array `[{id: 'avXxx', uuid: '...'}]` mapping name → uuid (11 entries pour les avatars)
  - `__bundler/template` — string JSON contenant le HTML complet de la page (avec CSS inline, JSX modules)
- **Modules clés (UUIDs stables)** :
  - `6641f2bf-70da-46eb-a716-a60b6030f1c7` — `sections.jsx` (Benefits + HowItWorks avec les 5 actes)
  - `b077057a-5a3a-41a8-8f45-fe3c0011a134` — `avatars.jsx` (OurAgents, CTA, Footer)
  - `6633b62e-97d2-4947-9f72-56d63e72e82a` — `main.js` (bundle principal 1080K)
  - `ca8d9519-...` à `f66dd697-...` — UUIDs avatars (cf. ext_resources)
- **Compression modules JS** : gzip + base64, champ `"compressed": true`
- **Images** : `"compressed": false` avec base64 direct (JPEG ~600KB-1.3MB chacune)
- **CSS théming** : variables `--ink`, `--bone`, `--bone-2`, `--bone-3`, `--bone-4`, `--brass`, `--brass-3`, `--indigo`, `--plum`, `--terra`, `--sage`, `--slate`, `--ochre` dans `:root`
- **Variable `--ac`** : agent color, appliquée via `style={{'--ac': a.ac || 'var(--brass)'}}` sur la `.agent-card`. Utilisée uniquement par `.hero-photo::after` (cerclage 3px). Aucun autre élément ne porte la couleur agent.

### ⚠️ Pièges rencontrés

1. **Apostrophes ASCII dans les strings JSX** — `role:'L'Interprete'` casse la string JS. Toujours utiliser l'apostrophe typographique `'` (U+2019) dans les rôles FR.
2. **Escapement \u00b7 dans le contenu JSX** — `<span>\u00b7</span>` est rendu littéralement comme texte. Soit utiliser le caractère réel `·` (U+00B7) directement, soit l'évaluer en expression `<span>{'\u00b7'}</span>`. Pour conserver le caractère UTF-8 au passage par `json.dumps`, mettre `ensure_ascii=False`.
3. **Escape critique `</script>` et `</style>`** dans le template JSON sérialisé — sinon le parser HTML termine le script `<script type="__bundler/template">` prématurément. Toujours faire :
   ```python
   new_template_body = json.dumps(template_html, ensure_ascii=False)
   new_template_body = new_template_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")
   ```
   Le JSON parser runtime décodera `\u002F` en `/`.
4. **Cache navigateur** — toujours recharger en `Ctrl+Shift+R` après modif, sinon on voit l'ancienne version.

---

## 📋 Prochaines étapes (par ordre probable)

1. **Validation visuelle Mod 15** — Sam juge le rendu des 6 covers en série en contexte galerie. Itérer sur palette/encadré si besoin
2. **Produire 5 SDS manquants** (pharma, telecom, b2b-distribution, energy, retail) pour passer les 5 cards "SDS · coming soon" en liens réels
3. **Debug Mod 11** (alignement droit Sophie) — basse priorité, à reprendre quand on aura un pic de motivation pour DevTools
4. **Traitement "dossier CIA"** des slides — N&B + photo grand format + cercle couleur autour + nom + tagline en légende (à préciser en séance — variante stylistique de la section actuelle ?)
5. **Section prix** — 4 tiers (Free / Pro 49€ / Team 1490€ / Enterprise)
6. **Overlay urgence d'entrée** — 5-7s, skip, localStorage une fois par session
7. **Manifesto + FAQ** adaptés ton studio
8. **Passerelle "entrer dans le studio"** vers la plateforme (`/login` → dashboard React)

---

## 💡 Décisions actées (mémoire longue)

- Couleur d'agent via **cerclage CSS** uniquement (pas rim light dans la photo, pas dans le chrome du step)
- **Couleur d'acte retirée** du chrome — multi-agent = bordel de couleurs sinon
- Photos toutes à la **même taille 220×275** (4:5), staggered possible avec `nth-child(2)` margin-top 38px
- **Rôles bilingues** avec séparateur `·` (typo du site) — la punchline narrative ("The Pianist", "Le Bâtisseur"...) suit le label métier
- **Punchline sur sa propre ligne** (Mod 14) — donne du poids à la signature sans tomber dans l'arc-en-ciel
- **Filtre photo subtil** : `filter: saturate(0.9) contrast(1.03)` — pas de B&W pour l'instant (reservé au "dossier CIA" plus tard)
- **Style hero du SDS** validé comme référence visuelle pour le reste de l'app (cf. https://digital-humans.fr/sds-preview/146.html)

---

## 📍 Fichiers de référence dans le projet Claude

- `DH_brief_consolide.docx` — base stratégique, 7 parties (décisions design)
- `DH_direction_photo.docx` — 11 prompts de génération + cartes projets, mapping agents/accents
- `Generated_Image_April_19_2026_*.jpg` — 12 photos sources (présentes aussi sur VPS dans `/tmp/agents-photos/`)
- `SDS_LogiFleet_146_Studio.html` / `.pdf` — exemple SDS pour gabarit "Our work" (galerie projets)

## 📞 Accès VPS rapide

```bash
ssh root@72.61.161.222         # ou via MCP "Digital Human VPS"
cd /var/www/dh-preview
ls -la index.html*             # voir les backups
cd /tmp/agents-photos          # photos source des agents
```

---

— fin du mémo, version 25 avril 2026 (post Mods 12-14) —
