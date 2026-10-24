/**
 * Écran de consentement Opus — GL-22 (vague 2, file C).
 *
 * Affiché avant tout lancement où Marcus serait servi par Opus : coût estimé
 * en crédits, portée (cette exécution), modèle de repli. Le texte vient de
 * `opusConsentText` ; sa version est tracée avec la décision côté serveur.
 * Refuser n'annule pas : l'exécution part avec Sonnet, et le dit.
 */
import { useLang } from '../contexts/LangContext';
import { opusConsentText, type OpusDecision, type OpusEstimate } from '../lib/opusConsent.ts';

interface Props {
  estimation: OpusEstimate;
  stale?: boolean;
  busy?: boolean;
  onDecide: (decision: OpusDecision) => void;
  onCancel: () => void;
}

export default function OpusConsentDialog({ estimation, stale, busy, onDecide, onCancel }: Props) {
  const { lang } = useLang();
  const texte = opusConsentText(estimation, lang);
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="opus-consent-title"
      data-testid="opus-consent-dialog"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/80 px-4"
    >
      <div className="max-w-lg w-full border border-brass/40 bg-ink-2 p-6">
        <h2 id="opus-consent-title" className="font-serif italic text-2xl text-bone">
          {texte.title}
        </h2>
        {stale && (
          <p className="mt-3 font-mono text-[11px] text-warning">{texte.stale}</p>
        )}
        <p className="mt-4 font-mono text-[12px] leading-relaxed text-bone-3">{texte.body}</p>
        <div className="mt-6 flex flex-col gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => onDecide('accepte')}
            className="px-5 py-3 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 disabled:opacity-50"
          >
            {texte.accept}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onDecide('refuse')}
            className="px-5 py-3 border border-bone/30 text-bone font-mono text-[11px] tracking-cta uppercase hover:border-bone/60 disabled:opacity-50"
          >
            {texte.refuse}
          </button>
          <p className="font-mono text-[10px] text-bone-4">{texte.refuseNote}</p>
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="self-start font-mono text-[10px] text-bone-4 underline hover:text-bone"
          >
            {texte.cancel}
          </button>
        </div>
      </div>
    </div>
  );
}
