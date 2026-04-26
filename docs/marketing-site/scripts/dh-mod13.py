#!/usr/bin/env python3
"""Mod 13 — Punchline visible. Fix : utiliser · direct (pas escape \\u00b7) dans le JSX."""
import re, json, base64, gzip, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
content = SRC.read_text()
print(f"[0] index.html loaded — {len(content):,} bytes")

m_manifest = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
manifest_open, manifest_body, manifest_close = m_manifest.groups()
manifest = json.loads(manifest_body.strip())

m_template = re.search(r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
template_open, template_body, template_close = m_template.groups()
template_html = json.loads(template_body.strip())

NEW_CSS = """
  /* ===== Mod 13 — punchline visible (split role) ===== */
  .steps .step .hero-role { line-height: 1.4; }
  .steps .step .hero-role .role-sep {
    display: inline-block;
    margin: 0 5px 0 3px;
    color: var(--brass);
    font-size: 12px;
    font-family: var(--serif);
    letter-spacing: 0;
    font-weight: 400;
    vertical-align: -1px;
  }
  .steps .step .hero-role .role-tag {
    font-family: var(--serif);
    font-style: italic;
    font-size: 14.5px;
    font-weight: 400;
    color: rgba(245, 242, 236, 0.88);
    text-transform: none;
    letter-spacing: -0.005em;
    line-height: 1.3;
  }
"""

INJECT_MARK = '/* ===== Sequence navigation : arrows + dots ===== */'
if INJECT_MARK not in template_html:
    sys.exit(f"FATAL: marker not found")
template_html = template_html.replace(INJECT_MARK, NEW_CSS + '\n  ' + INJECT_MARK, 1)
print("[1] CSS injected")

SECTIONS_UUID = '6641f2bf-70da-46eb-a716-a60b6030f1c7'
sec_entry = manifest[SECTIONS_UUID]
sec_raw = gzip.decompress(base64.b64decode(sec_entry['data'])).decode('utf-8') if sec_entry.get('compressed') else base64.b64decode(sec_entry['data']).decode('utf-8')

# Replace direct (apostrophes ASCII OK car la JSX string contient · UTF-8 directement, pas d'apostrophe a l'interieur)
old_render = '<div className="hero-role">{a.role}</div>'
# IMPORTANT : utiliser le caractere · UTF-8 directement (pas \u00b7) dans le JSX texte enfant
# Le contenu du span <span>...</span> est interprete comme texte litteral en JSX, donc · doit etre present tel quel
new_render = (
    '<div className="hero-role">'
    "<span className=\"role-label\">{a.role.split(' · ')[0]}</span>"
    "{a.role.includes(' · ') && (<><span className=\"role-sep\">·</span>"
    "<span className=\"role-tag\">{a.role.split(' · ').slice(1).join(' · ')}</span></>)}"
    '</div>'
)

if old_render not in sec_raw:
    sys.exit("FATAL: old render not found")

sec_raw_new = sec_raw.replace(old_render, new_render, 1)
print(f"[2] sections.jsx render patched")

# Verify the · character is correctly encoded UTF-8 (not escaped)
if '\\u00b7' in new_render:
    print("  WARNING: \\u00b7 still in new_render — should be · UTF-8")

sec_compressed = base64.b64encode(gzip.compress(sec_raw_new.encode('utf-8'))).decode('ascii')
manifest[SECTIONS_UUID] = {
    "mime": sec_entry.get('mime', 'application/javascript'),
    "compressed": True,
    "data": sec_compressed,
}
Path('/tmp/sections_after_mod13.jsx').write_text(sec_raw_new)

new_manifest_body = json.dumps(manifest, separators=(',', ':'))
new_template_body = json.dumps(template_html, ensure_ascii=False)  # ensure_ascii=False pour garder · UTF-8 dans le JSON
new_template_body = new_template_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")

new_content = (
    content[:m_manifest.start()]
    + manifest_open + new_manifest_body + manifest_close
    + content[m_manifest.end():m_template.start()]
    + template_open + new_template_body + template_close
    + content[m_template.end():]
)
SRC.write_text(new_content)
print(f"[3] index.html written — {len(new_content):,} bytes")
