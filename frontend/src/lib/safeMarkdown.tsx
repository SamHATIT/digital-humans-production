/**
 * Rendu markdown inline SANS injection HTML (LOT-F — cla:SEC-02, ope:SEC-01/02/03).
 *
 * Les composants qui affichent du contenu produit par les agents (chat HITL,
 * preview SDS) formataient auparavant le markdown en concaténant une chaîne
 * HTML injectée via `dangerouslySetInnerHTML`. Les expressions régulières ne
 * traitaient que `` ` ``, `**` et `*` : tout le reste du texte — donc
 * `<img src=x onerror=...>` — arrivait intact dans le DOM et s'exécutait.
 *
 * Ici on ne produit plus de HTML du tout : on retourne des noeuds React.
 * React échappe automatiquement toute chaîne rendue comme enfant, donc le
 * balisage éventuellement présent dans le texte de l'agent est affiché
 * littéralement au lieu d'être interprété. Aucune dépendance de sanitisation
 * n'est nécessaire (pas de DOMPurify) : il n'y a plus de HTML à assainir.
 */
import type { ReactNode } from 'react';

/** Classes Tailwind appliquées à chaque type de fragment. */
export interface InlineMarkdownClasses {
  code?: string;
  strong?: string;
  em?: string;
  link?: string;
}

export interface InlineMarkdownOptions {
  /** Autoriser la syntaxe `[texte](url)`. Désactivé par défaut. */
  links?: boolean;
}

/**
 * Schémas d'URL autorisés pour les liens. Bloque notamment `javascript:`,
 * `data:` et `vbscript:` — l'ancien `inlineFormat` de SDSPreview interpolait
 * l'URL telle quelle dans un attribut `href`.
 */
const SAFE_URL_SCHEME = /^(https?:\/\/|mailto:)/i;

/**
 * Un seul passage, alternance ordonnée :
 *   1. code inline  `...`
 *   2. lien         [texte](url)
 *   3. gras         **...**
 *   4. italique     *...*
 */
const INLINE_TOKEN =
  /`([^`]+)`|\[([^\]\n]+)\]\(([^)\s]+)\)|\*\*([^*\n]+)\*\*|\*([^*\n]+)\*/;

export function renderInlineMarkdown(
  text: string,
  classes: InlineMarkdownClasses = {},
  options: InlineMarkdownOptions = {},
): ReactNode[] {
  const nodes: ReactNode[] = [];
  let rest = text ?? '';
  let key = 0;

  while (rest.length > 0) {
    const match = INLINE_TOKEN.exec(rest);
    if (!match) {
      nodes.push(rest);
      break;
    }

    if (match.index > 0) nodes.push(rest.slice(0, match.index));

    const [full, code, linkText, linkHref, bold, italic] = match;

    if (code !== undefined) {
      nodes.push(
        <code key={key++} className={classes.code}>
          {code}
        </code>,
      );
    } else if (linkText !== undefined) {
      if (options.links && SAFE_URL_SCHEME.test(linkHref)) {
        nodes.push(
          <a
            key={key++}
            href={linkHref}
            className={classes.link}
            target="_blank"
            rel="noopener noreferrer"
          >
            {linkText}
          </a>,
        );
      } else {
        // Lien non autorisé (ou liens désactivés) : rendu en texte inerte.
        nodes.push(full);
      }
    } else if (bold !== undefined) {
      nodes.push(
        <strong key={key++} className={classes.strong}>
          {bold}
        </strong>,
      );
    } else {
      nodes.push(
        <em key={key++} className={classes.em}>
          {italic}
        </em>,
      );
    }

    rest = rest.slice(match.index + full.length);
  }

  return nodes;
}
