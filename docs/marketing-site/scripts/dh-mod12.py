#!/usr/bin/env python3
"""
Mod 12 — Inject 10 remaining agent photos in batch + enrich bilingual roles + ac colors.
Sophie was already done in Mod 9. We don't touch her here.

Pattern reused from Mod 9 :
- Replace each agent's SVG placeholder by the corresponding JPEG in manifest
- Add ac (agent color hex) and update role (bilingual EN/FR) for each agent
"""
import re, json, base64, gzip, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
PHOTOS_DIR = Path('/tmp/agents-photos')

# Mapping agent -> {uuid (avXxx), photo file, accent hex, role EN, role FR}
AGENTS = {
    'olivia': {
        'uuid': 'b9895109-82c7-4aa0-b086-2708967854a6',
        'photo': 'Generated Image April 19, 2026 - 8_25PM.jpg',
        'ac': '#3B82F6',
        'role_en_old': 'Business Analyst',
        'role_en_new': 'Business Analyst · The Interpreter',
        'role_fr_old': 'Business Analyst',
        'role_fr_new': "Business Analyst · L’Interprete",
    },
    'emma': {
        'uuid': 'cd501775-3dea-4e13-b833-587390e26a1f',
        'photo': 'Generated Image April 19, 2026 - 8_28PM.jpg',
        'ac': '#06B6D4',
        'role_en_old': 'Research',
        'role_en_new': 'Research Analyst · The Verifier',
        'role_fr_old': 'Research Analyst',
        'role_fr_new': 'Research Analyst · La Verificatrice',
    },
    'marcus': {
        'uuid': '4a42e7a8-096b-431d-9276-2c80f185ad60',
        'photo': 'Generated Image April 19, 2026 - 8_36PM.jpg',
        'ac': '#F97316',
        'role_en_old': 'Architect',
        'role_en_new': 'Solution Architect · The Builder of Shapes',
        'role_fr_old': 'Architecte Solution',
        'role_fr_new': 'Architecte Solution · Le Batisseur',
    },
    'diego': {
        'uuid': 'a18a6c38-23e2-4fb1-9bc6-1e2b8f1c4885',
        'photo': 'Generated Image April 19, 2026 - 8_37PM.jpg',
        'ac': '#EF4444',
        'role_en_old': 'Apex',
        'role_en_new': 'Apex Developer · The Pianist',
        'role_fr_old': 'Développeur Apex',
        'role_fr_new': 'Développeur Apex · Le Pianiste',
    },
    'zara': {
        'uuid': '2580dfa5-4fd1-4fb5-bfb6-c956ed2d8f18',
        'photo': 'Generated Image April 19, 2026 - 8_41PM.jpg',
        'ac': '#22C55E',
        'role_en_old': 'LWC',
        'role_en_new': 'LWC Developer · The Painter',
        'role_fr_old': 'Développeuse LWC',
        'role_fr_new': 'Développeuse LWC · La Peintre',
    },
    'raj': {
        'uuid': '938d750e-beca-4ccc-b66f-f766e6226a45',
        'photo': 'Generated Image April 19, 2026 - 8_42PM.jpg',
        'ac': '#EAB308',
        'role_en_old': 'Administrator',
        'role_en_new': 'Administrator · The No-Code Wizard',
        'role_fr_old': 'Administrateur',
        'role_fr_new': 'Administrateur · Le Magicien No-Code',
    },
    'aisha': {
        'uuid': '4750abb7-3712-402e-93e7-6caa765f8398',
        'photo': 'Generated Image April 19, 2026 - 8_44PM.jpg',
        'ac': '#92400E',
        'role_en_old': 'Data Migration',
        'role_en_new': 'Data Specialist · The Curator',
        'role_fr_old': 'Migration de Données',
        'role_fr_new': 'Spécialiste Data · La Curatrice',
    },
    'elena': {
        'uuid': 'f04675b6-7c79-4272-9666-ce1de9e148dc',
        'photo': 'Generated Image April 19, 2026 - 8_44PM (1).jpg',
        'ac': '#6B7280',
        'role_en_old': 'QA',
        'role_en_new': 'QA Engineer · The Guardian',
        'role_fr_old': 'Ingénieure QA',
        'role_fr_new': 'Ingénieure QA · La Gardienne',
    },
    'jordan': {
        'uuid': 'f1bb74e3-7ec7-4661-9027-6fc274e6a331',
        'photo': 'Generated Image April 19, 2026 - 8_45PM.jpg',
        'ac': '#1E40AF',
        'role_en_old': 'DevOps',
        'role_en_new': 'DevOps Engineer · The Stagehand',
        'role_fr_old': 'Ingénieur DevOps',
        'role_fr_new': 'Ingénieur DevOps · Le Regisseur',
    },
    'lucas': {
        'uuid': 'f66dd697-5f60-4da9-b2f1-037ae0ffc5a0',
        'photo': 'Generated Image April 19, 2026 - 8_46PM.jpg',
        'ac': '#D946EF',
        'role_en_old': 'Trainer',
        'role_en_new': 'Trainer · The Transmitter',
        'role_fr_old': 'Formateur',
        'role_fr_new': 'Formateur · Le Transmetteur',
    },
}

content = SRC.read_text()
print(f"[0] index.html loaded — {len(content):,} bytes")

# ---------- 1) Parse manifest ----------
m_manifest = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
manifest_open, manifest_body, manifest_close = m_manifest.groups()
manifest = json.loads(manifest_body.strip())
print(f"[1] Manifest parsed — {len(manifest)} entries")

# ---------- 2) Replace 10 SVG placeholders by JPEGs ----------
total_bytes = 0
for name, cfg in AGENTS.items():
    photo_path = PHOTOS_DIR / cfg['photo']
    if not photo_path.exists():
        sys.exit(f"FATAL: photo not found — {photo_path}")
    photo_bytes = photo_path.read_bytes()
    photo_b64 = base64.b64encode(photo_bytes).decode('ascii')
    manifest[cfg['uuid']] = {
        "mime": "image/jpeg",
        "compressed": False,
        "data": photo_b64,
    }
    total_bytes += len(photo_bytes)
    print(f"    av{name.capitalize():<8s} -> JPEG {len(photo_bytes):>7,} bytes")
print(f"[2] 10 photos injected — {total_bytes:,} bytes total")

# ---------- 3) Update sections.jsx ----------
SECTIONS_UUID = '6641f2bf-70da-46eb-a716-a60b6030f1c7'
sec = manifest[SECTIONS_UUID]
sec_raw = gzip.decompress(base64.b64decode(sec['data'])).decode('utf-8') if sec['compressed'] else base64.b64decode(sec['data']).decode('utf-8')

# 3a) Add ac:'...' and update bilingual roles for each agent
patches_done = 0
for name, cfg in AGENTS.items():
    av = name  # av: 'olivia', 'emma', etc
    # EN side : {n:'Olivia Parker',role:'Business Analyst',av:'olivia',...
    en_old = f"{{n:'{{name_en}}',role:'{cfg['role_en_old']}',av:'{av}'"
    # We need actual full names — extract from existing JSX
    # Simpler approach : regex to capture each agent's existing string and patch
    patterns_en = [
        (rf"\{{n:'([^']+)',\s*role:'{re.escape(cfg['role_en_old'])}',\s*av:'{av}'",
         lambda mm, c=cfg: f"{{n:'{mm.group(1)}', role:'{c['role_en_new']}', ac:'{c['ac']}', av:'{av}'"),
    ]
    patterns_fr = [
        (rf"\{{n:'([^']+)',\s*role:'{re.escape(cfg['role_fr_old'])}',\s*av:'{av}'",
         lambda mm, c=cfg: f"{{n:'{mm.group(1)}', role:'{c['role_fr_new']}', ac:'{c['ac']}', av:'{av}'"),
    ]
    
    for pat, repl in patterns_en + patterns_fr:
        new_raw, n = re.subn(pat, repl, sec_raw, count=1)
        if n == 1:
            sec_raw = new_raw
            patches_done += 1
        else:
            print(f"    [WARN] {name}: pattern not matched: {pat[:80]}...")

print(f"[3a] sections.jsx role/ac patches : {patches_done}/{len(AGENTS)*2} expected")

# 3b) Re-encode sections module
sec_compressed = base64.b64encode(gzip.compress(sec_raw.encode('utf-8'))).decode('ascii')
manifest[SECTIONS_UUID] = {
    "mime": sec.get('mime', 'application/javascript'),
    "compressed": True,
    "data": sec_compressed,
}
Path('/tmp/sections_after_mod12.jsx').write_text(sec_raw)
print(f"[3b] sections.jsx re-encoded — saved decoded version to /tmp/sections_after_mod12.jsx")

# ---------- 4) Parse template (no CSS change in mod12) ----------
m_template = re.search(r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
template_open, template_body, template_close = m_template.groups()
template_html = json.loads(template_body.strip())

# ---------- 5) Reconstruct index.html ----------
new_manifest_body = json.dumps(manifest, separators=(',', ':'))
new_template_body = json.dumps(template_html)
# Critical escapes for </script> and </style>
new_template_body = new_template_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")

new_content = (
    content[:m_manifest.start()]
    + manifest_open + new_manifest_body + manifest_close
    + content[m_manifest.end():m_template.start()]
    + template_open + new_template_body + template_close
    + content[m_template.end():]
)

SRC.write_text(new_content)
print(f"[5] index.html written — {len(new_content):,} bytes (was {len(content):,})")
print(f"    diff : +{len(new_content) - len(content):,} bytes")
