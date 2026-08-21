# Audit croisé du 21 août 2026

Quatre modèles, 823 000 tokens de code source, un prompt identique.
**Les quatre refusent l'ouverture au 1er octobre en l'état.**

| Rapport | Modèle | Constats | Coût |
| --- | --- | --- | --- |
| `rapport-kimi.md` | Kimi K3 (1M ctx) | 36 | 2,47 $ |
| `rapport-claude.md` | Claude Opus | 22 | ~4,50 $ |
| `rapport-gpt5-frontend.md` | GPT-5.3 Codex | 15 (frontend seul) | ~0,50 $ |
| `rapport-gemini.md` | Gemini 3.1 Pro | 11 | ~1,70 $ |

`prompt-audit.md` est le prompt soumis à l'identique aux quatre.
À rejouer une fois la vague 1 terminée : c'est le seul moyen de vérifier
que les correctifs tiennent — l'expérience des P0-P12 montre que quatre
correctifs déclarés « corrigés » ne l'étaient pas.

GPT-5.3 n'a pu traiter que le frontend : sa fenêtre de contexte ne tient
pas les 823 000 tokens, et il a refusé d'auditer un backend découpé —
à juste titre, puisqu'il ne pouvait plus tracer les appels entre fichiers.

## Chiffres

84 constats · 25 bloquants · 36 majeurs · 18 mineurs · 16 thèmes.

Trois points sont signalés par trois modèles ou plus :
la frontière payante inexistante côté serveur, l'isolation entre clients
absente, et l'absence totale d'observabilité.

## Déjà traité le 21/08

La route `/api/agent-tester/org/query` exécutait des commandes shell depuis
un paramètre d'URL, sans authentification, joignable depuis Internet.
Bloquée au niveau nginx (403) le jour même. **Le code reste vulnérable** —
c'est un pansement, pas un correctif. Voir LOT-C.
