/**
 * Consentement Opus — GL-22 (vague 2, file C).
 *
 * Le site promet « Opus on opt-in, cost shown before each call ». Avant un
 * lancement où Marcus serait servi par Opus, le backend exige une décision :
 *
 *   - `GET  /api/pm-orchestrator/execute/opus-estimate` rend l'estimation ;
 *   - `POST /api/pm-orchestrator/execute` sans décision → 409
 *     `consentement_opus_requis` ; avec un montant qui n'est plus celui
 *     affiché → 409 `consentement_opus_montant_perime`.
 *
 * Ce module lit ces refus, construit le corps du lancement et porte le texte
 * de l'écran (`OPUS_CONSENT_TEXT_VERSION`, tracée par le backend avec la
 * décision). Testé par `frontend/tests/opusConsent.test.ts`.
 */
import { ApiError } from './apiContracts.ts';

/** Doit rester égale à `TEXTE_VERSION` de `consentement_opus_service.py`. */
export const OPUS_CONSENT_TEXT_VERSION = 'gl22-v1-20261024';

export interface OpusEstimate {
  requis: boolean;
  modele: string | null;
  modele_repli: string | null;
  credits_par_appel: number;
  credits_repli_par_appel: number;
  appels_max: number;
  credits_estimes: number;
  credits_repli_estimes: number;
  texte_version: string;
  raison: string;
}

export type OpusDecision = 'accepte' | 'refuse';

export interface OpusChoice {
  decision: OpusDecision;
  estimation: OpusEstimate;
}

export interface OpusConsentRequest {
  motif: 'requis' | 'montant_perime';
  estimation: OpusEstimate;
}

const MOTIFS: Record<string, OpusConsentRequest['motif']> = {
  consentement_opus_requis: 'requis',
  consentement_opus_montant_perime: 'montant_perime',
};

/** Le refus du lancement demande-t-il l'écran de consentement ? */
export function readOpusConsentRequest(err: unknown): OpusConsentRequest | null {
  if (!(err instanceof ApiError) || err.status !== 409) return null;
  const payload = err.payload as { detail?: Record<string, unknown> } | undefined;
  const detail = payload?.detail;
  if (!detail || typeof detail !== 'object') return null;
  const motif = MOTIFS[String(detail.code ?? detail.error ?? '')];
  const estimation = detail.estimation as OpusEstimate | undefined;
  if (!motif || !estimation || typeof estimation.credits_estimes !== 'number') return null;
  return { motif, estimation };
}

/** Corps de `POST /execute`. Accepter envoie le montant affiché. */
export function buildStartBody(
  projectId: number,
  selectedAgents: string[],
  choice?: OpusChoice,
): Record<string, unknown> {
  const body: Record<string, unknown> = { project_id: projectId, selected_agents: selectedAgents };
  if (!choice) return body;
  body.consentement_opus = choice.decision;
  // Reprise R3 : la version du texte affiché part avec la décision ; le
  // serveur la vérifie (409 consentement_opus_texte_perime) et la trace.
  body.texte_version_opus = OPUS_CONSENT_TEXT_VERSION;
  if (choice.decision === 'accepte') body.credits_opus_acceptes = choice.estimation.credits_estimes;
  return body;
}

function credits(n: number, lang: 'fr' | 'en'): string {
  return n.toLocaleString(lang === 'fr' ? 'fr-FR' : 'en-US');
}

/** Texte de l'écran. Toute modification change `OPUS_CONSENT_TEXT_VERSION`. */
export function opusConsentText(e: OpusEstimate, lang: 'fr' | 'en') {
  if (lang === 'fr') {
    return {
      title: 'Marcus avec Opus ?',
      body:
        `Marcus, l'architecte, rédige la conception de la solution. Sur votre abonnement, il peut ` +
        `être servi par Opus, notre modèle le plus avancé, au prix de ${credits(e.credits_estimes, 'fr')} crédits ` +
        `au plus pour cette exécution (${e.appels_max} appels au plus, ${credits(e.credits_par_appel, 'fr')} ` +
        `crédits chacun au plus). Ce montant est un plafond : s'il est atteint, la suite passe sur ` +
        `Sonnet et l'exécution l'indique. Votre accord ne vaut que pour cette exécution.`,
      accept: `Accepter Opus — ${credits(e.credits_estimes, 'fr')} crédits au plus`,
      refuse: 'Refuser — Marcus utilisera Sonnet',
      refuseNote: `Avec Sonnet : ${credits(e.credits_repli_estimes, 'fr')} crédits au plus. Le choix sera indiqué sur l'exécution.`,
      stale: 'L’estimation a changé depuis l’affichage : voici le nouveau montant.',
      cancel: 'Annuler',
    };
  }
  return {
    title: 'Marcus on Opus?',
    body:
      `Marcus, the architect, writes the solution design. On your plan he can run on Opus, our most ` +
      `capable model, for at most ${credits(e.credits_estimes, 'en')} credits for this run ` +
      `(at most ${e.appels_max} calls, at most ${credits(e.credits_par_appel, 'en')} credits each). ` +
      `This amount is a cap: once reached, the rest runs on Sonnet and the run says so. ` +
      `Your consent applies to this run only.`,
    accept: `Accept Opus — up to ${credits(e.credits_estimes, 'en')} credits`,
    refuse: 'Decline — Marcus will use Sonnet',
    refuseNote: `With Sonnet: up to ${credits(e.credits_repli_estimes, 'en')} credits. The choice is shown on the run.`,
    stale: 'The estimate changed since it was shown: here is the new amount.',
    cancel: 'Cancel',
  };
}

/**
 * Les replis annoncés sur l'exécution (`executions.degraded`, motif
 * `opus_repli_sonnet`) : refus au lancement, ou montant accepté atteint.
 * Rendus par `/execute/{id}/progress` ; la page de suivi les affiche.
 */
export function readOpusFallbackNotices(progress: unknown): string[] {
  if (!progress || typeof progress !== 'object') return [];
  const marques = (progress as { degraded?: unknown }).degraded;
  if (!Array.isArray(marques)) return [];
  return marques
    .filter((m) => m && typeof m === 'object' && (m as Record<string, unknown>).motif === 'opus_repli_sonnet')
    .map((m) => String((m as Record<string, unknown>).detail ?? ''))
    .filter(Boolean);
}
