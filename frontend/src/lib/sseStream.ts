/**
 * Decodage d'un flux SSE lu via `ReadableStream.getReader()`.
 *
 * VAGUE 2 / LOT 3 — audit croise du 21/08/2026.
 *
 * Le code d'origine, dans `AgentTesterPage`, faisait :
 *
 *     const text = decoder.decode(value);
 *     for (const line of text.split('\n')) {
 *       if (line.startsWith('data: ')) {
 *         try { setLogs(prev => [...prev, JSON.parse(line.slice(6))]); }
 *         catch { }
 *       }
 *     }
 *
 * Deux defauts, une consequence.
 *
 *  1. `decoder.decode(value)` sans `{ stream: true }`. Le decoupage en chunks
 *     vient de la pile TCP, pas du serveur : un caractere multi-octets coupe en
 *     deux devient U+FFFD et le caractere est perdu.
 *  2. Aucun tampon entre deux chunks. Un evenement coupe a la frontiere — cas
 *     normal des que le flux depasse la taille d'un chunk — arrive en deux
 *     morceaux dont aucun n'est du JSON valide.
 *
 * Dans les deux cas, `JSON.parse` echoue et le `catch { }` avale. **La ligne de
 * log disparait en silence.** Sur un flux de test d'agent, une ligne manquante
 * peut faire conclure qu'une etape n'a pas eu lieu.
 *
 * Cette classe tient le tampon et decode en mode flux. Elle ne depend de rien
 * et se teste seule (`frontend/tests/sseStream.test.ts`).
 */

/** Evenement synthetique emis quand un evenement complet est illisible. */
export interface SseDecodeError {
  type: 'error';
  level: 'ERROR';
  message: string;
}

export class SseLineReader {
  private readonly decoder = new TextDecoder();
  private buffer = '';

  /**
   * Consomme un chunk et rend les evenements complets qu'il termine.
   *
   * Ce qui reste apres le dernier separateur est garde en tampon pour le
   * prochain appel — c'est tout l'objet de la classe.
   */
  push(chunk: Uint8Array): unknown[] {
    // `{ stream: true }` : le decodeur garde en interne les octets d'un
    // caractere multi-octets coupe entre deux chunks.
    this.buffer += this.decoder.decode(chunk, { stream: true });

    const events: unknown[] = [];
    // Un evenement SSE se termine par une ligne vide. `\r\n` est tolere : la
    // specification l'autorise et certains proxys le produisent.
    const parts = this.buffer.split(/\r?\n\r?\n/);
    // Le dernier fragment est incomplet par construction : il retourne au tampon.
    this.buffer = parts.pop() ?? '';

    for (const part of parts) {
      const event = this.parseEvent(part);
      if (event !== undefined) events.push(event);
    }
    return events;
  }

  /**
   * A appeler quand le flux se ferme : rend l'evenement encore en tampon.
   *
   * Un serveur qui ferme la connexion juste apres le dernier `data:`, sans
   * envoyer la ligne vide finale, a bien envoye un evenement complet. Le jeter
   * serait le meme repli silencieux, une ligne plus loin.
   */
  flush(): unknown[] {
    // Vider le decodeur : un caractere multi-octets tronque en fin de flux
    // devient U+FFFD ici plutot que de disparaitre.
    this.buffer += this.decoder.decode();
    const rest = this.buffer;
    this.buffer = '';
    if (!rest.trim()) return [];
    const event = this.parseEvent(rest);
    return event === undefined ? [] : [event];
  }

  /**
   * Rend l'objet porte par un bloc d'evenement, `undefined` si le bloc ne
   * porte aucune ligne `data:` (commentaire `:`, `event:` seul, keep-alive).
   */
  private parseEvent(block: string): unknown | undefined {
    const payloads: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('data:')) {
        // La specification autorise `data:x` comme `data: x`.
        payloads.push(line.slice(5).replace(/^ /, ''));
      }
    }
    if (payloads.length === 0) return undefined;

    const raw = payloads.join('\n');
    if (!raw.trim()) return undefined;

    try {
      return JSON.parse(raw);
    } catch {
      // Regle 5 : jamais de repli silencieux. Un evenement complet et illisible
      // est une anomalie du serveur — elle ressort dans le flux au lieu d'etre
      // avalee. C'est ce que l'ancien `catch { }` faisait disparaitre.
      const error: SseDecodeError = {
        type: 'error',
        level: 'ERROR',
        message: `Evenement SSE illisible (JSON invalide) : ${raw.slice(0, 200)}`,
      };
      return error;
    }
  }
}
