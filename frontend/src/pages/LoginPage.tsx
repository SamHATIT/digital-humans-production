import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, Loader2, ArrowRight } from 'lucide-react';
import { auth } from '../services/api';
import { LangProvider, useLang } from '../contexts/LangContext';
import LangToggle from '../components/layout/LangToggle';

function LoginInner() {
  const navigate = useNavigate();
  const { t } = useLang();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      await auth.login(email, password);
      navigate('/');
    } catch (err) {
      const message = err instanceof Error ? err.message : t(
        'Login failed. Please check your credentials.',
        'Échec de connexion. Vérifiez vos identifiants.',
      );
      setError(message);
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
          style={{ backgroundImage: "url('/covers/dispatch-logifleet.jpg')" }}
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
            № 01 · Studio
          </p>
          <p className="mt-3 font-serif italic text-3xl text-bone leading-tight max-w-md">
            Digital · Humans
          </p>
        </div>

        <div className="relative max-w-md">
          <p className="font-serif italic text-2xl text-bone-2 leading-snug">
            {t(
              '"The eleven agents perform — you direct."',
              '"Les onze agents exécutent — vous dirigez."',
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
          <div className="w-full max-w-[400px] bg-ink-2 border border-bone/5 px-8 py-10">
            <div className="mb-8">
              <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
                {t('Welcome back · Sign in', 'Heureux de vous revoir · Connexion')}
              </p>
              <h1 className="mt-3 font-serif italic text-3xl text-bone">
                Digital · Humans
              </h1>
              <p className="mt-2 font-mono text-[11px] tracking-eyebrow uppercase text-bone-4">
                Studio Console · v5.1
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
                  className="w-full bg-ink-3 border border-bone/10 focus:border-brass focus:outline-none px-4 py-3 text-bone placeholder-bone-4 font-mono text-sm transition-colors"
                  placeholder="you@studio.com"
                />
              </div>

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
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full bg-ink-3 border border-bone/10 focus:border-brass focus:outline-none px-4 py-3 text-bone placeholder-bone-4 font-mono text-sm transition-colors"
                  placeholder="••••••••"
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full inline-flex items-center justify-center gap-2 bg-brass hover:bg-brass-2 disabled:bg-brass-3 disabled:cursor-not-allowed text-ink py-3 font-mono text-[12px] tracking-cta uppercase transition-colors"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    {t('Signing in…', 'Connexion en cours…')}
                  </>
                ) : (
                  <>
                    {t('Enter the studio', 'Entrer dans le studio')}
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            <div className="mt-8 pt-6 border-t border-bone/5">
              <Link
                to="/signup"
                className="block font-mono text-[11px] tracking-[0.04em] uppercase text-bone-3 hover:text-brass transition-colors"
              >
                {t(
                  "Don't have an account? Open your studio →",
                  "Pas encore de compte ? Ouvrir votre studio →",
                )}
              </Link>
              <a
                href="mailto:[email protected]?subject=Enterprise%20access%20request"
                className="block mt-3 font-mono text-[10px] tracking-[0.04em] uppercase text-bone-4 hover:text-bone-3 transition-colors"
              >
                {t(
                  "— or request enterprise access",
                  "— ou demander un accès Entreprise",
                )}
              </a>
            </div>
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

export default function LoginPage() {
  return (
    <LangProvider>
      <LoginInner />
    </LangProvider>
  );
}
