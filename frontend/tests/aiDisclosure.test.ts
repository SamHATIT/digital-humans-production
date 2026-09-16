/**
 * VAGUE 1 / file D — GL-19 : mention IA dans les fenetres de dialogue du Studio.
 *
 * AI Act article 50, en vigueur depuis le 02/08/2026 : l'utilisateur doit
 * savoir qu'il s'adresse a une machine, au premier contact. Mesure du 16/09
 * sur `f78e8ad` : `grep -rn "IA\b|intelligence artificielle|AI-generated"
 * frontend/src` ne rendait aucune ligne — les trois fenetres de dialogue du
 * Studio (`ChatSidebarStudio`, `ChatSidebar`, onglet chat de
 * `ProjectDetailPage`) ouvraient sur un champ de saisie sans rien annoncer.
 *
 * Le texte vit ici, dans un module pur, pour une raison mesuree : la mention
 * du pied de livrable avait deja trois copies divergentes cote backend. Un
 * seul endroit, trois consommateurs.
 *
 * Lance sans aucune dependance :
 *   node --experimental-strip-types --test frontend/tests/aiDisclosure.test.ts
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  AI_CHAT_DISCLOSURE,
  AI_DELIVERABLE_DISCLOSURE,
  aiChatDisclosure,
  aiDeliverableDisclosure,
} from '../src/lib/aiDisclosure.ts';

test('la mention de dialogue existe en francais et en anglais', () => {
  assert.deepEqual(Object.keys(AI_CHAT_DISCLOSURE).sort(), ['en', 'fr']);
  assert.notEqual(aiChatDisclosure('fr'), aiChatDisclosure('en'));
});

test("la mention de dialogue dit qu'on s'adresse a une IA", () => {
  assert.match(aiChatDisclosure('fr').toLowerCase(), /intelligence artificielle/);
  assert.match(aiChatDisclosure('en').toLowerCase(), /artificial intelligence/);
});

test('la mention de livrable nomme le contenu genere par IA', () => {
  assert.match(aiDeliverableDisclosure('fr').toLowerCase(), /intelligence artificielle/);
  assert.match(aiDeliverableDisclosure('en').toLowerCase(), /artificial intelligence/);
  assert.deepEqual(Object.keys(AI_DELIVERABLE_DISCLOSURE).sort(), ['en', 'fr']);
});

test('les deux mentions sont distinctes', () => {
  // « vous echangez avec une IA » et « ce contenu est genere par une IA » ne
  // disent pas la meme chose ; l'article 50 demande les deux, a deux endroits.
  assert.notEqual(aiChatDisclosure('fr'), aiDeliverableDisclosure('fr'));
});

test('une langue inconnue ne rend jamais une mention vide', () => {
  // Regle 6 : pas de repli silencieux. Un code de langue inattendu doit
  // afficher la mention francaise, pas la faire disparaitre.
  for (const valeur of ['zz', '', undefined, null, 42]) {
    assert.equal(aiChatDisclosure(valeur as never), aiChatDisclosure('fr'));
    assert.equal(aiDeliverableDisclosure(valeur as never), aiDeliverableDisclosure('fr'));
  }
});

test('la mention de dialogue reste courte assez pour tenir dans un bandeau', () => {
  // Controle de forme : au-dela, le bandeau devient un paragraphe que
  // personne ne lit — la mention serait presente sans etre portee a
  // connaissance, ce que l'article 50 n'accepte pas.
  for (const langue of ['fr', 'en'] as const) {
    assert.ok(
      aiChatDisclosure(langue).length <= 160,
      `mention ${langue} trop longue : ${aiChatDisclosure(langue).length}`,
    );
  }
});
