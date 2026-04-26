# BRIEF — Track B5.2 — Newsletter Studio · patch N8N + archive Ghost (unifié)

> **Owner** : Claude Code (autonome, sur le VPS)
> **Branche cible** : `claude/newsletter-n8n-archive`
> **Estimation** : 1 session
> **Priorité** : 🔴 Bloquant pour clôture B5

---

## 1. Contexte court

Deux livraisons B5 sous-tâche 1 ont été produites en parallèle ce 26 avril :

| Branche | Mockup HTML |
|---|---|
| `claude/newsletter-studio-covers-Emso5` | `round2bis/newsletter-studio-mockup.html` (321 lignes) — porte aussi le pipeline covers complet (sous-tâche 3) |
| `claude/newsletter-studio-mockup-nr0hp` | `docs/marketing-site/newsletter-studio-mockup.html` (364 lignes) — plus complet (logo bicolore brass/bone, 4 conditional MSO, 14 tables) |

**Le maître d'œuvre a tranché** : le mockup HTML retenu comme base finale est celui de **`mockup-nr0hp`** (364 lignes). Il porte le logo bicolore que Sam a demandé et a une meilleure couverture Outlook desktop. L'autre mockup est abandonné — son pipeline covers (sous-tâche 3) reste valable.

**Décision Sam (26 avril)** : les newsletters envoyées chaque lundi sont aussi **archivées comme articles Ghost taggés `archive`**. L'URL d'archive (`https://digital-humans.fr/journal/archive/week-{N}-{YYYY}`) sert à la fois pour :
- Le lien `View on web` de la newsletter elle-même (standard email pour clients qui bloquent les images/HTML)
- Le listing dans la rubrique № 04 Archive du Journal

C'est l'**Option α** (newsletter = article unique taggé `archive` dans Ghost, pas un conteneur regroupant les articles individuels de la semaine).

---

## 2. État actuel du système (vérifié sur VPS par maître d'œuvre)

### Workflow N8N existant
- ID : `qcVVPMTE0LyhNAO2`
- Nom : `Blog - Newsletter Hebdo (Lundi 9h)`
- 12 nodes : Trigger → Init Week → Get Ghost Token → Get Published Posts → Filter This Week → Has Articles? → **Generate Newsletter HTML** ← cible du patch → Get Subscribers → Send Newsletter → Response OK/Skip
- Mode test : `test_mode=true` envoie uniquement à `[email protected]`

### Ghost CMS
- Container Docker `ghost-blog` (port 2368 interne)
- Aucun tag `archive` / `manifesto` / `craft-notes` / `dispatches` n'existe encore
- Intégration **"Digital Humans API"** existe déjà (id `695a5936e3b3d60001bcd395`) — la clé Admin doit être récupérable via le UI Ghost Admin (`https://blog-admin.digital-humans.fr/ghost/`) ou directement en DB

### Mockup retenu
Branche `claude/newsletter-studio-mockup-nr0hp`, fichier `docs/marketing-site/newsletter-studio-mockup.html`, 364 lignes.
Variables placeholders déjà présentes : `{{unsubscribe_url}}`, `{{view_in_browser_url}}`.

---

## 3. Tâches détaillées

### Étape 1 — Préparer la branche (5 min)

```bash
cd /root/workspace/digital-humans-production
git fetch origin
git checkout main
git pull origin main
git checkout -b claude/newsletter-n8n-archive

# Récupérer le mockup retenu depuis sa branche source
git checkout origin/claude/newsletter-studio-mockup-nr0hp -- docs/marketing-site/newsletter-studio-mockup.html
git add docs/marketing-site/newsletter-studio-mockup.html
git -c user.name="Sam (via Claude)" -c user.email="[email protected]" commit -m "chore(b5): cherry-pick newsletter mockup retenu (logo bicolore + 14 tables MSO)

Source : claude/newsletter-studio-mockup-nr0hp commit 8a8d77c
Le mockup mockup-nr0hp est retenu comme base finale (vs covers-Emso5)
pour son logo bicolore Studio brass/bone et sa meilleure couverture
Outlook desktop (4 conditional MSO vs 1)."
```

### Étape 2 — Créer les tags Ghost manquants (10 min)

Via API Ghost Admin OU directement en DB SQLite (la base étant en mode dev local, c'est acceptable).

Tags à créer :
- `archive` (slug `archive`, visibilité publique)
- `manifesto` (slug `manifesto`)
- `craft-notes` (slug `craft-notes`)
- `dispatches` (slug `dispatches`)

Méthode recommandée : via l'API Ghost Admin pour rester propre. Sam fournit la clé Admin (à récupérer dans UI Ghost Admin > Integrations > Digital Humans API > Admin API Key).

```bash
# Variable d'env temporaire (à effacer après)
export GHOST_ADMIN_KEY="ID:SECRET"  # format de l'Admin API Key Ghost

# Génération du JWT pour Ghost Admin API (Python helper inline)
python3 << 'PY'
import os, jwt, datetime
key_id, secret = os.environ["GHOST_ADMIN_KEY"].split(":")
iat = int(datetime.datetime.now().timestamp())
header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
payload = {"iat": iat, "exp": iat + 5*60, "aud": "/admin/"}
token = jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=header)
print(f"export GHOST_JWT={token}")
PY
# Sourcer la variable retournée

# Créer les 4 tags
for tag in archive manifesto craft-notes dispatches; do
  curl -X POST "http://localhost:2368/ghost/api/admin/tags/" \
    -H "Authorization: Ghost $GHOST_JWT" \
    -H "Content-Type: application/json" \
    -d "{\"tags\":[{\"name\":\"$tag\",\"slug\":\"$tag\",\"visibility\":\"public\"}]}" \
    -s | python3 -m json.tool | head -5
done
```

### Étape 3 — Backup workflow N8N existant (5 min)

```bash
mkdir -p /root/workspace/digital-humans-production/n8n/workflows
sqlite3 /root/.n8n/database.sqlite \
  "SELECT json_object('id', id, 'name', name, 'active', active, 'nodes', json(nodes), 'connections', json(connections), 'settings', json(settings), 'staticData', json(staticData)) FROM workflow_entity WHERE id='qcVVPMTE0LyhNAO2';" \
  > /root/workspace/digital-humans-production/n8n/workflows/blog-newsletter-hebdo.before-studio.json

# Vérifier que le backup est lisible
python3 -m json.tool /root/workspace/digital-humans-production/n8n/workflows/blog-newsletter-hebdo.before-studio.json > /dev/null && echo "OK backup parsable"
```

### Étape 4 — Modifier le node `Generate Newsletter HTML` (40-60 min)

**Approche recommandée** : modifier le workflow via l'UI N8N (`http://localhost:5678/`), pas en SQL direct (N8N maintient un cache mémoire qui demanderait un restart sinon).

Le code JS du node doit :

1. Lire les variables d'entrée (articles, week_number, year, hero_deck généré par Sophie)
2. Calculer l'URL d'archive de cette newsletter : `view_in_browser_url = https://digital-humans.fr/journal/archive/week-${week_number}-${year}`
3. Calculer l'URL d'unsubscribe : `unsubscribe_url = https://digital-humans.fr/journal/unsubscribe?email=${email}` (si pas déjà fourni par N8N)
4. Mapper chaque article Ghost vers le format attendu par le template :
   - `rubric` → couleur d'acte : `manifesto`→`#C8A97E` brass, `craft-notes`→`#8E6B8E` mauve, `dispatches`→`#7A9B76` sage, `archive`→`#76716A` bone-4
   - `published_at` → format `APR 22`
   - `read_time` → `${n} MIN READ`
   - `author_name.toUpperCase()`
   - `cover_url` → URL absolue (Ghost `feature_image` est déjà absolu normalement)
5. Tronquer à 3 articles max ; si > 3, ajouter une ligne `+ N more this week →` avant le CTA
6. Composer le HTML via template literal en injectant le mockup `docs/marketing-site/newsletter-studio-mockup.html` avec les valeurs réelles

**Code de référence (à transposer dans le node)** :

```js
// === INPUTS ===
const articles = items[0].json.articles || [];
const week_number = items[0].json.week_number;
const year = items[0].json.year;
const hero_deck = items[0].json.hero_deck || "Field notes from the writers' room.";
const test_mode = items[0].json.test_mode || false;

// === ARCHIVE URL — partagé entre view_in_browser et la rubrique Archive ===
const archive_slug = `week-${week_number}-${year}`;
const view_in_browser_url = `https://digital-humans.fr/journal/archive/${archive_slug}`;

// === MAPPING RUBRIC → COULEUR D'ACTE ===
const RUBRIC_COLOR = {
  'manifesto':   '#C8A97E',  // brass
  'craft-notes': '#8E6B8E',  // architecture mauve
  'dispatches':  '#7A9B76',  // quality sage
  'archive':     '#76716A',  // bone-4
};
const RUBRIC_LABEL = {
  'manifesto':   'MANIFESTO',
  'craft-notes': 'CRAFT NOTES',
  'dispatches':  'DISPATCHES',
  'archive':     'ARCHIVE',
};

// === HELPERS ===
function fmtDate(iso) {
  return new Date(iso)
    .toLocaleDateString('en-US', {month:'short', day:'2-digit'})
    .toUpperCase();
}
function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// === TRUNCATION 3 MAX ===
const renderedArticles = articles.slice(0, 3);
const remaining = Math.max(0, articles.length - 3);

// === BUILD ARTICLE BLOCKS ===
function articleBlock(a) {
  const rubricSlug = (a.tags && a.tags[0] && a.tags[0].slug) || 'craft-notes';
  const rubricColor = RUBRIC_COLOR[rubricSlug] || '#76716A';
  const rubricLabel = RUBRIC_LABEL[rubricSlug] || 'NOTES';
  const author = (a.primary_author && a.primary_author.name) || 'The Studio';
  const coverUrl = a.feature_image || 'https://digital-humans.fr/assets/covers/placeholder.jpg';
  return `
    <tr><td style="padding:0 40px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr><td height="1" style="height:1px;line-height:1px;font-size:1px;background-color:#1F1E1B;">&nbsp;</td></tr>
      </table>
    </td></tr>
    <tr><td style="padding:36px 40px 32px;">
      <a href="${a.url}" style="display:block;text-decoration:none;">
        <img src="${coverUrl}" alt="${escapeHTML(a.title)}" width="520" height="325"
             style="display:block;width:100%;max-width:520px;height:auto;border:0;outline:none;background-color:#141416;">
      </a>
      <p style="margin:24px 0 8px;font-family:'JetBrains Mono',Consolas,monospace;font-size:10px;
                font-weight:500;letter-spacing:1.6px;text-transform:uppercase;color:${rubricColor};">
        ${rubricLabel} &nbsp;·&nbsp; BY ${escapeHTML(author).toUpperCase()}
      </p>
      <p style="margin:0 0 14px;font-family:'JetBrains Mono',Consolas,monospace;font-size:10px;
                font-weight:400;letter-spacing:1.6px;text-transform:uppercase;color:#76716A;">
        ${(a.reading_time || 5)} MIN READ &nbsp;·&nbsp; ${fmtDate(a.published_at)}
      </p>
      <h2 style="margin:0 0 14px;font-family:'Cormorant Garamond',Georgia,serif;font-style:italic;
                 font-weight:500;font-size:24px;line-height:1.15;color:#F5F2EC;">
        <a href="${a.url}" style="color:#F5F2EC;text-decoration:none;">${escapeHTML(a.title)}</a>
      </h2>
      <p style="margin:0 0 18px;font-family:Inter,-apple-system,Arial,sans-serif;font-size:14.5px;
                line-height:1.65;color:#B8B2A6;">
        ${escapeHTML(a.custom_excerpt || a.excerpt || '').slice(0, 280)}
      </p>
      <a href="${a.url}" style="font-family:'JetBrains Mono',Consolas,monospace;font-size:11px;
                                font-weight:500;letter-spacing:1.4px;text-transform:uppercase;
                                color:#C8A97E;text-decoration:none;">
        Read in The Journal →
      </a>
    </td></tr>
  `;
}

const articleBlocksHTML = renderedArticles.map(articleBlock).join('');

// === MORE LINK SI > 3 ARTICLES ===
const moreLink = remaining > 0 ? `
  <tr><td style="padding:0 40px 24px;text-align:center;">
    <a href="${view_in_browser_url}" style="font-family:'JetBrains Mono',Consolas,monospace;
                                            font-size:11px;letter-spacing:1.4px;text-transform:uppercase;
                                            color:#76716A;text-decoration:underline;">
      + ${remaining} more this week in The Journal →
    </a>
  </td></tr>
` : '';

// === TEMPLATE COMPLET ===
// Colle ici l'intégralité du HTML de docs/marketing-site/newsletter-studio-mockup.html
// MAIS remplace :
//  - les 3 blocs articles hardcodés par ${articleBlocksHTML}
//  - {{view_in_browser_url}} par ${view_in_browser_url}
//  - {{unsubscribe_url}} par ${items[0].json.unsubscribe_url}
//  - le numéro de semaine "№ Week 17" par "№ Week ${week_number}"
//  - "2026" par "${year}" si année dynamique
//  - le hero_deck si présent
const TEMPLATE = `<!DOCTYPE html>
<html ...>
... (le mockup intégral, avec interpolations) ...
${articleBlocksHTML}
${moreLink}
... (suite du mockup : CTA, footer) ...
</html>`;

// === RETURN ===
const subject = `№ Week ${week_number} · This week from the studio.`;
return [{
  json: {
    html: TEMPLATE,
    subject,
    archive_slug,           // pour le node Publish to Ghost qui suit
    archive_url: view_in_browser_url,
    archive_excerpt: hero_deck,
    archive_html: TEMPLATE  // même HTML, on archive ce qu'on envoie
  }
}];
```

**À adapter pendant l'implémentation** : le template literal `TEMPLATE` doit être copié-collé depuis `docs/marketing-site/newsletter-studio-mockup.html`, en escapant correctement les backticks éventuels (le mockup ne semble pas en avoir mais à vérifier).

### Étape 5 — Ajouter le node `Publish to Ghost as Archive` (30 min)

**Position dans le workflow** : après `Generate Newsletter HTML`, en parallèle de `Send Newsletter` (les deux peuvent partir simultanément, indépendants).

**Type de node** : `n8n-nodes-base.httpRequest`

**Configuration** :
- URL : `http://localhost:2368/ghost/api/admin/posts/?source=html`
- Method : POST
- Authentication : Header
- Header `Authorization` : `Ghost {{$node["Generate Ghost JWT"].json.token}}`
  → ⚠️ Cela suppose un node préliminaire qui génère le JWT. Si ce node n'existe pas, l'ajouter (Code node Python ou JS qui prend la GHOST_ADMIN_KEY depuis les credentials N8N et calcule le JWT 5min).
- Body :
  ```json
  {
    "posts": [{
      "title": "№ Week {{$json.week_number}} · This week from the studio.",
      "slug": "{{$json.archive_slug}}",
      "html": "{{$json.archive_html}}",
      "custom_excerpt": "{{$json.archive_excerpt}}",
      "tags": [{"slug": "archive"}],
      "status": "published",
      "visibility": "public",
      "feature_image": null
    }]
  }
  ```

**Idempotence** : si le slug `week-17-2026` existe déjà (re-run du workflow le même jour), Ghost retourne 422. Gérer en faisant un GET préalable sur `/ghost/api/admin/posts/slug/{slug}/` ; si 200, faire un PUT (update) au lieu de POST. Sinon POST.

### Étape 6 — Test mode (15 min)

```bash
# Trigger le workflow en test mode
curl -X POST http://localhost:5678/webhook/blog-newsletter-trigger \
  -H "Content-Type: application/json" \
  -d '{"test_mode": true}'
```

Sam reçoit l'email à `[email protected]`. Il valide :
- Logo bicolore lisible
- Articles bien rendus (cover, title, excerpt, métadonnée mono couleur d'acte)
- CTA brass `Open the Journal →` visible
- Footer avec View on web, Brief us, The Journal, Unsubscribe
- Le lien "View on web" pointe vers `https://digital-humans.fr/journal/archive/week-17-2026`

**Vérifications côté Ghost** :
```bash
# Article archive a bien été créé
curl -s "http://localhost:2368/ghost/api/content/posts/slug/week-17-2026/?key=PUBLIC_CONTENT_KEY" | python3 -m json.tool | head -20

# Visible dans la rubrique archive (count posts taggués archive)
curl -s "http://localhost:2368/ghost/api/content/posts/?key=PUBLIC_CONTENT_KEY&filter=tag:archive" | python3 -m json.tool | head -10
```

### Étape 7 — Backup post-modif + commit final (10 min)

```bash
# Re-export du workflow modifié
sqlite3 /root/.n8n/database.sqlite \
  "SELECT json_object('id', id, 'name', name, 'active', active, 'nodes', json(nodes), 'connections', json(connections), 'settings', json(settings), 'staticData', json(staticData)) FROM workflow_entity WHERE id='qcVVPMTE0LyhNAO2';" \
  > /root/workspace/digital-humans-production/n8n/workflows/blog-newsletter-hebdo.studio.json

git add n8n/workflows/blog-newsletter-hebdo.before-studio.json
git add n8n/workflows/blog-newsletter-hebdo.studio.json
git -c user.name="Sam (via Claude)" -c user.email="[email protected]" \
  commit -m "feat(newsletter): patch N8N node Generate Newsletter HTML + Publish to Ghost archive

- Mockup studio (mockup-nr0hp) transposé dans le node Generate Newsletter HTML
- view_in_browser_url = https://digital-humans.fr/journal/archive/week-{N}-{YYYY}
- Nouveau node 'Publish to Ghost as Archive' POST /admin/posts/ après génération HTML
- Article créé avec tag 'archive' (visible dans rubrique № 04 du Journal)
- Idempotence : GET slug puis POST ou PUT
- Backup avant/après dans n8n/workflows/

Test mode validé par Sam (envoi à [email protected])."
git push origin claude/newsletter-n8n-archive
```

---

## 4. Critères de fin (DoD)

- ✅ Mockup `docs/marketing-site/newsletter-studio-mockup.html` cherry-picked depuis `mockup-nr0hp` sur la branche
- ✅ 4 tags Ghost créés : `archive`, `manifesto`, `craft-notes`, `dispatches`
- ✅ Workflow N8N modifié avec nouveau code node `Generate Newsletter HTML` + nouveau node `Publish to Ghost as Archive`
- ✅ Backup avant/après dans `n8n/workflows/`
- ✅ Test mode envoie email à `[email protected]` au format Studio (Sam valide visuellement)
- ✅ Article archive créé dans Ghost, accessible via `https://digital-humans.fr/journal/archive/week-N-YYYY`
- ✅ Idempotence : re-trigger en test mode ne crée pas de doublon, met à jour l'article
- ✅ Branche pushée

---

## 5. Garde-fous

### Ce que tu peux faire
- Modifier le workflow N8N via UI ou via SQL **avec backup avant**
- Créer les tags Ghost via API Admin
- Créer la branche `claude/newsletter-n8n-archive` depuis `main`
- Commit / push sur cette branche

### Ce que tu NE DOIS PAS faire
- ❌ Toucher au mockup HTML lui-même (il est figé après le cherry-pick)
- ❌ Modifier les autres nodes du workflow (`Get Subscribers`, `Send Newsletter`, etc.)
- ❌ Désactiver le workflow ou le mettre off pendant l'édition (préférer dupliquer en `Blog - Newsletter Hebdo (Studio TEST)` si tu veux travailler en isolation)
- ❌ Merger sur main — c'est mon rôle après revue
- ❌ Stocker la GHOST_ADMIN_KEY ou la clé Anthropic en clair dans le repo (utiliser env var ou credentials N8N)

### Si bloqué
- Si la GHOST_ADMIN_KEY n'est pas accessible via UI Ghost, signaler à Sam (il peut la régénérer depuis Ghost Admin > Integrations)
- Si N8N ne charge pas le code modifié après edit (cache), tenter `systemctl restart n8n`
- Si l'API Ghost refuse le POST (validation slug, conflit), documenter et abandonner l'archive Ghost en gardant juste le patch newsletter

---

## 6. Commit conventions

Format `<type>(<scope>): <description>`. Scopes : `newsletter`, `n8n`, `ghost`.

Exemples :
- `chore(b5): cherry-pick newsletter mockup retenu`
- `feat(ghost): create Studio rubric tags (archive/manifesto/craft-notes/dispatches)`
- `feat(newsletter): patch N8N node Generate Newsletter HTML`
- `feat(newsletter): add Publish to Ghost archive node`
- `chore(n8n): backup workflow before/after Studio patch`

---

## 7. Protocole de rapport

À la fin :
1. Liste des commits poussés (hashes courts + messages)
2. Confirmation des 4 tags Ghost créés
3. Résultat du test mode (mail reçu OK / KO + capture éventuelle)
4. URL de l'article archive créé (vérifiable via curl Content API)
5. Idempotence : test re-run = pas de doublon
6. Estimation honnête : "branche prête à merger" / "blockers"

---

*Brief produit par : Claude (maître d'œuvre) · 26 avril 2026, fin de journée*
