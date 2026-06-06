#!/usr/bin/env python3
"""
Mod 31 — Hero shortening (13 mai 2026)
=======================================
Sam : "enlever la fin 'and at your fingertips', ça gâche la fluidité"

Avant (EN) :
  That happens to be autonomous and at your fingertips.
Après (EN) :
  That happens to be autonomous.

La version FR ("Qui se trouve être autonome.") était déjà courte —
on harmonise EN sur FR.

Cible : composant Header/Hero, UUID b7ddfc56-c91a-475b-8210-cdc552a1589d
Backup : index.html.pre-mod31-hero-shorten
"""
import re, json, base64, gzip, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
HERO_UUID = 'b7ddfc56-c91a-475b-8210-cdc552a1589d'

OLD = 'That happens to be autonomous and at your fingertips.'
NEW = 'That happens to be autonomous.'

content = SRC.read_text()
print(f"[0] index.html : {len(content):,} bytes")

m_manifest = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
m_template = re.search(r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
manifest = json.loads(m_manifest.group(2).strip())
template_html = json.loads(m_template.group(2).strip())

entry = manifest[HERO_UUID]
raw = gzip.decompress(base64.b64decode(entry['data'])).decode('utf-8')

count = raw.count(OLD)
if count != 1:
    sys.exit(f"FATAL: expected exactly 1 occurrence of OLD, found {count}")
raw_new = raw.replace(OLD, NEW, 1)
print(f"[1] hero JSX patched ({len(raw):,} -> {len(raw_new):,} bytes)")

manifest[HERO_UUID] = {
    "mime": entry.get('mime', 'application/javascript'),
    "compressed": True,
    "data": base64.b64encode(gzip.compress(raw_new.encode('utf-8'))).decode('ascii'),
}

new_manifest_body = json.dumps(manifest, separators=(',', ':'))
new_template_body = json.dumps(template_html, ensure_ascii=False)
new_template_body = new_template_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")

new_content = (
    content[:m_manifest.start()]
    + m_manifest.group(1) + new_manifest_body + m_manifest.group(3)
    + content[m_manifest.end():m_template.start()]
    + m_template.group(1) + new_template_body + m_template.group(3)
    + content[m_template.end():]
)

# Backup before write
backup = Path('/var/www/dh-preview/index.html.pre-mod31-hero-shorten')
backup.write_bytes(SRC.read_bytes())
print(f"[2] backup -> {backup.name}")

SRC.write_text(new_content)
print(f"[3] index.html written : {len(new_content):,} bytes (delta {len(new_content)-len(content):+,})")

# Sanity-check : re-decode and verify
content_check = SRC.read_text()
m = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content_check, re.DOTALL)
mf = json.loads(m.group(2).strip())
raw_check = gzip.decompress(base64.b64decode(mf[HERO_UUID]['data'])).decode('utf-8')
assert NEW in raw_check, "NEW string not found after roundtrip"
assert OLD not in raw_check, "OLD string still present after roundtrip"
print("[4] roundtrip verified : OLD removed, NEW present.")
