#!/usr/bin/env python3
"""Verifie que le prompt de Marcus et la table de routage disent la meme chose.

POURQUOI CE SCRIPT EXISTE (10/08/2026, sur une remarque de Sam : « on aurait
besoin d'une boucle d'amelioration ici, comme une lecon pour l'avenir »).

Marcus produit un WBS ou chaque tache porte un `task_type`. Ce vocabulaire est
declare a DEUX endroits qui doivent concorder :

  1. `backend/prompts/agents/marcus_architect.yaml` — ce qu'on ANNONCE a Marcus
  2. `backend/app/services/phased_build_executor.py` — ce que le code SAIT router

Quand les deux divergent, Marcus produit un type valide de son point de vue que
le code ne sait pas router. La tache retombe alors sur le repli par agent — qui
fonctionne, mais classe approximativement, et le defaut est SILENCIEUX.

Constate sur l'execution 167 : 23 types annonces, 20 routes. `dev_lwc` — le
composant Lightning — en faisait partie.

REGLE : tout type ajoute au prompt doit etre ajoute a la table le meme jour.
Les deux fichiers forment un seul contrat.

    python3 tools/verifier_vocabulaire_wbs.py
"""
import io, re, sys, os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT = os.path.join(RACINE, "backend/prompts/agents/marcus_architect.yaml")
TABLE = os.path.join(RACINE, "backend/app/services/phased_build_executor.py")


def lire(chemin):
    return io.open(chemin, encoding="utf-8", errors="replace").read()


def types_du_prompt():
    p = lire(PROMPT)
    return set(re.findall(
        r"\|\s*([a-z_]+)\s*\|\s*(?:Raj|Diego|Zara|Jordan|Lucas|Aisha|Elena|MANUAL)", p))


def types_routes():
    s = lire(TABLE)
    i = s.find("TASK_TYPE_TO_PHASE")
    if i < 0:
        return set()
    j = s.find("}", s.find("{", i))
    return set(re.findall(r'"([a-z_]+)"\s*:', s[i:j + 1]))


def main():
    annonces, routes = types_du_prompt(), types_routes()
    orphelins = sorted(annonces - routes)

    print(f"  {len(annonces)} types annonces a Marcus")
    print(f"  {len(routes)} types routes par le code")

    if orphelins:
        print(f"\n  ECART — {len(orphelins)} type(s) annonce(s) mais NON route(s) :")
        for t in orphelins:
            print(f"    · {t}")
        print("\n  Ces taches retomberont sur le repli par agent, silencieusement.")
        print("  Ajouter ces types a TASK_TYPE_TO_PHASE avec leur numero de phase.")
        return 1

    print("\n  OK — le prompt et la table de routage concordent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
