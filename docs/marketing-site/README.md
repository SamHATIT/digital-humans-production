# Marketing site — refonte 2026

Travail sur la maquette du site marketing Digital Humans, hébergée en preview sur
le VPS à `/var/www/dh-preview/index.html` (bundle React autonome au format custom).

## URL preview

http://72.61.161.222/preview/ — auth basic : `preview` / `a88PtPREkPe9`

## Structure

- `REPRISE_MEMO.md` — mémo vivant : où on en est, ce qui reste à faire, principes
  techniques du bundle, mapping des photos, hypothèses sur les bugs. À mettre à jour
  à chaque session.
- `scripts/dh-modN.py` — scripts d'injection itératifs. Chaque script :
  1. Parse les 3 sections du bundle (`__bundler/manifest`, `__bundler/ext_resources`, `__bundler/template`)
  2. Modifie ce qui est nécessaire (manifest entry pour photos JPEG, sections.jsx pour rôles/layouts, CSS pour styling)
  3. Reconstruit le HTML en escapant `</script>` et `</style>` dans le template JSON

## Workflow

```bash
# Sur le VPS, avant chaque modification :
cp /var/www/dh-preview/index.html /var/www/dh-preview/index.html.pre-modN

# Run script
python3 docs/marketing-site/scripts/dh-modN.py

# Verif
curl -u 'preview:a88PtPREkPe9' http://72.61.161.222/preview/

# Rollback en cas de pépin :
cp /var/www/dh-preview/index.html.pre-modN /var/www/dh-preview/index.html
```

## Fichier source des photos

Photos dans `/tmp/agents-photos/` sur le VPS (12 fichiers `Generated Image April 19, 2026 - *.jpg`).
Mapping agent ↔ photo ↔ accent color dans `REPRISE_MEMO.md`.
