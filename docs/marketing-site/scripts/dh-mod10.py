#!/usr/bin/env python3
"""
Mod 10 — Unified layout across all acts (I-V):
- Photos consistent size: 220×275 (4:5), fixed width
- Up to 3 agents per slide, staggered vertically for breathing
- Act colors dropped from step header & border (use site brass)
- Agent color retained ONLY on photo rim (per-agent via --ac)
- Detail rect + act tagline stay on right (meta-col)
- Old .step-agent path deprecated in favor of .agent-card
"""
import re, json, base64, gzip, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
content = SRC.read_text()

# ---------- Helpers ----------
def extract(content, script_type):
    """Return (match, body) for a specific __bundler script tag."""
    m_open = re.search(rf'(<script\s+type="{re.escape(script_type)}"[^>]*>)', content)
    if not m_open: sys.exit(f"Missing script: {script_type}")
    start = m_open.end()
    close = content.index('</script>', start)
    return m_open, start, close

def replace_body(content, m_open, start, close, new_body):
    return content[:start] + new_body + content[close:]

# ---------- 1) Parse manifest ----------
m_open, m_start, m_close = extract(content, '__bundler/manifest')
manifest = json.loads(content[m_start:m_close].strip())
print(f"[0/3] Manifest loaded — {len(manifest)} entries")

# ---------- 2) Update CSS in template ----------
t_open, t_start, t_close = extract(content, '__bundler/template')
tpl_body_raw = content[t_start:t_close]
template_html = json.loads(tpl_body_raw.strip())

# Remove the previous Mod-9 CSS block (between "Mod 9 —" and the next comment block)
# Easier: just replace the whole previous block with the new unified one.
MOD9_START = '/* ===== Mod 9 — editorial single-agent layout (Act I etc.) ===== */'
MOD9_END_MARK = '/* ===== Sequence navigation : arrows + dots ===== */'
if MOD9_START in template_html:
    i = template_html.index(MOD9_START)
    j = template_html.index(MOD9_END_MARK, i)
    template_html = template_html[:i] + template_html[j:]
    print("  (removed Mod-9 CSS block)")

NEW_CSS = """/* ===== Mod 10 — Unified ensemble layout ===== */
  /* Drop act colors from step chrome; keep brass (site color) */
  .steps .step { border-top-color: rgba(245,242,236,0.18); }
  .steps .step .step-head .num { color: var(--brass); }

  /* Two-column body: agents row (left) + meta (right) */
  .steps .step .step-body {
    display: grid;
    grid-template-columns: minmax(220px, auto) minmax(260px, 1fr);
    gap: 56px;
    align-items: start;
  }
  .steps .step .step-photo-col {
    display: flex;
    flex-direction: row;
    gap: 28px;
    flex-wrap: wrap;
  }
  .steps .step .agent-card {
    width: 220px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
  }
  /* Staggered rhythm — air the slide out when 2+ agents */
  .steps .step .agent-card:nth-child(2) { margin-top: 38px; }
  .steps .step .agent-card:nth-child(3) { margin-top: 0; }
  .steps .step .hero-photo {
    width: 100%;
    aspect-ratio: 4 / 5;
    border-radius: 2px;
    overflow: hidden;
    position: relative;
    background: rgba(245,242,236,0.04);
    outline: 1px solid rgba(245,242,236,0.12);
  }
  .steps .step .hero-photo::after {
    content: "";
    position: absolute; inset: 0;
    pointer-events: none;
    box-shadow: inset 0 0 0 3px var(--ac, var(--brass));
    opacity: 0.95;
  }
  .steps .step .hero-photo img {
    width: 100%; height: 100%;
    object-fit: cover; display: block;
    filter: saturate(0.9) contrast(1.03);
  }
  .steps .step .hero-meta {
    margin-top: 18px;
    display: flex; flex-direction: column; gap: 3px;
  }
  .steps .step .hero-name {
    font-family: var(--serif);
    font-size: 18px;
    font-weight: 500;
    color: var(--bone);
    letter-spacing: -0.005em;
    line-height: 1.15;
  }
  .steps .step .hero-role {
    font-family: var(--mono);
    font-size: 9.5px;
    color: var(--bone-4);
    letter-spacing: 0.16em;
    text-transform: uppercase;
    margin-top: 2px;
    margin-bottom: 10px;
  }
  .steps .step .hero-line {
    font-family: var(--serif);
    font-style: italic;
    font-size: 13.5px;
    line-height: 1.5;
    color: rgba(245,242,236,0.72);
  }
  .steps .step .hero-line + .hero-line { margin-top: 2px; }
  .steps .step .step-meta-col {
    display: flex; flex-direction: column; gap: 22px;
    padding-top: 4px;
    max-width: 420px;
  }
  .steps .step .step-meta-col .detail { margin: 0; }
  .steps .step .step-meta-col .step-desc {
    border-top: none;
    padding-top: 0;
    font-family: var(--serif);
    font-style: italic;
    font-size: 15px;
    line-height: 1.6;
    color: rgba(245,242,236,0.72);
    max-width: none;
  }
  @media (max-width: 960px) {
    .steps .step .step-body {
      grid-template-columns: 1fr;
      gap: 32px;
    }
    .steps .step .agent-card:nth-child(2) { margin-top: 0; }
    .steps .step .step-photo-col { gap: 24px; }
  }

  """

# Inject just before the nav block marker
if MOD9_END_MARK not in template_html:
    sys.exit("FATAL: nav marker missing from template")
template_html = template_html.replace(MOD9_END_MARK, NEW_CSS + MOD9_END_MARK, 1)
print("[1/3] CSS replaced with Mod-10 unified block")

# ---------- 3) Rewrite sections.jsx ----------
SECTIONS_UUID = '6641f2bf-70da-46eb-a716-a60b6030f1c7'
sec_entry = manifest[SECTIONS_UUID]
sec_raw = gzip.decompress(base64.b64decode(sec_entry['data'])).decode('utf-8')

# The previous render had a conditional `solo` branch. Replace the whole
# `{t.steps.map((s,i) => ...)}` with a single unified renderer.
#
# Use a regex to find the block from "{t.steps.map((s,i) =>" up to its closing ")}"
# balanced. Use a marker-based approach: we know it starts with
# "{t.steps.map((s,i) => {" (after Mod 9) and ends with "})}" on a line.

OLD_START = "            {t.steps.map((s,i) => {"
OLD_END_MARK = "            })}"

if OLD_START not in sec_raw or OLD_END_MARK not in sec_raw:
    sys.exit("FATAL: Mod-9 render block markers not found in JSX — manual fix required")

start_idx = sec_raw.index(OLD_START)
# find the next OLD_END_MARK after start_idx
end_idx = sec_raw.index(OLD_END_MARK, start_idx) + len(OLD_END_MARK)

NEW_RENDER = """            {t.steps.map((s,i) => (
              <div key={i} className=\"step\">
                <div className=\"step-head\">
                  <div className=\"num\">{s.r}</div>
                  <div className=\"step-title\"><h3>{s.t}</h3></div>
                </div>
                <div className=\"step-body\">
                  <div className=\"step-photo-col\">
                    {s.agents.map((a,j) => (
                      <div key={j} className=\"agent-card\" style={{'--ac': a.ac || 'var(--brass)'}}>
                        <div className=\"hero-photo\"><img src={AV(a.av)} alt={a.n}/></div>
                        <div className=\"hero-meta\">
                          <div className=\"hero-name\">{a.n}</div>
                          <div className=\"hero-role\">{a.role}</div>
                          {a.lines.map((ln,k) => (<div key={k} className=\"hero-line\">{ln}</div>))}
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className=\"step-meta-col\">
                    <div className=\"detail\">{s.detail}</div>
                    <div className=\"step-desc\">{s.d}</div>
                  </div>
                </div>
              </div>
            ))}"""

sec_raw_new = sec_raw[:start_idx] + NEW_RENDER + sec_raw[end_idx:]
print(f"[2/3] JSX render unified — old render block ({end_idx - start_idx} chars) replaced")

# Re-encode sections module
sec_compressed = base64.b64encode(gzip.compress(sec_raw_new.encode('utf-8'))).decode('ascii')
manifest[SECTIONS_UUID] = {
    "mime": sec_entry.get('mime', 'application/javascript'),
    "compressed": True,
    "data": sec_compressed,
}

# ---------- 4) Write back ----------
new_manifest_body = json.dumps(manifest, separators=(',', ':'))
new_template_body = json.dumps(template_html)
new_template_body = new_template_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")

# m_start/m_close etc are from the ORIGINAL content; we need to splice manifest first
new_content = content[:m_start] + new_manifest_body + content[m_close:]
# re-locate template offsets in the rewritten content
t_open2, t_start2, t_close2 = extract(new_content, '__bundler/template')
new_content = new_content[:t_start2] + new_template_body + new_content[t_close2:]

SRC.write_text(new_content)
print(f"[3/3] index.html written — {len(new_content)} bytes")
