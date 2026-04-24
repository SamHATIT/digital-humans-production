#!/usr/bin/env python3
"""Phase 4 — build_docs.py avec backup, deploy atomique, purge.

Assemble la doc en 3 passes :
    1. Rendu des partials Jinja2 avec les données collectées.
    2. Substitution des markers ``<!-- PARTIAL:X -->`` dans les fragments de
       ``sections/*.html``. L'indentation du marker est préservée sur chaque
       ligne du bloc rendu.
    3. Substitution des markers ``<!-- SECTION:X -->`` dans ``shell.html``
       avec les sections assemblées.

Modes :

    python3 tools/build_docs.py
        → Écrit dans ``docs/refonte/index.html`` avec backup préalable
          ``index.html.bak.YYYYMMDD_HHMMSS``. Purge les backups > 7 jours.
          Imprime un diff contre l'ancienne version.

    python3 tools/build_docs.py --dry-run
        → Écrit dans ``docs/refonte/index.generated.html`` (comportement
          historique). Pas de backup, pas de modification de l'index.html
          canonique. Diff imprimé. Utile pour tester sans impact.

    python3 tools/build_docs.py --deploy
        → Build normal (write + backup dans le repo) PUIS copie atomique
          vers /var/www/digital-humans.fr/docs/refonte/index.html avec
          backup de la version /var/www avant écrasement. Smoke test HTTP
          post-deploy. Purge /var/www des backups > 7 jours.

    python3 tools/build_docs.py --strict
        → Échoue au premier marker manquant ou surnuméraire. Combinable
          avec les autres flags.

    python3 tools/build_docs.py --no-backup
        → Skippe la création de backup (utile pour rebuild rapide sans
          pollution). Incompatible avec --deploy (le backup /var/www
          est toujours créé avant écrasement).

    python3 tools/build_docs.py --purge-days N
        → Change la rétention des backups (défaut 7). N=0 désactive la purge.
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

# Permet l'import du package local "lib" quand on lance depuis le repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

from lib import collect, render  # noqa: E402

DOCS = REPO_ROOT / "docs" / "refonte"
SECTIONS_DIR = DOCS / "sections"
SHELL = DOCS / "templates" / "shell.html"
INDEX = DOCS / "index.html"
GENERATED = DOCS / "index.generated.html"

DEPLOY_DIR = Path("/var/www/digital-humans.fr/docs/refonte")
DEPLOY_INDEX = DEPLOY_DIR / "index.html"
SMOKE_URL = "https://digital-humans.fr/docs/refonte/"

BACKUP_GLOB = "index.html.bak.*"


# Mapping partial → (template_name, context_builder).
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
    "database_tables": (
        "database_tables",
        lambda d: {
            "groups": d["database"]["groups"],
            "total_tables": d["database"]["total_tables"],
            "orphan_tables": d["database"]["orphan_tables"],
        },
    ),
    "frontend_pages_table": (
        "frontend_pages_table",
        lambda d: {
            "pages": d["frontend"]["pages"],
            "total_routes": d["frontend"]["total_routes"],
            "orphan_yaml": d["frontend"]["orphan_yaml"],
        },
    ),
    "api_endpoints_table": (
        "api_endpoints_table",
        lambda d: {
            "groups": d["api"]["groups"],
            "total_endpoints": d["api"]["total_endpoints"],
            "unmapped_files": d["api"]["unmapped_files"],
        },
    ),
}


def replace_marker_preserving_indent(
    content: str, marker_name: str, rendered: str, marker_prefix: str = "PARTIAL",
    reindent: bool = True,
) -> tuple[str, bool]:
    """Remplace ``{indent}<!-- {marker_prefix}:{marker_name} -->\\n`` dans content.

    L'indentation du marker est préservée sur chaque ligne non-vide du bloc rendu
    si ``reindent=True`` (pour les PARTIALS à colonne 0). Si ``reindent=False``
    (pour les SECTIONS déjà indentées par split_sections), on fait une simple
    substitution textuelle.
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
                indented.append("")
            else:
                indented.append(indent + line)
        replacement = "\n".join(indented) + "\n"
    else:
        replacement = rendered if rendered.endswith("\n") else rendered + "\n"

    return pattern.sub(replacement, content, count=1), True


def collect_all() -> dict:
    """Exécute les 6 fonctions de collecte."""
    return {
        "agents": collect.collect_agents(),
        "llm_profiles": collect.collect_llm_profiles(),
        "rag": collect.collect_rag_stats(),
        "services": collect.collect_services(),
        "problems": collect.collect_problems(),
        "timeline": collect.collect_timeline(),
        "database": collect.collect_database_tables(),
        "frontend": collect.collect_frontend_pages(),
        "api": collect.collect_api_endpoints(),
    }


def render_all_partials(data: dict) -> dict[str, str]:
    """Rend chaque partial avec son contexte."""
    out = {}
    for name, (tpl_name, ctx_builder) in PARTIALS.items():
        ctx = ctx_builder(data)
        out[name] = render.render_partial(tpl_name, ctx)
    return out


def assemble_sections(rendered_partials: dict[str, str], strict: bool = False) -> dict[str, str]:
    """Pour chaque section, substitue les markers PARTIAL."""
    assembled = {}
    used_partials: set[str] = set()
    unknown_re = re.compile(r"<!-- PARTIAL:([a-z0-9_]+) -->")

    for path in sorted(SECTIONS_DIR.glob("*.html")):
        content = path.read_text()
        markers = set(unknown_re.findall(content))
        unknown = markers - rendered_partials.keys()
        if unknown:
            msg = f"{path.name}: markers inconnus : {sorted(unknown)}"
            if strict:
                raise RuntimeError(msg)
            print(f"  ⚠ {msg}", file=sys.stderr)

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
    """Substitue ``<!-- SECTION:X -->`` dans shell.html."""
    shell = SHELL.read_text()
    for sec_id, content in sections.items():
        new_shell, replaced = replace_marker_preserving_indent(
            shell, sec_id, content, marker_prefix="SECTION", reindent=False,
        )
        if replaced:
            shell = new_shell
        else:
            msg = f"Section '{sec_id}' n'a pas de marker dans shell.html"
            if strict:
                raise RuntimeError(msg)
            print(f"  ⚠ {msg}", file=sys.stderr)

    leftover = re.findall(r"<!-- SECTION:([a-z0-9\-]+) -->", shell)
    if leftover:
        msg = f"Markers SECTION non consommés : {leftover}"
        if strict:
            raise RuntimeError(msg)
        print(f"  ⚠ {msg}", file=sys.stderr)

    return shell


def diff_report(reference: Path, generated: str, max_lines: int = 40) -> int:
    """Imprime un diff unifié et retourne le nombre de lignes différentes."""
    if not reference.exists():
        print(f"  ℹ Pas de référence ({reference.name}), diff skippé")
        return 0
    ref = reference.read_text()
    if ref == generated:
        print(f"\n✅ Aucune différence avec {reference.name}")
        return 0
    diff_lines = list(difflib.unified_diff(
        ref.splitlines(keepends=True),
        generated.splitlines(keepends=True),
        fromfile=reference.name,
        tofile="generated",
        n=2,
    ))
    changed = sum(
        1 for l in diff_lines
        if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))
    )
    print(f"\n📝 {changed} lignes modifiées vs {reference.name}")
    if changed > 0 and max_lines > 0:
        print(f"   Aperçu (max {max_lines} lignes) :\n")
        for line in diff_lines[:max_lines]:
            print(line, end="")
        if len(diff_lines) > max_lines:
            print(f"\n   ... ({len(diff_lines) - max_lines} lignes de diff omises)")
    return changed


# ─────────────────────────────────────────────────────────────────────────
# Phase 4 additions : backup, purge, atomic deploy, smoke test
# ─────────────────────────────────────────────────────────────────────────

def backup_file(path: Path, dry: bool = False) -> Path | None:
    """Crée un backup ``{path}.bak.YYYYMMDD_HHMMSS`` et retourne son chemin.

    Retourne None si le fichier source n'existe pas (rien à sauvegarder).
    ``dry=True`` affiche ce qui serait fait sans l'exécuter.
    """
    if not path.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_name(f"{path.name}.bak.{ts}")
    if dry:
        print(f"  · [dry] backup {path.name} → {bak.name}")
        return bak
    shutil.copy2(path, bak)
    print(f"  · backup : {bak.name}")
    return bak


def purge_backups(directory: Path, glob_pattern: str, days: int) -> int:
    """Supprime les backups matching glob_pattern plus vieux que ``days`` jours.

    Retourne le nombre de fichiers supprimés. ``days=0`` désactive la purge.
    """
    if days <= 0:
        return 0
    if not directory.exists():
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for bak in directory.glob(glob_pattern):
        try:
            if bak.stat().st_mtime < cutoff:
                bak.unlink()
                removed += 1
        except OSError as e:
            print(f"  ⚠ échec suppression {bak.name}: {e}", file=sys.stderr)
    if removed:
        print(f"  · purge : {removed} backup(s) > {days}j supprimé(s) dans {directory}")
    return removed


def atomic_write(dst: Path, content: str) -> None:
    """Écrit ``content`` dans ``dst`` de manière atomique.

    Écrit dans un tmpfile dans le MÊME répertoire que dst (pour que
    ``os.replace`` soit atomique — pas de cross-device), puis rename.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{dst.name}.tmp.", dir=str(dst.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        # Préserver les permissions du fichier existant si possible
        if dst.exists():
            shutil.copymode(dst, tmp_path)
        os.replace(tmp_path, dst)
    except Exception:
        # Cleanup en cas d'échec
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def smoke_test(url: str, timeout: int = 10) -> tuple[bool, str]:
    """HEAD request via curl, retourne (ok, message)."""
    try:
        r = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 2,
        )
        code = r.stdout.strip()
        ok = code == "200"
        return ok, f"HTTP {code}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, "curl not installed"
    except Exception as e:
        return False, f"erreur : {e}"


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build docs/refonte/index.html from sources.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--strict", action="store_true",
                    help="Échoue si un marker est manquant ou surnuméraire")
    ap.add_argument("--dry-run", action="store_true",
                    help="Écrit dans index.generated.html (pas index.html), pas de backup")
    ap.add_argument("--deploy", action="store_true",
                    help="Après le build, copie atomique vers /var/www + smoke test")
    ap.add_argument("--no-backup", action="store_true",
                    help="Skippe le backup local (incompatible avec --deploy pour /var/www)")
    ap.add_argument("--purge-days", type=int, default=7,
                    help="Rétention backups (jours, défaut 7, 0 pour désactiver)")
    args = ap.parse_args()

    # 1. Collecte
    print("→ Collecte des données…")
    data = collect_all()
    print(f"  · agents        : {len(data['agents']['agents'])}")
    print(f"  · llm tiers     : {len(data['llm_profiles']['tiers'])} (profile : {data['llm_profiles']['active_profile']})")
    print(f"  · rag chunks    : {data['rag']['total_chunks']:,} ({len(data['rag']['collections'])} collections)")
    print(f"  · services      : {len(data['services']['services'])}")
    print(f"  · problems      : {data['problems']['stats']}")
    print(f"  · timeline      : {len(data['timeline']['entries'])} entrées")
    print(f"  · db tables     : {data['database']['total_tables']} ({len(data['database']['groups'])} groupes)")
    print(f"  · fe pages      : {len(data['frontend']['pages'])} ({data['frontend']['total_routes']} routes)")
    print(f"  · api endpoints : {data['api']['total_endpoints']} ({len(data['api']['groups'])} modules)")

    # 2. Rendu
    print("\n→ Rendu des partials…")
    rendered = render_all_partials(data)
    for name, html in rendered.items():
        print(f"  · {name:30s} → {len(html):5d} chars")

    # 3. Assemblage
    print("\n→ Assemblage…")
    sections = assemble_sections(rendered, strict=args.strict)
    final = assemble_shell(sections, strict=args.strict)
    print(f"  · HTML final : {len(final):,} chars")

    # 4. Écriture
    print()
    if args.dry_run:
        # Mode preview : écrit dans index.generated.html sans toucher index.html
        GENERATED.write_text(final)
        print(f"→ [dry-run] écrit dans {GENERATED.name}")
        diff_report(INDEX, final)
        return 0

    # Mode normal : backup puis write dans index.html
    print("→ Écriture dans index.html")
    if not args.no_backup:
        backup_file(INDEX)
    else:
        print("  · [--no-backup] backup skippé")

    # Diff contre l'ancienne version AVANT de l'écraser (si backup) ou
    # vs l'actuel si pas de backup. On lit l'ancien avant write.
    old = INDEX.read_text() if INDEX.exists() else ""
    atomic_write(INDEX, final)
    print(f"  · {INDEX.name} : {len(final):,} chars")

    if old:
        diff_changed = sum(
            1 for l in difflib.unified_diff(old.splitlines(), final.splitlines())
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))
        )
        print(f"  · {diff_changed} lignes modifiées vs ancien index.html")

    purge_backups(DOCS, BACKUP_GLOB, args.purge_days)

    # 5. Deploy vers /var/www si demandé
    if args.deploy:
        print("\n→ Déploiement /var/www")
        if not DEPLOY_DIR.exists():
            print(f"  ❌ répertoire cible inexistant : {DEPLOY_DIR}", file=sys.stderr)
            return 2
        backup_file(DEPLOY_INDEX)  # backup /var/www AVANT écrasement
        atomic_write(DEPLOY_INDEX, final)
        print(f"  · {DEPLOY_INDEX} : {len(final):,} chars")
        purge_backups(DEPLOY_DIR, BACKUP_GLOB, args.purge_days)

        # Smoke test
        print("\n→ Smoke test HTTP")
        ok, msg = smoke_test(SMOKE_URL)
        if ok:
            print(f"  ✅ {SMOKE_URL} : {msg}")
        else:
            print(f"  ❌ {SMOKE_URL} : {msg}", file=sys.stderr)
            return 3

    print("\n✅ Build terminé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
