#!/usr/bin/env python3
"""Phase 2 — split index.html en fragments sections/ + templates/shell.html.

Stratégie :
- Parse ligne par ligne pour repérer les sections top-level.
- Section = <div id="..." class="section"> ... </div> au niveau racine du <main>.
- La fermeture est trouvée par comptage d'imbrication <div>/</div>.
- Chaque section est extraite telle quelle dans sections/<id>.html (pas de reformat).
- templates/shell.html = index.html avec chaque section remplacée par un marker
  <!-- SECTION:<id> --> (consommé par build_docs.py en Phase 4).
- Un rebuild de contrôle concatène shell + fragments et compare byte-à-byte
  à l'original. Zéro diff attendu.
"""
import re
import sys
import difflib
from pathlib import Path

ROOT = Path("/root/workspace/digital-humans-production")
DOCS = ROOT / "docs/refonte"
SRC = DOCS / "index.html"
SECTIONS_DIR = DOCS / "sections"
SHELL = DOCS / "templates/shell.html"
REBUILT = DOCS / "index.rebuilt.html"

SECTION_RE = re.compile(
    r'^(\s*)<div id="([a-z0-9\-]+)" class="section(?: active)?"\s*>\s*$'
)
OPEN_DIV_RE = re.compile(r'<div\b')
CLOSE_DIV_RE = re.compile(r'</div\s*>')


def find_sections(lines):
    sections = []
    i = 0
    while i < len(lines):
        m = SECTION_RE.match(lines[i])
        if m:
            indent = m.group(1)
            sec_id = m.group(2)
            start = i
            depth = 1
            j = i + 1
            while j < len(lines):
                opens = len(OPEN_DIV_RE.findall(lines[j]))
                closes = len(CLOSE_DIV_RE.findall(lines[j]))
                depth += opens - closes
                if depth == 0:
                    break
                j += 1
            if depth != 0:
                raise RuntimeError(
                    f"Section {sec_id} démarrée ligne {start+1} non refermée"
                )
            end = j
            sections.append((sec_id, start, end, indent))
            i = end + 1
        else:
            i += 1
    return sections


def main():
    text = SRC.read_text()
    lines = text.splitlines(keepends=True)
    sections = find_sections(lines)
    print(f"Sections détectées : {len(sections)}")
    for sid, s, e, _ in sections:
        print(f"  - {sid:15s} lignes {s+1:4d}..{e+1:4d}  ({e-s+1:3d} lignes)")

    SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    SHELL.parent.mkdir(parents=True, exist_ok=True)

    # 1) Ecrire les fragments
    for sid, s, e, _ in sections:
        frag = ''.join(lines[s:e+1])
        (SECTIONS_DIR / f"{sid}.html").write_text(frag)

    # 2) Construire le shell
    shell_lines = []
    sec_map = {s: (sid, e, ind) for sid, s, e, ind in sections}
    i = 0
    while i < len(lines):
        if i in sec_map:
            sid, e, ind = sec_map[i]
            shell_lines.append(f"{ind}<!-- SECTION:{sid} -->\n")
            i = e + 1
        else:
            shell_lines.append(lines[i])
            i += 1
    SHELL.write_text(''.join(shell_lines))

    # 3) Rebuild + compare byte-à-byte
    rebuilt = SHELL.read_text()
    for sid, s, e, ind in sections:
        frag = (SECTIONS_DIR / f"{sid}.html").read_text()
        marker = f"{ind}<!-- SECTION:{sid} -->\n"
        if marker not in rebuilt:
            print(f"  ⚠ marker absent pour {sid}")
            return 2
        rebuilt = rebuilt.replace(marker, frag, 1)

    REBUILT.write_text(rebuilt)

    if rebuilt == text:
        print("\n✅ Rebuild IDENTIQUE à l'original (byte-à-byte)")
        print(f"   Fragments   : {SECTIONS_DIR} ({len(sections)} fichiers)")
        print(f"   Shell       : {SHELL} ({len(shell_lines)} lignes)")
        REBUILT.unlink()
        return 0

    print("\n❌ DIFFÉRENCES détectées :")
    diff = difflib.unified_diff(
        text.splitlines(keepends=True),
        rebuilt.splitlines(keepends=True),
        fromfile='original', tofile='rebuilt', n=2
    )
    for d in list(diff)[:80]:
        print(d, end='')
    print(f"\n   (rebuild divergent écrit dans {REBUILT})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
