#!/usr/bin/env python3
"""Mod 11 — right-align meta-col across all slides (CSS one-liner)."""
import re, json, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
content = SRC.read_text()

def extract(content, script_type):
    m = re.search(rf'(<script\s+type="{re.escape(script_type)}"[^>]*>)', content)
    start = m.end()
    close = content.index('</script>', start)
    return start, close

t_start, t_close = extract(content, '__bundler/template')
tpl = json.loads(content[t_start:t_close].strip())

# Patch the .step-meta-col rule: add justify-self: end + margin-left: auto (belt + suspenders)
OLD = """  .steps .step .step-meta-col {
    display: flex; flex-direction: column; gap: 22px;
    padding-top: 4px;
    max-width: 420px;
  }"""
NEW = """  .steps .step .step-meta-col {
    display: flex; flex-direction: column; gap: 22px;
    padding-top: 4px;
    max-width: 420px;
    justify-self: end;   /* anchor to right edge of grid cell */
    width: 100%;         /* fill cell up to max-width so alignment is visible */
  }"""

if OLD not in tpl:
    sys.exit("FATAL: step-meta-col rule block not found")
tpl = tpl.replace(OLD, NEW, 1)

# write back with </script> / </style> escaping
new_tpl_body = json.dumps(tpl)
new_tpl_body = new_tpl_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")
new_content = content[:t_start] + new_tpl_body + content[t_close:]

SRC.write_text(new_content)
print(f"Mod 11 applied. Template bytes: {len(content[t_start:t_close])} → {len(new_tpl_body)}")
