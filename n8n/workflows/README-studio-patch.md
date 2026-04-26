# Track B5.2 — Newsletter Studio patch (N8N + Ghost archive)

This directory contains the artifacts for the Studio newsletter patch. Two
classes of work live here: **(A) sandbox-completed** changes that are
already in the repo, and **(B) VPS-only** steps that must be replayed on
the production VPS because they touch live infra.

---

## A. What is already in this branch

| Path | Purpose |
|---|---|
| `docs/marketing-site/newsletter-studio-mockup.html` | Cherry-pick from `claude/newsletter-studio-mockup-nr0hp` (commit `8a8d77c`). 364 lines, 4 MSO conditionals, brass/bone logo. **Frozen** — reference only. |
| `n8n/workflows/blog-newsletter-hebdo.before-studio.json` | Snapshot of the workflow `Blog - Newsletter Hebdo (Lundi 9h)` *before* the Studio patch. |
| `n8n/workflows/blog-newsletter-hebdo.studio.json` | Same workflow *after* the Studio patch (gen_html replaced + 5 new nodes for Ghost archive). |
| `n8n/workflows/blog-newsletter.json` | Canonical mirror of `…studio.json` — this is the file that should be re-imported into N8N. |
| `n8n/workflows/nodes/generate_newsletter_html.studio.js` | Source of the new Code node `Generate Newsletter HTML`. Reviewable in plain JS. |
| `n8n/workflows/nodes/generate_ghost_jwt.studio.js` | Source of the new Code node `Generate Ghost JWT`. Pure Node `crypto`, no extra deps. |
| `n8n/workflows/scripts/build_studio_patch.py` | Idempotent builder. Reads the `.before-studio.json` + the `.js` sources, emits `…studio.json` + `blog-newsletter.json`. Re-run after editing any node JS. |
| `n8n/workflows/scripts/smoke_test_gen_html.js` | Node smoke test for the gen_html JS. Mocks `items` + `$()` and asserts 20 invariants on the rendered HTML. |

**Smoke test status (run from the repo root):**

```bash
node n8n/workflows/scripts/smoke_test_gen_html.js
# → 20 passed · 0 failed
```

---

## B. VPS replay procedure

The sandbox where the patch was prepared has no Ghost container, no live
N8N, and no SMTP — so the steps below must be done on the VPS by hand or
in a follow-up VPS session. Each block is copy-pasteable.

### B.1  Ghost — create the four Studio tags

These tags do not exist yet on the Ghost instance. Run once.

```bash
# Get the Admin API Key from Ghost UI
#   https://blog-admin.digital-humans.fr/ghost/#/settings/integrations
#   → Digital Humans API → Admin API Key  (format "id:secret")
export GHOST_ADMIN_KEY="ID:SECRET"

# Mint a 5-min JWT
export GHOST_JWT=$(python3 - <<'PY'
import os, hmac, hashlib, json, base64, time
key_id, secret_hex = os.environ["GHOST_ADMIN_KEY"].split(":")
def b64(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
header  = b64(json.dumps({"alg":"HS256","typ":"JWT","kid":key_id}).encode())
payload = b64(json.dumps({"iat":int(time.time()),"exp":int(time.time())+300,"aud":"/admin/"}).encode())
sig     = b64(hmac.new(bytes.fromhex(secret_hex), f"{header}.{payload}".encode(), hashlib.sha256).digest())
print(f"{header}.{payload}.{sig}")
PY
)

for tag in archive manifesto craft-notes dispatches; do
  curl -sS -X POST "https://blog-admin.digital-humans.fr/ghost/api/admin/tags/" \
    -H "Authorization: Ghost $GHOST_JWT" \
    -H "Content-Type: application/json" \
    -d "{\"tags\":[{\"name\":\"$tag\",\"slug\":\"$tag\",\"visibility\":\"public\"}]}" \
  | python3 -c "import sys,json; t=json.load(sys.stdin)['tags'][0]; print(f\"OK {t['slug']}  id={t['id']}\")"
done
```

If a tag already exists, Ghost returns `422` — that's fine, treat it as a
no-op and move on.

### B.2  Backup the live N8N workflow (before)

```bash
cd /root/workspace/digital-humans-production
mkdir -p n8n/workflows
sqlite3 /root/.n8n/database.sqlite \
  "SELECT json_object('id', id, 'name', name, 'active', active,
          'nodes', json(nodes), 'connections', json(connections),
          'settings', json(settings), 'staticData', json(staticData))
   FROM workflow_entity WHERE id='qcVVPMTE0LyhNAO2';" \
  > /tmp/blog-newsletter-hebdo.live-before.json

# Sanity-check it parses
python3 -m json.tool /tmp/blog-newsletter-hebdo.live-before.json > /dev/null \
  && echo "OK live snapshot parsable"

# Diff against the repo "before" — should match (or be very close)
diff <(python3 -m json.tool /tmp/blog-newsletter-hebdo.live-before.json) \
     <(python3 -m json.tool n8n/workflows/blog-newsletter-hebdo.before-studio.json) | head -40
```

If the live workflow has drifted from the repo `…before-studio.json`, **stop
and reconcile** before importing the patch — N8N's UI is the source of
truth, and we don't want to silently overwrite manual edits.

### B.3  Set the GHOST_ADMIN_KEY env var for N8N

The new `Generate Ghost JWT` Code node reads `process.env.GHOST_ADMIN_KEY`.
Add it to N8N's environment:

```bash
sudo systemctl edit n8n
# In the override file, add under [Service]:
#   Environment="GHOST_ADMIN_KEY=ID:SECRET"

sudo systemctl daemon-reload
sudo systemctl restart n8n
```

(Alternative: create an N8N "Env Variable" credential and reference it in
the Code node, but the systemd env is simpler and matches how the existing
`Get Ghost Token` helper at `127.0.0.1:8765` is wired.)

### B.4  Import the patched workflow into N8N

Two options:

**Option 1 — UI (recommended).**  
Open `http://localhost:5678/workflow/qcVVPMTE0LyhNAO2`, click `…` → **Import
from File** → select
`/root/workspace/digital-humans-production/n8n/workflows/blog-newsletter.json`.
N8N will show a diff; accept the overwrite. **Verify in the UI:**

- The `Generate Newsletter HTML` Code node has the new JS (≈340 lines, references `archive_slug`, `RUBRIC`, `articleBlock`).
- The `Send Newsletter` node's `html` parameter now contains a `.replace('__UNSUBSCRIBE_URL__', …)` expression.
- Five new nodes exist below the email branch: **Generate Ghost JWT** → **Lookup Archive Slug** → **Archive Exists?** → {**Update Archive** | **Create Archive**}.
- `Generate Newsletter HTML` fans out to *both* `Get Subscribers` *and* `Generate Ghost JWT`.
- The workflow is still **active** after import.

**Option 2 — direct SQL.**  
Only if the UI import is unavailable. Note: N8N caches the workflow in
memory; restart the service after a SQL update.

```bash
sudo systemctl stop n8n
python3 - <<'PY'
import json, sqlite3
wf = json.load(open('/root/workspace/digital-humans-production/n8n/workflows/blog-newsletter.json'))
db = sqlite3.connect('/root/.n8n/database.sqlite')
db.execute(
  "UPDATE workflow_entity SET nodes=?, connections=?, settings=? WHERE id=?",
  (json.dumps(wf['nodes']), json.dumps(wf['connections']),
   json.dumps(wf['settings']), 'qcVVPMTE0LyhNAO2')
)
db.commit(); db.close()
print('OK SQL update applied')
PY
sudo systemctl start n8n
```

### B.5  Test mode — full E2E

```bash
curl -sS -X POST http://localhost:5678/webhook/send-newsletter \
  -H 'Content-Type: application/json' \
  -d '{"test_mode": true}' | python3 -m json.tool
```

Expected:
- HTTP 200 with `{ "success": true, "articles": N, "recipients": 1, "test_mode": true }`
- `[email protected]` receives the Studio-format newsletter
- A new Ghost post appears at `https://digital-humans.fr/journal/archive/week-{N}-{YYYY}`, tagged `archive`, status `published`

**Idempotence check** — re-trigger immediately:

```bash
curl -sS -X POST http://localhost:5678/webhook/send-newsletter \
  -H 'Content-Type: application/json' \
  -d '{"test_mode": true}' | python3 -m json.tool

# Verify only ONE archive post for this slug
curl -sS "https://blog-admin.digital-humans.fr/ghost/api/admin/posts/?filter=slug:week-{N}-{YYYY}" \
  -H "Authorization: Ghost $GHOST_JWT" \
  | python3 -c "import sys,json; print('count =', len(json.load(sys.stdin)['posts']))"
# → count = 1
```

The second call should hit the **Update Archive** branch (PUT) rather than
**Create Archive** (POST). You can confirm in N8N's execution view: the IF
node `Archive Exists?` should fire on the *true* output.

### B.6  Backup the live N8N workflow (after) and commit

```bash
cd /root/workspace/digital-humans-production
sqlite3 /root/.n8n/database.sqlite \
  "SELECT json_object('id', id, 'name', name, 'active', active,
          'nodes', json(nodes), 'connections', json(connections),
          'settings', json(settings), 'staticData', json(staticData))
   FROM workflow_entity WHERE id='qcVVPMTE0LyhNAO2';" \
  | python3 -m json.tool \
  > n8n/workflows/blog-newsletter-hebdo.studio.live.json

# Diff against the repo's "studio.json" — should be equivalent semantically
diff <(python3 -m json.tool n8n/workflows/blog-newsletter-hebdo.studio.live.json) \
     <(python3 -m json.tool n8n/workflows/blog-newsletter-hebdo.studio.json) | head -40
```

Commit the live-after snapshot if you want a record of the actual N8N state
at the moment the workflow went into production.

---

## Architecture notes

### Why `__UNSUBSCRIBE_URL__` and not `{{unsubscribe_url}}`?

The original mockup uses Mustache-style `{{unsubscribe_url}}`. We can't keep
that token in the live HTML because the **Send Newsletter** node uses an
n8n expression to substitute per-recipient — and `{{ … }}` collides with
n8n's own expression delimiters. So the gen_html node emits
`__UNSUBSCRIBE_URL__` instead, which is then replaced per recipient by:

```
={{ $('Generate Newsletter HTML').first().json.html
     .replace('__UNSUBSCRIBE_URL__',
              'https://digital-humans.fr/journal/unsubscribe?email='
              + encodeURIComponent($json.email)) }}
```

The mockup file at `docs/marketing-site/newsletter-studio-mockup.html` is
**not** modified — it stays Mustache-style for design-doc purposes, per the
brief's "do not touch the mockup HTML itself" guard-rail.

### Why three nodes for Ghost upsert (lookup + IF + create/update)?

Ghost's `POST /admin/posts/` returns `422` on slug collision, and the only
clean way to update is `PUT /admin/posts/{id}/?source=html` with the
existing `updated_at` (collision detection token). Doing it in one HTTP
node would require parsing the 422 response and recovering — fragile and
hard to read in N8N's UI. Splitting into:

```
Generate Ghost JWT
  → Lookup Archive Slug          (GET, neverError so 404 doesn't crash)
    → Archive Exists?            (IF on posts[].length > 0)
       → true  → Update Archive  (PUT  with updated_at)
       → false → Create Archive  (POST)
```

…makes the control flow explicit in the canvas, gives clean execution
traces, and keeps the failure modes per-node (a 401 on lookup is clearly
"JWT minting broke", not "Ghost rejected my body").

### Per-recipient unsubscribe leak prevention on the archive page

The archive copy of the newsletter is published as a public Ghost post.
If we simply re-used the per-recipient HTML, the archive page would either
contain a broken `__UNSUBSCRIBE_URL__` token *or* one specific
recipient's email. Neither is acceptable. The gen_html node therefore
emits two distinct strings:

- `html` — has `__UNSUBSCRIBE_URL__`, intended for `Send Newsletter` to
  per-recipient-substitute.
- `archive_html` — `__UNSUBSCRIBE_URL__` already substituted with the
  generic `https://digital-humans.fr/journal/unsubscribe`, intended for the
  Ghost POST/PUT body.

---

## C. VPS runtime fixes appliqués (post-livraison sandbox)

Lors du déploiement live le 26 avril 2026, 4 ajustements ont été nécessaires
côté VPS pour faire fonctionner le workflow sur N8N v1+ (sandbox plus stricte
que la version dev sandbox supposait) :

### C.1 — env vars systemd N8N requises

Trois variables d'environnement doivent être posées dans
`/etc/systemd/system/n8n.service.d/override.conf` :

```ini
[Service]
Environment="GHOST_ADMIN_KEY=<id>:<secret>"
Environment="NODE_FUNCTION_ALLOW_BUILTIN=crypto"
Environment="N8N_BLOCK_ENV_ACCESS_IN_NODE=false"
```

- **GHOST_ADMIN_KEY** : la clé Admin Ghost au format `id:secret` (récupérable dans Ghost Admin > Integrations > Digital Humans API). À reprendre dans Track A2/Doppler quand actif.
- **NODE_FUNCTION_ALLOW_BUILTIN=crypto** : autorise `require('crypto')` dans les Code nodes (Generate Ghost JWT en a besoin pour signer le JWT HMAC-SHA256).
- **N8N_BLOCK_ENV_ACCESS_IN_NODE=false** : autorise `$env.GHOST_ADMIN_KEY` dans les Code nodes (bloqué par défaut depuis N8N v1+).

Permissions du fichier override : `chmod 600`, owner root.

### C.2 — Code nodes : `$env` vs `process.env`

Le node `Generate Ghost JWT` utilise `$env.GHOST_ADMIN_KEY` (API native N8N)
et **non pas** `process.env.GHOST_ADMIN_KEY` (qui est filtré par la sandbox).
Le fichier source `nodes/generate_ghost_jwt.studio.js` a été corrigé en
conséquence — si tu re-bâtis le workflow via `scripts/build_studio_patch.py`,
l'export reflète automatiquement la version corrigée.

### C.3 — `Create Archive` / `Update Archive` : jsonBody syntax

Les deux nodes HTTP qui POST/PUT vers Ghost Admin utilisent un `jsonBody`
construit via une **seule** expression N8N qui fait `JSON.stringify({...})`,
plutôt qu'un mélange invalide d'expressions imbriquées :

```
={{ JSON.stringify({
  posts: [{
    title: $('Generate Newsletter HTML').first().json.subject,
    slug: $('Generate Newsletter HTML').first().json.archive_slug,
    html: $('Generate Newsletter HTML').first().json.archive_html,
    custom_excerpt: $('Generate Newsletter HTML').first().json.archive_excerpt,
    tags: [{slug: 'archive'}],
    status: 'published',
    visibility: 'public',
    feature_image: null
    // (pour Update Archive seulement) updated_at: $('Lookup Archive Slug').first().json.posts[0].updated_at
  }]
}) }}
```

### C.4 — Trigger schedule désactivé (post-go-live test)

Le node `Lundi 9h` (scheduleTrigger) a été désactivé via `disabled: true`
après les tests E2E pour éviter un envoi automatique non-désiré le lundi
suivant. Le workflow reste `active: true` globalement, le webhook
`/webhook/send-newsletter` reste actif pour les triggers manuels et tests.

Pour réactiver le schedule plus tard : remettre `disabled: false` sur le
node, ou via UI N8N (toggle sur le node).

### C.5 — Validation E2E live (26 avr 2026)

- Exec 437 : success — article archive `week-17-2026` créé via POST (Create Archive branch)
- Exec 438 : success — même slug, branche UPDATE prise (PUT), pas de doublon
- Email Studio reçu à shatit@gmail.com (validé visuellement par Sam)
- Article archive accessible à `https://digital-humans.fr/journal/archive/week-17-2026`

---

*Section C ajoutée par le maître d'œuvre lors du déploiement live (commit post-merge).*
