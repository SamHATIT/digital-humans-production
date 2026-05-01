#!/usr/bin/env python3
"""
Mod 30 — Favicon fix (1er mai 2026)
====================================
Lighthouse mobile post-mod29 reportait 1 console error :
  "Failed to load resource: the server responded with a status of 404"
  → cible : http://.../favicon.ico

Le bundle ne déclarait aucun favicon. Le browser fait par défaut un GET
/favicon.ico, qui retournait 404 → console error → Best Practices < 100.

Solution : favicon SVG inline en data URI dans le <head>. Pas de fichier
externe à servir, charge dans le bundle, taille +341 bytes seulement.

Design : "DH" en Cormorant Garamond italic (ish — Georgia fallback côté
favicon, Cormorant n'est pas dispo dans les SVG inline du browser),
brass (#c8a97e) sur ink (#0a0a0b), rounded 4px.

Backup : index.html.pre-mod30-favicon
"""
import re, json

INDEX = '/var/www/dh-preview/index.html'

def main():
    with open(INDEX) as f:
        content = f.read()

    m = re.search(r'(<script[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
    template_open, template_body, template_close = m.group(1), m.group(2), m.group(3)
    template = json.loads(template_body.strip())

    favicon_svg = (
        '<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 32 32\'>'
        '<rect width=\'32\' height=\'32\' rx=\'4\' fill=\'%230a0a0b\'/>'
        '<text x=\'16\' y=\'22\' font-family=\'Georgia,serif\' font-size=\'18\' font-style=\'italic\' '
        'fill=\'%23c8a97e\' text-anchor=\'middle\' font-weight=\'500\'>DH</text>'
        '</svg>'
    )
    favicon_link = f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{favicon_svg}">'
    anchor = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'

    if favicon_link in template:
        print("Already present, skipping")
        return
    if anchor not in template:
        raise RuntimeError("viewport anchor not found")

    template = template.replace(anchor, anchor + '\n' + favicon_link, 1)

    new_template_body = json.dumps(template, ensure_ascii=False)
    new_template_body = new_template_body.replace('</script>', r'<\u002Fscript>').replace('</style>', r'<\u002Fstyle>')
    pattern = re.compile(r'(<script[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)', re.DOTALL)
    new_content = pattern.sub(lambda m: m.group(1) + new_template_body + m.group(3), content, count=1)

    with open(INDEX, 'w') as f:
        f.write(new_content)
    print(f"Bundle: {len(content):,} -> {len(new_content):,} ({len(new_content)-len(content):+,})")


if __name__ == "__main__":
    main()
