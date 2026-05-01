#!/usr/bin/env python3
"""
Mod 29 — Sprint 2 (1er mai 2026)
=================================
Refonte mobile + a11y + SEO basics, suite audit Lighthouse baseline :
- Performance 25/100 (bundle 16MB = dette technique, pas dans cette mod)
- Accessibility 86/100 (color-contrast 14 items, target-size 9, aria-required-children)
- SEO 91/100 (meta-description manquante)
- Best practices : 1 console error (network 404, à investiguer separe)

Backup : index.html.pre-mod29-mobile-a11y-seo
"""
import re, json, base64, gzip, sys

INDEX_PATH = '/var/www/dh-preview/index.html'

UUID_AVATARS  = 'b077057a-5a3a-41a8-8f45-fe3c0011a134'
UUID_SECTIONS = '6641f2bf-70da-46eb-a716-a60b6030f1c7'
UUID_ICONS    = 'b7ddfc56-c91a-475b-8210-cdc552a1589d'  # contient Header
UUID_SITE     = '0fbb2257-1e12-4e49-857e-4774d4dc6847'


def read_bundle():
    with open(INDEX_PATH) as f:
        content = f.read()
    m = re.search(r'(<script[^>]*type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
    manifest = json.loads(m.group(2).strip())
    m = re.search(r'(<script[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
    template = json.loads(m.group(2).strip())
    m = re.search(r'(<script[^>]*type="__bundler/ext_resources"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
    ext_resources = json.loads(m.group(2).strip())
    return content, manifest, template, ext_resources


def decode_module(manifest, uuid):
    e = manifest.get(uuid)
    if not e: return None
    d = base64.b64decode(e['data'])
    if e.get('compressed'): d = gzip.decompress(d)
    return d.decode('utf-8')


def encode_module(code, compressed=True, mime='application/javascript'):
    data = code.encode('utf-8')
    if compressed: data = gzip.compress(data)
    return {'data': base64.b64encode(data).decode('ascii'), 'compressed': compressed, 'mime': mime}


# ============================================================================
# 1. Patch icons module : Header — tap targets, aria-labels, role tab
# ============================================================================
def patch_icons(icons):
    # Le Header a .lang aria-label="Toggle language" mais texte visible "FR · EN"
    # → mismatch : on rend le texte visible inclus dans l'aria-label
    
    # Patch a11y aria-label .lang
    old = """<button className="lang" onClick={() => setLang(lang === 'en' ? 'fr' : 'en')} aria-label="Toggle language">
            {lang === 'en' ? 'FR' : 'EN'} \u00b7 {lang === 'en' ? 'EN' : 'FR'}
          </button>"""
    new = """<button className="lang" onClick={() => setLang(lang === 'en' ? 'fr' : 'en')} aria-label={lang === 'en' ? 'Switch to French (FR)' : 'Passer en anglais (EN)'} title={lang === 'en' ? 'Switch language' : 'Changer de langue'}>
            {lang === 'en' ? 'FR' : 'EN'} \u00b7 {lang === 'en' ? 'EN' : 'FR'}
          </button>"""
    if old in icons:
        icons = icons.replace(old, new, 1)
        print("  [icons] lang button aria-label aligned with visible text")
    else:
        print("  [icons WARN] lang button pattern not found")
    
    # Patch .mk anchor — aria-label doit contenir le texte visible "Digital·Humans"
    old2 = """<a href="#" className="mk" aria-label="Digital-Humans home">"""
    new2 = """<a href="#" className="mk" aria-label="Digital-Humans \u2014 home">"""
    if old2 in icons:
        icons = icons.replace(old2, new2, 1)
        print("  [icons] .mk aria-label clarified")
    
    return icons


# ============================================================================
# 2. Patch sections module : seq-dot role tab, aria-required-children
# ============================================================================
def patch_sections(sec):
    # Le seq-dots div a role="tablist" mais ses enfants buttons n'ont pas role="tab"
    # → ajouter role="tab" aux buttons (deux endroits : HowItWorks + OurWork)
    
    old = """<button
              key={i}
              className={'seq-dot' + (i === activeIdx ? ' active' : '')}
              style={{'--c': s.c}}
              onClick={() => goTo(i)}
              aria-label={'Act ' + s.r}
              aria-current={i === activeIdx ? 'true' : 'false'}
            />"""
    new = """<button
              key={i}
              role="tab"
              className={'seq-dot' + (i === activeIdx ? ' active' : '')}
              style={{'--c': s.c}}
              onClick={() => goTo(i)}
              aria-label={'Act ' + s.r}
              aria-selected={i === activeIdx ? 'true' : 'false'}
              aria-current={i === activeIdx ? 'true' : 'false'}
            />"""
    count = sec.count(old)
    if count > 0:
        sec = sec.replace(old, new)
        print(f"  [sections] seq-dot role=tab added ({count} occurrences)")
    else:
        print("  [sections WARN] seq-dot pattern not found in HowItWorks")
    
    return sec


# ============================================================================
# 3. Patch avatars module : OurWork seq-dot (same fix), and other buttons
# ============================================================================
def patch_avatars(av):
    # Same seq-dot pattern in OurWork
    # Pattern might differ slightly (Project i vs Act r)
    old = """<button
              key={i}
              className={'seq-dot' + (i === activeIdx ? ' active' : '')}
              style={{'--c': s.c}}
              onClick={() => goTo(i)}
              aria-label={'Project ' + s.r}
              aria-current={i === activeIdx ? 'true' : 'false'}
            />"""
    new = """<button
              key={i}
              role="tab"
              className={'seq-dot' + (i === activeIdx ? ' active' : '')}
              style={{'--c': s.c}}
              onClick={() => goTo(i)}
              aria-label={'Project ' + s.r}
              aria-selected={i === activeIdx ? 'true' : 'false'}
              aria-current={i === activeIdx ? 'true' : 'false'}
            />"""
    if old in av:
        av = av.replace(old, new, 1)
        print("  [avatars] OurWork seq-dot role=tab added")
    else:
        # Search variants
        m = re.search(r'<button\s+key=\{i\}\s+className=\{\'seq-dot\'[^}]+\}[\s\S]+?aria-label=\{[^}]+\}[\s\S]+?/>', av)
        if m:
            print(f"  [avatars] alt pattern found:\n     {m.group()[:200]}")
            old_actual = m.group()
            # Insert role="tab" right after key={i}
            new_actual = old_actual.replace('key={i}', 'key={i}\n              role="tab"', 1)
            # Insert aria-selected before aria-current
            if 'aria-current=' in new_actual and 'aria-selected=' not in new_actual:
                new_actual = re.sub(
                    r'(aria-label=\{[^}]+\})',
                    r'\1\n              aria-selected={i === activeIdx ? \'true\' : \'false\'}',
                    new_actual,
                    count=1
                )
            av = av.replace(old_actual, new_actual, 1)
            print("  [avatars] OurWork seq-dot role=tab added (alt pattern)")
        else:
            print("  [avatars WARN] seq-dot pattern in OurWork not found")
    
    return av


# ============================================================================
# 4. Patch CSS template : variables couleur + responsive mobile + meta tags + a11y
# ============================================================================

# 4a. Update --bone-4 pour atteindre WCAG AA (4.5+ contrast ratio sur ink-2 #141416)
# #76716A sur #141416 = 3.8 (KO)
# #9A938A sur #141416 = 5.10 (AA OK)
# #ABA396 sur #141416 = 6.30 (AA confortable)
def patch_root_vars(template):
    old = "--bone-4: #76716A;"
    new = "--bone-4: #9A938A;"
    if old in template:
        template = template.replace(old, new, 1)
        print("  [css] --bone-4: #76716A -> #9A938A (WCAG AA, contrast 5.10 on --ink-2)")
    else:
        print("  [css WARN] --bone-4 not found")
    return template


# 4b. CSS additionnel : mobile responsive complet + tap targets + meta
MOBILE_CSS = '''
/* ============= Mod 29 — Sprint 2 mobile + a11y ============= */

/* a11y : tap targets minimum 44x44 px */
.seq-dot {
  min-width: 44px !important;
  min-height: 44px !important;
  padding: 16px !important;
  background-clip: content-box !important;
  position: relative;
}
.seq-dot::after {
  content: '';
  position: absolute;
  inset: 50% 50% 50% 50%;
  width: 8px; height: 8px;
  margin: -4px 0 0 -4px;
  border-radius: 50%;
  background: var(--c, var(--brass));
  opacity: 0.4;
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.seq-dot.active::after { opacity: 1; transform: scale(1.4); }
.seq-dot:hover::after { opacity: 0.8; }

/* a11y : focus visible everywhere for keyboard users */
button:focus-visible,
a:focus-visible {
  outline: 2px solid var(--brass, #C8A97E);
  outline-offset: 2px;
}

/* ============ Mobile responsive (<= 720px) ============ */
@media (max-width: 720px) {
  /* Header — pack tighter, allow scroll on nav */
  header.glass .bar {
    padding: 10px 14px !important;
    gap: 6px !important;
    flex-wrap: nowrap !important;
    overflow-x: auto;
    overscroll-behavior-x: contain;
    scroll-snap-type: x mandatory;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  header.glass .bar::-webkit-scrollbar { display: none; }

  header.glass .mk { flex-shrink: 0; }
  header.glass .mk .tag { display: none; }
  header.glass .mk .wm { font-size: 18px; }

  header.glass nav.links {
    gap: 12px !important;
    flex-shrink: 0;
  }
  header.glass nav.links .link { font-size: 11px; padding: 6px 4px; }
  header.glass nav.links a:not(.btn-studio) {
    /* Hide secondary links on mobile, keep only Studio + lang + theme */
    display: none;
  }
  header.glass nav.links .btn-studio {
    padding: 10px 14px !important;
    font-size: 11px !important;
    min-height: 40px;
    display: inline-flex;
    align-items: center;
  }
  header.glass nav.links .lang,
  header.glass nav.links .theme-toggle {
    min-width: 40px;
    min-height: 40px;
    padding: 8px 10px;
  }

  /* Hero */
  .hero { padding: 80px 16px 48px !important; }
  .hero-eyebrow { font-size: 10px !important; }
  .hero h1, .hero-title { font-size: clamp(36px, 9vw, 52px) !important; line-height: 1.05 !important; }
  .hero-actions { flex-direction: column; gap: 12px; align-items: stretch; }
  .hero-actions a, .hero-actions button { text-align: center; padding: 14px 20px !important; }

  /* Section heads */
  .section-head { padding: 16px !important; }
  .section-head h2 { font-size: clamp(28px, 7vw, 40px) !important; }
  .section-head .num { font-size: 11px !important; }
  .lede { font-size: 15px !important; line-height: 1.55 !important; }

  /* Wrap */
  .wrap { padding: 0 16px !important; }

  /* Benefits — already 1-col below 560, ensure spacing */
  .benefits-grid { padding: 0 16px; }
  .benefit { padding: 24px 20px 20px !important; }
  .benefit h3 { font-size: 22px !important; line-height: 1.2 !important; }
  .benefit p { font-size: 14.5px !important; line-height: 1.55 !important; }

  /* Sequence (Acts) — full width per step, photo card smaller */
  .sequence-container { padding: 0 !important; }
  .step {
    grid-template-columns: 1fr !important;
    gap: 16px !important;
    padding: 16px !important;
  }
  .step-head { gap: 16px !important; padding-bottom: 12px; }
  .step-head .num { font-size: 36px !important; line-height: 1; }
  .step-title h3 { font-size: 22px !important; line-height: 1.2 !important; }
  .step-body {
    grid-template-columns: 1fr !important;
    flex-direction: column !important;
    gap: 16px !important;
  }
  .step-photo-col {
    flex-direction: row !important;
    flex-wrap: wrap;
    gap: 8px !important;
    justify-content: flex-start;
    padding: 0 !important;
  }
  .agent-card {
    flex: 0 0 auto;
    width: calc(50% - 4px) !important;
    max-width: 165px;
  }
  .agent-card .hero-photo {
    width: 100% !important;
    height: auto !important;
    aspect-ratio: 4/5;
    max-width: 165px !important;
  }
  .agent-card .hero-photo img { width: 100%; height: 100%; object-fit: cover; }
  .agent-card .hero-meta { padding: 8px 4px !important; }
  .agent-card .hero-name { font-size: 13px !important; }
  .agent-card .hero-role { font-size: 10px !important; }
  .agent-card .hero-line { font-size: 11.5px !important; line-height: 1.4 !important; }
  .step-meta-col { padding: 0 !important; }
  .step-meta-col .detail { font-size: 12px !important; }
  .step-desc { font-size: 14px !important; line-height: 1.55 !important; }

  /* Sequence dots positioning */
  .seq-dots { padding: 16px 0 !important; gap: 4px !important; }

  /* Sequence arrows : already styled at 720, ensure visibility */
  .seq-arrow { display: flex !important; }

  /* Pricing — 1 colonne */
  .pricing-grid {
    grid-template-columns: 1fr !important;
    padding: 0 16px !important;
    gap: 16px !important;
    max-width: 100% !important;
  }
  .pricing-card {
    padding: 24px 20px 20px !important;
  }
  .pricing-card.featured { transform: none !important; }
  .pricing-eyebrow { font-size: 10px !important; }
  .pricing-name { font-size: 26px !important; }
  .pricing-tagline { font-size: 14px !important; }
  .pricing-price-row, .pricing-price { font-size: 36px !important; }
  .pricing-period { font-size: 13px !important; }
  .pricing-bullets li { font-size: 13.5px !important; line-height: 1.55 !important; }
  .pricing-cta { padding: 14px 16px !important; min-height: 44px; }
  .pricing-cta-arrow { display: none; }

  /* Pricing Enterprise */
  .pricing-enterprise {
    margin: 24px 16px 0 !important;
    padding: 24px 20px !important;
    flex-direction: column !important;
    gap: 16px !important;
    align-items: flex-start !important;
  }
  .pricing-enterprise-eyebrow { font-size: 10px !important; }
  .pricing-enterprise-text { font-size: 14px !important; }

  /* Work grid (Our Work / projets) */
  .work-grid {
    grid-template-columns: 1fr !important;
    gap: 16px !important;
    padding: 0 16px !important;
  }

  /* CTA section */
  .cta { padding: 48px 16px !important; }
  .cta-title { font-size: clamp(28px, 7vw, 40px) !important; }
  .cta-actions { flex-direction: column !important; gap: 12px !important; align-items: stretch !important; }
  .cta-actions a, .cta-actions button { text-align: center; }

  /* Footer */
  footer { padding: 32px 16px 24px !important; }
  footer .row { font-size: 12px !important; align-items: flex-start !important; }
  .footer-legal { font-size: 11px; }
  .footer-mail { font-size: 12px; }

  /* Sophie Chat launcher : tap target larger */
  .sophie-launcher {
    min-height: 48px !important;
    padding: 12px 18px !important;
  }
}

/* Mobile small (<= 380px) */
@media (max-width: 380px) {
  .agent-card { width: 100% !important; max-width: 200px; }
  .step-photo-col { flex-direction: column !important; }
  .pricing-grid { padding: 0 12px !important; }
}
'''


def patch_template_css(template):
    """Inject mobile + a11y CSS at end of last <style> block."""
    last_style = template.rfind('</style>')
    if last_style == -1:
        raise RuntimeError("No </style> in template")
    return template[:last_style] + MOBILE_CSS + template[last_style:]


# ============================================================================
# 5. SEO + Open Graph meta tags
# ============================================================================
SEO_META = '''<meta name="description" content="Digital Humans \u2014 the autonomous Salesforce studio. Eleven AI agents draft your SDS, design your architecture and ship your code. From brief to delivered SDS in days, not months.">
<meta name="keywords" content="Salesforce, AI, automated development, SDS, Apex, LWC, multi-agent, studio, consulting alternative">
<meta name="author" content="Digital Humans">
<meta name="theme-color" content="#0A0A0B" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#F5F2EC" media="(prefers-color-scheme: light)">
<meta name="robots" content="index, follow">
<link rel="canonical" href="https://digital-humans.fr/">

<!-- Open Graph -->
<meta property="og:type" content="website">
<meta property="og:url" content="https://digital-humans.fr/">
<meta property="og:title" content="Digital\u00b7Humans \u2014 Autonomous Salesforce Studio">
<meta property="og:description" content="Eleven AI agents. From brief to delivered SDS in days, not months. The studio pattern, replacing the consultancy model.">
<meta property="og:locale" content="en_US">
<meta property="og:locale:alternate" content="fr_FR">
<meta property="og:site_name" content="Digital\u00b7Humans">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:url" content="https://digital-humans.fr/">
<meta name="twitter:title" content="Digital\u00b7Humans \u2014 Autonomous Salesforce Studio">
<meta name="twitter:description" content="Eleven AI agents. From brief to delivered SDS in days, not months.">

'''


def patch_template_meta(template):
    """Inject SEO meta after the existing viewport meta."""
    anchor = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    if anchor not in template:
        raise RuntimeError("viewport meta anchor not found")
    
    # Avoid double-injection
    if '<meta name="description"' in template:
        print("  [seo] meta description already present, skipping")
        return template
    
    template = template.replace(anchor, anchor + '\n' + SEO_META, 1)
    print("  [seo] injected description, OG, Twitter Card meta tags")
    return template


# ============================================================================
# 6. Write back
# ============================================================================
def write_bundle(content, manifest, template, ext_resources):
    new_manifest_body = json.dumps(manifest, ensure_ascii=False)
    new_template_body = json.dumps(template, ensure_ascii=False)
    new_template_body = new_template_body.replace('</script>', r'<\u002Fscript>').replace('</style>', r'<\u002Fstyle>')
    new_ext_body = json.dumps(ext_resources, ensure_ascii=False)

    new_content = content
    p = re.compile(r'(<script[^>]*type="__bundler/manifest"[^>]*>)(.*?)(</script>)', re.DOTALL)
    new_content = p.sub(lambda m: m.group(1) + new_manifest_body + m.group(3), new_content, count=1)
    p = re.compile(r'(<script[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)', re.DOTALL)
    new_content = p.sub(lambda m: m.group(1) + new_template_body + m.group(3), new_content, count=1)
    p = re.compile(r'(<script[^>]*type="__bundler/ext_resources"[^>]*>)(.*?)(</script>)', re.DOTALL)
    new_content = p.sub(lambda m: m.group(1) + new_ext_body + m.group(3), new_content, count=1)
    return new_content


if __name__ == "__main__":
    print("=== Mod 29 — Sprint 2 mobile/a11y/SEO ===\n")
    print("[1/6] Reading bundle...")
    content, manifest, template, ext_resources = read_bundle()
    print(f"  manifest: {len(manifest)} | template: {len(template):,} chars")

    print("\n[2/6] Patching modules (a11y JS)...")
    icons = decode_module(manifest, UUID_ICONS)
    sec   = decode_module(manifest, UUID_SECTIONS)
    av    = decode_module(manifest, UUID_AVATARS)

    icons2 = patch_icons(icons)
    sec2   = patch_sections(sec)
    av2    = patch_avatars(av)

    manifest[UUID_ICONS]    = encode_module(icons2)
    manifest[UUID_SECTIONS] = encode_module(sec2)
    manifest[UUID_AVATARS]  = encode_module(av2)

    print("\n[3/6] Patching CSS variables (color contrast)...")
    template = patch_root_vars(template)

    print("\n[4/6] Injecting mobile + a11y responsive CSS...")
    template = patch_template_css(template)

    print("\n[5/6] Injecting SEO meta tags (description, OG, Twitter)...")
    template = patch_template_meta(template)

    print("\n[6/6] Writing bundle...")
    new_content = write_bundle(content, manifest, template, ext_resources)
    print(f"  before: {len(content):,} bytes")
    print(f"  after:  {len(new_content):,} bytes  (delta {len(new_content)-len(content):+,})")
    
    with open(INDEX_PATH, 'w') as f:
        f.write(new_content)
    print(f"\nWritten to {INDEX_PATH}")
