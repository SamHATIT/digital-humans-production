# Studio covers — operator guide

Generate editorial cover images for the marketing site (Acte 3 gallery) and for
The Journal articles, using **nanobanana2** (= Google Gemini 3 Pro Image,
model `gemini-3-pro-image-preview`).

This doc is a runbook. Read once, refer to it whenever a new cover is needed.

---

## 0. Prerequisites

- Python 3.11+ with `pyyaml` and `pillow`:
  ```bash
  python3 -m pip install --user pyyaml pillow
  ```
- A Gemini API key (Google AI Studio → "Get API key").
- The repo cloned at `/root/workspace/digital-humans-production/` (VPS) or
  wherever you work locally.

The key **must not** land in git. Two options for the session:

```bash
# Option A — env var, ephemeral, recommended
export GEMINI_API_KEY="sk-..."

# Option B — local .env (already gitignored). Source it explicitly.
echo 'GEMINI_API_KEY=sk-...' > .env.local
set -a; source .env.local; set +a
```

When the session is over, **`unset GEMINI_API_KEY`** and shred any local file
that held it. Track A2 (Doppler) will replace this manual handling later.

---

## 1. Inventory of briefs

`tools/cover_briefs.yaml` is the source of truth. Each entry is one cover.

```yaml
- id: logifleet           # → assets/covers/logifleet.jpg
  subject: a fleet of long-haul trucks viewed from directly overhead, ...
  rubric: gallery         # gallery | manifesto | craft | dispatch | archive
  aspect_ratio: "16:10"
  tags: [gallery, logistics, b2b]
```

Two batches are predefined:

| Tag | Count | Purpose |
|---|---|---|
| `gallery` | 6 | Acte 3 of the marketing site (one per vertical: LogiFleet, Pharma, Telecom, B2B Distribution, Energy, Retail) |
| `article` | 8 | Cover replacements for existing Ghost articles |

Sam owns the briefs file. To add or refine a cover, edit the YAML and re-run.

---

## 2. Run the generator

### Dry run (no API call, no cost)

```bash
python3 tools/generate_studio_covers.py --dry-run
```

This prints every prompt that would be sent. Useful when tweaking the style
template or rubric directives before paying for tokens.

### Generate one cover

```bash
GEMINI_API_KEY=... python3 tools/generate_studio_covers.py logifleet
```

Output: `assets/covers/logifleet.jpg`. The script will skip the call if the
file already exists; pass `--force` to regenerate.

### Generate a batch by tag

```bash
# All 6 gallery covers
GEMINI_API_KEY=... python3 tools/generate_studio_covers.py --tag gallery

# All 8 article covers
GEMINI_API_KEY=... python3 tools/generate_studio_covers.py --tag article
```

### Generate everything

```bash
GEMINI_API_KEY=... python3 tools/generate_studio_covers.py
```

Estimated cost: 14 covers × 1-3 attempts × ~$0.04 ≈ $0.56 to $1.68. Logged in
`assets/covers/.generation.log`.

---

## 3. Quality gate

For each cover, the script runs a basic gate:

- **Min dimensions** : 1280×800. Most Gemini outputs at `aspect_ratio: "16:10"`
  return well above that; if the model downsizes a particular subject, the
  gate triggers a retry.

If a brief fails 3 attempts, it is logged with `[give up]` and skipped. **You
visually inspect the rest** — the script doesn't catch:

- Text accidentally inserted in the image (Gemini sometimes does this despite
  the explicit "NO text" instruction). If this happens, edit the brief
  to add `". Absolutely no glyphs, no inscriptions, no labels."` and re-run with
  `--force`.
- Color drift (image too saturated, palette drifted from ink/bone/brass). Tune
  `STYLE_TEMPLATE` in the script if it happens systematically; or override
  per-brief via `prompt_override:` in the YAML.
- People accidentally included (rare with editorial style + explicit "NO
  people" but check anyway).

A failed cover is rare but real. Sam re-prompts manually in such cases.

---

## 4. Where the covers are used

### Marketing site (gallery covers)

The 6 gallery covers (`logifleet.jpg`, `pharma.jpg`, `telecom.jpg`,
`b2b-distribution.jpg`, `energy.jpg`, `retail.jpg`) are referenced from the
Acte 3 slides in the React bundle (`/var/www/dh-preview/index.html`).

Local URLs at `https://digital-humans.fr/assets/covers/<id>.jpg` once the
preview is promoted to prod. For now, the marketing site preview includes the
images directly in the bundle (cf. `docs/marketing-site/scripts/dh-mod*.py`).

### The Journal articles

The 8 article covers are uploaded to Ghost and assigned as `feature_image`. To
do that:

1. Generate the cover with the script.
2. In Ghost admin → Posts → \[the article\] → Feature image → upload the JPEG
   from `assets/covers/<id>.jpg`.
3. Update the article slug in Ghost to match `<id>` if it doesn't already
   (otherwise the newsletter falls back to the default cover).

> Don't auto-replace existing `feature_image` programmatically. Sam validates
> each cover visually before swapping.

### Newsletter

The newsletter (`Generate Newsletter HTML` node in N8N — see
`round2bis/BRIEF_B5_NEWSLETTER_SYNTHESIS.md`) reuses the article's Ghost
`feature_image` URL directly. So once the Ghost cover is updated, the next
Monday newsletter automatically uses the new one. No second action needed.

---

## 5. Adding a new cover later

A new article is published. To produce a Studio cover for it:

1. Open `tools/cover_briefs.yaml`. Add a new entry at the end:
   ```yaml
   - id: craft-flow-debugger        # match the future Ghost slug
     subject: <one concrete singular subject, written in plain English>
     rubric: craft                  # match the article's tone
     aspect_ratio: "16:10"
     tags: [article, craft]
   ```
2. Dry run to check the prompt:
   ```bash
   python3 tools/generate_studio_covers.py craft-flow-debugger --dry-run
   ```
3. Generate:
   ```bash
   GEMINI_API_KEY=... python3 tools/generate_studio_covers.py craft-flow-debugger
   ```
4. Inspect `assets/covers/craft-flow-debugger.jpg`. If you don't like it,
   adjust the `subject:` line, then `--force` regenerate.
5. Upload to Ghost as the article's feature image.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `[fatal] GEMINI_API_KEY env var not set` | env not exported in this shell | `export GEMINI_API_KEY=...` |
| `[fatal] PyYAML not installed` | missing dep | `pip install pyyaml` |
| `Gemini HTTP 403` | quota dépassé OR clé révoquée | Vérifier la console Google AI Studio. Ne pas insister. |
| `Gemini HTTP 429` | rate limit | Le script ne re-tente pas le 429 ; relancer dans 5 min. |
| `Gemini returned no candidates` | safety filter triggered | Reformuler le subject pour l'éloigner d'éléments potentiellement filtrés (armes, marques, célébrités). |
| Image saved mais le gate échoue avec "too small" | Gemini a renvoyé une thumb basse-rés | Re-run avec `--force` ; si récurrent, ajouter explicitement `". High resolution."` au template. |
| Texte parasite dans l'image | Gemini ignore parfois "NO text" | Ajouter au prompt : `". Absolutely no glyphs, no inscriptions, no labels."` Re-run. |

---

## 7. Cost log convention

After each batch, append a line to `assets/covers/.generation.log`. The script
does this automatically. Format:

```
[YYYY-MM-DDTHH:MM:SS] === Studio covers run · N brief(s) · model=... · dry_run=False ===
[YYYY-MM-DDTHH:MM:SS] [attempt 1/3] logifleet ...
[YYYY-MM-DDTHH:MM:SS] [ok] logifleet -> assets/covers/logifleet.jpg (1600x1000 OK)
...
[YYYY-MM-DDTHH:MM:SS] === Done · N/N succeeded ===
```

That log is gitignored (it can grow and contains timestamps that aren't
useful in version control). For traceability of cost, copy a summary into the
session report.

---

## 8. Reference — the style template

The script applies this template to every prompt (unless `prompt_override:` is
set in the YAML):

> Editorial illustration, monochromatic palette of charcoal black (#0A0A0B),
> warm bone white (#F5F2EC), and brass gold accent (#C8A97E). Style: refined
> 1920s technical lithograph crossed with a modern engineering blueprint.
> Single subject: **{subject}**. Composed off-center on the lower-right third,
> with hairline geometric details and one brass-toned focal element. Absolutely
> NO people, NO text, NO letters, NO numbers, NO logos, NO photorealism.
> Print-quality, austere, calm, contemplative, breathable negative space.

Plus a rubric-conditioned mood line:

| Rubric | Mood appended |
|---|---|
| `manifesto` | declarative, foundational, slightly weighty |
| `craft` | precise, instructional, hand-drawn feel |
| `dispatch` | situated, atmospheric, in-the-field |
| `archive` | distant, reflective, archival |
| `gallery` | signature, representative of the vertical |

Final clause: `Aspect ratio <16:10 or 16:9>.`

If the visual identity drifts (Sam adopts a new accent color, wants a different
era reference, etc.), modify `STYLE_TEMPLATE` in
`tools/generate_studio_covers.py` and re-run all gallery+article covers with
`--force`.

---

*Operator guide written 26 April 2026. Updated when the workflow changes.*
