#!/usr/bin/env python3
"""
Mod 15 — Galerie projets « № 04 · The work » dans le preview Mod 14.

Insère une nouvelle section ``OurWork`` entre ``OurAgents`` (№ 03) et la CTA
qui devient ``№ 05 · Correspondence``. Six cards (logifleet, pharma, telecom,
b2b-distribution, energy, retail) en grille 3×2 avec hover panneau slide-up.

Patches :
- manifest        : 6 entrées covers JPEG (compressed=False, mime image/jpeg)
- ext_resources   : 6 entrées cvLogifleet / cvPharma / cvTelecom /
                    cvB2bDistribution / cvEnergy / cvRetail
- avatars.jsx     : ajoute ``OurWork`` avant ``CTA``, renumérote la CTA
                    (№ 04 → № 05), et expose ``OurWork`` sur ``window``
- template (CSS)  : règles ``.work-grid`` / ``.work-card`` / ``.work-hover``
- template (JSX)  : ``<OurWork lang={lang}/>`` injecté entre OurAgents et CTA

Pièges traités (cf. REPRISE_MEMO §⚠️) :
1. apostrophes typographiques ’ (U+2019) dans toutes les strings JSX
2. caractère · (U+00B7) en UTF-8 direct, ``ensure_ascii=False`` au dump
3. escape ``</script>`` → ``<\\u002Fscript>`` et idem pour ``</style>``
"""
from __future__ import annotations

import base64
import gzip
import json
import re
import sys
import uuid as uuidlib
from pathlib import Path

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SRC = Path('/var/www/dh-preview/index.html')
COVERS_DIR = Path('/root/workspace/digital-humans-production/assets/covers')
AVATARS_UUID = 'b077057a-5a3a-41a8-8f45-fe3c0011a134'

# (project_id, ext_resources_id) — l’id ext_resources suit la convention
# `cv` + camelCase tirée du helper COVER côté JS.
PROJECTS_FOR_BUNDLE = [
    ('logifleet',         'cvLogifleet'),
    ('pharma',            'cvPharma'),
    ('telecom',           'cvTelecom'),
    ('b2b-distribution',  'cvB2bDistribution'),
    ('energy',            'cvEnergy'),
    ('retail',            'cvRetail'),
]

# ---------------------------------------------------------------------------
# OurWork — JSX module à injecter dans avatars.jsx (avant function CTA)
# ---------------------------------------------------------------------------
# IMPORTANT — toutes les apostrophes des strings JSX sont typographiques (’).
# Les · sont en UTF-8 direct (pas d’escape ·).

OUR_WORK_JSX = r"""
const PROJECTS = [
  {
    id: 'logifleet',
    industry:  { en: 'LOGISTICS · B2B', fr: 'LOGISTIQUE · B2B' },
    title:     { en: 'LogiFleet — Fleet Service Cloud',
                 fr: 'LogiFleet — Fleet Service Cloud' },
    punchline: { en: 'A 320-vehicle fleet brought into Service Cloud in eight days. Drivers, dispatch, maintenance — one canonical record per asset.',
                 fr: 'Une flotte de 320 véhicules basculée dans Service Cloud en huit jours. Chauffeurs, dispatch, maintenance — un seul enregistrement canonique par actif.' },
    scope:    ['Service Cloud · Field Service · 320 assets',
               '12 custom objects · 47 flows · 9 LWC',
               'Live in production, week 11 · 0 critical bugs'],
    sds_url: 'https://digital-humans.fr/sds-preview/146.html',
  },
  {
    id: 'pharma',
    industry:  { en: 'PHARMA · CLINICAL TRIALS', fr: 'PHARMA · ESSAIS CLINIQUES' },
    title:     { en: 'Clinical Trial Watch', fr: 'Clinical Trial Watch' },
    punchline: { en: 'A regulated trial pipeline turned into a single Salesforce dashboard. Sites, enrolments, deviations — every event audit-trailed.',
                 fr: 'Un pipeline d’essais cliniques régulés transformé en un seul dashboard Salesforce. Sites, recrutements, déviations — chaque événement traçable.' },
    scope:    ['Health Cloud · Experience Cloud · 21 CFR Part 11',
               '38 trial sites · 1 200 enrolments tracked',
               'Audit-ready logs, end-to-end'],
    sds_url: null,
  },
  {
    id: 'telecom',
    industry:  { en: 'TELECOM · CLAIMS', fr: 'TÉLÉCOM · RÉCLAMATIONS' },
    title:     { en: 'Claim Resolver', fr: 'Claim Resolver' },
    punchline: { en: '14-day average resolution dropped to 4. Claims triaged by Einstein, dispatched by Sophie, audited by Elena.',
                 fr: 'Délai moyen de résolution passé de 14 à 4 jours. Réclamations triées par Einstein, dispatchées par Sophie, auditées par Elena.' },
    scope:    ['Service Cloud · Einstein Bots · Omnichannel',
               '110 000 claims/year · 87% first-touch resolution',
               '−71% AHT, +12 NPS in two quarters'],
    sds_url: null,
  },
  {
    id: 'b2b-distribution',
    industry:  { en: 'B2B · DISTRIBUTION', fr: 'B2B · DISTRIBUTION' },
    title:     { en: 'Pipeline Tuner', fr: 'Pipeline Tuner' },
    punchline: { en: 'Twelve regional sales pipelines reconciled into one consolidated view. Forecast accuracy up from 68% to 91% in the first quarter.',
                 fr: 'Douze pipelines commerciaux régionaux réconciliés en une vue consolidée. Précision du forecast passée de 68% à 91% au premier trimestre.' },
    scope:    ['Sales Cloud · CPQ · Tableau CRM',
               '12 regions · 240 reps · €310M ARR tracked',
               '+23 forecast accuracy points'],
    sds_url: null,
  },
  {
    id: 'energy',
    industry:  { en: 'ENERGY · GRID', fr: 'ÉNERGIE · RÉSEAU' },
    title:     { en: 'Grid Foresight', fr: 'Grid Foresight' },
    punchline: { en: 'High-voltage maintenance scheduling moved from spreadsheets to Salesforce. Outage windows down 38%, asset uptime up 6 points.',
                 fr: 'Planification de la maintenance haute tension basculée des spreadsheets vers Salesforce. Fenêtres de coupure −38%, disponibilité des actifs +6 points.' },
    scope:    ['Field Service · Asset 360 · Net Zero Cloud',
               '4 800 high-voltage assets monitored',
               'Predictive maintenance via Einstein Discovery'],
    sds_url: null,
  },
  {
    id: 'retail',
    industry:  { en: 'RETAIL · OMNICHANNEL', fr: 'RETAIL · OMNICANAL' },
    title:     { en: 'Omnichannel Loop', fr: 'Omnichannel Loop' },
    punchline: { en: 'Fifty stores, one customer record. Loyalty events, returns, e-commerce orders, in-store visits — stitched into a single graph.',
                 fr: 'Cinquante magasins, un seul dossier client. Événements de fidélité, retours, commandes e-commerce, visites en magasin — cousus dans un seul graphe.' },
    scope:    ['Commerce Cloud · Marketing Cloud · Loyalty',
               '50 stores · 1.4M customers unified',
               '+18% repeat purchase rate'],
    sds_url: null,
  },
];

const COVER = id => {
  const key = 'cv' + id.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
  return (typeof AV === 'function' ? AV(key) : null) || ('assets/covers/' + id + '.jpg');
};

function OurWork({lang}) {
  const t = lang === 'en'
    ? { num:   '№ 04 · The work',
        head:  'Six fields, one rim rule.',
        lede:  'Each engagement is a single Salesforce solution composed by the ensemble. Six are public ; the rest live behind NDAs we are happy to honour.',
        cta:   'Read the SDS',
        soon:  'SDS · coming soon' }
    : { num:   '№ 04 · L’atelier',
        head:  'Six terrains, une règle.',
        lede:  'Chaque mission est une solution Salesforce composée par l’ensemble. Six sont publiques ; les autres vivent derrière des NDA que nous respectons volontiers.',
        cta:   'Lire le SDS',
        soon:  'SDS · bientôt' };
  return (
    <section id="work" className="block">
      <div className="wrap">
        <div className="section-head">
          <div className="num">{t.num}</div>
          <div>
            <h2>{t.head}</h2>
            <p className="lede">{t.lede}</p>
          </div>
        </div>
        <div className="work-grid">
          {PROJECTS.map(p => (
            <article key={p.id} className="work-card">
              <div className="work-cover">
                <img src={COVER(p.id)} alt={p.title[lang]} loading="lazy"/>
              </div>
              <div className="work-meta">
                <div className="work-industry">{p.industry[lang]}</div>
                <h3 className="work-title">{p.title[lang]}</h3>
                <p className="work-punch">{p.punchline[lang]}</p>
              </div>
              <div className="work-hover">
                <div className="work-hover-industry">{p.industry[lang]}</div>
                <ul className="work-hover-scope">
                  {p.scope.map((s, i) => (<li key={i}>{s}</li>))}
                </ul>
                {p.sds_url
                  ? (<a href={p.sds_url} className="work-hover-cta" target="_blank" rel="noopener">{t.cta}<span className="ar"> →</span></a>)
                  : (<span className="work-hover-soon">{t.soon}</span>)}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

"""

# ---------------------------------------------------------------------------
# CSS — règles à injecter dans le <style> du template
# ---------------------------------------------------------------------------

NEW_CSS = """
  /* ===== Mod 15 — № 04 · The work — gallery ===== */
  .work-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 32px;
    margin-top: 48px;
  }
  @media (max-width: 900px) {
    .work-grid { grid-template-columns: repeat(2, 1fr); }
  }
  @media (max-width: 600px) {
    .work-grid { grid-template-columns: 1fr; }
  }
  .work-card {
    position: relative;
    background: var(--ink-2);
    border: 1px solid rgba(245, 242, 236, 0.06);
    overflow: hidden;
    transition: border-color 280ms ease;
  }
  .work-card:hover {
    border-color: var(--brass-3, var(--brass));
  }
  .work-cover {
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: var(--ink);
  }
  .work-cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    filter: saturate(0.92) contrast(1.02);
  }
  .work-meta {
    padding: 24px 24px 28px;
  }
  .work-industry {
    font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--brass);
    margin-bottom: 12px;
  }
  .work-title {
    font-family: var(--serif, 'Cormorant Garamond', Georgia, serif);
    font-style: italic;
    font-size: 22px;
    font-weight: 500;
    line-height: 1.2;
    color: var(--bone);
    margin: 0 0 10px;
  }
  .work-punch {
    font-family: Inter, -apple-system, sans-serif;
    font-size: 14px;
    line-height: 1.55;
    color: var(--bone-3);
    margin: 0;
  }
  .work-hover {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    background: var(--ink-2);
    border-top: 1px solid var(--brass);
    padding: 24px;
    transform: translateY(100%);
    transition: transform 280ms ease-out;
    pointer-events: none;
  }
  .work-card:hover .work-hover,
  .work-card:focus-within .work-hover {
    transform: translateY(0);
    pointer-events: auto;
  }
  .work-hover-industry {
    font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--brass);
    margin-bottom: 14px;
  }
  .work-hover-scope {
    list-style: none;
    padding: 0;
    margin: 0 0 18px;
  }
  .work-hover-scope li {
    font-family: Inter, -apple-system, sans-serif;
    font-size: 13px;
    line-height: 1.55;
    color: var(--bone-3);
    margin-bottom: 6px;
    padding-left: 14px;
    position: relative;
  }
  .work-hover-scope li::before {
    content: '·';
    position: absolute;
    left: 0;
    color: var(--brass);
  }
  .work-hover-cta {
    font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--brass);
    text-decoration: none;
  }
  .work-hover-cta .ar { margin-left: 6px; }
  .work-hover-soon {
    font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--bone-4);
  }
"""

CSS_INJECT_MARK = '/* ===== Sequence navigation : arrows + dots ===== */'

# ---------------------------------------------------------------------------
# Patch utilities
# ---------------------------------------------------------------------------

def _decode_module(entry: dict) -> str:
    raw = base64.b64decode(entry['data'])
    if entry.get('compressed'):
        raw = gzip.decompress(raw)
    return raw.decode('utf-8')


def _encode_module(text: str, mime: str) -> dict:
    data = base64.b64encode(gzip.compress(text.encode('utf-8'))).decode('ascii')
    return {"mime": mime, "compressed": True, "data": data}


def _reencode_module(orig_entry: dict, new_text: str) -> dict:
    """Ré-encode en respectant le flag compressed et le mime de l'entrée d'origine."""
    new_entry = dict(orig_entry)
    encoded = new_text.encode('utf-8')
    if orig_entry.get('compressed'):
        new_entry['data'] = base64.b64encode(gzip.compress(encoded)).decode('ascii')
    else:
        new_entry['data'] = base64.b64encode(encoded).decode('ascii')
    return new_entry


def _renumber_cta(av_raw: str) -> str:
    """№ 04 · Correspondence|Correspondance → № 05 · …."""
    pairs = [
        ("№ 04 · Correspondence", "№ 05 · Correspondence"),
        ("№ 04 · Correspondance", "№ 05 · Correspondance"),
    ]
    for old, new in pairs:
        if av_raw.count(old) != 1:
            sys.exit(f"FATAL: expected exactly 1 occurrence of '{old}' in avatars.jsx, found {av_raw.count(old)}")
        av_raw = av_raw.replace(old, new, 1)
    return av_raw


def _inject_our_work(av_raw: str) -> str:
    """Insère OUR_WORK_JSX avant la déclaration ``function CTA(``."""
    if 'function OurWork' in av_raw:
        sys.exit("FATAL: OurWork already present in avatars.jsx — Mod 15 déjà appliqué ?")
    m = re.search(r'\nfunction\s+CTA\s*\(', av_raw)
    if not m:
        sys.exit("FATAL: 'function CTA(' anchor not found in avatars.jsx")
    return av_raw[:m.start()] + '\n' + OUR_WORK_JSX + av_raw[m.start():]


def _expose_our_work_on_window(av_raw: str) -> str:
    """Ajoute ``OurWork`` à ``Object.assign(window, {…})`` s’il n’y est pas."""
    pattern = re.compile(
        r'(Object\.assign\(\s*window\s*,\s*\{)([^}]*?)(\}\s*\))',
        re.DOTALL,
    )
    m = pattern.search(av_raw)
    if not m:
        # fallback : pas tous les bundles utilisent Object.assign — chercher
        # un export simple ``window.OurAgents = OurAgents`` et y ajouter
        # ``window.OurWork = OurWork``.
        m2 = re.search(r'(window\.OurAgents\s*=\s*OurAgents\s*;?)', av_raw)
        if m2 and 'window.OurWork' not in av_raw:
            return av_raw[:m2.end()] + '\nwindow.OurWork = OurWork;' + av_raw[m2.end():]
        sys.exit("FATAL: aucun point d’export window.{OurAgents,...} trouvé dans avatars.jsx")

    body = m.group(2)
    if 'OurWork' in body:
        return av_raw  # déjà exposé
    new_body = body.rstrip().rstrip(',') + ', OurWork'
    return av_raw[:m.start()] + m.group(1) + new_body + m.group(3) + av_raw[m.end():]


def _inject_composition_in_module(module_content: str) -> str:
    """Insère ``<OurWork lang={lang}/>`` entre ``<OurAgents…/>`` et ``<CTA…/>``
    dans le module JS du Site (UUID 0fbb2257-1e1f-4b29-9a76-…).
    
    Le composant Site est défini dans un module JS séparé du __bundler/template,
    donc la composition est dans le content du module, pas dans le HTML.
    """
    if '<OurWork lang={lang}/>' in module_content:
        return module_content  # idempotent
    pat = re.compile(
        r'(<OurAgents\s+lang=\{lang\}\s*/>)(\s*)(<CTA\s+lang=\{lang\}\s*/>)'
    )
    new_content, n = pat.subn(
        r'\1\2<OurWork lang={lang}/>\2\3',
        module_content, count=1,
    )
    if n != 1:
        sys.exit("FATAL: composition <OurAgents…/><CTA…/> introuvable dans le module Site")
    return new_content


def _inject_composition(template_html: str) -> str:
    """No-op : composition is in a separate JS module, not the template HTML."""
    return template_html


def _inject_css(template_html: str) -> str:
    if CSS_INJECT_MARK not in template_html:
        sys.exit(f"FATAL: marker CSS introuvable: '{CSS_INJECT_MARK}'")
    if '/* ===== Mod 15 —' in template_html:
        return template_html  # idempotent
    return template_html.replace(CSS_INJECT_MARK, NEW_CSS + '\n  ' + CSS_INJECT_MARK, 1)


def _replace_block(content: str, m: re.Match, new_body: str) -> str:
    return content[:m.start()] + m.group(1) + new_body + m.group(3) + content[m.end():]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not SRC.exists():
        sys.exit(f"FATAL: bundle introuvable — {SRC}")
    if not COVERS_DIR.exists():
        sys.exit(f"FATAL: dossier covers introuvable — {COVERS_DIR}")

    # Backup obligatoire avant patch (convention pre-modN du REPRISE_MEMO).
    backup = SRC.with_suffix(SRC.suffix + '.pre-mod15')
    if not backup.exists():
        backup.write_bytes(SRC.read_bytes())
        print(f"[backup] {backup} créé")
    else:
        print(f"[backup] {backup} existe déjà — conservé tel quel")

    content = SRC.read_text()
    print(f"[0] index.html chargé — {len(content):,} bytes")

    m_manifest = re.search(
        r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)',
        content, re.DOTALL,
    )
    m_ext = re.search(
        r'(<script\s+type="__bundler/ext_resources"[^>]*>)(.*?)(</script>)',
        content, re.DOTALL,
    )
    m_template = re.search(
        r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)',
        content, re.DOTALL,
    )
    if not (m_manifest and m_ext and m_template):
        sys.exit("FATAL: l’une des trois sections __bundler/* est manquante")

    manifest = json.loads(m_manifest.group(2).strip())
    ext_resources = json.loads(m_ext.group(2).strip())
    template_html = json.loads(m_template.group(2).strip())
    print(f"[1] sections parsées — manifest={len(manifest)}, ext_resources={len(ext_resources)}")

    # 2) Covers → manifest + ext_resources
    total_bytes = 0
    for project_id, ext_id in PROJECTS_FOR_BUNDLE:
        cover_path = COVERS_DIR / f'{project_id}.jpg'
        if not cover_path.exists():
            sys.exit(f"FATAL: cover introuvable — {cover_path}")
        data = cover_path.read_bytes()
        total_bytes += len(data)
        cover_uuid = str(uuidlib.uuid4())
        manifest[cover_uuid] = {
            "mime": "image/jpeg",
            "compressed": False,
            "data": base64.b64encode(data).decode('ascii'),
        }
        ext_resources = [r for r in ext_resources if r.get('id') != ext_id]
        ext_resources.append({"id": ext_id, "uuid": cover_uuid})
        print(f"    {ext_id:<22s} → {len(data):>7,} bytes")
    print(f"[2] 6 covers injectées — {total_bytes:,} bytes")

    # 3) avatars.jsx : OurWork + renumérotation CTA + window.OurWork
    if AVATARS_UUID not in manifest:
        sys.exit(f"FATAL: UUID avatars.jsx ({AVATARS_UUID}) absent du manifest")
    av_entry = manifest[AVATARS_UUID]
    av_raw = _decode_module(av_entry)
    Path('/tmp/avatars_before_mod15.jsx').write_text(av_raw)

    av_raw = _renumber_cta(av_raw)
    av_raw = _inject_our_work(av_raw)
    av_raw = _expose_our_work_on_window(av_raw)
    print("[3] avatars.jsx patché (OurWork + CTA №05 + window.OurWork)")

    manifest[AVATARS_UUID] = _encode_module(av_raw, av_entry.get('mime', 'application/javascript'))
    Path('/tmp/avatars_after_mod15.jsx').write_text(av_raw)

    # 4) template : CSS + composition
    template_html = _inject_css(template_html)
    template_html = _inject_composition(template_html)  # no-op désormais

    # ---- Patch du module JS Site ----------------------------------------
    # La composition <OurAgents/><CTA/> vit dans un module séparé (pas dans
    # le template HTML), donc on doit le patcher dans le manifest.
    site_uuid = None
    for uuid_, entry_ in list(manifest.items()):
        if 'application/javascript' in entry_.get('mime', '') or 'jsx' in entry_.get('mime', ''):
            try:
                content_ = _decode_module(entry_)
                if '<OurAgents lang={lang}/>' in content_ and '<CTA lang={lang}/>' in content_:
                    site_uuid = uuid_
                    site_content_old = content_
                    break
            except Exception:
                continue
    if not site_uuid:
        sys.exit("FATAL: module JS contenant <OurAgents lang={lang}/><CTA…/> introuvable dans le manifest")
    
    site_content_new = _inject_composition_in_module(site_content_old)
    if site_content_new != site_content_old:
        manifest[site_uuid] = _reencode_module(manifest[site_uuid], site_content_new)
        print(f"[5b] Site module {site_uuid[:12]}... patché — <OurWork/> inséré")
    else:
        print(f"[5b] Site module {site_uuid[:12]}... déjà à jour (idempotent)")

    print("[4] template patché (CSS + <OurWork lang={lang}/>)")

    # 5) Réécriture des trois sections
    new_manifest_body = json.dumps(manifest, separators=(',', ':'))
    new_ext_body = json.dumps(ext_resources, separators=(',', ':'))
    new_template_body = json.dumps(template_html, ensure_ascii=False)
    # Escape critique : empêcher le parser HTML de fermer prématurément le
    # <script type="__bundler/template">. JSON.parse au runtime décode /
    # en / et reconstitue les balises littérales attendues par Babel.
    new_template_body = (new_template_body
                         .replace("</script>", r"<\u002Fscript>")
                         .replace("</style>",  r"<\u002Fstyle>"))

    # On remplace les blocs en partant de la fin pour que les offsets restent
    # valides au fur et à mesure des substitutions.
    new_content = content
    for m, new_body in sorted(
        [(m_manifest, new_manifest_body),
         (m_ext, new_ext_body),
         (m_template, new_template_body)],
        key=lambda t: t[0].start(),
        reverse=True,
    ):
        new_content = _replace_block(new_content, m, new_body)

    SRC.write_text(new_content)
    diff = len(new_content) - len(content)
    print(f"[5] index.html écrit — {len(new_content):,} bytes (Δ={diff:+,})")
    print(f"    manifest: {len(m_manifest.group(2))} → {len(new_manifest_body)} chars")
    print(f"    ext_res : {len(m_ext.group(2))} → {len(new_ext_body)} chars")
    print(f"    template: {len(m_template.group(2))} → {len(new_template_body)} chars")


if __name__ == '__main__':
    main()
