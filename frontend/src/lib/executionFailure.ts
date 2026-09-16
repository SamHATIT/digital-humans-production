/**
 * Motif d'echec d'une execution — BILL-11.
 *
 * Constat d'Astra L807 : « le refus de credits reste invisible dans le
 * parcours reellement utilise ». Mesure du 16/09 : la route
 * `GET /api/pm-orchestrator/execute/{id}/progress` sert bien un champ
 * `failure_reason` — cable par le lot B1-bis, avec son test
 * (`test_vague_b_b1_credits.py::test_la_route_de_progression_rend_le_motif_du_refus`)
 * — mais `useExecutionStream` ne le lit pas et la page d'execution propose
 * toujours « Rejouer l'acte ». Un client sans credits rejoue donc une action
 * impossible, sans jamais lire pourquoi.
 *
 * Le backend rend `failure_reason: null` tant que la cause n'est pas reconnue,
 * volontairement (regle 6 : mieux vaut ne rien dire qu'une cause devinee). Ce
 * module respecte ce contrat : il ne comble jamais.
 */

/** Code stable servi par `_helpers.motif_echec_execution`. */
export const CODE_CREDITS_INSUFFISANTS = 'insufficient_credits';

export interface FailureReason {
  code: string;
  message: string;
}

interface ProgressLike {
  status?: string;
  failure_reason?: unknown;
}

/** Le motif servi par `/progress`, ou `null` si le backend n'en donne pas. */
export function readFailureReason(progress: unknown): FailureReason | null {
  if (!progress || typeof progress !== 'object') return null;
  const brut = (progress as ProgressLike).failure_reason;
  if (!brut || typeof brut !== 'object') return null;

  const r = brut as Record<string, unknown>;
  const code = typeof r.code === 'string' ? r.code : '';
  const message = typeof r.message === 'string' ? r.message : '';
  if (!code && !message) return null;
  return { code, message };
}

/**
 * Faut-il proposer de rejouer l'execution ?
 *
 * Non sur un refus de credits : l'action est impossible tant que le solde n'a
 * pas change, et la reproposer fait perdre du temps au client sans rien lui
 * apprendre. Oui sur les autres echecs — un timeout ou une panne de
 * fournisseur se rattrapent, et masquer le bouton dans ces cas casserait le
 * rattrapage (c'est le controle negatif du test).
 */
export function canRetryExecution(progress: unknown): boolean {
  if (!progress || typeof progress !== 'object') return false;
  const statut = String((progress as ProgressLike).status ?? '').toLowerCase();
  if (statut !== 'failed' && statut !== 'cancelled') return false;

  const motif = readFailureReason(progress);
  return motif?.code !== CODE_CREDITS_INSUFFISANTS;
}

/**
 * L'action utile a proposer face a un motif d'echec.
 *
 * `null` quand il n'y a rien de mieux a offrir que de rejouer : on ne fabrique
 * pas un bouton qui ne menerait nulle part.
 */
export function failureAction(
  motif: FailureReason | null,
): { label: { en: string; fr: string }; href: string } | null {
  if (motif?.code === CODE_CREDITS_INSUFFISANTS) {
    return {
      label: { en: 'See plans', fr: 'Voir les offres' },
      href: '/pricing',
    };
  }
  return null;
}
