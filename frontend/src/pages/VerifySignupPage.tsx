import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle2, AlertTriangle, Loader2, ArrowRight } from 'lucide-react';
import { auth } from '../services/api';
import { LangProvider, useLang } from '../contexts/LangContext';
import LangToggle from '../components/layout/LangToggle';

/**
 * VerifySignupPage — public route /verify-signup
 *
 * ONBOARDING-002 — second step of the verify-then-create flow.
 * Reads ?token= from the URL, calls POST /api/auth/signup-confirm.
 * Three outcomes:
 *  - Success → store the access token, set the WelcomeBanner flag, redirect to /
 *  - Token invalid/expired → friendly error + CTA back to /signup
 *  - Network error → retry button
 */
type Status = 'verifying' | 'success' | 'error';

function VerifyInner() {
  const { t } = useLang();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';

  const [status, setStatus] = useState<Status>('verifying');
  const [errorKind, setErrorKind] = useState<'expired' | 'invalid' | 'network' | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setErrorKind('invalid');
      return;
    }

    let cancelled = false;
    const verify = async () => {
      try {
        const resp = await auth.signupConfirm(token);
        if (cancelled) return;

        // Store the access token like the standard /login flow does.
        if (resp?.access_token) {
          localStorage.setItem('access_token', resp.access_token);
        }

        // Pull the tier set on the previous page (sessionStorage) so the
        // WelcomeBanner shows the right copy. Defaults to 'free' if absent.
        const pendingTier = sessionStorage.getItem('onboarding:pendingTier') || 'free';
        sessionStorage.setItem('onboarding:justSignedUp', pendingTier);
        sessionStorage.removeItem('onboarding:pendingTier');

        setStatus('success');
        // Small delay so the user reads the success message.
        setTimeout(() => navigate('/'), 1500);
      } catch (err) {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message.toLowerCase() : '';
        if (msg.includes('invalid_or_expired_token') || msg.includes('400')) {
          setErrorKind('expired');
        } else if (msg.includes('network') || msg.includes('fetch')) {
          setErrorKind('network');
        } else {
          setErrorKind('invalid');
        }
        setStatus('error');
      }
    };

    verify();
    return () => {
      cancelled = true;
    };
  }, [token, navigate]);

  return (
    <div className="min-h-screen flex flex-col bg-ink text-bone">
      <div className="flex justify-end px-6 lg:px-12 py-6">
        <LangToggle />
      </div>

      <main className="flex-1 flex items-center justify-center px-6 pb-12">
        <div className="w-full max-w-[440px] bg-ink-2 border border-bone/5 px-8 py-12 text-center">
          {status === 'verifying' && (
            <>
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-brass/10 border border-brass/30 mb-6">
                <Loader2 className="w-6 h-6 text-brass animate-spin" aria-hidden />
              </div>
              <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
                {t('Verifying', 'Vérification')}
              </p>
              <h1 className="mt-3 font-serif italic text-3xl text-bone leading-tight">
                {t('One moment.', 'Un instant.')}
              </h1>
              <p className="mt-5 font-mono text-[11px] leading-relaxed text-bone-3">
                {t(
                  'Confirming your email and opening your studio…',
                  'Confirmation de votre e-mail et ouverture du studio…',
                )}
              </p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-success/10 border border-success/40 mb-6">
                <CheckCircle2 className="w-6 h-6 text-success" aria-hidden />
              </div>
              <p className="font-mono text-[11px] tracking-eyebrow uppercase text-success">
                {t('Verified', 'Confirmé')}
              </p>
              <h1 className="mt-3 font-serif italic text-3xl text-bone leading-tight">
                {t('Welcome to the studio.', 'Bienvenue dans le studio.')}
              </h1>
              <p className="mt-5 font-mono text-[11px] leading-relaxed text-bone-3">
                {t('Redirecting you in a second…', 'Redirection en cours…')}
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-error/10 border border-error/40 mb-6">
                <AlertTriangle className="w-6 h-6 text-error" aria-hidden />
              </div>
              <p className="font-mono text-[11px] tracking-eyebrow uppercase text-error">
                {errorKind === 'expired'
                  ? t('Link expired', 'Lien expiré')
                  : errorKind === 'network'
                  ? t('Connection issue', 'Problème de connexion')
                  : t('Invalid link', 'Lien invalide')}
              </p>
              <h1 className="mt-3 font-serif italic text-3xl text-bone leading-tight">
                {errorKind === 'expired'
                  ? t('Your link has expired.', 'Votre lien a expiré.')
                  : errorKind === 'network'
                  ? t('We could not reach the studio.', 'Le studio est injoignable.')
                  : t('That link did not check out.', 'Ce lien n\u2019est pas valide.')}
              </h1>
              <p className="mt-5 font-mono text-[11px] leading-relaxed text-bone-3">
                {errorKind === 'expired'
                  ? t(
                      'The verification link is valid for 30 minutes only. Sign up again — it takes 30 seconds.',
                      'Le lien de confirmation est valable 30 minutes. Recommencez l\u2019inscription — c\u2019est l\u2019affaire de 30 secondes.',
                    )
                  : errorKind === 'network'
                  ? t('Try again in a moment.', 'Réessayez dans un instant.')
                  : t(
                      'Make sure the link in the email is intact. If in doubt, sign up again.',
                      'Vérifiez que le lien de l\u2019e-mail est intact. Dans le doute, recommencez.',
                    )}
              </p>

              <div className="mt-8 flex flex-col items-center gap-3">
                <Link
                  to="/signup"
                  className="inline-flex items-center gap-2 px-5 py-2.5 bg-brass text-ink font-mono text-[11px] tracking-cta uppercase hover:bg-brass-2 transition-colors"
                >
                  {t('Start over', 'Recommencer')}
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <Link
                  to="/login"
                  className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 hover:text-brass transition-colors"
                >
                  {t('Or sign in if you already have an account', 'Ou connectez-vous si vous avez déjà un compte')}
                </Link>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

export default function VerifySignupPage() {
  return (
    <LangProvider>
      <VerifyInner />
    </LangProvider>
  );
}
