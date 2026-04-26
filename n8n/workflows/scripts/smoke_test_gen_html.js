#!/usr/bin/env node
/**
 * Smoke test for n8n/workflows/nodes/generate_newsletter_html.studio.js.
 *
 * Wraps the node's JS in a tiny harness that mocks `items[0].json`
 * and `$('Init Week').first().json`, executes it, and asserts the
 * output shape is sane.
 *
 *   node n8n/workflows/scripts/smoke_test_gen_html.js
 *
 * Exits 0 on success, 1 on any assertion failure.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(
  __dirname,
  '..',
  'nodes',
  'generate_newsletter_html.studio.js'
);
const code = fs.readFileSync(SRC, 'utf8');

// Synthetic Ghost-shaped articles — covers the 3 main rubrics + an extra
// to exercise the "+ N more" branch.
const fixtureArticles = [
  {
    title: 'Why we name our agents.',
    slug: 'why-we-name-our-agents',
    url: 'https://digital-humans.fr/journal/why-we-name-our-agents/',
    feature_image: 'https://digital-humans.fr/assets/covers/why-we-name-our-agents.jpg',
    custom_excerpt:
      'Sophie, Olivia, Marcus. The names look decorative — they are not. They are how we hold each agent accountable for its act.',
    reading_time: 4,
    published_at: '2026-04-24T08:30:00Z',
    primary_author: { name: 'Sophie Chen' },
    tags: [{ slug: 'manifesto', name: 'Manifesto' }],
  },
  {
    title: 'The Builder/Trace separation, in production.',
    slug: 'builder-trace-separation',
    url: 'https://digital-humans.fr/journal/builder-trace-separation/',
    feature_image: 'https://digital-humans.fr/assets/covers/builder-trace-separation.jpg',
    custom_excerpt:
      "For two months we kept the agent's reasoning trace and the artifact in the same buffer. Here's how we split them.",
    reading_time: 7,
    published_at: '2026-04-23T08:30:00Z',
    primary_author: { name: 'Marcus Johnson' },
    tags: [{ slug: 'craft-notes', name: 'Craft Notes' }],
  },
  {
    title: 'Week 17 — fourteen BR resolved, four BUILDs deployed.',
    slug: 'week-17-dispatches',
    url: 'https://digital-humans.fr/journal/week-17-dispatches/',
    feature_image: 'https://digital-humans.fr/assets/covers/week-17-dispatches.jpg',
    custom_excerpt: 'Numbers from the studio floor. Median SDS run-cost held at $0.11.',
    reading_time: 3,
    published_at: '2026-04-22T08:30:00Z',
    primary_author: { name: 'Emma Rodriguez' },
    tags: [{ slug: 'dispatches', name: 'Dispatches' }],
  },
  {
    // 4th article — should trigger the "+ 1 more this week" link
    title: 'A note on the FormaPro deployment.',
    slug: 'formapro-note',
    url: 'https://digital-humans.fr/journal/formapro-note/',
    feature_image: null,
    custom_excerpt: 'Small lessons from a real deploy.',
    reading_time: 2,
    published_at: '2026-04-21T08:30:00Z',
    primary_author: { name: 'Diego Martinez' },
    tags: [{ slug: 'archive', name: 'Archive' }],
  },
];

const items = [{
  json: {
    posts: fixtureArticles,
    week_label: 'Semaine du 20 avril',
    test_mode: true,
    week_number: 17,
    year: 2026,
    hero_deck:
      'Three pieces this week — why we name our agents, how the Builder/Trace separation behaves under load, and the dispatch from week 17.',
  }
}];

// Minimal $() shim — only the `Init Week` lookup is referenced by the JS.
function $(name) {
  if (name === 'Init Week') {
    return { first: () => ({ json: { test_mode: true, week_label: 'Semaine du 20 avril' } }) };
  }
  throw new Error(`unexpected $('${name}') in smoke test`);
}

// The node JS ends with `return [...]` outside a function — wrap it.
const wrapped = `(function(items, $) {\n${code}\n})`;
let result;
try {
  result = eval(wrapped)(items, $);
} catch (e) {
  console.error('FAIL: gen_html JS threw:', e.stack || e.message);
  process.exit(1);
}

const out = result[0].json;

const checks = [
  ['html is a non-empty string', typeof out.html === 'string' && out.html.length > 1000],
  ['archive_html is a non-empty string', typeof out.archive_html === 'string' && out.archive_html.length > 1000],
  ['subject mentions Week 17', /№ Week 17/.test(out.subject)],
  ['archive_slug = week-17-2026', out.archive_slug === 'week-17-2026'],
  ['archive_url points to /journal/archive/', out.archive_url === 'https://digital-humans.fr/journal/archive/week-17-2026'],
  ['week_number=17', out.week_number === 17],
  ['year=2026', out.year === 2026],
  ['html contains __UNSUBSCRIBE_URL__ token', out.html.includes('__UNSUBSCRIBE_URL__')],
  ['archive_html does NOT contain __UNSUBSCRIBE_URL__', !out.archive_html.includes('__UNSUBSCRIBE_URL__')],
  ['archive_html resolves placeholder to studio URL', out.archive_html.includes('https://digital-humans.fr/journal/unsubscribe')],
  ['html shows MANIFESTO label (brass)', out.html.includes('MANIFESTO') && out.html.includes('#C8A97E')],
  ['html shows CRAFT NOTES label (mauve)', out.html.includes('CRAFT NOTES') && out.html.includes('#8E6B8E')],
  ['html shows DISPATCHES label (sage)', out.html.includes('DISPATCHES') && out.html.includes('#7A9B76')],
  ['rendered exactly 3 article blocks (4th truncated)', out.rendered_articles === 3 && out.total_articles === 4],
  ['"+ 1 more this week" present', out.html.includes('+ 1 more this week')],
  ['"View on web" footer link uses archive URL', out.html.includes(out.archive_url)],
  ['MSO conditionals preserved (4 expected)', (out.html.match(/<!--\[if/g) || []).length >= 4],
  ['Logo bicolore brass/bone present', out.html.includes('#8C6E4A') && out.html.includes('Digital') && out.html.includes('Humans')],
  ['no unresolved {{ }} mustache token in archive', !/\{\{[a-zA-Z_]+\}\}/.test(out.archive_html)],
  ['preheader has hero_deck', out.html.includes('Three pieces this week')],
];

let pass = 0;
let fail = 0;
for (const [name, ok] of checks) {
  console.log(`  ${ok ? '✓' : '✗'}  ${name}`);
  if (ok) pass++; else fail++;
}
console.log(`\n${pass} passed · ${fail} failed`);
console.log(`\nhtml size:         ${out.html.length} chars`);
console.log(`archive_html size: ${out.archive_html.length} chars`);
console.log(`subject:           ${out.subject}`);
process.exit(fail === 0 ? 0 : 1);
