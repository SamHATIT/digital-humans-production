/**
 * VAGUE 2 — LOT 3 : decodage SSE de `AgentTesterPage`.
 *
 * Le defaut : `decoder.decode(value)` sans `{ stream: true }` ni tampon entre
 * deux chunks. Un evenement coupe a la frontiere d'un chunk — cas normal, pas
 * exceptionnel : le decoupage vient de la pile TCP, pas du serveur — produit un
 * `JSON.parse` en echec, avale par un `catch { }`. La ligne de log disparait en
 * silence. Sur un flux de test d'agent, une ligne manquante peut faire conclure
 * qu'une etape n'a pas eu lieu.
 *
 * Lance sans aucune dependance :
 *   node --experimental-strip-types --test frontend/tests/
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { SseLineReader } from '../src/lib/sseStream.ts';

const encoder = new TextEncoder();

function collect(chunks: string[]): unknown[] {
  const reader = new SseLineReader();
  const out: unknown[] = [];
  for (const chunk of chunks) {
    for (const event of reader.push(encoder.encode(chunk))) {
      out.push(event);
    }
  }
  for (const event of reader.flush()) {
    out.push(event);
  }
  return out;
}

test('un evenement entier dans un seul chunk', () => {
  assert.deepEqual(collect(['data: {"message":"a"}\n\n']), [{ message: 'a' }]);
});

test('un evenement coupe entre deux chunks n est pas perdu', () => {
  // Le coeur du defaut : `JSON.parse('{"message":"bonj')` echouait, le catch
  // avalait, et la ligne disparaissait.
  const out = collect(['data: {"messa', 'ge":"bonjour"}\n\n']);
  assert.deepEqual(out, [{ message: 'bonjour' }]);
});

test('une coupure au milieu du prefixe data: n est pas perdue', () => {
  assert.deepEqual(collect(['da', 'ta: {"n":1}\n\n']), [{ n: 1 }]);
});

test('une coupure sur le retour a la ligne n est pas perdue', () => {
  assert.deepEqual(
    collect(['data: {"n":1}\n', '\ndata: {"n":2}\n\n']),
    [{ n: 1 }, { n: 2 }],
  );
});

test('plusieurs evenements dans un seul chunk', () => {
  assert.deepEqual(
    collect(['data: {"n":1}\n\ndata: {"n":2}\n\ndata: {"n":3}\n\n']),
    [{ n: 1 }, { n: 2 }, { n: 3 }],
  );
});

test('un caractere multi-octets coupe entre deux chunks est recompose', () => {
  // « é » = 0xC3 0xA9. Sans `{ stream: true }`, TextDecoder rend U+FFFD sur le
  // premier chunk et perd le caractere.
  const bytes = encoder.encode('data: {"message":"éxécution"}\n\n');
  const cut = 20;
  const reader = new SseLineReader();
  const out: unknown[] = [];
  for (const event of reader.push(bytes.slice(0, cut))) out.push(event);
  for (const event of reader.push(bytes.slice(cut))) out.push(event);
  assert.deepEqual(out, [{ message: 'éxécution' }]);
});

test('les lignes qui ne sont pas des donnees sont ignorees', () => {
  assert.deepEqual(
    collect([': keep-alive\n\nevent: ping\ndata: {"n":1}\n\n']),
    [{ n: 1 }],
  );
});

test('un JSON reellement invalide est signale, pas avale', () => {
  // Regle 5 : jamais de repli silencieux. Un evenement complet et illisible est
  // une anomalie du serveur — elle doit ressortir dans le flux, pas disparaitre.
  const reader = new SseLineReader();
  const out = [...reader.push(encoder.encode('data: {ceci nest pas du json}\n\n'))];
  assert.equal(out.length, 1);
  const event = out[0] as { type?: string; level?: string; message?: string };
  assert.equal(event.level, 'ERROR');
  assert.match(String(event.message), /illisible|invalide/i);
});

test('flush ne rend rien quand le tampon est vide', () => {
  const reader = new SseLineReader();
  reader.push(encoder.encode('data: {"n":1}\n\n'));
  assert.deepEqual([...reader.flush()], []);
});

test('flush rend le dernier evenement quand le flux se ferme sans ligne vide', () => {
  // Un serveur qui ferme la connexion juste apres le dernier `data:` sans
  // envoyer le `\n\n` final : l'evenement est complet, il doit sortir.
  assert.deepEqual(collect(['data: {"n":9}']), [{ n: 9 }]);
});
