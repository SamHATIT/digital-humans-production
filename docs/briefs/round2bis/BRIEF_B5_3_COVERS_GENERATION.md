# BRIEF — Track B5.3 — Génération des 14 covers Studio (Gemini 3 Pro Image)

> **Owner** : Claude Code (autonome)
> **Branche source** : `claude/newsletter-studio-covers-Emso5`
> **Branche cible** : continuer sur `claude/newsletter-studio-covers-Emso5` (push direct)
> **Estimation** : 30-45 min (selon temps API Gemini)
> **Priorité** : 🟡 Production des assets visuels — peut tourner en parallèle de B5.2

---

## 1. Contexte court

La branche `claude/newsletter-studio-covers-Emso5` contient déjà tout le pipeline (commit `0eca581`) :
- `tools/generate_studio_covers.py` — client Gemini 3 Pro Image avec retry, dimension gate, filtres `--tag` / `--dry-run` / single-id
- `tools/cover_briefs.yaml` — 14 briefs (6 galerie + 8 articles)
- `docs/COVERS_GENERATION.md` — runbook complet
- `assets/covers/.gitkeep` — dossier de sortie tracké

Le `--dry-run` a déjà validé 14/14 prompts. **Cette tâche-ci = exécuter les vrais appels API** pour produire les images.

---

## 2. Objectif

Générer les 14 covers JPEG dans `assets/covers/` :

### Galerie acte 3 (6 covers)
- `logifleet.jpg` — Fleet management LogiFleet
- `pharma.jpg` — Pharmaceutical / Clinical Trial Watch
- `telecom.jpg` — Telecom / Claim Resolver
- `b2b-distribution.jpg` — B2B Distribution / Pipeline Tuner
- `energy.jpg` — Energy / Grid Foresight
- `retail.jpg` — Retail / Omnichannel Loop

### Articles The Journal (8 covers)
- `manifesto-trust-apex.jpg`
- `craft-triggers-flows.jpg`
- `dispatch-logifleet.jpg`
- `craft-bulk-api.jpg`
- `archive-no-code-myth.jpg`
- `dispatch-pharma-validation.jpg`
- `manifesto-eleven-agents.jpg`
- `craft-lwc-without-react.jpg`

---

## 3. Tâches détaillées

### Étape 1 — Préparer la branche (3 min)

```bash
cd /root/workspace/digital-humans-production
git fetch origin
git checkout claude/newsletter-studio-covers-Emso5
git pull origin claude/newsletter-studio-covers-Emso5

# Optionnel : rebase sur main pour récupérer les commits récents
# (pas obligatoire, juste plus propre)
git rebase origin/main
# Si conflits sur docs/refonte/* : git checkout --theirs docs/refonte/* && git rebase --continue
```

### Étape 2 — Vérifier les dépendances (2 min)

```bash
python3 -m pip install --user pyyaml pillow
python3 -c "import yaml, PIL; print('OK', yaml.__version__, PIL.__version__)"
```

### Étape 3 — Configurer la clé Gemini éphémère (2 min)

Sam fournit la clé en variable d'environnement dans la session. **Ne JAMAIS la commit, ne JAMAIS l'écrire en clair dans un fichier tracké.**

```bash
export GEMINI_API_KEY="<clé fournie par Sam>"

# Vérification rapide que la clé est bien chargée
echo "Key length: ${#GEMINI_API_KEY}"  # doit être ~39 chars pour une clé Google AI
```

À la fin de la session : `unset GEMINI_API_KEY`.

### Étape 4 — Smoke test sur 1 cover (3 min)

Avant de lancer les 14 d'un coup, valider sur la première :

```bash
python3 tools/generate_studio_covers.py logifleet 2>&1 | tee /tmp/cover_smoke.log
```

Vérifications attendues :
- ✅ Fichier `assets/covers/logifleet.jpg` créé
- ✅ Dimensions ≥ 1280×800 (le dimension gate du script bloque sinon)
- ✅ Format JPEG, taille raisonnable (300 KB - 2 MB)
- ✅ Pas d'erreur 403 / 429 / quota dans les logs
- ✅ Visuellement cohérent avec la charte Studio (palette ink/bone/brass, pas de texte, pas de personnages)

Si le smoke test échoue → STOP, report à Sam avec les logs. Ne pas continuer la batch tant que la première cover n'est pas correcte.

### Étape 5 — Générer les 5 autres covers galerie (10 min)

```bash
python3 tools/generate_studio_covers.py --tag gallery 2>&1 | tee /tmp/covers_gallery.log
```

Le tag `gallery` cible les 6 entrées de la galerie acte 3. Comme `logifleet` est déjà fait, le script soit le skip (si `--force` n'est pas passé), soit le régénère. Vérifier le comportement dans les logs.

Pour ne pas re-générer logifleet :
```bash
# Le script a un mode "skip if exists" par défaut ; vérifier dans le code
python3 tools/generate_studio_covers.py --tag gallery 2>&1 | grep -E "skip|generated|failed"
```

Sinon, générer une à une :
```bash
for id in pharma telecom b2b-distribution energy retail; do
  echo "=== $id ==="
  python3 tools/generate_studio_covers.py "$id"
  sleep 2  # rate limit safety
done
```

### Étape 6 — Générer les 8 covers articles (15 min)

```bash
python3 tools/generate_studio_covers.py --tag article 2>&1 | tee /tmp/covers_articles.log
```

Si le yaml utilise un autre tag (vérifier dans `cover_briefs.yaml`), adapter. Sinon, génération une à une comme étape 5.

### Étape 7 — Validation visuelle automatique (5 min)

```bash
echo "=== Inventaire ==="
ls -la assets/covers/*.jpg | awk '{print $5, $9}' | sort -k2

echo ""
echo "=== Vérif dimensions ==="
for f in assets/covers/*.jpg; do
  python3 -c "
from PIL import Image
img = Image.open('$f')
w, h = img.size
ok = '✅' if w >= 1280 and h >= 800 else '❌'
print(f'$f: {w}x{h} {ok}')
"
done

echo ""
echo "=== Couleurs dominantes (sanity check) ==="
for f in assets/covers/*.jpg; do
  python3 -c "
from PIL import Image
img = Image.open('$f').convert('RGB').resize((50, 50))
pixels = list(img.getdata())
avg = tuple(sum(c[i] for c in pixels)//len(pixels) for i in range(3))
print(f'$f: avg RGB {avg}')
"
done
```

Les couleurs moyennes doivent être **sombres** (palette ink dominante). Si une cover sort très claire ou avec une teinte exotique, la régénérer manuellement avec `--force` :

```bash
python3 tools/generate_studio_covers.py <id> --force
```

### Étape 8 — Commit + push (5 min)

```bash
# Les .jpg sont dans le .gitignore par défaut (cf. .gitignore de la branche)
# Mais on veut les commit ici car ils sont les assets finaux
# Approche : forcer l'add des fichiers présents dans assets/covers/

git add -f assets/covers/*.jpg
git status --short

# Vérifier qu'il y a bien 14 fichiers .jpg
ls assets/covers/*.jpg | wc -l  # doit être 14

git -c user.name="Sam (via Claude)" -c user.email="[email protected]" commit -m "feat(covers): generate 14 Studio covers via Gemini 3 Pro Image

- 6 covers galerie acte 3 (logifleet, pharma, telecom, b2b-distribution, energy, retail)
- 8 covers articles The Journal (manifesto x2, craft x3, dispatch x2, archive x1)

Toutes en charte Studio (palette ink/bone/brass, pas de texte, pas de personnages).
Dimensions ≥ 1280x800, format JPEG quality 85.
Coût total estimé : ~\$0.56-1.68 (14 images, 1-3 attempts each).

Generated using Gemini 3 Pro Image (gemini-3-pro-image-preview) via
nanobanana2 ephemeral key. Key destroyed after session per Sam's instruction.

Source briefs: tools/cover_briefs.yaml
Generation script: tools/generate_studio_covers.py
Runbook: docs/COVERS_GENERATION.md"

git push origin claude/newsletter-studio-covers-Emso5
```

### Étape 9 — Cleanup clé éphémère (1 min)

```bash
unset GEMINI_API_KEY
# Vérifier qu'elle n'est nulle part dans les logs commités
git diff HEAD~1 | grep -i "AIza" && echo "⚠️  CLÉ DÉTECTÉE DANS LE DIFF" || echo "✅ Aucune trace"
```

---

## 4. Critères de fin (DoD)

- ✅ 14 fichiers `.jpg` présents dans `assets/covers/`
- ✅ Toutes dimensions ≥ 1280×800
- ✅ Toutes en charte Studio (palette ink/bone/brass dominante, pas de texte, pas de personnages)
- ✅ Aucune trace de la clé API dans les commits
- ✅ Branche pushée
- ✅ Coût total reporté dans le rapport (estimation : $0.56 - $1.68)

---

## 5. Garde-fous

### Ce que tu peux faire
- Lancer le script `tools/generate_studio_covers.py` autant de fois que nécessaire (mais conscience du coût ~$0.04/image)
- Régénérer une cover individuellement si le résultat n'est pas satisfaisant (`--force`)
- Adapter les prompts dans `cover_briefs.yaml` si besoin (commit le change si tu le fais)
- `git rebase` sur main pour rester à jour (résoudre conflits docs/refonte avec --theirs)

### Ce que tu NE DOIS PAS faire
- ❌ Commit la clé API Gemini, même temporairement
- ❌ Modifier le script `generate_studio_covers.py` ou le yaml sauf justification claire
- ❌ Lancer plus de 3 tentatives par cover (le script a déjà un retry interne — pas besoin d'en rajouter)
- ❌ Merger sur main — c'est mon rôle (maître d'œuvre) après validation Sam
- ❌ Continuer la batch si le smoke test logifleet échoue

### Si bloqué
- Si l'API Gemini retourne 403 / quota : signaler à Sam, ne pas insister
- Si une cover sort visuellement bizarre malgré 3 tentatives : commit ce qui marche, signaler les manquantes dans le rapport, Sam ou le maître d'œuvre re-prompte manuellement
- Si rebase sur main pose des conflits ailleurs que docs/refonte : push tel quel, signaler dans le rapport

---

## 6. Note sur les sandboxes Claude Code

Si la session Claude Code tourne dans un sandbox web sans accès VPS direct :
- Le script peut tourner localement dans le sandbox (il n'a besoin que de Python + clé API)
- Les 14 .jpg seront générés dans le sandbox `assets/covers/` puis commités sur la branche
- Au pull suivant côté VPS, les fichiers seront disponibles (c'est le repo qui les véhicule, pas le filesystem)

Si le sandbox a une limite de bande passante / temps : générer par lots de 5-7 covers, faire un commit intermédiaire, recommencer.

---

## 7. Protocole de rapport

À la fin :
1. Liste des 14 fichiers générés avec leurs tailles + dimensions
2. Coût total réel constaté (lignes de log Gemini avec usage)
3. Hash du commit final
4. Si des covers ont été régénérées avec `--force`, lesquelles et pourquoi
5. Confirmation cleanup clé : `git diff` montre 0 occurrence de "AIza"

---

*Brief produit par : Claude (maître d'œuvre) · 26 avril 2026*
