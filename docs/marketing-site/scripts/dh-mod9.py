#!/usr/bin/env python3
"""
Mod 9 — Sophie's slide: new editorial layout + real photo.
- Replace avSophie SVG placeholder by Generated_Image_April_19_2026__7_15PM.jpg
- New slide layout for single-agent acts (only Act I for now):
    Row 1: act num + step title (brass, not --c)
    Row 2 left: photo big (agent color outline) + name/role/tagline under
    Row 2 right: detail mono rect (moved from bottom) + act tagline under
- Multi-agent acts (II-V) keep the old layout for now.
"""
import re, json, base64, gzip, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
PHOTO = Path('/tmp/dh-photos/Generated Image April 19, 2026 - 7_15PM.jpg')

content = SRC.read_text()

# ---------- 1) Parse manifest ----------
manifest_match = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)',
                           content, re.DOTALL)
manifest_open, manifest_body, manifest_close = manifest_match.groups()
manifest = json.loads(manifest_body.strip())

# ---------- 2) Replace avSophie entry ----------
AV_SOPHIE_UUID = 'ca8d9519-ec17-4078-9e5c-7a42cf99e7f7'
photo_bytes = PHOTO.read_bytes()
photo_b64 = base64.b64encode(photo_bytes).decode('ascii')
manifest[AV_SOPHIE_UUID] = {
    "mime": "image/jpeg",
    "compressed": False,
    "data": photo_b64,
}
print(f"[1/4] avSophie replaced — {len(photo_bytes)} bytes JPEG")

# ---------- 3) Parse template, update CSS + sections.jsx ----------
template_match = re.search(r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)',
                           content, re.DOTALL)
template_open, template_body, template_close = template_match.groups()
template_html = json.loads(template_body.strip())

# --- 3a) Append new CSS rules for single-agent editorial layout ---
NEW_CSS = """
  /* ===== Mod 9 — editorial single-agent layout (Act I etc.) ===== */
  .steps .step.is-solo {
    border-top: 2px solid rgba(245,242,236,0.18);   /* neutral — no act color */
  }
  .steps .step.is-solo .step-head .num {
    color: var(--brass);                             /* site color, not act */
  }
  .steps .step.is-solo .step-body {
    display: grid;
    grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
    gap: 48px;
    align-items: start;
  }
  .step-hero-photo {
    width: 100%;
    aspect-ratio: 4 / 5;
    border-radius: 2px;
    overflow: hidden;
    position: relative;
    background: rgba(245,242,236,0.04);
    outline: 1px solid rgba(245,242,236,0.12);
    outline-offset: 0;
  }
  .step-hero-photo::after {
    content: "";
    position: absolute; inset: 0;
    pointer-events: none;
    box-shadow: inset 0 0 0 4px var(--ac, var(--brass));
    opacity: 0.95;
  }
  .step-hero-photo img {
    width: 100%; height: 100%;
    object-fit: cover; display: block;
    filter: saturate(0.9) contrast(1.03);
  }
  .step-hero-meta {
    margin-top: 24px;
    display: flex; flex-direction: column; gap: 6px;
  }
  .step-hero-name {
    font-family: var(--serif);
    font-size: clamp(22px, 2.1vw, 28px);
    font-weight: 500;
    color: var(--bone);
    letter-spacing: -0.01em;
    line-height: 1.1;
  }
  .step-hero-role {
    font-family: var(--mono);
    font-size: 10.5px;
    color: var(--bone-4);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-top: 2px;
    margin-bottom: 14px;
  }
  .step-hero-line {
    font-family: var(--serif);
    font-style: italic;
    font-size: 15.5px;
    line-height: 1.55;
    color: rgba(245,242,236,0.78);
    max-width: 38ch;
  }
  .step-hero-line + .step-hero-line { margin-top: 4px; }
  .steps .step.is-solo .step-meta-col {
    display: flex; flex-direction: column; gap: 24px;
    padding-top: 4px;
  }
  .steps .step.is-solo .step-meta-col .detail {
    margin: 0;
  }
  .steps .step.is-solo .step-meta-col .step-desc {
    border-top: none;
    padding-top: 0;
    font-family: var(--serif);
    font-style: italic;
    font-size: 16px;
    line-height: 1.6;
    color: rgba(245,242,236,0.72);
    max-width: none;
  }
  @media (max-width: 860px) {
    .steps .step.is-solo .step-body {
      grid-template-columns: 1fr;
      gap: 28px;
    }
    .step-hero-photo { aspect-ratio: 3 / 4; max-width: 380px; }
  }
"""

# Inject just before the closing style block that contains .step CSS
INJECT_MARK = '/* ===== Sequence navigation : arrows + dots ===== */'
if INJECT_MARK not in template_html:
    sys.exit(f"FATAL: marker not found — '{INJECT_MARK}'")
template_html = template_html.replace(INJECT_MARK, NEW_CSS + '\n  ' + INJECT_MARK, 1)
print("[2/4] CSS rules injected")

# --- 3b) Rewrite sections.jsx JSX to support the new layout ---
SECTIONS_UUID = '6641f2bf-70da-46eb-a716-a60b6030f1c7'
sec_entry = manifest[SECTIONS_UUID]
sec_raw = gzip.decompress(base64.b64decode(sec_entry['data'])).decode('utf-8') if sec_entry.get('compressed') else base64.b64decode(sec_entry['data']).decode('utf-8')

# Add `ac` (agent color hex) to Sophie's agent in both en and fr steps.
# Sophie is the ONLY agent in Act I, for both languages.
SOPHIE_AC = '#8B5CF6'  # from direction photo doc

# EN side
sec_raw_new = sec_raw.replace(
    "agents:[{n:'Sophie Chen', role:'Orchestrator', av:'sophie', lines:",
    "agents:[{n:'Sophie Chen', role:'Project Manager · Orchestrator', ac:'#8B5CF6', av:'sophie', lines:",
    1
)
# FR side
sec_raw_new = sec_raw_new.replace(
    "agents:[{n:'Sophie Chen', role:'Chef d’orchestre', av:'sophie', lines:",
    "agents:[{n:'Sophie Chen', role:'Chef de projet · Chef d’orchestre', ac:'#8B5CF6', av:'sophie', lines:",
    1
)
assert sec_raw_new.count("ac:'#8B5CF6'") == 2, f"Failed to inject Sophie ac color ({sec_raw_new.count(chr(39) + '#8B5CF6' + chr(39))} occurrences, expected 2)"

# Replace the inside-of-step render (the block between {t.steps.map((s,i) => ( and the closing `))}`)
OLD_RENDER = """            {t.steps.map((s,i) => (
              <div key={i} className=\"step\" style={{'--c': s.c}}>
                <div className=\"step-head\">
                  <div className=\"num\">{s.r}</div>
                  <div className=\"step-title\"><h3>{s.t}</h3></div>
                </div>
                <div className=\"step-agents\">
                  {s.agents.map((a,j) => (
                    <div key={j} className=\"step-agent\">
                      <div className=\"step-agent-photo\"><img src={AV(a.av)} alt={a.n}/></div>
                      <div className=\"step-agent-body\">
                        <div className=\"step-agent-name\">{a.n}</div>
                        <div className=\"step-agent-role\">{a.role}</div>
                        {a.lines.map((ln,k) => (<div key={k} className=\"step-tagline\">{ln}</div>))}
                      </div>
                    </div>
                  ))}
                </div>
                <div className=\"step-desc\">{s.d}</div>
                <div className=\"detail\">{s.detail}</div>
              </div>
            ))}"""

NEW_RENDER = """            {t.steps.map((s,i) => {
              const solo = s.agents.length === 1;
              if (solo) {
                const a = s.agents[0];
                return (
                  <div key={i} className=\"step is-solo\" style={{'--c': s.c, '--ac': a.ac || s.c}}>
                    <div className=\"step-head\">
                      <div className=\"num\">{s.r}</div>
                      <div className=\"step-title\"><h3>{s.t}</h3></div>
                    </div>
                    <div className=\"step-body\">
                      <div className=\"step-photo-col\">
                        <div className=\"step-hero-photo\"><img src={AV(a.av)} alt={a.n}/></div>
                        <div className=\"step-hero-meta\">
                          <div className=\"step-hero-name\">{a.n}</div>
                          <div className=\"step-hero-role\">{a.role}</div>
                          {a.lines.map((ln,k) => (<div key={k} className=\"step-hero-line\">{ln}</div>))}
                        </div>
                      </div>
                      <div className=\"step-meta-col\">
                        <div className=\"detail\">{s.detail}</div>
                        <div className=\"step-desc\">{s.d}</div>
                      </div>
                    </div>
                  </div>
                );
              }
              return (
                <div key={i} className=\"step\" style={{'--c': s.c}}>
                  <div className=\"step-head\">
                    <div className=\"num\">{s.r}</div>
                    <div className=\"step-title\"><h3>{s.t}</h3></div>
                  </div>
                  <div className=\"step-agents\">
                    {s.agents.map((a,j) => (
                      <div key={j} className=\"step-agent\">
                        <div className=\"step-agent-photo\"><img src={AV(a.av)} alt={a.n}/></div>
                        <div className=\"step-agent-body\">
                          <div className=\"step-agent-name\">{a.n}</div>
                          <div className=\"step-agent-role\">{a.role}</div>
                          {a.lines.map((ln,k) => (<div key={k} className=\"step-tagline\">{ln}</div>))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className=\"step-desc\">{s.d}</div>
                  <div className=\"detail\">{s.detail}</div>
                </div>
              );
            })}"""

if OLD_RENDER not in sec_raw_new:
    # dump both for debugging
    Path('/tmp/dh-decoded/sections_fresh.jsx').write_text(sec_raw_new)
    Path('/tmp/dh-decoded/OLD_RENDER.txt').write_text(OLD_RENDER)
    sys.exit("FATAL: OLD_RENDER block not found in sections.jsx — see /tmp/dh-decoded/sections_fresh.jsx and OLD_RENDER.txt to diff")

sec_raw_new = sec_raw_new.replace(OLD_RENDER, NEW_RENDER, 1)
print("[3/4] sections.jsx rewritten")

# Re-encode sections module
sec_compressed = base64.b64encode(gzip.compress(sec_raw_new.encode('utf-8'))).decode('ascii')
manifest[SECTIONS_UUID] = {
    "mime": sec_entry.get('mime', 'application/javascript'),
    "compressed": True,
    "data": sec_compressed,
}

# ---------- 4) Rewrite manifest + template back into index.html ----------
new_manifest_body = json.dumps(manifest, separators=(',', ':'))
new_template_body = json.dumps(template_html)
# Escape </script> and </style> closing tags to prevent HTML parser from
# terminating the outer <script type="__bundler/template"> prematurely.
# JSON parse at runtime will decode \u002F back to /.
new_template_body = new_template_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")

new_content = (
    content[:manifest_match.start()]
    + manifest_open + new_manifest_body + manifest_close
    + content[manifest_match.end():template_match.start() - manifest_match.end() + manifest_match.end()]
)
# simpler: reconstruct from slices
new_content = (
    content[:manifest_match.start()]
    + manifest_open + new_manifest_body + manifest_close
    + content[manifest_match.end():template_match.start()]
    + template_open + new_template_body + template_close
    + content[template_match.end():]
)

SRC.write_text(new_content)
print(f"[4/4] index.html written — {len(new_content)} bytes")
print(f"      manifest: {len(manifest_body)} → {len(new_manifest_body)} chars")
print(f"      template: {len(template_body)} → {len(new_template_body)} chars")
