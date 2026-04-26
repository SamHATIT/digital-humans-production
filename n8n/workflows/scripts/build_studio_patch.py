#!/usr/bin/env python3
"""
Build the Studio-patched newsletter workflow.

Reads:
  - n8n/workflows/blog-newsletter-hebdo.before-studio.json   (canonical "before")
  - n8n/workflows/nodes/generate_newsletter_html.studio.js   (new gen_html JS)
  - n8n/workflows/nodes/generate_ghost_jwt.studio.js         (new JWT JS)

Writes:
  - n8n/workflows/blog-newsletter-hebdo.studio.json          (patched workflow)
  - n8n/workflows/blog-newsletter.json                       (canonical, mirror)

The patch:
  1. Replace the jsCode of the existing "Generate Newsletter HTML" node with
     the Studio template renderer.
  2. Append three new nodes after gen_html, on a parallel branch to the
     existing email-send chain:
       - Generate Ghost JWT  (Code, mints Admin token)
       - Lookup Archive Slug (HTTP GET, neverError)
       - Archive Exists?     (IF on posts[].length > 0)
       - Update Archive      (HTTP PUT  → idempotent upsert path)
       - Create Archive      (HTTP POST → idempotent upsert path)
  3. Wire the new branch off "Generate Newsletter HTML" so email-send and
     Ghost-archive run in parallel and don't block each other.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WF_DIR = ROOT / "n8n" / "workflows"
NODES_DIR = WF_DIR / "nodes"

SRC = WF_DIR / "blog-newsletter-hebdo.before-studio.json"
OUT_STUDIO = WF_DIR / "blog-newsletter-hebdo.studio.json"
OUT_CANON = WF_DIR / "blog-newsletter.json"


def load_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def patch_workflow(wf: dict) -> dict:
    nodes_by_id = {n["id"]: n for n in wf["nodes"]}

    # ---- 1. Replace gen_html jsCode --------------------------------------
    gen_html = nodes_by_id["gen_html"]
    if gen_html["type"] != "n8n-nodes-base.code":
        raise SystemExit("gen_html node is not a Code node — aborting")
    gen_html["parameters"]["jsCode"] = load_text(
        NODES_DIR / "generate_newsletter_html.studio.js"
    )
    # Bump position-y a touch so the new branch fans out cleanly below the
    # existing email branch.
    gen_html_x, gen_html_y = gen_html["position"]

    # ---- 2. Patch Send Newsletter to substitute {{unsubscribe_url}} ------
    # Per-recipient interpolation: replace the placeholder in the rendered
    # html with a per-recipient unsubscribe URL.
    send = nodes_by_id["send_email"]
    send["parameters"]["html"] = (
        "={{ $('Generate Newsletter HTML').first().json.html"
        ".replace('__UNSUBSCRIBE_URL__',"
        " 'https://digital-humans.fr/journal/unsubscribe?email='"
        " + encodeURIComponent($json.email)) }}"
    )

    # ---- 3. New nodes ----------------------------------------------------
    new_nodes = []

    # 3a. Generate Ghost JWT
    new_nodes.append({
        "parameters": {
            "jsCode": load_text(NODES_DIR / "generate_ghost_jwt.studio.js"),
        },
        "id": "ghost_jwt",
        "name": "Generate Ghost JWT",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [gen_html_x + 220, gen_html_y + 220],
    })

    # 3b. Lookup Archive Slug
    new_nodes.append({
        "parameters": {
            "method": "GET",
            "url": (
                "=https://blog-admin.digital-humans.fr/ghost/api/admin/"
                "posts/slug/{{ $('Generate Newsletter HTML').first().json.archive_slug }}/"
            ),
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [{
                    "name": "Authorization",
                    "value": "=Ghost {{ $('Generate Ghost JWT').first().json.token }}",
                }]
            },
            "sendQuery": True,
            "queryParameters": {
                "parameters": [
                    {"name": "fields", "value": "id,slug,updated_at,status"},
                ]
            },
            "options": {
                "response": {
                    "response": {
                        "fullResponse": False,
                        "neverError": True,
                    }
                }
            },
        },
        "id": "ghost_lookup",
        "name": "Lookup Archive Slug",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [gen_html_x + 440, gen_html_y + 220],
    })

    # 3c. Archive Exists?
    new_nodes.append({
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": True,
                    "leftValue": "",
                    "typeValidation": "strict",
                },
                "conditions": [{
                    "id": "exists",
                    "leftValue": "={{ ($json.posts || []).length }}",
                    "rightValue": 0,
                    "operator": {
                        "type": "number",
                        "operation": "gt",
                    },
                }],
                "combinator": "and",
            },
        },
        "id": "ghost_exists_if",
        "name": "Archive Exists?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [gen_html_x + 660, gen_html_y + 220],
    })

    # Body shared by create + update
    archive_body_create = {
        "posts": [{
            "title":          "={{ $('Generate Newsletter HTML').first().json.subject }}",
            "slug":           "={{ $('Generate Newsletter HTML').first().json.archive_slug }}",
            "html":           "={{ $('Generate Newsletter HTML').first().json.archive_html }}",
            "custom_excerpt": "={{ $('Generate Newsletter HTML').first().json.archive_excerpt }}",
            "tags": [{"slug": "archive"}],
            "status": "published",
            "visibility": "public",
            "feature_image": None,
        }]
    }
    archive_body_update = copy.deepcopy(archive_body_create)
    # Ghost requires the existing updated_at on PUT for collision detection.
    archive_body_update["posts"][0]["updated_at"] = "={{ $json.posts[0].updated_at }}"

    # 3d. Create Archive (POST)
    new_nodes.append({
        "parameters": {
            "method": "POST",
            "url": (
                "https://blog-admin.digital-humans.fr/ghost/api/admin/"
                "posts/?source=html"
            ),
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Authorization",
                        "value": "=Ghost {{ $('Generate Ghost JWT').first().json.token }}",
                    },
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ " + json.dumps(archive_body_create) + " }}",
            "options": {},
        },
        "id": "ghost_create",
        "name": "Create Archive",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [gen_html_x + 880, gen_html_y + 320],
    })

    # 3e. Update Archive (PUT)
    new_nodes.append({
        "parameters": {
            "method": "PUT",
            "url": (
                "=https://blog-admin.digital-humans.fr/ghost/api/admin/"
                "posts/{{ $json.posts[0].id }}/?source=html"
            ),
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [
                    {
                        "name": "Authorization",
                        "value": "=Ghost {{ $('Generate Ghost JWT').first().json.token }}",
                    },
                    {"name": "Content-Type", "value": "application/json"},
                ]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ " + json.dumps(archive_body_update) + " }}",
            "options": {},
        },
        "id": "ghost_update",
        "name": "Update Archive",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [gen_html_x + 880, gen_html_y + 120],
    })

    wf["nodes"].extend(new_nodes)

    # ---- 4. Connections --------------------------------------------------
    conns = wf["connections"]

    # gen_html now fans out to BOTH "Get Subscribers" (existing) and
    # "Generate Ghost JWT" (new archive branch).
    conns["Generate Newsletter HTML"] = {
        "main": [[
            {"node": "Get Subscribers",     "type": "main", "index": 0},
            {"node": "Generate Ghost JWT",  "type": "main", "index": 0},
        ]]
    }

    conns["Generate Ghost JWT"] = {
        "main": [[{"node": "Lookup Archive Slug", "type": "main", "index": 0}]]
    }
    conns["Lookup Archive Slug"] = {
        "main": [[{"node": "Archive Exists?", "type": "main", "index": 0}]]
    }
    conns["Archive Exists?"] = {
        "main": [
            [{"node": "Update Archive", "type": "main", "index": 0}],  # true
            [{"node": "Create Archive", "type": "main", "index": 0}],  # false
        ]
    }
    # Update/Create are leaves — no downstream connections.

    return wf


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: source workflow not found: {SRC}", file=sys.stderr)
        return 1

    wf = json.loads(load_text(SRC))
    patched = patch_workflow(wf)

    # Pretty 2-space indent, trailing newline — matches existing repo style.
    text = json.dumps(patched, indent=2, ensure_ascii=False) + "\n"
    OUT_STUDIO.write_text(text, encoding="utf-8")
    OUT_CANON.write_text(text, encoding="utf-8")

    print(f"OK  wrote {OUT_STUDIO.relative_to(ROOT)}")
    print(f"OK  wrote {OUT_CANON.relative_to(ROOT)}")
    print(f"    nodes: {len(patched['nodes'])}")
    print(f"    new : Generate Ghost JWT, Lookup Archive Slug, "
          f"Archive Exists?, Update Archive, Create Archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
