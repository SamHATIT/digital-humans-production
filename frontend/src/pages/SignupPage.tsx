import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Loader2, ArrowRight, MailCheck } from 'lucide-react';
import { auth } from '../services/api';
import { LangProvider, useLang } from '../contexts/LangContext';
import LangToggle from '../components/layout/LangToggle';

/**
 * SignupPage — public route /signup
 *
 * Free-tier signup. Mirrors LoginPage layout (cover left, form right) so the
 * arrival ↔ login crossfade is visually seamless.
 *
 * Workflow: validate client-side → POST /api/auth/register → POST /api/auth/login
 * (the register endpoint returns the user but no token) → navigate('/').
 *
 * Free tier is created by default server-side; a Stripe customer is also created
 * best-effort so the user can upgrade in one click later.
 */
// Tier metadata used by the hero left column to show the user what they
// just chose on /pricing. Only `free` is self-serve for now (ONBOARDING-001).
const TIER_META: Record<string, { label: string; tagline: { en: string; fr: string } }> = {
  free: {
    label: 'Free',
    tagline: {
      en: 'Sophie and Olivia, on the house. Up to 1 project, SDS only.',
      fr: 'Sophie et Olivia, gracieusement. 1 projet, SDS uniquement.',
    },
  },
};

function SignupInner() {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const navigate = useNavigate();
  const { t, lang } = useLang();
  const [searchParams] = useSearchParams();

  // ONBOARDING-002 — when the verify-email is sent, swap the right column
  // for a "check your inbox" view. The form data stays available so we can
  // offer a "resend" button without forcing the user to re-type.
  const [mailSent, setMailSent] = useState(false);

  // ONBOARDING-001 — tier coming from /pricing (?tier=free). Anything else
  // is silently coerced to free; the backend validates again.
  const requestedTier = (() => {
    const raw = searchParams.get('tier');
    return raw && raw in TIER_META ? raw : 'free';
  })();
  const tierMeta = TIER_META[requestedTier];

  // ONBOARDING-003 — industry intent coming from a marketing CTA
  // (e.g. /signup?tier=free&intent=pharma). Whitelisted to known industries
  // so a malicious value can't slip through to /projects/new.
  const KNOWN_INTENTS = new Set([
    'logistics', 'pharma', 'healthcare', 'telecom',
    'b2b', 'energy', 'retail', 'agentforce',
  ]);
  const requestedIntent = (() => {
    const raw = searchParams.get('intent');
    return raw && KNOWN_INTENTS.has(raw) ? raw : null;
  })();

  const [name, setName]                       = useState('');
  const [email, setEmail]                     = useState('');
  const [password, setPassword]               = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [acceptedTerms, setAcceptedTerms]     = useState(false);
  const [isLoading, setIsLoading]             = useState(false);
  const [error, setError]                     = useState('');

  // ----- Client-side validation (visual feedback only) -----
  const passwordTooShort   = password.length > 0 && password.length < 8;
  const passwordsMismatch  = confirmPassword.length > 0 && password !== confirmPassword;
  const passwordsMatch     = confirmPassword.length >= 8 && password === confirmPassword;
  const emailInvalid       = email.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const formValid =
    name.trim().length > 0 &&
    email.length > 0 && !emailInvalid &&
    password.length >= 8 &&
    !passwordsMismatch &&
    acceptedTerms;

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');

    if (!formValid) {
      setError(t(
        'Please fill all fields correctly and accept the terms.',
        'Veuillez remplir tous les champs correctement et accepter les conditions.',
      ));
      return;
    }

    setIsLoading(true);
    try {
      // ONBOARDING-002: verify-then-create. We send the email; no DB row
      // until the user clicks the link. Backend returns 202 with a generic
      // message in ALL cases (incl. email-already-used) for anti-enumeration.
      // We pre-store the tier flag so the future /verify-signup can pass it
      // to the WelcomeBanner once the account is materialised.
      sessionStorage.setItem('onboarding:pendingTier', requestedTier);
      if (requestedIntent) {
        sessionStorage.setItem('onboarding:pendingIntent', requestedIntent);
      }
      await auth.signupRequest(email.trim(), name.trim(), password, requestedTier, lang);
      setMailSent(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '';
      const lower = msg.toLowerCase();
      if (lower.includes('rate limit') || lower.includes('too many')) {
        setError(t(
          'Too many signup attempts. Please wait a moment and try again.',
          'Trop de tentatives. Patientez quelques instants avant de réessayer.',
        ));
      } else {
        setError(msg || t(
          'Signup failed. Please try again.',
          'Échec de la création du compte. Veuillez réessayer.',
        ));
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Resend: same payload, same endpoint. Rate limited server-side.
  const handleResend = async () => {
    setError('');
    setIsLoading(true);
    try {
      await auth.signupRequest(email.trim(), name.trim(), password, requestedTier, lang);
    } catch {
      // Silent — anti-enumeration. The user already has the original mail (or not).
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-2 bg-ink text-bone">
      {/* Left — Studio cover */}
      <aside className="relative hidden lg:flex flex-col justify-between p-12 overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: "url('/covers/manifesto-eleven-agents.jpg')" }}
          aria-hidden
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(160deg, rgba(10,10,11,0.55) 0%, rgba(10,10,11,0.92) 60%, var(--ink) 100%)',
          }}
          aria-hidden
        />

        <div className="relative">
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
            {t('№ 01 · Welcome', '№ 01 · Bienvenue')}
          </p>
          <p className="mt-3 font-serif italic text-3xl text-bone leading-tight max-w-md">
            Digital · Humans
          </p>

          {/* Tier badge — what the user just chose on /pricing */}
          <div className="mt-8 inline-flex items-center gap-3 border border-brass/30 bg-brass/5 px-4 py-2.5">
            <span className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
              {t('Starting tier', 'Tier de départ')}
            </span>
            <span className="font-serif italic text-base text-brass">
              {tierMeta.label}
            </span>
          </div>
          <p className="mt-3 font-mono text-[11px] leading-relaxed text-bone-3 max-w-sm">
            {t(tierMeta.tagline.en, tierMeta.tagline.fr)}
          </p>
        </div>

        <div className="relative max-w-md">
          <p className="font-serif italic text-2xl text-bone-2 leading-snug">
            {t(
              '"Cast a project, brief them, and watch the studio at work."',
              '"Confiez un projet, briefez les onze agents, et regardez le studio jouer."',
            )}
          </p>
          <p className="mt-4 font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
            Autonomous Studio · Est MMXXV
          </p>
        </div>
      </aside>

      {/* Right — Form */}
      <section className="relative flex flex-col">
        <div className="flex justify-end px-6 lg:px-12 py-6">
          <LangToggle />
        </div>

        <div className="flex-1 flex items-center justify-center px-6 lg:px-12 pb-12">
          <div className="w-full max-w-[440px] bg-ink-2 border border-bone/5 px-8 py-10">
            {mailSent ? (
              /* ONBOARDING-002 — "check your inbox" view */
              <div className="text-center">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-brass/10 border border-brass/30 mb-6">
                  <MailCheck className="w-6 h-6 text-brass" aria-hidden />
                </div>
                <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
                  {t('Check your inbox', 'Consultez vos e-mails')}
                </p>
                <h1 className="mt-3 font-serif italic text-3xl text-bone leading-tight">
                  {t('One last step.', 'Un dernier pas.')}
                </h1>
                <p className="mt-5 font-mono text-[12px] leading-relaxed text-bone-2">
                  {t(
                    'We just sent a confirmation link to',
                    'Nous venons d\'envoyer un lien de confirmation à',
                  )}
                </p>
                <p className="mt-1 font-mono text-[13px] text-brass break-all">{email}</p>
                <p className="mt-5 font-mono text-[11px] leading-relaxed text-bone-3">
                  {t(
                    'Open it to finish creating your account. The link is valid for 30 minutes.',
                    'Ouvrez-le pour finaliser la création de votre compte. Le lien est valable 30 minutes.',
                  )}
                </p>
                {error && (
                  <div role="alert" className="mt-5 flex items-start gap-3 bg-ink-3 border border-error/40 px-4 py-3 text-left">
                    <AlertTriangle className="w-4 h-4 text-error mt-[2px] shrink-0" />
                    <p className="font-mono text-[11px] tracking-[0.04em] uppercase text-bone-2 leading-relaxed">{error}</p>
                  </div>
                )}
                {/* UI-005 — proéminent: l'API ne dit pas "déjà inscrit" (anti-enumeration),
                    mais l'UX doit signaler la possibilité au user qui sait. */}
                <div className="mt-8 pt-6 border-t border-bone/10">
                  <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-3">
                    {t('Already have an account?', 'Vous avez déjà un compte ?')}
                  </p>
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-2 px-4 py-2 border border-brass/40 hover:border-brass hover:bg-brass/5 font-mono text-[11px] tracking-cta uppercase text-brass transition-colors"
                  >
                    {t('Sign in instead', 'Se connecter plutôt')}
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>

                <div className="mt-6 pt-6 border-t border-bone/10">
                  <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-4 mb-3">
                    {t('Didn\'t receive it?', 'Pas reçu ?')}
                  </p>
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={isLoading}
                    className="inline-flex items-center gap-2 px-4 py-2 border border-bone/15 hover:border-brass/40 font-mono text-[11px] tracking-cta uppercase text-bone-2 hover:text-bone transition-colors disabled:opacity-50"
                  >
                    {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : null}
                    {t('Resend the link', 'Renvoyer le lien')}
                  </button>
                  <p className="mt-4 font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
                    {t('Wrong address?', 'Mauvaise adresse ?')}{' '}
                    <button
                      type="button"
                      onClick={() => { setMailSent(false); setError(''); }}
                      className="text-brass hover:underline"
                    >
                      {t('Edit', 'Corriger')}
                    </button>
                  </p>
                </div>
              </div>
            ) : (
            <>
            <div className="mb-8">
              <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
                {t('Get started · Free tier', 'Démarrer · Offre gratuite')}
              </p>
              <h1 className="mt-3 font-serif italic text-3xl text-bone">
                {t('Open your studio', 'Ouvrez votre studio')}
              </h1>
              <p className="mt-2 font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
                {t(
                  'Chat with Sophie & Olivia · No credit card',
                  'Chat avec Sophie & Olivia · Sans carte',
                )}
              </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit} noValidate>
              {error && (
                <div
                  role="alert"
                  className="flex items-start gap-3 bg-ink-3 border border-error/40 px-4 py-3"
                >
                  <AlertTriangle className="w-4 h-4 text-error mt-[2px] shrink-0" />
                  <p className="font-mono text-[11px] tracking-[0.04em] uppercase text-bone-2 leading-relaxed">
                    {error}
                  </p>
                </div>
              )}

              {/* Name */}
              <div>
                <label
                  htmlFor="name"
                  className="block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2"
                >
                  {t('Your name', 'Votre nom')}
                </label>
                <input
                  id="name"
                  type="text"
                  autoComplete="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  className="w-full bg-ink-3 border border-bone/10 focus:border-brass focus:outline-none px-4 py-3 text-bone placeholder-bone-4 font-mono text-sm transition-colors"
                  placeholder="Sam Hatit"
                />
              </div>

              {/* Email */}
              <div>
                <label
                  htmlFor="email"
                  className="block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2"
                >
                  {t('Email', 'Adresse e-mail')}
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className={`w-full bg-ink-3 border focus:outline-none px-4 py-3 text-bone placeholder-bone-4 font-mono text-sm transition-colors ${
                    emailInvalid
                      ? 'border-error/60 focus:border-error'
                      : 'border-bone/10 focus:border-brass'
                  }`}
                  placeholder="you@studio.com"
                />
                {emailInvalid && (
                  <p className="mt-2 font-mono text-[10px] tracking-[0.04em] uppercase text-error">
                    {t('Email format invalid', 'Format d’adresse invalide')}
                  </p>
                )}
              </div>

              {/* Password */}
              <div>
                <label
                  htmlFor="password"
                  className="block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2"
                >
                  {t('Password', 'Mot de passe')}
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={8}
                  className={`w-full bg-ink-3 border focus:outline-none px-4 py-3 text-bone placeholder-bone-4 font-mono text-sm transition-colors ${
                    passwordTooShort
                      ? 'border-error/60 focus:border-error'
                      : 'border-bone/10 focus:border-brass'
                  }`}
                  placeholder={t('At least 8 characters', 'Au moins 8 caractères')}
                />
                {passwordTooShort && (
                  <p className="mt-2 font-mono text-[10px] tracking-[0.04em] uppercase text-error">
                    {t('8 characters minimum', 'Minimum 8 caractères')}
                  </p>
                )}
              </div>

              {/* Confirm Password */}
              <div>
                <label
                  htmlFor="confirm"
                  className="block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2"
                >
                  {t('Confirm password', 'Confirmation')}
                </label>
                <input
                  id="confirm"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className={`w-full bg-ink-3 border focus:outline-none px-4 py-3 text-bone placeholder-bone-4 font-mono text-sm transition-colors ${
                    passwordsMismatch
                      ? 'border-error/60 focus:border-error'
                      : 'border-bone/10 focus:border-brass'
                  }`}
                  placeholder="••••••••"
                />
                {passwordsMismatch && (
                  <p className="mt-2 font-mono text-[10px] tracking-[0.04em] uppercase text-error">
                    {t('Passwords don’t match', 'Mots de passe différents')}
                  </p>
                )}
                {passwordsMatch && (
                  <p className="mt-2 inline-flex items-center gap-1 font-mono text-[10px] tracking-[0.04em] uppercase text-success">
                    <CheckCircle2 className="w-3 h-3" />
                    {t('Passwords match', 'Identiques')}
                  </p>
                )}
              </div>

              {/* Terms */}
              <label className="flex gap-3 items-start cursor-pointer pt-1">
                <input
                  type="checkbox"
                  checked={acceptedTerms}
                  onChange={(e) => setAcceptedTerms(e.target.checked)}
                  className="mt-[3px] h-4 w-4 shrink-0 border-bone/20 bg-ink-3 text-brass focus:ring-1 focus:ring-brass focus:ring-offset-0 cursor-pointer"
                />
                <span className="font-mono text-[10px] tracking-[0.04em] uppercase text-bone-3 leading-relaxed">
                  {t('I accept the ', 'J’accepte les ')}
                  <a
                    href="https://digital-humans.fr/cgv"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-brass hover:text-brass-2 underline-offset-2 hover:underline"
                  >
                    {t('Terms of Sale', 'CGV')}
                  </a>
                  {t(' and the ', ' et la ')}
                  <a
                    href="https://digital-humans.fr/privacy"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-brass hover:text-brass-2 underline-offset-2 hover:underline"
                  >
                    {t('Privacy Policy', 'Politique de Confidentialité')}
                  </a>
                </span>
              </label>

              <button
                type="submit"
                disabled={isLoading || !formValid}
                className="w-full inline-flex items-center justify-center gap-2 bg-brass hover:bg-brass-2 disabled:bg-brass-3 disabled:cursor-not-allowed text-ink py-3 font-mono text-[12px] tracking-cta uppercase transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('Opening the studio…', 'Ouverture en cours…')}
                  </>
                ) : (
                  <>
                    {t('Create my account', 'Créer mon compte')}
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
                </form>

                <div className="mt-8 pt-6 border-t border-bone/5">
                  <Link
                    to="/login"
                    className="font-mono text-[11px] tracking-[0.04em] uppercase text-bone-3 hover:text-brass transition-colors"
                  >
                    {t(
                      'Already have an account? Sign in →',
                      'Déjà un compte ? Se connecter →',
                    )}
                  </Link>
                </div>
            </>
            )}
          </div>
        </div>

        <div className="px-6 lg:px-12 pb-6">
          <p className="font-mono text-[10px] tracking-eyebrow uppercase text-bone-4">
            © MMXXVI · Samhatit Consulting
          </p>
        </div>
      </section>
    </div>
  );
}

export default function SignupPage() {
  return (
    <LangProvider>
      <SignupInner />
    </LangProvider>
  );
}
