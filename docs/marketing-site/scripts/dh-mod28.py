#!/usr/bin/env python3
"""
Mod 28 — Sprint 1 pre-launch (1er mai 2026)
============================================
Pre-launch fixes du site marketing identifiés par la revue critique :
- Footer : mailto: actif sur hello@digital-humans.fr
- Pricing : Free CTA → redirige vers app.digital-humans.fr/signup
- Pricing : Pro/Team CTAs grisés "Bientôt / Coming soon" (non-clickable)
- Routes SPA : /cgv, /legal, /privacy → vraies pages avec contenu rédigé
- Module nouveau "legal.jsx" + mini-router dans Site()

Backup : index.html.pre-mod28-sprint1
"""
import re, json, base64, gzip, sys, uuid as uuidlib

sys.path.insert(0, '/tmp/mod28')
from legal_content import ALL as LEGAL_CONTENT

INDEX_PATH = '/var/www/dh-preview/index.html'

# UUIDs des modules existants
UUID_AVATARS  = 'b077057a-5a3a-41a8-8f45-fe3c0011a134'
UUID_SECTIONS = '6641f2bf-70da-46eb-a716-a60b6030f1c7'
UUID_ICONS    = 'b7ddfc56-c91a-475b-8210-cdc552a1589d'  # contient Header
UUID_SITE     = '0fbb2257-1e12-4e49-857e-4774d4dc6847'

# Nouveau UUID pour le module legal
UUID_LEGAL = 'a1b2c3d4-e5f6-4789-9abc-def012345678'  # fixed for repeatability


# ============================================================================
# 1. Lecture du bundle
# ============================================================================
def read_bundle():
    with open(INDEX_PATH) as f:
        content = f.read()
    
    m = re.search(r'(<script[^>]*type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
    manifest_open, manifest_body, manifest_close = m.group(1), m.group(2), m.group(3)
    manifest = json.loads(manifest_body.strip())
    
    m = re.search(r'(<script[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
    template_open, template_body, template_close = m.group(1), m.group(2), m.group(3)
    template = json.loads(template_body.strip())
    
    m = re.search(r'(<script[^>]*type="__bundler/ext_resources"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
    ext_open, ext_body, ext_close = m.group(1), m.group(2), m.group(3)
    ext_resources = json.loads(ext_body.strip())
    
    return content, {
        'manifest': (manifest_open, manifest, manifest_close),
        'template': (template_open, template, template_close),
        'ext_resources': (ext_open, ext_resources, ext_close),
    }


def decode_module(manifest, uuid):
    entry = manifest.get(uuid)
    if not entry: return None
    data = base64.b64decode(entry['data'])
    if entry.get('compressed'):
        data = gzip.decompress(data)
    return data.decode('utf-8')


def encode_module(code, compressed=True, mime='application/javascript'):
    data = code.encode('utf-8')
    if compressed:
        data = gzip.compress(data)
    return {
        'data': base64.b64encode(data).decode('ascii'),
        'compressed': compressed,
        'mime': mime,
    }


# ============================================================================
# 2. Génération du module legal.jsx
# ============================================================================
def render_legal_module():
    """Génère le code JSX du module legal (Layout + 3 pages FR/EN)."""
    # Sérialiser le contenu en JS plain object (les chaînes contiennent du HTML)
    # On utilise json.dumps qui produit un JS object valide
    content_json = json.dumps(LEGAL_CONTENT, ensure_ascii=False, indent=2)
    
    code = '''// Legal module - Mod 28 (1er mai 2026)
// Pages CGV / Mentions légales / Confidentialité, FR + EN.
const LEGAL_DATA = ''' + content_json + ''';

function LegalLayout({lang, setLang, theme, setTheme, slug, children}) {
  // Reuse Header from icons module (defines window.Header)
  const Header = window.Header;
  const Footer = window.Footer;
  return (
    <div data-screen-label={'Legal · ' + slug}>
      {Header && <Header lang={lang} setLang={setLang} theme={theme} setTheme={setTheme}/>}
      <main className="legal-main">
        <div className="wrap legal-wrap">
          {children}
        </div>
      </main>
      {Footer && <Footer lang={lang}/>}
      {window.SophieChat && <window.SophieChat lang={lang}/>}
    </div>
  );
}

function LegalPage({slug, lang}) {
  const data = (LEGAL_DATA[slug] && LEGAL_DATA[slug][lang]) || (LEGAL_DATA[slug] && LEGAL_DATA[slug]['en']);
  if (!data) {
    return <div className="legal-404"><h1>Page not found</h1></div>;
  }
  // Update document title once on render
  React.useEffect(() => {
    document.title = data.title + ' \u00b7 Digital\u00b7Humans';
  }, [data.title]);
  return (
    <article className="legal-doc">
      <header className="legal-head">
        <div className="num">{
          slug === 'legal' ? (lang === 'en' ? '\u2116 99 \u00b7 Legal' : '\u2116 99 \u00b7 Mentions') :
          slug === 'cgv' ? (lang === 'en' ? '\u2116 98 \u00b7 Terms' : '\u2116 98 \u00b7 CGV') :
          (lang === 'en' ? '\u2116 97 \u00b7 Privacy' : '\u2116 97 \u00b7 Confidentialit\u00e9')
        }</div>
        <h1>{data.title}</h1>
        <p className="legal-updated">{data.updated}</p>
      </header>
      <nav className="legal-toc" aria-label={lang === 'en' ? 'On this page' : 'Sur cette page'}>
        <div className="legal-toc-label">{lang === 'en' ? 'On this page' : 'Sur cette page'}</div>
        <ol>
          {data.sections.map((s, i) => (
            <li key={i}><a href={'#sec-' + i}>{s.h}</a></li>
          ))}
        </ol>
      </nav>
      <div className="legal-body">
        {data.sections.map((s, i) => (
          <section key={i} id={'sec-' + i} className="legal-section">
            <h2>{s.h}</h2>
            {s.p.map((para, j) => (
              <p key={j} dangerouslySetInnerHTML={{__html: para}}/>
            ))}
          </section>
        ))}
      </div>
      <div className="legal-foot">
        <a href="/" className="legal-back">{lang === 'en' ? '\u2190 Back to home' : '\u2190 Retour \u00e0 l\u2019accueil'}</a>
      </div>
    </article>
  );
}

Object.assign(window, {LegalLayout, LegalPage, LEGAL_DATA});
'''
    return code


# ============================================================================
# 3. Patch avatars.jsx (Footer mailto + Pricing CTA disabled state)
# ============================================================================
def patch_avatars(av):
    """
    Modifications :
    1. Footer : hello@digital-humans.fr → <a href="mailto:...">
    2. PRICING_TIERS : Pro et Team marqués disabled, CTA renommé "Bientôt"
    3. Composant Pricing : rendu différencié si disabled, et Free CTA → redirect signup
    """
    
    # --- Patch 1 : Footer mailto ---
    old_footer = '<span className="r">hello@digital-humans.fr · MMXXV</span>'
    new_footer = '<span className="r"><a href="mailto:hello@digital-humans.fr" className="footer-mail">hello@digital-humans.fr</a> \u00b7 MMXXV</span>'
    assert old_footer in av, "Footer mailto anchor not found"
    av = av.replace(old_footer, new_footer, 1)
    print("  [P1] Footer mailto activated")
    
    # --- Patch 2 : PRICING_TIERS — wording grisé Pro/Team ---
    # Pro : ajouter disabled: true + CTA = Bientôt / Coming soon
    old_pro_cta = "cta: { en: 'Get on the list', fr: 'S\u2019inscrire \u00e0 la liste' },\n    note: { en: 'No code generation, no deployment"
    new_pro_cta = "cta: { en: 'Coming soon', fr: 'Bient\u00f4t' },\n    disabled: true,\n    note: { en: 'No code generation, no deployment"
    assert old_pro_cta in av, "Pro CTA anchor not found"
    av = av.replace(old_pro_cta, new_pro_cta, 1)
    print("  [P2a] Pro CTA -> Coming soon / Bientot, disabled=true")
    
    # Team : ajouter disabled: true + CTA = Bientôt / Coming soon
    old_team_cta = "cta: { en: 'Get on the list', fr: 'S\u2019inscrire \u00e0 la liste' },\n    note: { en: 'Sandbox only"
    new_team_cta = "cta: { en: 'Coming soon', fr: 'Bient\u00f4t' },\n    disabled: true,\n    note: { en: 'Sandbox only"
    assert old_team_cta in av, "Team CTA anchor not found"
    av = av.replace(old_team_cta, new_team_cta, 1)
    print("  [P2b] Team CTA -> Coming soon / Bientot, disabled=true")
    
    # --- Patch 3 : Composant Pricing — rendu différencié ---
    # On cherche le bouton CTA dans le composant Pricing pour l'adapter
    # La struture est : <button className="pricing-cta" onClick={...}>{cta}</button>
    
    # Trouver la fonction Pricing
    m = re.search(r'function Pricing\b', av)
    if not m:
        print("  [WARN] function Pricing not found, search for component")
    
    # Le bouton actuel est probablement quelque chose comme :
    #   <button className="pricing-cta" onClick={openSophie}>{tier.cta[lang]}</button>
    # On cherche les patterns possibles
    
    # Chercher "pricing-cta" pour localiser le bouton
    cta_idx = av.find('pricing-cta')
    if cta_idx == -1:
        raise RuntimeError("pricing-cta anchor not found in avatars module")
    
    # Affiche le contexte pour décider du patch
    snippet = av[max(0,cta_idx-300):cta_idx+500]
    print("  [P3-ctx] Pricing CTA context:")
    for line in snippet.split('\n'):
        print(f"          | {line}")
    
    return av


def find_pricing_button_pattern(av):
    """Identifier exactement la structure du bouton CTA pour le patcher."""
    # Recherche pattern <button className="pricing-cta"...>...</button>
    m = re.search(r'<button[^>]*className="pricing-cta"[^>]*>([^<]+)</button>', av)
    if m:
        return m.group(0), 'button-simple'
    # Fallback : pattern plus complexe (ex: avec onClick)
    m = re.search(r'<button[^>]*?pricing-cta[^>]*?>[\s\S]{0,200}?</button>', av)
    if m:
        return m.group(0), 'button-complex'
    return None, None


# ============================================================================
# 4. Patch Site composition (mini-router)
# ============================================================================
def patch_site(site):
    """Remplace Site() par une version qui route selon window.location.pathname."""
    
    new_site = '''const {useState, useEffect} = React;

function Site() {
  const [lang, setLang] = useState(() => localStorage.getItem('dh-lang') || 'en');
  useEffect(() => { localStorage.setItem('dh-lang', lang); }, [lang]);

  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'dark');
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('dh-theme', theme); } catch (e) {}
  }, [theme]);

  // Mini-router : on regarde le pathname courant
  const pathname = (window.location.pathname || '/').replace(/\\/$/, '') || '/';
  const legalRoutes = {'/cgv': 'cgv', '/legal': 'legal', '/privacy': 'privacy'};
  const legalSlug = legalRoutes[pathname];

  if (legalSlug) {
    const LegalLayout = window.LegalLayout;
    const LegalPage = window.LegalPage;
    if (LegalLayout && LegalPage) {
      return (
        <LegalLayout lang={lang} setLang={setLang} theme={theme} setTheme={setTheme} slug={legalSlug}>
          <LegalPage slug={legalSlug} lang={lang}/>
        </LegalLayout>
      );
    }
    // Fallback si module legal pas chargé : afficher message clair
    return <div style={{padding: '4rem', textAlign: 'center'}}>Loading legal module\u2026</div>;
  }

  // Home par défaut
  return (
    <div data-screen-label="Marketing Home">
      <Header lang={lang} setLang={setLang} theme={theme} setTheme={setTheme}/>
      <main>
        <Hero lang={lang}/>
        <Benefits lang={lang}/>
        <HowItWorks lang={lang}/>
        <OurWork lang={lang}/>
        <Pricing lang={lang}/>
        <CTA lang={lang}/>
      </main>
      <Footer lang={lang}/>
      {window.SophieChat && <window.SophieChat lang={lang}/>}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<Site/>);
'''
    return new_site


# ============================================================================
# 5. CSS additionnel pour pages légales + état grisé
# ============================================================================
ADDITIONAL_CSS = '''
/* ============= Mod 28 — Sprint 1 pre-launch ============= */

/* Footer mailto link */
.footer-mail {
  color: inherit;
  text-decoration: none;
  border-bottom: 1px solid currentColor;
  border-bottom-color: rgba(196, 162, 100, 0.4);
  transition: border-color 0.2s ease;
}
.footer-mail:hover { border-bottom-color: var(--brass, #c4a264); }

/* Pricing CTA — état grisé */
.pricing-cta.is-disabled,
.pricing-card[data-disabled="true"] .pricing-cta {
  background: transparent !important;
  color: var(--bone-3, rgba(245, 242, 236, 0.4)) !important;
  border: 1px dashed rgba(245, 242, 236, 0.18) !important;
  cursor: not-allowed !important;
  pointer-events: none;
  opacity: 0.6;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-size: 11px;
}
[data-theme="light"] .pricing-cta.is-disabled,
[data-theme="light"] .pricing-card[data-disabled="true"] .pricing-cta {
  color: rgba(10, 10, 11, 0.4) !important;
  border-color: rgba(10, 10, 11, 0.18) !important;
}

/* ===== Pages légales ===== */
.legal-main { padding-top: 96px; padding-bottom: 80px; min-height: 70vh; }
.legal-wrap { max-width: 880px; margin: 0 auto; }

.legal-doc { font-family: 'Inter', sans-serif; }

.legal-head { padding: 24px 0 32px; border-bottom: 1px solid rgba(196, 162, 100, 0.18); margin-bottom: 32px; }
.legal-head .num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: var(--brass, #c4a264);
  text-transform: uppercase;
  margin-bottom: 16px;
}
.legal-head h1 {
  font-family: 'Cormorant Garamond', serif;
  font-weight: 400;
  font-size: 56px;
  line-height: 1.05;
  letter-spacing: -0.01em;
  margin: 0 0 12px;
  color: var(--bone, #f5f2ec);
}
[data-theme="light"] .legal-head h1 { color: var(--ink, #0a0a0b); }

.legal-updated {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--bone-3, rgba(245, 242, 236, 0.55));
  margin: 0;
}

/* Table of contents */
.legal-toc {
  background: rgba(196, 162, 100, 0.04);
  border: 1px solid rgba(196, 162, 100, 0.14);
  padding: 20px 28px;
  margin-bottom: 48px;
  border-radius: 2px;
}
.legal-toc-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10.5px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brass, #c4a264);
  margin-bottom: 14px;
}
.legal-toc ol {
  list-style: none;
  padding-left: 0;
  margin: 0;
  columns: 2;
  column-gap: 32px;
}
.legal-toc li {
  font-size: 13.5px;
  line-height: 1.7;
  break-inside: avoid;
}
.legal-toc a {
  color: var(--bone-2, rgba(245, 242, 236, 0.78));
  text-decoration: none;
  border-bottom: 1px solid transparent;
  transition: all 0.18s ease;
}
.legal-toc a:hover {
  color: var(--bone, #f5f2ec);
  border-bottom-color: var(--brass, #c4a264);
}
[data-theme="light"] .legal-toc a { color: rgba(10, 10, 11, 0.78); }
[data-theme="light"] .legal-toc a:hover { color: var(--ink, #0a0a0b); }

/* Body */
.legal-section { margin-bottom: 40px; scroll-margin-top: 96px; }
.legal-section h2 {
  font-family: 'Cormorant Garamond', serif;
  font-weight: 500;
  font-size: 24px;
  line-height: 1.3;
  margin: 0 0 16px;
  color: var(--bone, #f5f2ec);
  letter-spacing: -0.005em;
}
[data-theme="light"] .legal-section h2 { color: var(--ink, #0a0a0b); }

.legal-section p {
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--bone-2, rgba(245, 242, 236, 0.82));
  margin: 0 0 14px;
}
[data-theme="light"] .legal-section p { color: rgba(10, 10, 11, 0.82); }

.legal-section p strong {
  color: var(--bone, #f5f2ec);
  font-weight: 600;
}
[data-theme="light"] .legal-section p strong { color: var(--ink, #0a0a0b); }

.legal-section a {
  color: var(--brass, #c4a264);
  text-decoration: none;
  border-bottom: 1px solid rgba(196, 162, 100, 0.4);
  transition: border-color 0.18s ease;
}
.legal-section a:hover { border-bottom-color: var(--brass, #c4a264); }

/* Footer back link */
.legal-foot {
  padding: 48px 0 0;
  border-top: 1px solid rgba(196, 162, 100, 0.14);
  margin-top: 64px;
}
.legal-back {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--bone-3, rgba(245, 242, 236, 0.55));
  text-decoration: none;
  border-bottom: 1px solid currentColor;
  padding-bottom: 2px;
  transition: color 0.18s ease;
}
.legal-back:hover { color: var(--brass, #c4a264); }

@media (max-width: 720px) {
  .legal-head h1 { font-size: 38px; }
  .legal-toc ol { columns: 1; }
  .legal-section h2 { font-size: 20px; }
}
'''


def patch_template(template):
    """Injecte le CSS additionnel à la fin du dernier <style> du template."""
    # Chercher le dernier </style> et insérer juste avant
    last_style_end = template.rfind('</style>')
    if last_style_end == -1:
        raise RuntimeError("No </style> found in template")
    new_template = template[:last_style_end] + ADDITIONAL_CSS + template[last_style_end:]
    return new_template


# ============================================================================
# 6. Réinjection dans index.html
# ============================================================================
def write_bundle(content, sections, manifest, template, ext_resources):
    """Reconstruit index.html avec les nouveaux manifest/template/ext."""
    
    # Re-encoder manifest
    manifest_open, _, manifest_close = sections['manifest']
    new_manifest_body = json.dumps(manifest, ensure_ascii=False)
    
    # Re-encoder template (string -> JSON-encoded)
    template_open, _, template_close = sections['template']
    new_template_body = json.dumps(template, ensure_ascii=False)
    # Post-process : escape </script> et </style>
    new_template_body = new_template_body.replace('</script>', r'<\u002Fscript>').replace('</style>', r'<\u002Fstyle>')
    
    # Re-encoder ext_resources
    ext_open, _, ext_close = sections['ext_resources']
    new_ext_body = json.dumps(ext_resources, ensure_ascii=False)
    
    # Replace each block
    new_content = content
    
    # Manifest
    pattern = re.compile(r'(<script[^>]*type="__bundler/manifest"[^>]*>)(.*?)(</script>)', re.DOTALL)
    new_content = pattern.sub(lambda m: m.group(1) + new_manifest_body + m.group(3), new_content, count=1)
    
    # Template
    pattern = re.compile(r'(<script[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)', re.DOTALL)
    new_content = pattern.sub(lambda m: m.group(1) + new_template_body + m.group(3), new_content, count=1)
    
    # Ext resources
    pattern = re.compile(r'(<script[^>]*type="__bundler/ext_resources"[^>]*>)(.*?)(</script>)', re.DOTALL)
    new_content = pattern.sub(lambda m: m.group(1) + new_ext_body + m.group(3), new_content, count=1)
    
    return new_content


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    print("=== Mod 28 — Sprint 1 pre-launch ===\n")
    
    print("[1/6] Reading bundle...")
    content, sections = read_bundle()
    manifest = sections['manifest'][1]
    template = sections['template'][1]
    ext_resources = sections['ext_resources'][1]
    print(f"  manifest: {len(manifest)} entries, template: {len(template):,} chars, ext: {len(ext_resources)}")
    
    print("\n[2/6] Decoding modules...")
    av = decode_module(manifest, UUID_AVATARS)
    site = decode_module(manifest, UUID_SITE)
    print(f"  avatars: {len(av):,} chars, site: {len(site):,} chars")
    
    # First pass : identifier la structure du bouton Pricing
    print("\n[2.5/6] Identifying Pricing CTA structure...")
    pat, kind = find_pricing_button_pattern(av)
    if pat:
        print(f"  found ({kind}): {pat[:200]}...")
    else:
        print(f"  WARNING: no <button pricing-cta> pattern found")
    
    print("\n[3/6] Patching avatars.jsx (footer + pricing tiers)...")
    av_patched = patch_avatars(av)
    
    # Patch button render (we'll do it now that we have context)
    # Find the button rendering in Pricing component
    # Pattern : <button ... onClick=... className="pricing-cta">{tier.cta[lang]}</button>
    # We need to add disabled state handling
    
    # Ancrage du bouton multiline (avec span enfant pour la flèche)
    # Format réel:
    #   <button type="button" className="pricing-cta" onClick={openSophie}>
    #     {t.cta[lang] || t.cta.en}
    #     <span className="pricing-cta-arrow">→</span>
    #   </button>
    old_btn = """<button type=\"button\" className=\"pricing-cta\" onClick={openSophie}>
              {t.cta[lang] || t.cta.en}
              <span className=\"pricing-cta-arrow\">\u2192</span>
            </button>"""
    new_btn = """{t.disabled ? (
              <span className=\"pricing-cta is-disabled\" aria-disabled=\"true\">
                {t.cta[lang] || t.cta.en}
              </span>
            ) : (
              <button type=\"button\" className=\"pricing-cta\" onClick={() => {
                if (t.id === 'free') {
                  window.location.href = 'https://app.digital-humans.fr/signup';
                } else if (typeof openSophie === 'function') {
                  openSophie();
                }
              }}>
                {t.cta[lang] || t.cta.en}
                <span className=\"pricing-cta-arrow\">\u2192</span>
              </button>
            )}"""
    if old_btn in av_patched:
        av_patched = av_patched.replace(old_btn, new_btn, 1)
        print("  [P3] Pricing button: t.disabled -> grey span, free -> signup redirect")
    else:
        print("  [ERROR] Old button not found verbatim — search pattern needs update")
        idx = av_patched.find('pricing-cta')
        if idx >= 0:
            print("  Context around first pricing-cta:")
            print(av_patched[idx-50:idx+400])
        sys.exit(1)
    
    print("\n[4/6] Patching Site composition (mini-router)...")
    site_patched = patch_site(site)
    
    print("\n[5/6] Generating new legal.jsx module...")
    legal_code = render_legal_module()
    print(f"  legal module: {len(legal_code):,} chars")
    
    # Re-encoder les modules modifiés
    manifest[UUID_AVATARS] = encode_module(av_patched, compressed=True)
    manifest[UUID_SITE] = encode_module(site_patched, compressed=True)
    manifest[UUID_LEGAL] = encode_module(legal_code, compressed=True)
    
    # Add legal module to ext_resources so it gets loaded? Check the format first.
    # ext_resources is a list of [name, uuid] pairs (we saw it earlier as list)
    # We need to make sure the legal module gets imported as a script.
    # Look at how other modules are loaded
    
    # Actually, modules in manifest with mime 'application/javascript' should be auto-loaded.
    # Let's check by searching how they're invoked in template
    
    print("\n  Verifying module load order in template...")
    # Look for module loader pattern in template
    # The legal module needs to load BEFORE the site composition
    
    # Patch template with CSS
    template_patched = patch_template(template)
    
    # Now we need to ensure the legal module is loaded as a script tag
    # Let's check current script loading in template
    print("\n[5.5/6] Checking template script loading...")
    script_uuids_in_template = re.findall(r'src="([0-9a-f-]{36})"', template_patched)
    print(f"  {len(script_uuids_in_template)} module-script tags in template")
    print(f"  Module UUIDs loaded: {script_uuids_in_template[-5:]}")
    
    # Si le module legal n'est pas dans la liste, on l'ajoute
    if UUID_LEGAL not in script_uuids_in_template:
        # Find where avatars module is loaded and inject legal right after it
        # Pattern: <script ...src="UUID_AVATARS"...></script>
        avatars_script_pattern = re.compile(
            r'(<script[^>]*src="' + re.escape(UUID_AVATARS) + r'"[^>]*></script>)'
        )
        m = avatars_script_pattern.search(template_patched)
        if m:
            avatars_script = m.group(1)
            # Inject the legal script right after avatars (uses same attributes pattern)
            legal_script = avatars_script.replace(UUID_AVATARS, UUID_LEGAL)
            new_section = avatars_script + '\n' + legal_script
            template_patched = template_patched.replace(avatars_script, new_section, 1)
            print(f"  injected <script src={UUID_LEGAL}> after avatars module")
        else:
            # Try another approach - look for script tag with type module
            # Show all script tags loading modules
            all_module_scripts = re.findall(r'<script[^>]+src="[0-9a-f-]{36}"[^>]*></script>', template_patched)
            print(f"  Module script tags: {len(all_module_scripts)}")
            for s in all_module_scripts[:3]:
                print(f"    {s}")
            if all_module_scripts:
                # Inject after the last one
                last_script = all_module_scripts[-1]
                legal_script = re.sub(r'src="[0-9a-f-]{36}"', f'src="{UUID_LEGAL}"', last_script)
                template_patched = template_patched.replace(last_script, last_script + '\n' + legal_script, 1)
                print(f"  injected legal script after last module script")
            else:
                print("  ERROR: can't figure out how to inject legal script tag")
                sys.exit(1)
    
    print("\n[6/6] Writing new bundle...")
    new_content = write_bundle(content, sections, manifest, template_patched, ext_resources)
    
    print(f"  before: {len(content):,} bytes")
    print(f"  after:  {len(new_content):,} bytes")
    print(f"  delta:  {len(new_content) - len(content):+,} bytes")
    
    with open(INDEX_PATH, 'w') as f:
        f.write(new_content)
    print(f"\n  Written to {INDEX_PATH}")
    print("\n=== Mod 28 done ===")
