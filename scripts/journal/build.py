#!/usr/bin/env python3
"""
The Journal — Static Site Generator for Digital Humans.

Reads from Ghost Content API, applies Studio rubric mapping, and writes
HTML files into /var/www/journal/. Layout faithful to the B4 Figma mockup
(b4-blog.jsx). Run by Ghost webhook on post.{published,updated,deleted}
or by cron every 15 min as a safety net.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import os
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

# ─── Preview shell extraction ────────────────────────────────────────
PREVIEW_BUNDLE = Path("/var/www/dh-preview/index.html")


def extract_preview_shell_css() -> str:
    """Read the design CSS from the preview bundle and return it as a
    standalone stylesheet. The bundle has 2 <style> blocks inside its
    __bundler/template:
      [0] @font-face rules using internal UUID URLs (NOT reusable here)
      [1] all the actual design CSS (--ink, .glass, .wrap, .mk, etc.)
    We keep only block 1 and rely on Google Fonts (loaded in journal.css)
    for the typefaces.
    """
    if not PREVIEW_BUNDLE.exists():
        return "/* preview bundle not found — shell css empty */\n"
    bundle = PREVIEW_BUNDLE.read_text()
    m = re.search(r'<script type="__bundler/template"[^>]*>([\s\S]*?)</script>', bundle)
    if not m:
        return "/* preview bundle template script not found */\n"
    template = json.loads(m.group(1))
    styles = re.findall(r'<style[^>]*>([\s\S]*?)</style>', template)
    if len(styles) < 2:
        return "/* preview bundle: less than 2 style blocks */\n"
    design_css = styles[1]
    return f"""/* ─────────────────────────────────────────────────────────────
   The Journal — preview-shell.css
   Auto-extracted from /var/www/dh-preview/index.html at build time.
   DO NOT EDIT MANUALLY. Source of truth is the preview bundle.
   ───────────────────────────────────────────────────────────── */

{design_css}
"""


# ─── Configuration ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"
OUTPUT = Path("/var/www/journal")

GHOST_URL = "https://blog-admin.digital-humans.fr"
CONTENT_KEY = os.environ.get("GHOST_CONTENT_KEY", "9985b20698251c494e823ca162")
SITE_URL = "https://digital-humans.fr"

# ─── Studio rubrics ───────────────────────────────────────────────────
RUBRICS = [
    {"id": "manifesto",  "num": "01", "title": "The Manifesto",
     "sub": "Editorials by the studio", "color": "#C8A97E",
     "long_desc": "Editorials on how the studio frames its work — vision, posture, and convictions, signed by those who hold the line."},
    {"id": "craft",      "num": "02", "title": "Craft Notes",
     "sub": "Patterns, methods, code", "color": "#8E6B8E",
     "long_desc": "Patterns kept, methods followed, code we'd ship twice. Working notes from the studio's developers and architects."},
    {"id": "dispatches", "num": "03", "title": "Dispatches",
     "sub": "From the projects in flight", "color": "#7A9B76",
     "long_desc": "Field notes from the projects in flight — what worked, what didn't, what we'd do again. Sent from the floor."},
    {"id": "archive",    "num": "04", "title": "The Archive",
     "sub": "Older essays, kept on file", "color": "#76716A",
     "long_desc": "Newsletters, older essays, and pieces from the road. Kept on file."},
]
RUBRIC_BY_ID = {r["id"]: r for r in RUBRICS}

# ─── Agent → rubric mapping (validated by Sam) ────────────────────────
AGENT_TO_RUBRIC = {
    "sophie-chen":     "manifesto",
    "olivia-parker":   "manifesto",
    "marcus-johnson":  "craft",
    "diego-martinez":  "craft",
    "zara-thompson":   "craft",
    "raj-patel":       "craft",
    "elena-vasquez":   "dispatches",
    "jordan-blake":    "dispatches",
    "aisha-okonkwo":   "dispatches",
    "lucas-fernandez": "dispatches",
}

# ─── Agent identity (mirrors AGENTS dict in blog_generator.py) ────────
AGENTS = {
    "sophie-chen":     {"name": "Sophie Chen",     "role": "Project Manager",      "short_role": "The framing",      "tagline": "she opens every project, she closes every spec",     "color": "#C8A97E", "bio": "Sophie writes editorials about how the studio frames its work — what gets decided in week one, why eleven players are enough, and the cheap mistakes that compound when the framing is rushed."},
    "olivia-parker":   {"name": "Olivia Parker",   "role": "Business Analyst",     "short_role": "The use cases",    "tagline": "the BA who turns interviews into specs",            "color": "#C8A97E", "bio": "Olivia writes about turning vague requests into use cases that survive the build. Process, requirements, and the discipline of asking the next question."},
    "marcus-johnson":  {"name": "Marcus Johnson",  "role": "Solution Architect",   "short_role": "The architecture", "tagline": "the architect who chooses what not to build",       "color": "#8E6B8E", "bio": "Marcus writes on Salesforce architecture — design patterns, integration choices, and the trade-offs between configuration and code."},
    "diego-martinez":  {"name": "Diego Martinez",  "role": "Apex Developer",       "short_role": "The code",         "tagline": "the developer who writes Apex with restraint",      "color": "#8E6B8E", "bio": "Diego writes on Apex, triggers, batches, and SOQL. Patterns kept, patterns discarded — the working developer's notebook."},
    "zara-thompson":   {"name": "Zara Thompson",   "role": "LWC Developer",        "short_role": "The interface",    "tagline": "the developer who keeps Lightning quiet",           "color": "#8E6B8E", "bio": "Zara writes on Lightning Web Components, Aura, and front-end craft on Salesforce. Sober UI, restraint with effects, accessibility before novelty."},
    "raj-patel":       {"name": "Raj Patel",       "role": "Salesforce Admin",     "short_role": "The platform",     "tagline": "the admin who makes Flows readable",                "color": "#8E6B8E", "bio": "Raj writes on Flows, Permissions, and Validation Rules. The admin's working notes — practical, step-by-step, configuration before code."},
    "elena-vasquez":   {"name": "Elena Vasquez",   "role": "QA Engineer",          "short_role": "The quality",      "tagline": "the QA who signs every coverage report",            "color": "#7A9B76", "bio": "Elena writes on test strategy, Apex tests, and UAT. Coverage as a verb, the discipline that produces 95%, and why every untested branch becomes a meeting."},
    "jordan-blake":    {"name": "Jordan Blake",    "role": "DevOps Engineer",      "short_role": "The pipeline",     "tagline": "the engineer who automates the deploy",             "color": "#7A9B76", "bio": "Jordan writes on SFDX, CI/CD, Git, and Sandboxes. The DevOps notebook — automation, repeatable deploys, and the cost of the manual step."},
    "aisha-okonkwo":   {"name": "Aisha Okonkwo",   "role": "Data Specialist",      "short_role": "The data",         "tagline": "the specialist who treats migrations as moves",     "color": "#7A9B76", "bio": "Aisha writes on Data Cloud, migration, and ETL. Field notes from the data room — what worked, what didn't, what we'd do again."},
    "lucas-fernandez": {"name": "Lucas Fernandez", "role": "Training Lead",        "short_role": "The handover",     "tagline": "the trainer who makes the spec usable",             "color": "#7A9B76", "bio": "Lucas writes on training, documentation, and adoption. The handover notes — turning a built system into a system that's actually used."},
}

# Default fallback for posts without an agent tag
DEFAULT_AGENT = {
    "slug": "sam",
    "name": "Sam Hatit",
    "role": "Studio",
    "short_role": "The studio",
    "tagline": None,
    "color": "#C8A97E",
    "bio": None,
    "avatar": None,
}


# ─── Ghost client ─────────────────────────────────────────────────────
def fetch_ghost_posts() -> list[dict[str, Any]]:
    url = f"{GHOST_URL}/ghost/api/content/posts/"
    posts: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {
            "key": CONTENT_KEY,
            "limit": 50,
            "page": page,
            "include": "tags,authors",
            "fields": "id,uuid,slug,title,html,plaintext,excerpt,custom_excerpt,feature_image,feature_image_alt,feature_image_caption,published_at,updated_at,reading_time,visibility,meta_title,meta_description",
            "filter": "status:published",
            "order": "published_at desc",
        }
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        posts.extend(data.get("posts", []))
        if not data.get("meta", {}).get("pagination", {}).get("next"):
            break
        page += 1
    return posts


# ─── Derivations ─────────────────────────────────────────────────────
MONTH_FR_TO_EN = {  # not used (dates already neutral) but kept for safety
    "janv": "JAN", "févr": "FEB", "mars": "MAR", "avr": "APR",
    "mai": "MAY", "juin": "JUN", "juil": "JUL", "août": "AUG",
    "sept": "SEP", "oct": "OCT", "nov": "NOV", "déc": "DEC",
}


def format_date_studio(iso: str) -> str:
    """ISO date → '24 APR 2026' Studio format."""
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    return d.strftime("%d %b %Y").upper()


def format_joined(iso: str) -> str:
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return ""
    return d.strftime("%b %Y").upper()


def derive_rubric(post: dict[str, Any]) -> dict[str, Any]:
    """From post tags, find the rubric (tag 'archive' wins, else agent → rubric, else 'craft')."""
    tag_slugs = [t["slug"] for t in post.get("tags") or []]
    if "archive" in tag_slugs or "newsletter" in tag_slugs:
        return RUBRIC_BY_ID["archive"]
    for slug in tag_slugs:
        if slug in AGENT_TO_RUBRIC:
            return RUBRIC_BY_ID[AGENT_TO_RUBRIC[slug]]
    return RUBRIC_BY_ID["craft"]  # safe default


def derive_author(post: dict[str, Any]) -> dict[str, Any]:
    """Display author = first agent tag if any, else fallback to Sam."""
    tag_slugs = [t["slug"] for t in post.get("tags") or []]
    for slug in tag_slugs:
        if slug in AGENTS:
            a = dict(AGENTS[slug])
            a["slug"] = slug
            a["initials"] = "".join([p[0].upper() for p in a["name"].split()][:2])
            a["avatar"] = None  # Ghost authors avatars are for `sam`, not the agents
            return a
    a = dict(DEFAULT_AGENT)
    # If a real Ghost author exists, use it (profile_image)
    authors = post.get("authors") or []
    if authors:
        gh = authors[0]
        a["name"] = gh.get("name") or a["name"]
        a["slug"] = gh.get("slug") or a["slug"]
        a["avatar"] = gh.get("profile_image")
        a["bio"] = gh.get("bio") or a["bio"]
    a["initials"] = "".join([p[0].upper() for p in a["name"].split()][:2])
    return a


def deck_from_post(post: dict[str, Any]) -> str:
    """Use custom_excerpt if any, else excerpt, else first 180 chars of plaintext."""
    deck = (post.get("custom_excerpt") or post.get("excerpt") or "").strip()
    if not deck and post.get("plaintext"):
        deck = post["plaintext"][:200].rsplit(" ", 1)[0].strip()
    # Ghost can put HTML in excerpt — strip tags
    deck = re.sub(r"<[^>]+>", "", deck).strip()
    return deck[:280]


def reading_time_label(rt: int | None) -> str:
    if not rt or rt < 1:
        return "1 min"
    return f"{rt} min"


def safe_initials(name: str) -> str:
    return "".join([p[0].upper() for p in (name or "").split() if p])[:2] or "DH"


def slug_safe(s: str) -> str:
    s = re.sub(r"[^a-z0-9-]", "-", (s or "").lower()).strip("-")
    return re.sub(r"-+", "-", s)


def build_posts(raw_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich raw Ghost posts with rubric, author, № N°, labels."""
    n = len(raw_posts)
    out: list[dict[str, Any]] = []
    for i, p in enumerate(raw_posts):
        # Numbering: most recent gets the highest N° (chrono inverse)
        # raw_posts is sorted by published_at desc, so:
        #   index 0 → N° = n
        #   index n-1 → N° = 1
        num_int = n - i
        num = f"№ {num_int:03d}"
        rubric = derive_rubric(p)
        author = derive_author(p)
        out.append({
            "id": p["id"],
            "slug": p["slug"],
            "title": p["title"],
            "html": p.get("html") or "",
            "deck": deck_from_post(p),
            "feature_image": p.get("feature_image"),
            "feature_image_alt": p.get("feature_image_alt"),
            "feature_image_caption": p.get("feature_image_caption"),
            "published_at": p["published_at"],
            "updated_at": p.get("updated_at") or p["published_at"],
            "date_label": format_date_studio(p["published_at"]),
            "read_label": reading_time_label(p.get("reading_time")),
            "rubric": rubric,
            "author": author,
            "num": num,
            "num_int": num_int,
            "tag_chips": [t["name"] for t in (p.get("tags") or []) if t["slug"] not in AGENT_TO_RUBRIC and t["slug"] not in ("archive",)][:3],
            "meta_description": p.get("meta_description") or deck_from_post(p),
        })
    return out


def post_with_related(post: dict[str, Any], all_posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        p for p in all_posts
        if p["rubric"]["id"] == post["rubric"]["id"] and p["slug"] != post["slug"]
    ][:3]


# ─── Author metadata helpers ─────────────────────────────────────────
def authors_in_use(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one entry per agent that has at least one post; sorted by article count desc."""
    counts: dict[str, list[dict[str, Any]]] = {}
    for p in posts:
        slug = p["author"]["slug"]
        counts.setdefault(slug, []).append(p)
    out = []
    contributor_num = 0
    # Order: highest count first, then alphabetical
    for slug, articles in sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        a = dict(articles[0]["author"])
        a["slug"] = slug
        # joined = oldest article date
        oldest = min(articles, key=lambda x: x["published_at"])
        a["joined_label"] = format_joined(oldest["published_at"])
        contributor_num += 1
        a["contributor_num"] = contributor_num
        out.append({"author": a, "articles": sorted(articles, key=lambda x: x["published_at"], reverse=True)})
    return out


# ─── Reserved slugs guard ────────────────────────────────────────────
RESERVED_SLUGS = {"manifesto", "craft", "dispatches", "archive", "by", "_static", "index"}


def assert_no_slug_collision(posts: list[dict[str, Any]]) -> None:
    bad = [p for p in posts if p["slug"] in RESERVED_SLUGS]
    if bad:
        slugs = ", ".join(p["slug"] for p in bad)
        raise SystemExit(f"[!!] reserved slug(s) used by Ghost posts: {slugs}. "
                         f"Either rename the post or move it.")


# ─── Render ──────────────────────────────────────────────────────────
def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=False,
        lstrip_blocks=False,
    )
    return env


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build(verbose: bool = False) -> None:
    t0 = time.time()
    print(f"[journal-build] fetching posts from {GHOST_URL}...")
    raw_posts = fetch_ghost_posts()
    print(f"[journal-build] {len(raw_posts)} posts fetched")

    posts = build_posts(raw_posts)
    assert_no_slug_collision(posts)

    env = make_env()
    build_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    common = {"build_id": build_id, "year": dt.datetime.now().year, "rubrics": RUBRICS}

    # ─ Index ─
    featured = posts[0] if posts else None
    rest = posts[1:] if posts else []
    html_index = env.get_template("index.html.j2").render(
        **common,
        page_title="The Journal",
        page_description="Editorials, craft notes, and dispatches from the studio.",
        canonical=f"{SITE_URL}/journal",
        featured=featured,
        posts=rest,
        posts_total=len(posts),
    )
    write(OUTPUT / "index.html", html_index)
    if verbose: print("  ✓ index.html")

    # ─ Each rubric page ─
    for rubric in RUBRICS:
        in_rubric = [p for p in posts if p["rubric"]["id"] == rubric["id"]]
        featured_pair = in_rubric[:2]
        rest_in_r = in_rubric[2:]
        html_rubric = env.get_template("rubric.html.j2").render(
            **common,
            page_title=rubric["title"],
            page_description=rubric["long_desc"],
            canonical=f"{SITE_URL}/journal/{rubric['id']}",
            rubric=rubric,
            featured_pair=featured_pair,
            rest=rest_in_r,
            rest_count=len(in_rubric),
        )
        write(OUTPUT / f"{rubric['id']}.html", html_rubric)
        if verbose: print(f"  ✓ {rubric['id']}.html  ({len(in_rubric)} posts)")

    # ─ Each article ─
    for p in posts:
        if p["rubric"]["id"] == "archive":
            template = "article_archive.html.j2"
            # iframe srcdoc uses HTML-attribute escaping; jinja's |e is sufficient
            p_render = dict(p)
            p_render["html_iframe"] = build_iframe_doc(p)
            ctx = {"post": p_render}
        else:
            template = "article.html.j2"
            related = post_with_related(p, posts)
            ctx = {"post": p, "related": related}
        html_article = env.get_template(template).render(
            **common,
            page_title=p["title"],
            page_description=p["meta_description"],
            canonical=f"{SITE_URL}/journal/{p['slug']}",
            og_image=p.get("feature_image"),
            og_type="article",
            **ctx,
        )
        write(OUTPUT / f"{p['slug']}.html", html_article)
        if verbose: print(f"  ✓ {p['slug']}.html")

    # ─ Author pages ─
    by_dir = OUTPUT / "by"
    if by_dir.exists():
        # clear out stale author pages
        for f in by_dir.glob("*.html"):
            f.unlink()
    for entry in authors_in_use(posts):
        html_author = env.get_template("author.html.j2").render(
            **common,
            page_title=entry["author"]["name"],
            page_description=entry["author"].get("bio") or "",
            canonical=f"{SITE_URL}/journal/by/{entry['author']['slug']}",
            author=entry["author"],
            articles=entry["articles"],
        )
        write(by_dir / f"{entry['author']['slug']}.html", html_author)
        if verbose: print(f"  ✓ by/{entry['author']['slug']}.html  ({len(entry['articles'])} articles)")

    # ─ Static assets ─
    static_dir = OUTPUT / "_static"
    static_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(STATIC / "journal.css", static_dir / "journal.css")
    if verbose: print("  ✓ _static/journal.css")
    (static_dir / "preview-shell.css").write_text(extract_preview_shell_css(), encoding="utf-8")
    if verbose: print(f"  ✓ _static/preview-shell.css  ({(static_dir / 'preview-shell.css').stat().st_size} bytes)")

    # ─ robots & sitemap ─
    write(OUTPUT / "sitemap-journal.xml", build_sitemap(posts))
    if verbose: print("  ✓ sitemap-journal.xml")

    elapsed = time.time() - t0
    print(f"[journal-build] done in {elapsed:.2f}s — {len(posts)} posts, {len(authors_in_use(posts))} authors, {len(RUBRICS)} rubrics")


def build_iframe_doc(post: dict[str, Any]) -> str:
    """Wrap newsletter HTML in a minimal dark HTML document for iframe srcdoc.

    Ghost prepends a raw <p>Digital·Humans — title.deck</p> to newsletter posts.
    We strip that since the title/deck are already in the Studio hero. We also
    force a dark body background so the iframe matches the Studio ink color.
    """
    raw = post.get("html") or ""
    # Strip the leading <p>...</p> Ghost preamble (everything up to the first
    # <!--kg-card-begin: html--> marker, which is where the actual newsletter starts)
    cleaned = raw
    marker = "<!--kg-card-begin: html-->"
    if marker in cleaned:
        cleaned = cleaned[cleaned.index(marker):]
    # Also strip any leading <p>Digital·Humans...</p> that survives (defensive)
    cleaned = re.sub(r"^\s*<p>\s*Digital[\u00B7\u002D\s]*Humans[\s\S]*?</p>\s*", "", cleaned, count=1)
    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><base target="_blank">
<style>html,body{{margin:0;padding:0;background:#0A0A0B;color:#F5F2EC;font-family:'Inter',Arial,sans-serif;}} *{{max-width:100%;}} a{{color:#C8A97E;}}</style>
</head><body>{cleaned}</body></html>"""


def build_sitemap(posts: list[dict[str, Any]]) -> str:
    items = [f"  <url><loc>{SITE_URL}/journal</loc></url>"]
    for r in RUBRICS:
        items.append(f"  <url><loc>{SITE_URL}/journal/{r['id']}</loc></url>")
    for p in posts:
        items.append(f"  <url><loc>{SITE_URL}/journal/{p['slug']}</loc><lastmod>{p['updated_at'][:10]}</lastmod></url>")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(items)}
</urlset>"""


# ─── CLI ─────────────────────────────────────────────────────────────
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="Print summary, don't write files")
    args = p.parse_args()
    if args.dry_run:
        posts = build_posts(fetch_ghost_posts())
        for p_ in posts:
            print(f"  {p_['num']}  [{p_['rubric']['id']}]  {p_['author']['slug']:<20}  {p_['title']}")
        return
    build(verbose=args.verbose)


if __name__ == "__main__":
    main()
