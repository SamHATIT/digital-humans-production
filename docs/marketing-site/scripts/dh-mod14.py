#!/usr/bin/env python3
"""Mod 14 — Punchline sur sa propre ligne (au lieu d'inline). Donne plus d'air et de poids."""
import re, json, base64, gzip, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
content = SRC.read_text()
print(f"[0] index.html loaded — {len(content):,} bytes")

m_manifest = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
manifest = json.loads(m_manifest.group(2).strip())

m_template = re.search(r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
template_html = json.loads(m_template.group(2).strip())

# CSS — modifier .role-tag pour le mettre en block + ajuster spacing
NEW_CSS = """
  /* ===== Mod 14 — punchline en bloc separe (sa propre ligne) ===== */
  .steps .step .hero-role {
    /* parent : juste pour layout, pas de flex */
    line-height: 1.4;
    margin-bottom: 0;
  }
  .steps .step .hero-role .role-label {
    /* hérite mono uppercase 9.5px bone-4 0.16em — c'est la métadata */
    display: block;
  }
  .steps .step .hero-role .role-tag {
    display: block;
    margin-top: 6px;
    margin-bottom: 4px;
    font-family: var(--serif);
    font-style: italic;
    font-size: 16.5px;
    font-weight: 400;
    color: var(--bone);
    text-transform: none;
    letter-spacing: -0.005em;
    line-height: 1.25;
  }
  .steps .step .hero-meta {
    gap: 4px;  /* un peu plus d'air entre name -> role -> tag */
  }
"""

INJECT_MARK = '/* ===== Sequence navigation : arrows + dots ===== */'
template_html = template_html.replace(INJECT_MARK, NEW_CSS + '\n  ' + INJECT_MARK, 1)
print("[1] CSS injected (block layout for .role-tag)")

# JSX : enlever le sep, garder juste label + tag (chacun sur sa ligne grace au CSS block)
SECTIONS_UUID = '6641f2bf-70da-46eb-a716-a60b6030f1c7'
sec_entry = manifest[SECTIONS_UUID]
sec_raw = gzip.decompress(base64.b64decode(sec_entry['data'])).decode('utf-8')

# L'ancien render Mod 13 (avec sep)
old_render = (
    '<div className="hero-role">'
    "<span className=\"role-label\">{a.role.split(' · ')[0]}</span>"
    "{a.role.includes(' · ') && (<><span className=\"role-sep\">·</span>"
    "<span className=\"role-tag\">{a.role.split(' · ').slice(1).join(' · ')}</span></>)}"
    '</div>'
)

# Nouveau : 2 spans block (label puis tag), pas de sep
new_render = (
    '<div className="hero-role">'
    "<span className=\"role-label\">{a.role.split(' · ')[0]}</span>"
    "{a.role.includes(' · ') && (<span className=\"role-tag\">{a.role.split(' · ').slice(1).join(' · ')}</span>)}"
    '</div>'
)

if old_render not in sec_raw:
    print("FATAL: old render not found")
    sys.exit(1)

sec_raw_new = sec_raw.replace(old_render, new_render, 1)
print("[2] sections.jsx render patched (sep removed, tag becomes block)")

sec_compressed = base64.b64encode(gzip.compress(sec_raw_new.encode('utf-8'))).decode('ascii')
manifest[SECTIONS_UUID] = {"mime": sec_entry.get('mime', 'application/javascript'), "compressed": True, "data": sec_compressed}
Path('/tmp/sections_after_mod14.jsx').write_text(sec_raw_new)

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
SRC.write_text(new_content)
print(f"[3] index.html written — {len(new_content):,} bytes")
