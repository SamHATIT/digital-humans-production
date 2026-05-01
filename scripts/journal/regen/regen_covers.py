#!/usr/bin/env python3
"""Regenerate Studio-style cover images for Journal posts.

Two styles, both blending into the dark site palette:
  STYLE_A — manifesto / editorial: pure black, abstract 3D drape with brass glint
  STYLE_B — craft notes / dispatches: cream paper hand-drawn technical sketch
            with ONE brass accent, fading to black at the bottom edge

Both use the same palette: ink #0A0A0B, bone #F5F2EC, brass #C8A97E.

Usage:
  python3 regen_covers.py --slug personnalisez-... [--dry-run]
  python3 regen_covers.py --all
"""
from __future__ import annotations

import argparse
import base64
import os
import time
from pathlib import Path

import jwt
import requests

ENV = Path("/root/workspace/digital-humans-production/.env")
for line in ENV.read_text().splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
GHOST_URL = "https://blog-admin.digital-humans.fr"
GHOST_ADMIN_KEY = os.environ["GHOST_ADMIN_KEY"]


# ─── Style prompts ───────────────────────────────────────────────────
STYLE_A = """Editorial cover image, 16:9 horizontal composition.
BACKGROUND: pure deep matte black (#0A0A0B) filling 70% of the frame, absolute black with subtle texture, no gradient backdrop.
SUBJECT: {subject}. The subject is rendered as a soft, abstract, photographic 3D form occupying ONLY the right third — emerging from shadow with a dim warm glow on its right edge. Generous black negative space on the left.
ACCENT: ONE brass-gold (#C8A97E) glint or small object catching the light somewhere on the subject. Nothing else colored.
LIGHTING: single warm tungsten source from upper-right, dramatic chiaroscuro, deep shadows, subject lit at 20%, museum-grade hush.
TEXTURE: 35mm film grain, slight warmth in highlights.
REFERENCES: Hiroshi Sugimoto seascapes, James Turrell light fields, the dark interior of a luxury jewellery box, Hermès campaign photography.
RULES: NO text, NO letters, NO logos, NO numbers, NO typography of any kind in the image. NO human faces, NO bodies, NO offices, NO laptops, NO UI screenshots, NO bright colors. Photo-realistic, NOT illustration."""

STYLE_B = """Hand-drawn architect's working drawing on warm cream paper background (#F5F2EC), 16:9 horizontal composition.
SUBJECT: {subject}. Rendered as a meticulous BLACK INK technical sketch with clean confident line-work, faint pencil construction lines visible, parallel hatching for shadows, tiny dimension tick-marks scattered around (NO readable text or numbers, just abstract marker shapes).
COMPOSITION: subject off-center to the RIGHT third, generous cream negative space on the left. The BOTTOM 20-30% of the frame transitions softly down to deep black (#0A0A0B) — a smooth gradient from cream to ink — so the image sits naturally embedded in a dark website without a hard edge.
BRASS ACCENT: exactly ONE element in solid brass-gold (#C8A97E) — one part of the subject filled or highlighted in brass. Everything else is pure black ink on cream paper.
DECORATIVE ELEMENTS: a small compass rose in the upper-left corner in light pencil, a few faint grid lines crossing the cream area, optionally one or two ghost-sketched gears or sextants in the background at 25% opacity.
TEXTURE: hand-drawn imperfection, slight pencil grain, paper fiber texture, subtle aging.
REFERENCES: Leonardo da Vinci's notebook pages, vintage architect's blueprints from the 1920s, mid-century engineering manuals, Italian luxury brand sketch archives, Hermès saddlery technical drawings.
RULES: NO readable text, NO letters, NO words, NO logos, NO photorealism — pure hand-drawn ink illustration on cream paper. NO modern UI, NO computers, NO offices."""


# ─── Per-post mapping ───────────────────────────────────────────────
# style: 'A' (dark editorial) or 'B' (cream sketch)
# subject: a vivid single-sentence description of WHAT to draw
POSTS = {
    "personnalisez-vos-sites-web-avec-les-fondamentaux-de-data-360": {
        "style": "B",
        "subject": (
            "a hand-drawn technical diagram of a single elegant pocket-watch dissected — "
            "showing concentric layered dials, each layer representing a different data plane, "
            "with the central crown wheel highlighted in brass, surrounded by faint annotation marks "
            "and a few floating gear sketches"
        ),
    },
    "flows-vs-apex-choisir-la-bonne-solution-salesforce": {
        "style": "B",
        "subject": (
            "two contrasting hand-drawn instruments side by side — a precision drafting pen on the left "
            "and a heavy iron forge hammer on the right — separated by a thin dotted brass line down the centre, "
            "small annotation arrows pointing to each one"
        ),
    },
    "optimiser-les-performances-de-vos-applications-salesforce-avec-salesforce-optimizer": {
        "style": "B",
        "subject": (
            "a hand-drawn detailed sketch of a precision tuning fork standing upright on a workbench, "
            "with measurement gauges and ghost-sketched gear wheels behind, the fork's tines highlighted in brass"
        ),
    },
    "des-innovations-mobiles-salesforce-qui-boostent-votre-productivite": {
        "style": "B",
        "subject": (
            "a hand-drawn folded topographic map being unfolded by an unseen hand, with rough crease lines "
            "and contour topography hand-sketched, a single brass compass needle floating in the centre"
        ),
    },
    "automatiser-la-gestion-des-versions-salesforce-avec-salesforce-dx": {
        "style": "B",
        "subject": (
            "an exploded technical drawing of a vintage cast-iron printing-press mechanism — gears, levers, plates "
            "rendered in clean black ink lines with construction guides — with one central drum filled in solid brass"
        ),
    },
    "optimiser-les-performances-des-agents-avec-lintelligence-artificielle": {
        "style": "B",
        "subject": (
            "a hand-drawn detailed sketch of a brass-weighted metronome on a wooden base, pendulum mid-swing with "
            "motion arcs lightly hatched, and a faint sextant ghost behind it, ONE pendulum weight filled in brass"
        ),
    },
    "debloquez-le-pouvoir-collaboratif-des-groupes-salesforce-trailblazer": {
        "style": "B",
        "subject": (
            "two hand-drawn intersecting circles in clean ink, the overlap area densely cross-hatched, "
            "small constellation marks scattered at the intersection points, a single brass star at the centre overlap"
        ),
    },
    "creez-des-chatbots-vocaux-performants-avec-salesforce-et-amazon-lex": {
        "style": "B",
        "subject": (
            "a hand-drawn orthographic technical projection of a vintage ribbon microphone — front view and side view "
            "side by side — with concentric sound-wave arcs sketched out lightly, the brass mesh of the front grille filled in brass"
        ),
    },
    # Manifesto + archive — abstract editorial style
    "week-17-2026": {
        "style": "A",
        "subject": (
            "a single folded letter on a dark leather surface, the paper edge catching dim warm tungsten light, "
            "a small brass wax seal at the bottom-right of the letter, the rest dissolving into black"
        ),
    },
    # Bienvenue — Sam said the current placeholder is great, skip it
    # Personnalisez Data 360 IS in B style above (the one Sam complained about)
}


# ─── Ghost helpers ───────────────────────────────────────────────────
def get_ghost_token() -> str:
    key_id, secret = GHOST_ADMIN_KEY.split(":")
    iat = int(time.time())
    return jwt.encode(
        {"iat": iat, "exp": iat + 5 * 60, "aud": "/admin/"},
        bytes.fromhex(secret),
        algorithm="HS256",
        headers={"alg": "HS256", "typ": "JWT", "kid": key_id},
    )


def upload_image_to_ghost(image_bytes: bytes, filename: str) -> str | None:
    r = requests.post(
        f"{GHOST_URL}/ghost/api/admin/images/upload/",
        headers={"Authorization": f"Ghost {get_ghost_token()}"},
        files={"file": (filename, image_bytes, "image/jpeg")},
        timeout=60,
    )
    if r.status_code != 201:
        print(f"  [!!] upload failed: {r.status_code} {r.text[:200]}")
        return None
    return r.json()["images"][0]["url"]


def update_post_feature_image(slug: str, feature_image_url: str) -> bool:
    # First, fetch the current post to get its id and updated_at (required by Ghost)
    r = requests.get(
        f"{GHOST_URL}/ghost/api/admin/posts/slug/{slug}/",
        headers={"Authorization": f"Ghost {get_ghost_token()}"},
        timeout=30,
    )
    if r.status_code != 200:
        print(f"  [!!] can't fetch post {slug}: {r.status_code}")
        return False
    post = r.json()["posts"][0]
    pid = post["id"]
    updated_at = post["updated_at"]

    # PUT update
    r2 = requests.put(
        f"{GHOST_URL}/ghost/api/admin/posts/{pid}/",
        headers={
            "Authorization": f"Ghost {get_ghost_token()}",
            "Content-Type": "application/json",
        },
        json={"posts": [{"feature_image": feature_image_url, "updated_at": updated_at}]},
        timeout=30,
    )
    if r2.status_code != 200:
        print(f"  [!!] can't update post {slug}: {r2.status_code} {r2.text[:200]}")
        return False
    return True


# ─── Gemini ──────────────────────────────────────────────────────────
def generate_image(prompt: str) -> bytes | None:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/nano-banana-pro-preview:generateContent?key={GEMINI_API_KEY}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        },
        timeout=120,
    )
    if r.status_code != 200:
        print(f"  [!!] gemini error: {r.status_code} {r.text[:300]}")
        return None
    data = r.json()
    if "candidates" not in data:
        print(f"  [!!] no candidates: {data}")
        return None
    for part in data["candidates"][0].get("content", {}).get("parts", []):
        if "inlineData" in part:
            return base64.b64decode(part["inlineData"]["data"])
    print(f"  [!!] no image data returned")
    return None


# ─── Orchestration ───────────────────────────────────────────────────
def regen_one(slug: str, dry_run: bool = False, save_local: bool = True) -> bool:
    if slug not in POSTS:
        print(f"  [!!] no mapping for {slug}")
        return False
    cfg = POSTS[slug]
    style = STYLE_A if cfg["style"] == "A" else STYLE_B
    prompt = style.format(subject=cfg["subject"])
    print(f"\n=== {slug} (style {cfg['style']}) ===")
    print(f"PROMPT:\n{prompt[:600]}...\n")
    if dry_run:
        return True
    print(f"  → calling Gemini...")
    img = generate_image(prompt)
    if not img:
        return False
    print(f"  ✓ {len(img)//1024}KB received")
    # Local snapshot for review
    local = Path(f"/tmp/regen-{slug}.jpg")
    local.write_bytes(img)
    if save_local:
        # Also expose via preview path so Sam can look at it via URL
        preview = Path(f"/var/www/dh-preview/_regen_{slug}.jpg")
        preview.write_bytes(img)
        preview.chmod(0o644)
        print(f"  ✓ visible at: http://72.61.161.222/preview/_regen_{slug}.jpg")
    print(f"  → uploading to Ghost...")
    url = upload_image_to_ghost(img, f"cover-{slug}.jpg")
    if not url:
        return False
    print(f"  ✓ uploaded: {url}")
    print(f"  → updating Ghost post feature_image...")
    if not update_post_feature_image(slug, url):
        return False
    print(f"  ✓ post updated")
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--slug", help="single post slug to regen")
    p.add_argument("--all", action="store_true", help="regen all mapped posts")
    p.add_argument("--dry-run", action="store_true", help="print prompts only")
    p.add_argument("--list", action="store_true", help="list mapped posts")
    args = p.parse_args()
    if args.list:
        for slug, cfg in POSTS.items():
            print(f"  [{cfg['style']}] {slug}")
            print(f"        {cfg['subject'][:120]}...")
        return
    if args.slug:
        regen_one(args.slug, dry_run=args.dry_run)
    elif args.all:
        for slug in POSTS:
            ok = regen_one(slug, dry_run=args.dry_run)
            if not ok:
                print(f"  [!!] skipping rest after failure on {slug}")
                break
            time.sleep(2)  # be nice to API
    else:
        p.print_help()


if __name__ == "__main__":
    main()
