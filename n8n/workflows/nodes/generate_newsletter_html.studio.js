// =============================================================================
// Node: Generate Newsletter HTML  (Studio template — Track B5.2)
// =============================================================================
// Renders docs/marketing-site/newsletter-studio-mockup.html with live data.
// Inputs (from "Filter This Week"):
//   - posts: Ghost article objects (with tags, primary_author, feature_image…)
//   - week_label, test_mode
// Optional overrides on the same payload:
//   - week_number, year, hero_deck
//
// Outputs:
//   - html             : per-recipient HTML (with __UNSUBSCRIBE_URL__ placeholder
//                        — substituted by the Send Newsletter node per recipient.
//                        We use __UNSUBSCRIBE_URL__ rather than {{unsubscribe_url}}
//                        to avoid colliding with n8n's `{{ }}` expression syntax.)
//   - subject          : email subject line
//   - week_number, year
//   - archive_slug     : "week-{N}-{YYYY}"
//   - archive_url      : https://digital-humans.fr/journal/archive/{slug}
//   - archive_excerpt  : hero deck (used as Ghost custom_excerpt)
//   - archive_html     : same HTML, unsubscribe placeholder substituted with
//                        the generic studio unsubscribe URL (no per-recipient leak)
//   - test_mode, total_articles, rendered_articles
// =============================================================================

const data = items[0].json;
const initData = $('Init Week').first().json;
const articles = data.posts || [];
const test_mode = data.test_mode === true || initData.test_mode === true;

// --- Week / Year ---------------------------------------------------------
function isoWeek(d) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return Math.ceil((((t - yearStart) / 86400000) + 1) / 7);
}
const today = new Date();
const week_number = data.week_number || isoWeek(today);
const year = data.year || today.getUTCFullYear();
const hero_deck = data.hero_deck || "Field notes from the writers' room.";

// --- URLs ----------------------------------------------------------------
const archive_slug = `week-${week_number}-${year}`;
const view_in_browser_url = `https://digital-humans.fr/journal/archive/${archive_slug}`;

// --- Rubric mapping (slug → color + label) -------------------------------
const RUBRIC = {
  'manifesto':   { color: '#C8A97E', label: 'MANIFESTO'   }, // brass
  'craft-notes': { color: '#8E6B8E', label: 'CRAFT NOTES' }, // mauve
  'dispatches':  { color: '#7A9B76', label: 'DISPATCHES'  }, // sage
  'archive':     { color: '#76716A', label: 'ARCHIVE'     }, // bone-4
};
const RUBRIC_FALLBACK = { color: '#76716A', label: 'NOTES' };
const STUDIO_TAG_SLUGS = new Set(Object.keys(RUBRIC));

// --- Helpers -------------------------------------------------------------
function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso)
    .toLocaleDateString('en-US', { month: 'short', day: '2-digit' })
    .toUpperCase();
}
function escapeHTML(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
function readingTime(post) {
  const r = Number(post.reading_time);
  return Number.isFinite(r) && r > 0 ? r : 5;
}
function rubricFor(post) {
  const tag = (post.tags || []).find(t => t && STUDIO_TAG_SLUGS.has(t.slug));
  return tag ? RUBRIC[tag.slug] : RUBRIC_FALLBACK;
}
function authorOf(post) {
  if (post.primary_author && post.primary_author.name) return post.primary_author.name;
  if (Array.isArray(post.authors) && post.authors[0] && post.authors[0].name) return post.authors[0].name;
  return 'The Studio';
}
function urlOf(post) {
  if (post.url) return post.url;
  if (post.slug) return `https://digital-humans.fr/journal/${post.slug}/`;
  return 'https://digital-humans.fr/journal/';
}

// --- Article block -------------------------------------------------------
function articleBlock(a) {
  const r = rubricFor(a);
  const author = authorOf(a);
  const cover = a.feature_image || 'https://digital-humans.fr/assets/covers/placeholder.jpg';
  const url = urlOf(a);
  const excerpt = (a.custom_excerpt || a.excerpt || '').slice(0, 280);
  const minutes = readingTime(a);
  const title = a.title || '(untitled)';

  return `
    <tr>
      <td class="px-40" style="padding:0 40px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td height="1" style="height:1px;line-height:1px;font-size:1px;background-color:#1F1E1B;border-top:1px solid #1F1E1B;">&nbsp;</td></tr>
        </table>
      </td>
    </tr>
    <tr>
      <td class="px-40" style="padding:36px 40px 32px 40px;">
        <p class="mso-mono" style="margin:0 0 22px 0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:10px;font-weight:500;line-height:1.4;letter-spacing:2.4px;text-transform:uppercase;color:#76716A;">
          <span style="color:${r.color};">${r.label}</span> &nbsp;·&nbsp; ${escapeHTML(author)} &nbsp;·&nbsp; ${minutes} min read &nbsp;·&nbsp; ${fmtDate(a.published_at)}
        </p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td style="padding:0 0 28px 0;">
              <a href="${url}" style="display:block;text-decoration:none;">
                <img src="${cover}" alt="${escapeHTML(title)}" width="520" height="325" class="cover-fluid" style="display:block;width:100%;max-width:520px;height:auto;border:0;outline:none;background-color:#141416;">
              </a>
            </td>
          </tr>
        </table>
        <h2 class="h2-fluid" style="margin:0 0 14px 0;font-family:'Cormorant Garamond', Georgia, 'Times New Roman', serif;font-size:26px;font-weight:500;line-height:1.18;letter-spacing:-0.02em;color:#F5F2EC;">
          <a href="${url}" style="color:#F5F2EC;text-decoration:none;">${escapeHTML(title)}</a>
        </h2>
        <p class="mso-sans" style="margin:0 0 22px 0;font-family:Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;font-size:14.5px;font-weight:400;line-height:1.65;color:#E8E3D9;">
          ${escapeHTML(excerpt)}
        </p>
        <p class="mso-mono" style="margin:0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:10.5px;font-weight:500;line-height:1.4;letter-spacing:2px;text-transform:uppercase;">
          <a href="${url}" style="color:#C8A97E;text-decoration:none;border-bottom:1px solid #8C6E4A;padding-bottom:2px;">Read the piece →</a>
        </p>
      </td>
    </tr>
  `;
}

// --- Render --------------------------------------------------------------
const renderedArticles = articles.slice(0, 3).map(articleBlock).join('');
const remaining = Math.max(0, articles.length - 3);
const moreBlock = remaining > 0 ? `
    <tr>
      <td class="px-40" align="center" style="padding:8px 40px 32px 40px;">
        <p class="mso-mono" style="margin:0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:10.5px;font-weight:500;line-height:1.4;letter-spacing:1.6px;text-transform:uppercase;color:#76716A;">
          <a href="${view_in_browser_url}" style="color:#B8B2A6;text-decoration:none;border-bottom:1px solid #76716A;padding-bottom:2px;">+ ${remaining} more this week →</a>
        </p>
      </td>
    </tr>
` : '';

const testBanner = test_mode ? `
    <tr>
      <td style="background:#3A2A12;color:#F5DCB1;padding:10px 16px;text-align:center;font-family:'JetBrains Mono', Consolas, monospace;font-size:11px;letter-spacing:1.4px;text-transform:uppercase;">
        ⚠ Test mode — recipient list limited to [email protected]
      </td>
    </tr>` : '';

// --- Full template (mirror of docs/marketing-site/newsletter-studio-mockup.html)
const html = `<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
  <meta name="color-scheme" content="dark">
  <meta name="supported-color-schemes" content="dark">
  <title>Digital·Humans — № Week ${week_number} · This week from the studio.</title>
  <!--[if !mso]><!-->
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;1,400;1,500&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <!--<![endif]-->
  <!--[if mso]>
  <style type="text/css">
    body, table, td, h1, h2, h3, p, a { font-family: Georgia, 'Times New Roman', serif !important; }
    .mso-mono, .mso-mono * { font-family: Consolas, 'Courier New', monospace !important; }
    .mso-sans, .mso-sans * { font-family: Arial, sans-serif !important; }
  </style>
  <![endif]-->
  <style type="text/css">
    body { margin: 0; padding: 0; width: 100% !important; -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; background-color: #0A0A0B; }
    table { border-collapse: collapse; mso-table-lspace: 0pt; mso-table-rspace: 0pt; }
    img { border: 0; outline: none; text-decoration: none; -ms-interpolation-mode: bicubic; display: block; }
    a { text-decoration: none; }
    a:hover { text-decoration: underline; }
    .preheader { display: none !important; visibility: hidden; opacity: 0; color: transparent; height: 0; width: 0; overflow: hidden; mso-hide: all; }
    @media only screen and (max-width: 620px) {
      .container { width: 100% !important; max-width: 100% !important; }
      .px-40 { padding-left: 24px !important; padding-right: 24px !important; }
      .h1-fluid { font-size: 30px !important; line-height: 1.12 !important; }
      .h2-fluid { font-size: 24px !important; line-height: 1.18 !important; }
      .cover-fluid { width: 100% !important; max-width: 100% !important; height: auto !important; }
    }
  </style>
</head>
<body style="margin:0;padding:0;background-color:#0A0A0B;color:#F5F2EC;">
<div class="preheader" style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all;color:transparent;">
  ${escapeHTML(hero_deck)}
</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#0A0A0B;">
<tr>
<td align="center" style="padding:0;">
${testBanner}
  <!--[if mso | IE]>
  <table role="presentation" align="center" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;"><tr><td>
  <![endif]-->
  <table role="presentation" class="container" align="center" width="600" cellpadding="0" cellspacing="0" border="0" style="width:600px;max-width:600px;background-color:#0A0A0B;">
    <tr><td style="height:32px;line-height:32px;font-size:0;">&nbsp;</td></tr>
    <tr>
      <td class="px-40" style="padding:0 40px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td align="left" valign="middle" style="font-family:'Cormorant Garamond', Georgia, 'Times New Roman', serif;font-size:24px;font-weight:500;line-height:1.1;color:#F5F2EC;letter-spacing:-0.01em;">
              <a href="https://digital-humans.fr/" style="color:#F5F2EC;text-decoration:none;">
                Digital<span style="color:#8C6E4A;">·</span><em style="font-style:italic;color:#C8A97E;font-weight:400;">Humans</em>
              </a>
            </td>
            <td align="right" valign="middle" class="mso-mono" style="font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:10px;font-weight:400;line-height:1.4;color:#76716A;letter-spacing:2px;text-transform:uppercase;">
              № Week ${week_number} &nbsp;·&nbsp; <span style="color:#C8A97E;">${year}</span>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr><td style="height:32px;line-height:32px;font-size:0;">&nbsp;</td></tr>
    <tr>
      <td class="px-40" style="padding:0 40px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td height="1" style="height:1px;line-height:1px;font-size:1px;background-color:#8C6E4A;border-top:1px solid #8C6E4A;">&nbsp;</td></tr>
        </table>
      </td>
    </tr>
    <tr>
      <td class="px-40" style="padding:48px 40px 44px 40px;">
        <p class="mso-mono" style="margin:0 0 20px 0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:10px;font-weight:500;line-height:1.4;color:#C8A97E;letter-spacing:3px;text-transform:uppercase;">
          № ${String(week_number).padStart(3, '0')} &nbsp;·&nbsp; <span style="color:#76716A;">The Dispatch</span>
        </p>
        <h1 class="h1-fluid" style="margin:0 0 22px 0;font-family:'Cormorant Garamond', Georgia, 'Times New Roman', serif;font-size:38px;font-weight:500;line-height:1.08;color:#F5F2EC;letter-spacing:-0.025em;">
          This week <em style="font-style:italic;color:#C8A97E;font-weight:400;">from the studio.</em>
        </h1>
        <p style="margin:0;font-family:'Cormorant Garamond', Georgia, 'Times New Roman', serif;font-size:17px;font-style:italic;font-weight:400;line-height:1.55;color:#B8B2A6;padding-left:14px;border-left:1px solid #8C6E4A;">
          ${escapeHTML(hero_deck)}
        </p>
      </td>
    </tr>
${renderedArticles}${moreBlock}
    <tr>
      <td class="px-40" style="padding:0 40px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td height="1" style="height:1px;line-height:1px;font-size:1px;background-color:#8C6E4A;border-top:1px solid #8C6E4A;">&nbsp;</td></tr>
        </table>
      </td>
    </tr>
    <tr>
      <td class="px-40" style="padding:48px 40px 16px 40px;">
        <h2 class="h2-fluid" style="margin:0 0 16px 0;font-family:'Cormorant Garamond', Georgia, 'Times New Roman', serif;font-size:28px;font-weight:500;line-height:1.15;letter-spacing:-0.02em;color:#F5F2EC;">
          The journal keeps going <em style="font-style:italic;color:#C8A97E;font-weight:400;">between dispatches.</em>
        </h2>
        <p class="mso-sans" style="margin:0;font-family:Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;font-size:14.5px;font-weight:400;line-height:1.65;color:#B8B2A6;">
          Daily craft notes, archive pieces and the occasional manifesto. No tracking pixels, no engagement bait — just the studio thinking out loud.
        </p>
      </td>
    </tr>
    <tr>
      <td class="px-40" align="left" style="padding:24px 40px 56px 40px;">
        <!--[if mso]>
        <v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" href="https://digital-humans.fr/journal/" style="height:46px;v-text-anchor:middle;width:240px;" arcsize="0%" stroke="f" fillcolor="#C8A97E">
          <w:anchorlock/>
          <center style="color:#0A0A0B;font-family:Arial,sans-serif;font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;">Open the Journal &rarr;</center>
        </v:roundrect>
        <![endif]-->
        <!--[if !mso]><!-->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:separate;">
          <tr>
            <td align="center" valign="middle" style="background-color:#C8A97E;padding:14px 28px;">
              <a href="https://digital-humans.fr/journal/" style="display:inline-block;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:11px;font-weight:600;line-height:1;color:#0A0A0B;letter-spacing:0.14em;text-transform:uppercase;text-decoration:none;">
                Open the Journal &nbsp;→
              </a>
            </td>
          </tr>
        </table>
        <!--<![endif]-->
      </td>
    </tr>
    <tr>
      <td class="px-40" style="padding:0 40px;">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td height="1" style="height:1px;line-height:1px;font-size:1px;background-color:#8C6E4A;border-top:1px solid #8C6E4A;">&nbsp;</td></tr>
        </table>
      </td>
    </tr>
    <tr>
      <td class="px-40" style="padding:36px 40px 16px 40px;">
        <p class="mso-mono" style="margin:0 0 18px 0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:10.5px;font-weight:500;line-height:1.6;letter-spacing:1.8px;text-transform:uppercase;">
          <a href="https://digital-humans.fr/brief/" style="color:#C8A97E;text-decoration:none;border-bottom:1px solid #8C6E4A;padding-bottom:2px;">Brief us &nbsp;→</a>
          &nbsp;<span style="color:#8C6E4A;">·</span>&nbsp;
          <a href="https://digital-humans.fr/journal/" style="color:#B8B2A6;text-decoration:none;">The Journal</a>
          &nbsp;<span style="color:#8C6E4A;">·</span>&nbsp;
          <a href="${view_in_browser_url}" style="color:#76716A;text-decoration:none;">View on web</a>
        </p>
        <p class="mso-mono" style="margin:0 0 8px 0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:9.5px;font-weight:400;line-height:1.5;letter-spacing:1.6px;text-transform:uppercase;color:#76716A;">
          Digital<span style="color:#8C6E4A;">·</span>Humans &nbsp;·&nbsp; Autonomous Salesforce studio
        </p>
        <p class="mso-mono" style="margin:0 0 24px 0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:9.5px;font-weight:400;line-height:1.5;letter-spacing:1.6px;color:#76716A;">
          Samhatit Consulting &nbsp;·&nbsp; Paris, France &nbsp;·&nbsp; <a href="mailto:[email protected]" style="color:#76716A;text-decoration:none;">[email protected]</a>
        </p>
      </td>
    </tr>
    <tr>
      <td class="px-40" style="padding:0 40px 48px 40px;">
        <p class="mso-mono" style="margin:0;font-family:'JetBrains Mono', Consolas, 'Courier New', monospace;font-size:9.5px;font-weight:400;line-height:1.5;letter-spacing:1.4px;color:#76716A;">
          You are receiving this because you subscribed to the Digital&middot;Humans Dispatch.
          <br>
          <a href="__UNSUBSCRIBE_URL__" style="color:#76716A;text-decoration:underline;">Unsubscribe</a>
          &nbsp;·&nbsp;
          <a href="https://digital-humans.fr/privacy/" style="color:#76716A;text-decoration:underline;">Privacy</a>
        </p>
      </td>
    </tr>
  </table>
  <!--[if mso | IE]>
  </td></tr></table>
  <![endif]-->
</td>
</tr>
</table>
</body>
</html>`;

// Per-recipient unsubscribe is injected by the Send Newsletter node
// (it does .replace('__UNSUBSCRIBE_URL__', ...) on the html field).
// For the archive copy on Ghost, no per-recipient context exists — we
// substitute the placeholder with a generic studio URL so the archive page
// never displays an unresolved token.
const archive_html = html.split('__UNSUBSCRIBE_URL__').join(
  'https://digital-humans.fr/journal/unsubscribe'
);

const subject = `№ Week ${week_number} · This week from the studio.`;

return [{
  json: {
    html,
    subject,
    week_number,
    year,
    archive_slug,
    archive_url: view_in_browser_url,
    archive_excerpt: hero_deck,
    archive_html,
    test_mode,
    total_articles: articles.length,
    rendered_articles: Math.min(articles.length, 3),
  }
}];
