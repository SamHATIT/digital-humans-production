#!/usr/bin/env python3
"""
Mod 16 — Galerie projets en slider horizontal flip 3D, REMPLACE le trombinoscope.

- La galerie remplace OurAgents (retiré de la composition Site)
- Format slider horizontal (squelette HowItWorks acte 2)
- Slide : photo cover plein format, titre + industrie en overlay (gradient ink bottom 40%)
- Hover : flip 3D rotateY 180° (600ms) → verso (scope + punchline + CTA SDS)
- Mobile : tap toggle .flipped
- Bug COVER fixé : R[key] direct (plus de AV() qui re-préfixait 'av')
- CTA renumérotée № 05 → № 04
- Tagline : "Whatever theatre of work, one rim rule."

Numérotation site : 01 The case · 02 The sequence · 03 The work · 04 Correspondence
"""
from __future__ import annotations
import base64, gzip, json, re, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
AVATARS_UUID = 'b077057a-5a3a-41a8-8f45-fe3c0011a134'

OUR_WORK_JSX = r"""
const PROJECTS = [
  {
    id: 'logifleet', roman: 'I',
    industry:  { en: 'LOGISTICS · B2B', fr: 'LOGISTIQUE · B2B' },
    title:     { en: 'LogiFleet — Fleet Service Cloud', fr: 'LogiFleet — Fleet Service Cloud' },
    punchline: { en: 'A 320-vehicle fleet brought into Service Cloud in eight days. Drivers, dispatch, maintenance — one canonical record per asset.',
                 fr: 'Une flotte de 320 véhicules basculée dans Service Cloud en huit jours. Chauffeurs, dispatch, maintenance — un seul enregistrement canonique par actif.' },
    scope: ['Service Cloud · Field Service · 320 assets',
            '12 custom objects · 47 flows · 9 LWC',
            'Live in production, week 11 · 0 critical bugs'],
    sds_url: 'https://digital-humans.fr/sds-preview/146.html',
  },
  {
    id: 'pharma', roman: 'II',
    industry:  { en: 'PHARMA · CLINICAL TRIALS', fr: 'PHARMA · ESSAIS CLINIQUES' },
    title:     { en: 'Clinical Trial Watch', fr: 'Clinical Trial Watch' },
    punchline: { en: 'A regulated trial pipeline turned into a single Salesforce dashboard. Sites, enrolments, deviations — every event audit-trailed.',
                 fr: 'Un pipeline d’essais cliniques régulés transformé en un seul dashboard Salesforce. Sites, recrutements, déviations — chaque événement traçable.' },
    scope: ['Health Cloud · Experience Cloud · 21 CFR Part 11',
            '38 trial sites · 1 200 enrolments tracked',
            'Audit-ready logs, end-to-end'],
    sds_url: null,
  },
  {
    id: 'telecom', roman: 'III',
    industry:  { en: 'TELECOM · CLAIMS', fr: 'TÉLÉCOM · RÉCLAMATIONS' },
    title:     { en: 'Claim Resolver', fr: 'Claim Resolver' },
    punchline: { en: '14-day average resolution dropped to 4. Claims triaged by Einstein, dispatched by Sophie, audited by Elena.',
                 fr: 'Délai moyen de résolution passé de 14 à 4 jours. Réclamations triées par Einstein, dispatchées par Sophie, auditées par Elena.' },
    scope: ['Service Cloud · Einstein Bots · Omnichannel',
            '110 000 claims/year · 87% first-touch resolution',
            '−71% AHT, +12 NPS in two quarters'],
    sds_url: null,
  },
  {
    id: 'b2b-distribution', roman: 'IV',
    industry:  { en: 'B2B · DISTRIBUTION', fr: 'B2B · DISTRIBUTION' },
    title:     { en: 'Pipeline Tuner', fr: 'Pipeline Tuner' },
    punchline: { en: 'Twelve regional sales pipelines reconciled into one consolidated view. Forecast accuracy up from 68% to 91% in the first quarter.',
                 fr: 'Douze pipelines commerciaux régionaux réconciliés en une vue consolidée. Précision du forecast passée de 68% à 91% au premier trimestre.' },
    scope: ['Sales Cloud · CPQ · Tableau CRM',
            '12 regions · 240 reps · €310M ARR tracked',
            '+23 forecast accuracy points'],
    sds_url: null,
  },
  {
    id: 'energy', roman: 'V',
    industry:  { en: 'ENERGY · GRID', fr: 'ÉNERGIE · RÉSEAU' },
    title:     { en: 'Grid Foresight', fr: 'Grid Foresight' },
    punchline: { en: 'High-voltage maintenance scheduling moved from spreadsheets to Salesforce. Outage windows down 38%, asset uptime up 6 points.',
                 fr: 'Planification de la maintenance haute tension basculée des spreadsheets vers Salesforce. Fenêtres de coupure −38%, disponibilité des actifs +6 points.' },
    scope: ['Field Service · Asset 360 · Net Zero Cloud',
            '4 800 high-voltage assets monitored',
            'Predictive maintenance via Einstein Discovery'],
    sds_url: null,
  },
  {
    id: 'retail', roman: 'VI',
    industry:  { en: 'RETAIL · OMNICHANNEL', fr: 'RETAIL · OMNICANAL' },
    title:     { en: 'Omnichannel Loop', fr: 'Omnichannel Loop' },
    punchline: { en: 'Fifty stores, one customer record. Loyalty events, returns, e-commerce orders, in-store visits — stitched into a single graph.',
                 fr: 'Cinquante magasins, un seul dossier client. Événements de fidélité, retours, commandes e-commerce, visites en magasin — cousus dans un seul graphe.' },
    scope: ['Commerce Cloud · Marketing Cloud · Loyalty',
            '50 stores · 1.4M customers unified',
            '+18% repeat purchase rate'],
    sds_url: null,
  },
];

// Mod 16 fix: COVER accède directement à R[key] (plus de AV() qui re-préfixe 'av')
const COVER = id => {
  const R = (window.__resources || {});
  const key = 'cv' + id.split('-').map(s => s[0].toUpperCase() + s.slice(1)).join('');
  return R[key] || ('assets/covers/' + id + '.jpg');
};

function OurWork({lang}) {
  const scrollerRef = React.useRef(null);
  const [activeIdx, setActiveIdx] = React.useState(0);

  React.useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    let rafId = null;
    const onScroll = () => {
      if (rafId) cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        const w = el.clientWidth;
        const i = Math.round(el.scrollLeft / w);
        const total = PROJECTS.length;
        const clamped = Math.max(0, Math.min(total - 1, i));
        setActiveIdx(clamped);
      });
    };
    el.addEventListener('scroll', onScroll, {passive: true});
    return () => { el.removeEventListener('scroll', onScroll); if (rafId) cancelAnimationFrame(rafId); };
  }, []);

  const goTo = (i) => {
    const el = scrollerRef.current;
    if (!el) return;
    const total = PROJECTS.length;
    const clamped = Math.max(0, Math.min(total - 1, i));
    el.scrollTo({left: clamped * el.clientWidth, behavior: 'smooth'});
  };

  const onSlideTap = (e) => {
    if (window.matchMedia && window.matchMedia('(hover: hover)').matches) return;
    e.currentTarget.classList.toggle('flipped');
  };

  const t = lang === 'en'
    ? { num: '№ 03 · The work',
        title: (<>Whatever theatre of work, <em>one rim rule</em>.</>),
        lede: 'Each engagement is a single Salesforce solution composed by the ensemble. Six are public ; the rest live behind NDAs we are happy to honour.',
        cta: 'Read the SDS', soon: 'SDS · coming soon' }
    : { num: '№ 03 · L’atelier',
        title: (<>Quel que soit le théâtre, <em>une seule règle</em>.</>),
        lede: 'Chaque mission est une solution Salesforce composée par l’ensemble. Six sont publiques ; les autres vivent derrière des NDA que nous respectons volontiers.',
        cta: 'Lire le SDS', soon: 'SDS · bientôt' };

  const isFirst = activeIdx === 0;
  const isLast = activeIdx === PROJECTS.length - 1;

  return (
    <section id="work" className="block">
      <div className="wrap">
        <div className="section-head">
          <div className="num">{t.num}</div>
          <div>
            <h2>{t.title}</h2>
            <p className="lede">{t.lede}</p>
          </div>
        </div>
        <div className="sequence-container work-sequence">
          <div className="steps work-steps" ref={scrollerRef}>
            {PROJECTS.map((p, i) => (
              <div key={p.id} className="step work-slide" onClick={onSlideTap}>
                <div className="work-flip">
                  <div className="work-face work-face-front">
                    <img className="work-cover-img" src={COVER(p.id)} alt={p.title[lang]} loading="lazy"/>
                    <div className="work-cover-gradient"></div>
                    <div className="work-cover-overlay">
                      <div className="work-eyebrow">
                        <span className="work-roman">{p.roman}</span>
                        <span className="work-sep"> · </span>
                        <span>{p.industry[lang]}</span>
                      </div>
                      <h3 className="work-title">{p.title[lang]}</h3>
                    </div>
                  </div>
                  <div className="work-face work-face-back">
                    <div className="work-eyebrow">
                      <span className="work-roman">{p.roman}</span>
                      <span className="work-sep"> · </span>
                      <span>{p.industry[lang]}</span>
                    </div>
                    <h3 className="work-title">{p.title[lang]}</h3>
                    <ul className="work-scope">
                      {p.scope.map((s, k) => (<li key={k}>{s}</li>))}
                    </ul>
                    <p className="work-punch">{p.punchline[lang]}</p>
                    {p.sds_url
                      ? (<a href={p.sds_url} className="work-cta" target="_blank" rel="noopener">{t.cta}<span className="ar"> →</span></a>)
                      : (<span className="work-soon">{t.soon}</span>)}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <button className="seq-arrow seq-prev" onClick={() => goTo(activeIdx - 1)} disabled={isFirst} aria-label="Previous project">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M15 6l-6 6 6 6"/></svg>
          </button>
          <button className="seq-arrow seq-next" onClick={() => goTo(activeIdx + 1)} disabled={isLast} aria-label="Next project">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6"/></svg>
          </button>
        </div>
        <div className="seq-dots" role="tablist" aria-label="Project navigation">
          {PROJECTS.map((p, i) => (
            <button key={p.id}
              className={'seq-dot' + (i === activeIdx ? ' active' : '')}
              style={{'--c': 'var(--brass)'}}
              onClick={() => goTo(i)}
              aria-label={'Project ' + p.roman}
              aria-current={i === activeIdx ? 'true' : 'false'}/>
          ))}
        </div>
      </div>
    </section>
  );
}

"""

NEW_CSS = """
  /* ===== Mod 16 — № 03 · The work — slider horizontal + flip 3D ===== */
  .work-sequence { position: relative; margin-top: 48px; }
  .work-steps {
    display: flex; overflow-x: auto; overflow-y: hidden;
    scroll-snap-type: x mandatory; scroll-behavior: smooth;
    scrollbar-width: none; -ms-overflow-style: none;
  }
  .work-steps::-webkit-scrollbar { display: none; }
  .work-slide {
    flex: 0 0 100%; scroll-snap-align: start;
    padding: 0 4%; perspective: 1400px; box-sizing: border-box;
  }
  .work-flip {
    position: relative; width: 100%; aspect-ratio: 16 / 10;
    transform-style: preserve-3d;
    transition: transform 600ms cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  @media (hover: hover) {
    .work-slide:hover .work-flip { transform: rotateY(180deg); }
  }
  .work-slide.flipped .work-flip { transform: rotateY(180deg); }
  .work-face {
    position: absolute; inset: 0;
    backface-visibility: hidden; -webkit-backface-visibility: hidden;
    overflow: hidden; background: var(--ink-2);
    border: 1px solid rgba(245, 242, 236, 0.06);
  }
  .work-face-back {
    transform: rotateY(180deg);
    padding: 44px 44px 40px;
    display: flex; flex-direction: column;
    border-top: 1px solid var(--brass);
  }
  .work-cover-img {
    position: absolute; inset: 0; width: 100%; height: 100%;
    object-fit: cover; filter: saturate(0.92) contrast(1.02);
  }
  .work-cover-gradient {
    position: absolute; left: 0; right: 0; bottom: 0; height: 40%;
    background: linear-gradient(to top,
      rgba(10,10,11,0.92) 0%, rgba(10,10,11,0.7) 50%, rgba(10,10,11,0) 100%);
    pointer-events: none;
  }
  .work-cover-overlay {
    position: absolute; left: 44px; right: 44px; bottom: 36px; pointer-events: none;
  }
  .work-eyebrow {
    font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
    font-size: 10px; font-weight: 500; letter-spacing: 0.16em;
    text-transform: uppercase; color: var(--brass); margin-bottom: 14px;
  }
  .work-roman { display: inline-block; min-width: 28px; font-style: italic; }
  .work-sep { color: var(--brass-3, var(--brass)); }
  .work-title {
    font-family: var(--serif, 'Cormorant Garamond', Georgia, serif);
    font-style: italic; font-size: 32px; font-weight: 500;
    line-height: 1.15; color: var(--bone); margin: 0;
  }
  .work-face-back .work-eyebrow { margin-bottom: 14px; }
  .work-face-back .work-title { font-size: 26px; margin-bottom: 26px; }
  .work-scope { list-style: none; padding: 0; margin: 0 0 24px; }
  .work-scope li {
    font-family: Inter, -apple-system, sans-serif;
    font-size: 13.5px; line-height: 1.55; color: var(--bone-3);
    margin-bottom: 7px; padding-left: 14px; position: relative;
  }
  .work-scope li::before { content: '·'; position: absolute; left: 0; color: var(--brass); }
  .work-punch {
    font-family: var(--serif, 'Cormorant Garamond', Georgia, serif);
    font-style: italic; font-size: 17px; line-height: 1.5;
    color: var(--bone-2, var(--bone)); margin: 0 0 28px; flex-grow: 1;
  }
  .work-cta {
    font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
    font-size: 11px; font-weight: 500; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--brass); text-decoration: none;
    align-self: flex-start;
  }
  .work-cta .ar { margin-left: 6px; }
  .work-soon {
    font-family: var(--mono, 'JetBrains Mono', Consolas, monospace);
    font-size: 11px; font-weight: 500; letter-spacing: 0.14em;
    text-transform: uppercase; color: var(--bone-4); align-self: flex-start;
  }
  @media (max-width: 760px) {
    .work-flip { aspect-ratio: 4 / 5; }
    .work-title { font-size: 24px; }
    .work-face-back { padding: 28px 24px 24px; }
    .work-face-back .work-title { font-size: 20px; }
    .work-cover-overlay { left: 24px; right: 24px; bottom: 24px; }
  }
"""


def decode_module(entry):
    raw = base64.b64decode(entry['data'])
    if entry.get('compressed'):
        raw = gzip.decompress(raw)
    return raw.decode('utf-8')


def reencode_module(orig_entry, new_text):
    new_entry = dict(orig_entry)
    encoded = new_text.encode('utf-8')
    if orig_entry.get('compressed'):
        new_entry['data'] = base64.b64encode(gzip.compress(encoded)).decode('ascii')
    else:
        new_entry['data'] = base64.b64encode(encoded).decode('ascii')
    return new_entry


def main():
    src = SRC.read_text()
    print(f"[0] index.html chargé — {len(src):,} bytes")

    m_manifest = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)', src, re.DOTALL)
    m_template = re.search(r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)', src, re.DOTALL)
    if not m_manifest or not m_template:
        sys.exit("FATAL: scripts manifest/template introuvables")

    manifest = json.loads(m_manifest.group(2))
    template_html = json.loads(m_template.group(2).strip())
    print(f"[1] sections parsées — manifest={len(manifest)}")

    # ---- avatars.jsx ----
    av_entry = manifest[AVATARS_UUID]
    av_raw = decode_module(av_entry)

    # Supprimer ancien bloc Mod 15 (PROJECTS + COVER + OurWork)
    pat_mod15 = re.compile(r'\nconst PROJECTS = \[.*?\n\}\n\n', re.DOTALL)
    if pat_mod15.search(av_raw):
        av_raw = pat_mod15.sub('\n', av_raw, count=1)
        print("    [avatars.jsx] ancien bloc Mod 15 supprimé")
    else:
        print("    [avatars.jsx] WARNING: bloc Mod 15 non trouvé")

    if 'function OurWork' in av_raw:
        sys.exit("FATAL: function OurWork toujours présente après suppression")
    if 'function CTA(' not in av_raw:
        sys.exit("FATAL: function CTA introuvable")
    av_raw = av_raw.replace('function CTA(', OUR_WORK_JSX + '\nfunction CTA(', 1)
    print("    [avatars.jsx] nouveau OurWork inséré")

    n_renum = 0
    for old, new in [
        ("'\u2116 05 \u00b7 Correspondence'", "'\u2116 04 \u00b7 Correspondence'"),
        ("'\u2116 05 \u00b7 Correspondance'", "'\u2116 04 \u00b7 Correspondance'"),
    ]:
        if old in av_raw:
            av_raw = av_raw.replace(old, new, 1)
            n_renum += 1
    print(f"    [avatars.jsx] CTA renumérotée №05→№04 ({n_renum}/2)")

    # window.OurWork ?
    obj_idx = av_raw.find('Object.assign(window')
    if obj_idx > 0 and 'OurWork' not in av_raw[obj_idx:obj_idx+200]:
        av_raw = re.sub(
            r'Object\.assign\(window,\s*\{([^}]+)\}\)',
            lambda m: 'Object.assign(window, {' + m.group(1).rstrip().rstrip(',') + ', OurWork})',
            av_raw, count=1,
        )
        print("    [avatars.jsx] OurWork ajouté à window")

    manifest[AVATARS_UUID] = reencode_module(av_entry, av_raw)
    print(f"[2] avatars.jsx patché ({len(av_raw):,} chars)")

    # ---- module Site ----
    site_uuid = None
    site_content = None
    for uuid_, entry_ in manifest.items():
        mime_ = entry_.get('mime', '')
        if 'javascript' not in mime_ and 'jsx' not in mime_:
            continue
        try:
            content_ = decode_module(entry_)
        except Exception:
            continue
        if '<OurAgents lang={lang}/>' in content_ and '<CTA lang={lang}/>' in content_:
            site_uuid = uuid_
            site_content = content_
            break

    if not site_uuid:
        sys.exit("FATAL: module Site (avec <OurAgents/> et <CTA/>) introuvable")

    new_site = re.sub(r'\n\s*<OurAgents\s+lang=\{lang\}\s*/>\s*(?=\n)', '', site_content, count=1)
    if new_site == site_content:
        sys.exit("FATAL: <OurAgents lang={lang}/> non retiré du Site")
    manifest[site_uuid] = reencode_module(manifest[site_uuid], new_site)
    print(f"[3] module Site {site_uuid[:12]}... patché — <OurAgents/> retiré")

    # ---- CSS ----
    pat_mod15_css = re.compile(r'\n\s*/\*\s*=====\s*Mod 15\s*\u2014.*?(?=\n\s*/\*\s*=====|\n\s*</style>)', re.DOTALL)
    if pat_mod15_css.search(template_html):
        template_html = pat_mod15_css.sub('\n', template_html, count=1)
        print("    [template] CSS Mod 15 supprimé")
    else:
        print("    [template] WARNING: CSS Mod 15 non trouvé")

    if '/* ===== Mod 16 \u2014' not in template_html and '</style>' in template_html:
        template_html = template_html.replace('</style>', NEW_CSS + '\n  </style>', 1)
        print("    [template] CSS Mod 16 inséré")

    print(f"[4] template patché ({len(template_html):,} chars)")

    # ---- Repacking ----
    new_manifest_body = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))
    new_template_body = json.dumps(template_html, ensure_ascii=False)
    new_template_body = (
        new_template_body
        .replace("</script>", r"<\u002Fscript>")
        .replace("</style>", r"<\u002Fstyle>")
    )

    new_src = (
        src[:m_manifest.start()]
        + m_manifest.group(1) + new_manifest_body + m_manifest.group(3)
        + src[m_manifest.end():m_template.start()]
        + m_template.group(1) + new_template_body + m_template.group(3)
        + src[m_template.end():]
    )

    SRC.write_text(new_src)
    delta = len(new_src) - len(src)
    sign = '+' if delta >= 0 else ''
    print(f"[5] index.html écrit — {len(new_src):,} bytes (Δ={sign}{delta:,})")


if __name__ == '__main__':
    main()
