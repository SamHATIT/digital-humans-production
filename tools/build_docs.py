#!/usr/bin/env python3
"""Phase 3 — build_docs.py minimal.

Assemble la doc en 3 passes :

    1. Rendu des partials Jinja2 avec les données collectées.
    2. Substitution des markers ``<!-- PARTIAL:X -->`` dans les fragments de
       ``sections/*.html``. L'indentation du marker est préservée sur chaque
       ligne du bloc rendu.
    3. Substitution des markers ``<!-- SECTION:X -->`` dans ``shell.html``
       avec les sections assemblées. (Marker format posé par split_sections.py.)

Le HTML final est écrit dans ``docs/refonte/index.generated.html`` (pas
d'écrasement de ``index.html`` en Phase 3 — c'est Phase 4 qui ajoutera
backup + copy atomique vers /var/www). Un diff unifié contre ``index.html``
est imprimé pour vérification manuelle.

Usage:
    python3 tools/build_docs.py             # build + diff contre index.html
    python3 tools/build_docs.py --strict    # échoue si markers manquants ou surnuméraires
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

# Permet l'import du package local "lib" quand on lance depuis le repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from lib import collect, render  # noqa: E402

DOCS = REPO_ROOT / "docs" / "refonte"
SECTIONS_DIR = DOCS / "sections"
SHELL = DOCS / "templates" / "shell.html"
OUTPUT = DOCS / "index.generated.html"
REFERENCE = DOCS / "index.html"


# Mapping partial → (template_name, context_builder).
# context_builder reçoit le dict `data` global et retourne le contexte du template.
PARTIALS: dict[str, tuple[str, callable]] = {
    "problems_status_cards": (
        "problems_status_cards",
        lambda d: {
            "by_status": d["problems"]["by_status"],
            "stats": d["problems"]["stats"],
        },
    ),
    "rag_collections_table": (
        "rag_collections_table",
        lambda d: {
            "collections": d["rag"]["collections"],
            "total_chunks": d["rag"]["total_chunks"],
            "orphan_collections": d["rag"]["orphan_collections"],
        },
    ),
    "infra_services_table": (
        "infra_services_table",
        lambda d: {"services": d["services"]["services"]},
    ),
    "agents_table": (
        "agents_table",
        lambda d: {
            "agents": d["agents"]["agents"],
            "llm_profiles": d["llm_profiles"],
        },
    ),
    "llm_routing_table": (
        "llm_routing_table",
        lambda d: {
            "llm_profiles": d["llm_profiles"],
            "agents": d["agents"]["agents"],
        },
    ),
    "journal_timeline": (
        "journal_timeline",
        lambda d: {"entries": d["timeline"]["entries"]},
    ),
}


def replace_marker_preserving_indent(
    content: str, marker_name: str, rendered: str, marker_prefix: str = "PARTIAL",
    reindent: bool = True,
) -> tuple[str, bool]:
    """Remplace ``{indent}<!-- {marker_prefix}:{marker_name} -->\\n`` dans content.

    L'indentation du marker est préservée sur chaque ligne non-vide du bloc rendu.

    Returns:
        Tuple ``(content_modifié, True)`` si le marker a été trouvé et substitué,
        ``(content, False)`` sinon.
    """
    pattern = re.compile(
        r"^([ \t]*)<!-- " + re.escape(marker_prefix) + r":"
        + re.escape(marker_name) + r" -->\n?",
        re.MULTILINE,
    )
    m = pattern.search(content)
    if not m:
        return content, False
    indent = m.group(1)

    if reindent:
        rendered = rendered.rstrip("\n")
        lines = rendered.split("\n")
        indented = []
        for line in lines:
            if line.strip() == "":
                indented.append("")  # Lignes vides → vraiment vides (pas d'indent-trail)
            else:
                indented.append(indent + line)
        replacement = "\n".join(indented) + "\n"
    else:
        # Le contenu injecté porte déjà son indentation d'origine (cas SECTION,
        # cohérent avec split_sections.py). On substitue à l'identique, avec
        # un simple '\n' final si le rendu n'en a pas.
        replacement = rendered if rendered.endswith("\n") else rendered + "\n"

    return pattern.sub(replacement, content, count=1), True


def collect_all() -> dict:
    """Exécute les 6 fonctions de collecte et retourne un dict global."""
    return {
        "agents": collect.collect_agents(),
        "llm_profiles": collect.collect_llm_profiles(),
        "rag": collect.collect_rag_stats(),
        "services": collect.collect_services(),
        "problems": collect.collect_problems(),
        "timeline": collect.collect_timeline(),
    }


def render_all_partials(data: dict) -> dict[str, str]:
    """Rend chaque partial avec son contexte. Retourne {partial_name: rendered_html}."""
    out = {}
    for name, (tpl_name, ctx_builder) in PARTIALS.items():
        ctx = ctx_builder(data)
        out[name] = render.render_partial(tpl_name, ctx)
    return out


def assemble_sections(
    rendered_partials: dict[str, str], strict: bool = False
) -> dict[str, str]:
    """Pour chaque ``sections/*.html``, substitue tous les markers PARTIAL présents.

    Args:
        rendered_partials: Dict {partial_name: html_rendu}.
        strict: Si True, échoue au moindre marker présent dans un fragment
            mais absent de ``rendered_partials`` (incohérence marker/code).

    Returns:
        Dict {section_id: contenu_assemblé}.
    """
    assembled = {}
    used_partials: set[str] = set()
    unknown_markers_re = re.compile(r"<!-- PARTIAL:([a-z0-9_]+) -->")

    for path in sorted(SECTIONS_DIR.glob("*.html")):
        content = path.read_text()
        # Détecter les markers présents, alerter si certains sont inconnus
        markers_in_file = set(unknown_markers_re.findall(content))
        unknown = markers_in_file - rendered_partials.keys()
        if unknown:
            msg = f"{path.name}: markers inconnus : {sorted(unknown)}"
            if strict:
                raise RuntimeError(msg)
            print(f"  ⚠ {msg}", file=sys.stderr)

        # Substituer chaque partial connu
        for name, html in rendered_partials.items():
            new_content, replaced = replace_marker_preserving_indent(
                content, name, html, marker_prefix="PARTIAL"
            )
            if replaced:
                content = new_content
                used_partials.add(name)

        assembled[path.stem] = content

    unused = set(rendered_partials) - used_partials
    if unused:
        msg = f"Partials rendus mais non consommés : {sorted(unused)}"
        if strict:
            raise RuntimeError(msg)
        print(f"  ⚠ {msg}", file=sys.stderr)

    return assembled


def assemble_shell(sections: dict[str, str], strict: bool = False) -> str:
    """Substitue chaque ``<!-- SECTION:X -->`` dans shell.html par le fragment correspondant."""
    shell = SHELL.read_text()
    used: set[str] = set()
    for sec_id, content in sections.items():
        new_shell, replaced = replace_marker_preserving_indent(
            shell, sec_id, content, marker_prefix="SECTION", reindent=False,
        )
        if replaced:
            shell = new_shell
            used.add(sec_id)
        else:
            msg = f"Section '{sec_id}' n'a pas de marker dans shell.html"
            if strict:
                raise RuntimeError(msg)
            print(f"  ⚠ {msg}", file=sys.stderr)

    # Vérifier qu'il ne reste aucun marker SECTION non consommé
    leftover = re.findall(r"<!-- SECTION:([a-z0-9\-]+) -->", shell)
    if leftover:
        msg = f"Markers SECTION non consommés dans le shell : {leftover}"
        if strict:
            raise RuntimeError(msg)
        print(f"  ⚠ {msg}", file=sys.stderr)

    return shell


def diff_report(reference: Path, generated: str, max_lines: int = 60) -> int:
    """Imprime un diff unifié et retourne le nombre de lignes différentes (±)."""
    if not reference.exists():
        print(f"  ℹ Pas de fichier de référence ({reference}), diff skippé")
        return 0
    ref = reference.read_text()
    if ref == generated:
        print("\n✅ Aucune différence avec index.html")
        return 0
    diff_lines = list(difflib.unified_diff(
        ref.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=str(reference.name),
        tofile="generated",
        n=2,
    ))
    changed = sum(1 for l in diff_lines if l.startswith(("+", "-")) and not l.startswith(("+++", "---")))
    print(f"\n📝 Différences détectées ({changed} lignes modifiées)")
    print(f"   Aperçu (max {max_lines} lignes) :\n")
    for line in diff_lines[:max_lines]:
        print(line, end="")
    if len(diff_lines) > max_lines:
        print(f"\n   ... ({len(diff_lines) - max_lines} lignes de diff suivantes omises)")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description="Build docs/refonte/index.html from sources.")
    ap.add_argument("--strict", action="store_true",
                    help="Échoue si un marker est manquant ou surnuméraire")
    args = ap.parse_args()

    print("→ Collecte des données…")
    data = collect_all()
    print(f"  · agents        : {len(data['agents']['agents'])}")
    print(f"  · llm tiers     : {len(data['llm_profiles']['tiers'])} (profile : {data['llm_profiles']['active_profile']})")
    print(f"  · rag chunks    : {data['rag']['total_chunks']:,} ({len(data['rag']['collections'])} collections)")
    print(f"  · services      : {len(data['services']['services'])}")
    print(f"  · problems      : {data['problems']['stats']}")
    print(f"  · timeline      : {len(data['timeline']['entries'])} entrées")

    print("\n→ Rendu des partials…")
    rendered = render_all_partials(data)
    for name, html in rendered.items():
        print(f"  · {name:30s} → {len(html):5d} chars")

    print("\n→ Assemblage des sections…")
    sections = assemble_sections(rendered, strict=args.strict)

    print("\n→ Assemblage du shell…")
    final = assemble_shell(sections, strict=args.strict)

    OUTPUT.write_text(final)
    print(f"\n✅ Sortie écrite : {OUTPUT} ({len(final):,} chars)")

    diff_report(REFERENCE, final)
    return 0


if __name__ == "__main__":
    sys.exit(main())
