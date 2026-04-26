#!/usr/bin/env python3
"""Generate Studio editorial covers via nanobanana2 (Gemini 3 Pro Image).

Usage:
    GEMINI_API_KEY=... python tools/generate_studio_covers.py            # all briefs
    GEMINI_API_KEY=... python tools/generate_studio_covers.py logifleet  # one brief
    GEMINI_API_KEY=... python tools/generate_studio_covers.py --tag gallery
    GEMINI_API_KEY=... python tools/generate_studio_covers.py --dry-run  # print prompts only

The script reads tools/cover_briefs.yaml, applies the Studio style template to
each brief's subject, calls the Gemini API, and saves the resulting image to
assets/covers/<id>.jpg.

Quality gate (basic, can be tightened):
- Image must be >= 1280x800.
- Run up to N attempts (default 3) per brief if the gate fails.
- Failures are reported but do not stop the batch.

Cost note: Gemini 3 Pro Image ~$0.04/image. 14 briefs * 3 attempts max ~= $1.68.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError:
    sys.stderr.write("[fatal] PyYAML not installed. Run: pip install pyyaml\n")
    sys.exit(2)

# Pillow is imported lazily in save_as_jpeg / passes_gate so --dry-run works
# without it.


# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIEFS_FILE = REPO_ROOT / "tools" / "cover_briefs.yaml"
OUTPUT_DIR = REPO_ROOT / "assets" / "covers"
LOG_FILE = REPO_ROOT / "assets" / "covers" / ".generation.log"

GEMINI_MODEL = "gemini-3-pro-image-preview"
GEMINI_ENDPOINT = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

MIN_DIMENSIONS = (1280, 720)
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SEC = (2, 4, 8)

STYLE_TEMPLATE = (
    "Editorial illustration, monochromatic palette of charcoal black (#0A0A0B), "
    "warm bone white (#F5F2EC), and brass gold accent (#C8A97E). "
    "Style: refined 1920s technical lithograph crossed with a modern engineering "
    "blueprint. Single subject: {subject}. Composed off-center on the lower-right "
    "third, with hairline geometric details and one brass-toned focal element. "
    "Absolutely NO people, NO text, NO letters, NO numbers, NO logos, NO "
    "photorealism. Print-quality, austere, calm, contemplative, breathable "
    "negative space."
)

RUBRIC_DIRECTIVES = {
    "manifesto": " Mood: declarative, foundational, slightly weighty.",
    "craft":     " Mood: precise, instructional, hand-drawn feel.",
    "dispatch":  " Mood: situated, atmospheric, in-the-field.",
    "archive":   " Mood: distant, reflective, archival.",
    "gallery":   " Mood: signature, representative of the vertical.",
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class Brief:
    id: str
    subject: str
    rubric: str | None = None
    aspect_ratio: str = "16:9"
    tags: list[str] | None = None
    prompt_override: str | None = None

    @property
    def output_path(self) -> Path:
        return OUTPUT_DIR / f"{self.id}.jpg"

    def render_prompt(self) -> str:
        if self.prompt_override:
            return self.prompt_override
        prompt = STYLE_TEMPLATE.format(subject=self.subject)
        if self.rubric and self.rubric in RUBRIC_DIRECTIVES:
            prompt += RUBRIC_DIRECTIVES[self.rubric]
        prompt += f" Aspect ratio {self.aspect_ratio}."
        return prompt


def load_briefs(path: Path) -> list[Brief]:
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a YAML list of briefs")
    return [Brief(**entry) for entry in raw]


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

def call_gemini(prompt: str, aspect_ratio: str, api_key: str) -> bytes:
    """Send one generateContent request and return the raw image bytes."""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
        },
    }
    payload = json.dumps(body).encode("utf-8")
    url = f"{GEMINI_ENDPOINT}?key={api_key}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            response = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc

    candidates = response.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(response)[:400]}")

    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError(f"Gemini response had no inlineData: {json.dumps(response)[:400]}")


# ---------------------------------------------------------------------------
# Image post-processing & quality gate
# ---------------------------------------------------------------------------

def save_as_jpeg(raw: bytes, target: Path, quality: int = 88):
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError("Pillow not installed. Run: pip install pillow")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(raw)
    img = Image.open(tmp).convert("RGB")
    img.save(target, format="JPEG", quality=quality, optimize=True)
    tmp.unlink(missing_ok=True)
    return img


def passes_gate(img) -> tuple[bool, str]:
    w, h = img.size
    if w < MIN_DIMENSIONS[0] or h < MIN_DIMENSIONS[1]:
        return False, f"too small: {w}x{h} < {MIN_DIMENSIONS[0]}x{MIN_DIMENSIONS[1]}"
    return True, f"{w}x{h} OK"


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(line: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{ts}] {line}")
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(f"[{ts}] {line}\n")


# ---------------------------------------------------------------------------
# Per-brief worker
# ---------------------------------------------------------------------------

def generate_one(brief: Brief, api_key: str, *, force: bool, dry_run: bool) -> bool:
    prompt = brief.render_prompt()

    if dry_run:
        log(f"[dry-run] {brief.id} -> {brief.output_path.relative_to(REPO_ROOT)}")
        log(f"  prompt: {prompt}")
        return True

    if brief.output_path.exists() and not force:
        log(f"[skip] {brief.id} already exists ({brief.output_path.relative_to(REPO_ROOT)}) — use --force to regenerate")
        return True

    for attempt in range(1, MAX_ATTEMPTS + 1):
        log(f"[attempt {attempt}/{MAX_ATTEMPTS}] {brief.id} ...")
        try:
            raw = call_gemini(prompt, brief.aspect_ratio, api_key)
        except Exception as exc:
            log(f"  fail: {exc}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SEC[min(attempt - 1, len(RETRY_BACKOFF_SEC) - 1)])
            continue

        try:
            img = save_as_jpeg(raw, brief.output_path)
        except Exception as exc:
            log(f"  fail (decode): {exc}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SEC[min(attempt - 1, len(RETRY_BACKOFF_SEC) - 1)])
            continue

        ok, detail = passes_gate(img)
        if ok:
            log(f"[ok] {brief.id} -> {brief.output_path.relative_to(REPO_ROOT)} ({detail})")
            return True
        log(f"  gate fail: {detail}")

    log(f"[give up] {brief.id} — all {MAX_ATTEMPTS} attempts failed; flag for manual re-prompt")
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def filter_briefs(briefs: list[Brief], ids: list[str], tag: str | None) -> Iterable[Brief]:
    if not ids and not tag:
        yield from briefs
        return
    if ids:
        wanted = set(ids)
        for b in briefs:
            if b.id in wanted:
                yield b
        return
    if tag:
        for b in briefs:
            if b.tags and tag in b.tags:
                yield b


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="Brief ids to generate (default: all).")
    parser.add_argument("--tag", help="Only generate briefs with this tag.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts, do not call the API.")
    parser.add_argument("--briefs-file", default=str(BRIEFS_FILE), help="Path to cover_briefs.yaml")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key and not args.dry_run:
        sys.stderr.write("[fatal] GEMINI_API_KEY env var not set. Re-run with the key, or use --dry-run.\n")
        return 2

    briefs = load_briefs(Path(args.briefs_file))
    selected = list(filter_briefs(briefs, args.ids, args.tag))
    if not selected:
        sys.stderr.write("[fatal] No briefs matched. Check ids / --tag.\n")
        return 1

    log(f"=== Studio covers run · {len(selected)} brief(s) · model={GEMINI_MODEL} · dry_run={args.dry_run} ===")
    successes = 0
    for brief in selected:
        if generate_one(brief, api_key or "", force=args.force, dry_run=args.dry_run):
            successes += 1
    log(f"=== Done · {successes}/{len(selected)} succeeded ===")

    return 0 if successes == len(selected) else 1


if __name__ == "__main__":
    raise SystemExit(main())
