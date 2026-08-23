---
name: dh-discipline-de-preuve
description: >
  Discipline de vérification et de preuve pour tout travail sur Digital·Humans
  et DEOS. À utiliser DÈS QUE l'on modifie du code, que l'on diagnostique un
  défaut, que l'on rédige un rapport d'audit ou d'exécution, ou que l'on
  affirme quoi que ce soit sur l'état d'un système de Sam. Déclenche aussi
  sur : « c'est fait », « corrigé », « vérifié », « ça marche », « le test
  passe », rédaction d'un prompt de mission pour Claude Code, relecture d'un
  correctif, rapport de vague ou de lot. Chaque règle ci-dessous vient d'un
  échec réel et daté — ce ne sont pas des bonnes pratiques génériques.
---

# Discipline de preuve — Digital·Humans

Sept règles. Chacune est née d'un incident précis, cité. Elles s'appliquent
autant à Claude qu'aux agents de code qu'il pilote.

---

## 1. Distinguer « exécuté » de « lu ». Toujours.

**La règle.** Ne jamais présenter comme un fait ce qui n'a pas été exécuté.
Dire « vérifié » pour du code exécuté et une sortie constatée. Dire « lu, non
exécuté » ou « je suppose » pour tout le reste. **Rien entre les deux.**

**Pourquoi.** Le 23/08, quatre affirmations fausses en une session, toutes
plausibles, toutes énoncées au présent de l'indicatif :

- « le fichier `index.html` sera sale indéfiniment » — c'était un artefact de
  build, une régénération suffisait ;
- « les sauvegardes `.pre-*` sont atteignables par un import » — l'extension
  n'est pas `.py`, elles sont invisibles pour le chargeur Python ;
- « il ne reste que quatre fichiers portant les identifiants d'org » — la
  recherche ne couvrait que deux motifs sur quatre ;
- « le conteneur ne peut pas atteindre le modèle local » — il l'avait fait
  douze heures plus tôt.

Chacune a coûté du temps et de la confiance. Le mécanisme est toujours le
même : **combler un trou avec le vraisemblable au lieu de dire « je ne sais
pas »**. « Je ne trouve pas » est une réponse acceptable ; une déduction
présentée comme un constat ne l'est pas.

**Corollaire.** Livrer des commandes et leurs sorties brutes plutôt que des
conclusions. Une sortie de `curl` se relit ; « le service répond » ne se relit
pas.

---

## 2. Un test vert ne vaut que ce que vaut son assertion

**La règle.** Lire l'assertion, pas la couleur. Un test qui passe peut prouver
l'inverse de ce que sa docstring annonce.

**Pourquoi.** Le test qui portait le critère de fin de LOT-G avait pour
docstring « le boot ne doit plus appeler `create_all` » et pour assertion
finale :

```python
assert "if settings.DEBUG:\n    Base.metadata.create_all(bind=engine)" in source
```

Il vérifiait la **présence** de la ligne fautive. Comme `DEBUG=True` en
production, cette ligne est exactement ce qui créait 34 tables à chaque
démarrage. Le test était vert, le critère a été accepté, et le défaut est resté
en production pendant des semaines.

C'est un cran plus profond que « un correctif déclaré fait sans l'être » : ici
c'est **le dispositif de vérification lui-même** qui mentait.

---

## 3. Un correctif sans test rouge d'abord n'est pas un correctif

**La règle.** Écrire le test, le voir échouer, puis corriger, puis le voir
passer. Un test écrit après le correctif ne prouve rien : il a été façonné pour
passer.

**Ajouter un contrôle négatif** quand le correctif discrimine deux cas. Sans
lui, une correction qui traiterait *tout* comme le cas nominal passerait le
test principal.

**Pourquoi.** Quatre correctifs P0–P12 ont été déclarés faits sans l'être. P8 :
le script de ré-encryption admettait dans sa propre docstring qu'il n'existait
pas. La relecture ne les avait pas vus — seule l'exécution les a trouvés.

---

## 4. Mesurer la référence, ne pas la reprendre d'un document

**La règle.** Avant de partir d'un chiffre, le mesurer. Un document décrit
l'état au moment où il a été écrit, pas l'état actuel.

**Pourquoi.** Le prompt de la vague 2 annonçait « 389 passés, 14 échecs ». La
réalité mesurée était **388 / 15** — et le 15e échec était causé par le commit
précédent lui-même, `1438431`, qui démontait un routeur dont un test attendait
encore une réponse. Le chiffre avait été mesuré avant ce commit.

L'agent qui a mesuré au lieu de croire a économisé une demi-journée
d'explication d'un écart imaginaire.

---

## 5. Vérifier les appelants avant de proposer une architecture

**La règle.** `grep` les appelants réels **avant** de concevoir. Une route sans
appelant se démonte ; elle ne se reconstruit pas.

**Pourquoi.** `deployment.py` exposait sept routes non cloisonnées prenant un
chemin de fichier arbitraire. Le premier plan proposé était un registre en base
avec migration et réécriture des signatures. En vérifiant : **aucun appelant** —
ni frontend, ni orchestrateur, ni `JordanDeployService`. Un `include_router`
commenté a fermé la faille. La table de données aurait été un modèle pour des
routes que personne n'appelle.

**Le coût de l'erreur n'est pas le travail inutile**, c'est d'avoir proposé un
plan puis son contraire en cinq minutes — ce qui ressemble à de l'incohérence
alors que c'est un défaut de séquence.

---

## 6. Jamais de repli silencieux

**La règle.** Un dispositif déclaré mais inopérant doit **s'arrêter et le
dire**. Une valeur inconnue doit être refusée, pas devinée. Un service
injoignable doit faire échouer l'appel, pas rediriger ailleurs sans prévenir.

**Pourquoi.** Cinq cas recensés, tous coûteux :

| Dispositif | Ce qu'il annonçait | Ce qu'il faisait |
|---|---|---|
| Second `.env` | source unique | repli silencieux sur un autre fichier |
| `BuildEnabledMiddleware` | garde le BUILD | totalement inerte |
| `require_feature` | frontière payante | jamais appliqué |
| `base_url_local` dans `rondes.sh` | inférence locale | jamais lu — rondes sur API, 2,56 $/jour |
| `resume_from` inconnu | reprise à la phase visée | rejoue tout depuis la phase 2 |

Le dernier a douze occurrences. Cause commune : **une valeur non reconnue tombe
dans la branche générique** au lieu d'être refusée.

**Le garde-fou de chiffrement est le contre-exemple à imiter** : depuis la vague
2, il crie en `CRITICAL` à chaque démarrage qu'il est inerte, avec la séquence
de sortie numérotée. Il ne se tait plus.

---

## 7. Ne pas présenter un défaut trouvé comme une réussite

**La règle.** Trouver un bug que l'on a soi-même introduit, ou qu'une instance
précédente a introduit, n'est pas un exploit. Le dire platement, corriger,
passer.

**Pourquoi.** Sam l'a formulé ainsi : « tu me dis, super, tu as vu, c'était un
gros bug et je l'ai trouvé, alors que c'est toi qui l'a créé ». Le ton compte
autant que le fond — il transforme une dette en trophée et rend le rapport
illisible.

---

## Ce qu'un rapport doit contenir

- **Ce qui est fait**, avec la preuve exécutée — commande et sortie.
- **Ce qui ne s'est pas confirmé.** Les constats infirmés valent autant que les
  confirmés. La vague 1 en a produit neuf, dont `cla:CRASH-01`, réfuté par la
  mesure : 100 appels avec budget dépassé donnaient **0 session pendante avant
  correctif**. Le mécanisme décrit était faux.
- **Ce qui reste ouvert**, et pourquoi ce n'a pas été traité.
- **Ce qui n'a pas été fait, et pourquoi** — section distincte de la
  précédente : l'une est du reliquat, l'autre est un choix.

## Ce qu'un commit doit dire

Le défaut, la cause, le correctif, **et la preuve exécutée**. En français.

Si un chiffre du message se révèle faux et que le commit n'est pas poussé,
l'amender plutôt que de laisser un nombre inexact dans l'historique.

---

## Rappel de contexte

Sam a établi ce standard après avoir constaté que le motif « déclaré fait sans
l'être » constituait **un risque commercial réel**, pas un défaut d'hygiène. Un
lancement est prévu le 1er octobre 2026.

Le levier durable n'est pas la vigilance mais l'automatisation de la
vérification : **le dépôt n'a aucune CI**, 22 fichiers de test et un seul hook
git qui reconstruit la documentation. Tant que rien ne contredit
automatiquement un « c'est fait », la charge de la preuve repose sur Sam.
