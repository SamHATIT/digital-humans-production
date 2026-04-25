#!/usr/bin/env python3
"""build_sds.py — Génère un SDS HTML depuis la DB pour une execution donnée.

Itération 1 : juste hero + TOC instrumentés. Les 12 sections de contenu
restent identiques au HTML de référence pour le moment. Au fil des
itérations on les transformera en partials Jinja2 paramétrés.

Usage :
    python3 tools/build_sds.py --execution-id 146
    python3 tools/build_sds.py --execution-id 146 --output /tmp/sds.html
    python3 tools/build_sds.py --execution-id 146 --check  # valide sans écrire

Modes futurs (pas encore implémentés) :
    --snapshot --project-id N --version N  # crée une row sds_versions
    --serve                                # mode endpoint pour live preview
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ajouter tools/ au path pour importer lib.collect_sds
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from jinja2 import Environment, FileSystemLoader, StrictUndefined  # noqa: E402
from lib.collect_sds import build_render_context  # noqa: E402


TEMPLATES_DIR = REPO_ROOT / "docs" / "sds" / "templates"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "sds" / "rendered.html"


def humanize(s):
    """Convertit snake_case en 'espace separe', avec quelques cas speciaux.
    
    Utilise par le macro render_value du partial 6.9 Integration Points
    pour transformer les cles JSON en libelles lisibles.
    """
    if not isinstance(s, str):
        return s
    SPECIAL = {
        "uc_refs": "UC refs",
        "url_pattern": "url pattern",
        "payload_format": "payload format",
        "key_fields": "key fields",
        "response_codes": "response codes",
        "rate_limits": "rate limits",
        "named_credential": "named credential",
        "endpoint_spec": "endpoint spec",
        "error_handling": "error handling",
        "retry_strategy": "retry strategy",
        "dead_letter": "dead letter",
        "requests_per_day": "requests per day",
        "requests_per_hour": "requests per hour",
        "requests_per_minute": "requests per minute",
    }
    return SPECIAL.get(s, s.replace("_", " "))


def render(execution_id: int) -> str:
    """Charge le contexte depuis la DB, rend le shell, retourne le HTML."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        # StrictUndefined : lever une erreur si une variable n'existe pas
        # (mieux que de laisser passer silencieusement un trou dans le rendu)
        undefined=StrictUndefined,
        autoescape=False,  # on génère du HTML structuré, pas un site multi-utilisateurs
        trim_blocks=False,
        lstrip_blocks=False,
    )
    env.filters["humanize"] = humanize
    template = env.get_template("sds_shell.html.j2")
    
    context = build_render_context(execution_id)
    return template.render(**context)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execution-id", type=int, required=True, help="ID de l'execution dans la DB")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=f"Chemin de sortie (défaut: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})")
    parser.add_argument("--check", action="store_true", help="Rendre en mémoire seulement, ne pas écrire")
    parser.add_argument("--diff-reference", action="store_true",
                        help="Comparer avec _reference_logifleet_146.html (utile pour exec 146)")
    args = parser.parse_args()
    
    print(f"→ Build SDS pour execution #{args.execution_id}")
    
    try:
        html = render(args.execution_id)
    except Exception as e:
        print(f"❌ Erreur de rendu : {type(e).__name__}: {e}")
        return 1
    
    print(f"  · HTML rendu : {len(html):,} chars")
    
    if args.check:
        print("✅ Rendu OK (mode --check, pas d'écriture)")
        return 0
    
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"  · Écrit dans : {args.output.relative_to(REPO_ROOT)}")
    
    if args.diff_reference:
        ref = TEMPLATES_DIR / "_reference_logifleet_146.html"
        if ref.exists():
            ref_html = ref.read_text()
            print()
            print(f"=== Diff vs référence ({ref.name}) ===")
            print(f"  référence : {len(ref_html):,} chars")
            print(f"  rendu     : {len(html):,} chars")
            print(f"  delta     : {len(html) - len(ref_html):+,} chars")
            
            # Diff structurel grossier
            import difflib
            ref_lines = ref_html.splitlines()
            new_lines = html.splitlines()
            print(f"  lignes    : {len(ref_lines)} vs {len(new_lines)}")
            
            diff = list(difflib.unified_diff(ref_lines, new_lines, lineterm="", n=0))
            change_lines = [l for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
            print(f"  diff lines: {len(change_lines)} lignes modifiées")
        else:
            print(f"⚠️  Référence introuvable : {ref}")
    
    print("\n✅ Build SDS terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
