#!/usr/bin/env python3
"""Alimente timeline.yaml a partir des messages de commit.

Pourquoi ce script existe : la documentation technique de la console d'admin
etait figee au 12/07 alors que le code avait continue d'evoluer. Le contenu
redactionnel des sections (architecture, agents, flux) merite d'etre ecrit a
la main, mais le JOURNAL, lui, est deja ecrit — dans les messages de commit,
qui portent la cause, l'effet et la reference de decision.

Ce script ne genere donc AUCUN texte : il regroupe et met en forme l'existant.
Aucun modele de langage, aucun risque d'invention.

Usage :
    python3 tools/journal_from_git.py --depuis 2026-06-01
    python3 tools/journal_from_git.py --depuis 2026-06-01 --ecrire
"""
import argparse, re, subprocess, sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
TIMELINE = RACINE / "docs/refonte/sources/timeline.yaml"

MOIS = {1:"janvier",2:"fevrier",3:"mars",4:"avril",5:"mai",6:"juin",
        7:"juillet",8:"aout",9:"septembre",10:"octobre",11:"novembre",12:"decembre"}

# Commits sans valeur documentaire : bruit de maintenance.
IGNORE = re.compile(r"^(chore|merge|wip|typo|bump|Fusion session)", re.I)

def commits(depuis):
    fmt = "%H\x1f%ad\x1f%s\x1f%b\x1e"
    r = subprocess.run(
        ["git", "log", f"--since={depuis}", "--date=short", f"--pretty=format:{fmt}", "--no-merges"],
        cwd=RACINE, capture_output=True, text=True, timeout=60)
    out = []
    for bloc in r.stdout.split("\x1e"):
        if not bloc.strip():
            continue
        p = bloc.strip().split("\x1f")
        if len(p) < 3:
            continue
        sha, date, sujet = p[0][:7], p[1], p[2]
        corps = p[3].strip() if len(p) > 3 else ""
        if IGNORE.match(sujet):
            continue
        out.append({"sha": sha, "date": date, "sujet": sujet, "corps": corps})
    return out

def echapper(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def mettre_en_forme(sujet):
    """Met en valeur les references (FIX-XXX-001, DEC-2026-XXXX-XX) sans rien reecrire."""
    s = echapper(sujet)
    s = re.sub(r"\b((?:FIX|FEAT|PATCH|OBSERV)-[A-Z0-9]+-\d+)", r"<code>\1</code>", s)
    s = re.sub(r"\b(DEC-\d{4}-\d{4}-\d{2})", r"<strong>\1</strong>", s)
    return s

def synthetiser(depuis):
    par_jour = defaultdict(list)
    for c in commits(depuis):
        par_jour[c["date"]].append(c)

    entrees = []
    for date in sorted(par_jour):
        lot = par_jour[date]
        d = datetime.strptime(date, "%Y-%m-%d")
        label = f"{d.day} {MOIS[d.month]} {d.year}"

        # Le titre reprend le commit le plus substantiel du jour, jamais invente.
        principal = max(lot, key=lambda c: len(c["sujet"]))
        titre = echapper(principal["sujet"].split(" : ")[0].split(". ")[0])[:110]

        lignes = "".join(
            f"<li>{mettre_en_forme(c['sujet'])} <span class=\"sha\">{c['sha']}</span></li>"
            for c in lot)
        desc = (f"<strong>{len(lot)} commit(s).</strong> "
                f"<ul class=\"journal-commits\">{lignes}</ul>")

        entrees.append({"date": date, "label": label, "status": "done",
                        "title": titre, "description": desc, "auto": True})
    return entrees

def rendre_yaml(entrees):
    def q(t):
        return '"' + t.replace("\\", "\\\\").replace('"', '\\"') + '"'
    out = []
    for e in entrees:
        out.append(f"\n  # genere automatiquement depuis git — ne pas editer a la main")
        out.append(f"  - date: {e['date']}")
        out.append(f"    label: {q(e['label'])}")
        out.append(f"    status: {e['status']}")
        out.append(f"    title: {q(e['title'])}")
        out.append(f"    description: {q(e['description'])}")
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--depuis", default="2026-06-01")
    ap.add_argument("--ecrire", action="store_true")
    a = ap.parse_args()

    entrees = synthetiser(a.depuis)
    if not entrees:
        print("Aucun commit documentable depuis", a.depuis)
        return 0

    print(f"{len(entrees)} journee(s) de travail synthetisee(s) depuis {a.depuis}")
    for e in entrees[-5:]:
        print(f"  {e['label']:<22} {e['title'][:70]}")

    if not a.ecrire:
        print("\n(mode apercu — ajoutez --ecrire pour appliquer)")
        return 0

    src = TIMELINE.read_text(encoding="utf-8")
    marqueur = "# --- ENTREES AUTO (git) ---"
    if marqueur in src:
        src = src.split(marqueur)[0].rstrip()
    else:
        # Retire l'entree "Prochain" pour la replacer apres les entrees auto.
        src = src.rstrip()
    TIMELINE.write_text(src + "\n\n" + marqueur + "\n" + rendre_yaml(entrees) + "\n",
                        encoding="utf-8")
    print(f"\ntimeline.yaml mis a jour : {len(entrees)} entrees auto")
    return 0

if __name__ == "__main__":
    sys.exit(main())
