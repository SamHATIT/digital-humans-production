#!/usr/bin/env python3
"""
Mod 23 — Section prix UI : 3 colonnes Free / Pro / Team + bloc Enterprise.

Décisions actées 26 + 29 avril 2026 :
- Free        — Sophie + Olivia chat seul (Haiku, pas d'upload)
- Pro    49€  — Équipe complète + 2 SDS/mois inclus, Marcus en Opus,
                pas de BUILD ni déploiement
- Team 1490€  — Pipeline complet jusqu'à sandbox (pas de prod)
- Enterprise  — On-premise sur devis (bloc séparé en bas)

Numérotation narrative :
  № 01 The case  →  № 02 The sequence  →  № 03 The work  →
  № 04 The pact (NEW)  →  № 05 Correspondence (renuméroté de 04)

Tous les boutons d'abonnement → "Get on the list" → ouvre le widget Sophie
(SophieChat existant, Mod 20). Pas de wiring Stripe pour l'instant
(en attente de Phase 3 backend).

Modules touchés :
  - 0fbb2257-... (Site composition) : ajout de <Pricing lang={lang}/>
  - b077057a-... (avatars.jsx)      : ajout du composant Pricing + renumérotation CTA
  - template CSS                     : nouvelles classes .pricing-*
"""
from __future__ import annotations
import base64, gzip, json, re, sys
from pathlib import Path

SRC = Path('/var/www/dh-preview/index.html')
SITE_UUID    = '0fbb2257-1e12-4e49-857e-4774d4dc6847'
AVATARS_UUID = 'b077057a-5a3a-41a8-8f45-fe3c0011a134'

# ─────────────────────────────────────────────────────────────────
# 1. PRICING — JSX du nouveau composant
# ─────────────────────────────────────────────────────────────────
PRICING_JSX = r"""
const PRICING_TIERS = [
  {
    id: 'free',
    eyebrow: { en: 'TIER I', fr: 'PALIER I' },
    name:    { en: 'Free',  fr: 'Gratuit' },
    tagline: { en: 'Discover the studio.', fr: 'Découvrir le studio.' },
    price:   { en: 'Free',  fr: 'Gratuit' },
    period:  { en: '',      fr: '' },
    bullets: {
      en: [
        'Chat with Sophie and Olivia',
        'No file upload, no persistent memory',
        'Haiku 4.5 model',
        'Sessions stateless — nothing stored',
      ],
      fr: [
        'Chat avec Sophie et Olivia',
        'Pas d’upload, pas de mémoire persistante',
        'Modèle Haiku 4.5',
        'Sessions sans trace — rien n’est stocké',
      ],
    },
    cta: { en: 'Get on the list', fr: 'S’inscrire à la liste' },
  },
  {
    id: 'pro',
    eyebrow:   { en: 'TIER II · MOST POPULAR', fr: 'PALIER II · LE PLUS DEMANDÉ' },
    name:      { en: 'Pro',   fr: 'Pro' },
    tagline:   { en: 'From brief to delivered SDS.', fr: 'Du brief au SDS livré.' },
    price:     { en: '49€',   fr: '49€' },
    period:    { en: '/month', fr: '/mois' },
    featured:  true,
    bullets: {
      en: [
        'Full ensemble of 11 agents',
        'File upload & persistent memory',
        '2 SDS per month included (BR · UC · Solution Design · Word/PDF)',
        'Marcus runs on Opus — the technical depth that makes the SDS shippable',
        'Sonnet 4.6 for the rest of the team',
      ],
      fr: [
        'L’ensemble complet des 11 agents',
        'Upload de fichiers & mémoire persistante',
        '2 SDS par mois inclus (BR · UC · Solution Design · Word/PDF)',
        'Marcus tourne en Opus — la rigueur technique qui rend le SDS livrable',
        'Sonnet 4.6 pour le reste de l’équipe',
      ],
    },
    cta: { en: 'Get on the list', fr: 'S’inscrire à la liste' },
    note: { en: 'No code generation, no deployment — those live in Team.',
            fr: 'Pas de génération de code ni de déploiement — c’est l’offre Team.' },
  },
  {
    id: 'team',
    eyebrow: { en: 'TIER III', fr: 'PALIER III' },
    name:    { en: 'Team',     fr: 'Team' },
    tagline: { en: 'Pocket team for continuous work.', fr: 'Équipe-poche pour les évolutions continues.' },
    price:   { en: '1 490€',   fr: '1 490€' },
    period:  { en: '/month',   fr: '/mois' },
    bullets: {
      en: [
        'Everything in Pro',
        'BUILD phase — Apex, LWC, Admin generation',
        'SFDX deployment to sandbox',
        'Opus 4.7 on opt-in (cost shown before each call)',
        'Multi-environment, git integration',
      ],
      fr: [
        'Tout le contenu de Pro',
        'Phase BUILD — génération Apex, LWC, Admin',
        'Déploiement SFDX vers sandbox',
        'Opus 4.7 en opt-in (coût affiché avant chaque appel)',
        'Multi-environnement, intégration git',
      ],
    },
    cta: { en: 'Get on the list', fr: 'S’inscrire à la liste' },
    note: { en: 'Sandbox only — production deploys are reserved for Enterprise contracts.',
            fr: 'Sandbox uniquement — la mise en production est réservée aux contrats Enterprise.' },
  },
];

function Pricing({lang}) {
  const openSophie = (e) => {
    e.preventDefault();
    const launcher = document.querySelector('.sophie-launcher');
    if (launcher) launcher.click();
  };

  return (
    <section className="pricing" id="pricing">
      <div className="pricing-head">
        <div className="eyebrow-mono">{lang==='fr' ? '№ 04 · Le pacte' : '№ 04 · The pact'}</div>
        <h2 className="pricing-title">
          {lang==='fr'
            ? <>Trois manières de <em>travailler avec nous</em>.</>
            : <>Three ways to <em>work with us</em>.</>}
        </h2>
        <p className="pricing-sub">
          {lang==='fr'
            ? 'Early access — l’ouverture se fait par paliers. Inscris-toi pour être prévenu·e.'
            : 'Early access — we’re opening in waves. Get on the list to be notified.'}
        </p>
      </div>

      <div className="pricing-grid">
        {PRICING_TIERS.map((t) => (
          <article key={t.id} className={"pricing-card" + (t.featured ? " is-featured" : "")}>
            <div className="pricing-eyebrow">{t.eyebrow[lang] || t.eyebrow.en}</div>
            <div className="pricing-name">{t.name[lang] || t.name.en}</div>
            <div className="pricing-tagline">{t.tagline[lang] || t.tagline.en}</div>
            <div className="pricing-price">
              <span className="pricing-amount">{t.price[lang] || t.price.en}</span>
              <span className="pricing-period">{t.period[lang] || t.period.en}</span>
            </div>
            <ul className="pricing-bullets">
              {(t.bullets[lang] || t.bullets.en).map((b, i) => (
                <li key={i}><span className="pricing-bullet-mark">—</span><span>{b}</span></li>
              ))}
            </ul>
            {t.note && (
              <div className="pricing-note">{t.note[lang] || t.note.en}</div>
            )}
            <button type="button" className="pricing-cta" onClick={openSophie}>
              {t.cta[lang] || t.cta.en}
              <span className="pricing-cta-arrow">→</span>
            </button>
          </article>
        ))}
      </div>

      <div className="pricing-enterprise">
        <div className="pricing-enterprise-eyebrow">
          {lang==='fr' ? 'TIER IV · ENTERPRISE' : 'TIER IV · ENTERPRISE'}
        </div>
        <div className="pricing-enterprise-body">
          <div className="pricing-enterprise-text">
            <strong>{lang==='fr' ? 'Sur devis · on-premise.' : 'On request · on-premise.'}</strong>{' '}
            {lang==='fr'
              ? 'Installation chez vous, choix du LLM (Claude, GPT, Mistral, Llama), customisation projet, SSO, audit logs, déploiement en production négocié au contrat.'
              : 'Hosted on your infrastructure, your choice of LLM (Claude, GPT, Mistral, Llama), project-level customisation, SSO, audit logs, production deploys negotiated in the contract.'}
          </div>
          <button type="button" className="pricing-enterprise-cta" onClick={openSophie}>
            {lang==='fr' ? 'Nous contacter' : 'Talk to us'}
            <span className="pricing-cta-arrow">→</span>
          </button>
        </div>
      </div>
    </section>
  );
}
"""

# ─────────────────────────────────────────────────────────────────
# 2. CSS — design Studio (ink/bone/brass) + grid responsive
# ─────────────────────────────────────────────────────────────────
PRICING_CSS = r"""
  /* ===== Mod 23 — Pricing section (Studio language) ===== */
  .pricing {
    padding: 120px 0 100px;
    border-top: var(--rail);
  }
  .pricing-head {
    max-width: 760px;
    margin: 0 auto 64px;
    padding: 0 48px;
    text-align: center;
  }
  .pricing-head .eyebrow-mono {
    font-family: var(--mono);
    font-size: 9.5px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bone-4);
    margin-bottom: 20px;
  }
  .pricing-title {
    font-family: var(--serif);
    font-weight: 400;
    font-size: clamp(36px, 5vw, 56px);
    line-height: 1.1;
    color: var(--bone);
    margin-bottom: 18px;
    letter-spacing: -0.015em;
  }
  .pricing-title em {
    color: var(--brass);
    font-style: italic;
    font-weight: 400;
  }
  .pricing-sub {
    font-size: 14.5px;
    color: var(--bone-3);
    line-height: 1.55;
    font-style: italic;
    font-family: var(--serif);
  }

  .pricing-grid {
    max-width: 1160px;
    margin: 0 auto;
    padding: 0 48px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 22px;
    align-items: stretch;
  }
  @media (max-width: 920px) { .pricing-grid { grid-template-columns: 1fr; gap: 16px; } }

  .pricing-card {
    background: rgba(20,20,22,0.55);
    border: 1px solid rgba(245,242,236,0.10);
    padding: 32px 28px 28px;
    display: flex;
    flex-direction: column;
    transition: border-color 0.3s ease, transform 0.3s ease;
    position: relative;
  }
  .pricing-card:hover { border-color: rgba(200,169,126,0.32); }
  .pricing-card.is-featured {
    border-color: rgba(200,169,126,0.42);
    background: rgba(20,20,22,0.78);
  }
  .pricing-card.is-featured::before {
    content: '';
    position: absolute;
    inset: -1px;
    border: 1px solid rgba(200,169,126,0.20);
    pointer-events: none;
    transform: translate(6px, 6px);
  }

  .pricing-eyebrow {
    font-family: var(--mono);
    font-size: 9.5px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bone-4);
    margin-bottom: 18px;
  }
  .pricing-card.is-featured .pricing-eyebrow { color: var(--brass); }

  .pricing-name {
    font-family: var(--serif);
    font-weight: 400;
    font-size: 32px;
    color: var(--bone);
    line-height: 1;
    margin-bottom: 8px;
    letter-spacing: -0.01em;
  }
  .pricing-tagline {
    font-family: var(--serif);
    font-style: italic;
    font-size: 15px;
    color: var(--bone-3);
    margin-bottom: 24px;
    line-height: 1.4;
  }

  .pricing-price {
    display: flex;
    align-items: baseline;
    gap: 4px;
    padding-bottom: 24px;
    margin-bottom: 24px;
    border-bottom: 1px solid rgba(245,242,236,0.08);
  }
  .pricing-amount {
    font-family: var(--serif);
    font-weight: 400;
    font-size: 38px;
    color: var(--bone);
    letter-spacing: -0.02em;
    line-height: 1;
  }
  .pricing-period {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--bone-4);
    letter-spacing: 0.04em;
  }

  .pricing-bullets {
    list-style: none;
    padding: 0;
    margin: 0 0 24px;
    flex-grow: 1;
  }
  .pricing-bullets li {
    display: flex;
    gap: 12px;
    padding: 8px 0;
    font-size: 13.5px;
    color: var(--bone-2);
    line-height: 1.5;
  }
  .pricing-bullet-mark {
    color: var(--brass);
    font-family: var(--serif);
    flex-shrink: 0;
    line-height: 1.55;
  }

  .pricing-note {
    font-family: var(--serif);
    font-style: italic;
    font-size: 12.5px;
    color: var(--bone-4);
    line-height: 1.5;
    padding: 12px 0;
    margin-bottom: 16px;
    border-top: 1px solid rgba(245,242,236,0.06);
  }

  .pricing-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 14px 22px;
    background: transparent;
    border: 1px solid rgba(200,169,126,0.42);
    color: var(--bone);
    font-family: var(--mono);
    font-size: 11px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    cursor: pointer;
    transition: background 0.25s ease, border-color 0.25s ease;
    width: 100%;
  }
  .pricing-cta:hover {
    background: rgba(200,169,126,0.10);
    border-color: var(--brass);
  }
  .pricing-card.is-featured .pricing-cta {
    background: rgba(200,169,126,0.14);
    border-color: var(--brass);
  }
  .pricing-card.is-featured .pricing-cta:hover {
    background: rgba(200,169,126,0.22);
  }
  .pricing-cta-arrow {
    transition: transform 0.25s ease;
  }
  .pricing-cta:hover .pricing-cta-arrow { transform: translateX(4px); }

  /* Enterprise block */
  .pricing-enterprise {
    max-width: 1160px;
    margin: 56px auto 0;
    padding: 28px 32px;
    border: 1px solid rgba(245,242,236,0.10);
    background: rgba(20,20,22,0.40);
  }
  .pricing-enterprise-eyebrow {
    font-family: var(--mono);
    font-size: 9.5px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--bone-4);
    margin-bottom: 14px;
  }
  .pricing-enterprise-body {
    display: flex;
    align-items: center;
    gap: 32px;
    justify-content: space-between;
    flex-wrap: wrap;
  }
  .pricing-enterprise-text {
    flex: 1;
    min-width: 280px;
    font-family: var(--serif);
    font-size: 15px;
    color: var(--bone-2);
    line-height: 1.55;
  }
  .pricing-enterprise-text strong {
    font-style: italic;
    color: var(--bone);
    font-weight: 400;
  }
  .pricing-enterprise-cta {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 12px 22px;
    background: transparent;
    border: 1px solid rgba(245,242,236,0.16);
    color: var(--bone-2);
    font-family: var(--mono);
    font-size: 10.5px;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    cursor: pointer;
    transition: border-color 0.25s ease, color 0.25s ease;
  }
  .pricing-enterprise-cta:hover {
    border-color: var(--brass);
    color: var(--bone);
  }
"""

# ─────────────────────────────────────────────────────────────────
# 3. Patch the bundle
# ─────────────────────────────────────────────────────────────────
print(f"[0] Loading {SRC}")
content = SRC.read_text()
print(f"    {len(content):,} bytes")

# Backup
backup = SRC.with_suffix('.html.pre-mod23-pricing')
backup.write_text(content)
print(f"    backup: {backup.name}")

m_manifest = re.search(r'(<script\s+type="__bundler/manifest"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
manifest_open, manifest_body, manifest_close = m_manifest.groups()
manifest = json.loads(manifest_body.strip())

m_template = re.search(r'(<script\s+type="__bundler/template"[^>]*>)(.*?)(</script>)', content, re.DOTALL)
template_open, template_body, template_close = m_template.groups()
template_html = json.loads(template_body.strip())

# 3a. Site composition — insert <Pricing/> between <OurWork/> and <CTA/>
print(f"[1] Patching Site composition ({SITE_UUID[:8]}...)")
site_entry = manifest[SITE_UUID]
site_js = gzip.decompress(base64.b64decode(site_entry['data'])).decode('utf-8') if site_entry.get('compressed') else base64.b64decode(site_entry['data']).decode('utf-8')
old_compo = '<OurWork lang={lang}/>\n        <CTA lang={lang}/>'
new_compo = '<OurWork lang={lang}/>\n        <Pricing lang={lang}/>\n        <CTA lang={lang}/>'
if old_compo not in site_js:
    print("    ERROR: composition anchor not found, aborting"); sys.exit(1)
site_js = site_js.replace(old_compo, new_compo, 1)
new_data = base64.b64encode(gzip.compress(site_js.encode('utf-8'))).decode('ascii') if site_entry.get('compressed') else base64.b64encode(site_js.encode('utf-8')).decode('ascii')
manifest[SITE_UUID]['data'] = new_data
print("    OK — <Pricing/> inserted between <OurWork/> and <CTA/>")

# 3b. avatars.jsx — add Pricing component + renumber CTA №04→№05
print(f"[2] Patching avatars.jsx ({AVATARS_UUID[:8]}...)")
av_entry = manifest[AVATARS_UUID]
av_jsx = gzip.decompress(base64.b64decode(av_entry['data'])).decode('utf-8')

# Renumber CTA №04 → №05
av_jsx = av_jsx.replace('№ 04 · Correspondence', '№ 05 · Correspondence', 1)
av_jsx = av_jsx.replace('№ 04 · Correspondance',  '№ 05 · Correspondance',  1)
print("    OK — CTA renumbered №04 → №05")

# Insert Pricing component before CTA. CTA is at index ~12950.
cta_idx = av_jsx.find('function CTA')
if cta_idx < 0:
    print("    ERROR: 'function CTA' not found"); sys.exit(1)
av_jsx = av_jsx[:cta_idx] + PRICING_JSX.lstrip() + '\n\n' + av_jsx[cta_idx:]
print("    OK — Pricing component inserted before CTA")

new_av_data = base64.b64encode(gzip.compress(av_jsx.encode('utf-8'))).decode('ascii')
manifest[AVATARS_UUID]['data'] = new_av_data

# 3c. Inject CSS into template
print(f"[3] Injecting CSS ({len(PRICING_CSS):,} chars)")
inject_marker = '/* ===== Sequence navigation : arrows + dots ===== */'
if inject_marker not in template_html:
    # Fallback : append to end of <style>
    template_html = template_html.replace('</style>', PRICING_CSS + '\n</style>', 1)
    print("    OK — CSS appended to end of <style> (fallback)")
else:
    template_html = template_html.replace(inject_marker, PRICING_CSS + '\n  ' + inject_marker, 1)
    print("    OK — CSS injected before sequence navigation block")

# ─────────────────────────────────────────────────────────────────
# 4. Reassemble + write
# ─────────────────────────────────────────────────────────────────
print(f"[4] Reassembling bundle")
new_manifest_body = json.dumps(manifest, ensure_ascii=False)
new_template_body = json.dumps(template_html, ensure_ascii=False)
# Critical : escape </script> and </style> in serialized template
new_template_body = new_template_body.replace("</script>", r"<\u002Fscript>").replace("</style>", r"<\u002Fstyle>")

content_new = (
    content[:m_manifest.start()] +
    manifest_open + new_manifest_body + manifest_close +
    content[m_manifest.end():m_template.start()] +
    template_open + new_template_body + template_close +
    content[m_template.end():]
)

SRC.write_text(content_new)
print(f"    OK — {len(content_new):,} bytes (was {len(content):,}, Δ {len(content_new)-len(content):+,})")

print()
print("✅ Mod 23 applied. Visit http://72.61.161.222/preview/ (Ctrl+Shift+R) to verify.")
print(f"   Rollback: cp {backup.name} index.html")
