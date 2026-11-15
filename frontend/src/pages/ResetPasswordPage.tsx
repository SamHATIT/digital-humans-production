// 15/11/2026 — Mot de passe oublie : une page, deux etapes.
//   /forgot-password            -> saisie de l'adresse, envoi du lien
//   /reset-password?token=...   -> choix du nouveau mot de passe
// Meme habillage que la connexion. La reponse a la demande est identique que
// le compte existe ou non (anti-enumeration, cote serveur).
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, Loader2, ArrowRight, CheckCircle2 } from 'lucide-react';
import { auth } from '../services/api';
import { LangProvider, useLang } from '../contexts/LangContext';
import LangToggle from '../components/layout/LangToggle';

const champ =
  'w-full bg-ink-3 border border-bone/10 focus:border-brass focus:outline-none px-4 py-3 text-bone placeholder-bone-4 font-mono text-sm transition-colors';
const etiquette = 'block font-mono text-[10px] tracking-eyebrow uppercase text-bone-3 mb-2';
const bouton =
  'w-full inline-flex items-center justify-center gap-2 bg-brass hover:bg-brass-2 disabled:bg-brass-3 disabled:cursor-not-allowed text-ink py-3 font-mono text-[12px] tracking-cta uppercase transition-colors';

function Alerte({ texte }: { texte: string }) {
  return (
    <div role="alert" className="flex items-start gap-3 bg-ink-3 border border-error/40 px-4 py-3">
      <AlertTriangle className="w-4 h-4 text-error mt-[2px] shrink-0" />
      <p className="font-mono text-[11px] tracking-[0.04em] uppercase text-bone-2 leading-relaxed">{texte}</p>
    </div>
  );
}

function Succes({ texte }: { texte: string }) {
  return (
    <div role="status" className="flex items-start gap-3 bg-ink-3 border border-brass/40 px-4 py-3">
      <CheckCircle2 className="w-4 h-4 text-brass mt-[2px] shrink-0" />
      <p className="font-mono text-[11px] tracking-[0.04em] uppercase text-bone-2 leading-relaxed">{texte}</p>
    </div>
  );
}

function ResetInner() {
  const { t, lang } = useLang();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const jeton = params.get('token') || '';

  const [email, setEmail] = useState('');
  const [motDePasse, setMotDePasse] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState('');
  const [fait, setFait] = useState(false);

  const tropCourt = motDePasse.length > 0 && motDePasse.length < 8;
  const different = confirmation.length > 0 && motDePasse !== confirmation;

  const demander = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setErreur(''); setEnCours(true);
    try {
      await auth.passwordResetRequest(email.trim(), lang === 'en' ? 'en' : 'fr');
      setFait(true);
    } catch {
      setErreur(t('Something went wrong. Please try again in a minute.', 'Un problème est survenu. Réessayez dans une minute.'));
    } finally { setEnCours(false); }
  };

  const confirmer = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (tropCourt || different || motDePasse.length < 8) return;
    setErreur(''); setEnCours(true);
    try {
      await auth.passwordResetConfirm(jeton, motDePasse);
      setFait(true);
      setTimeout(() => navigate('/login'), 2500);
    } catch {
      setErreur(t(
        'This link is invalid, expired or already used. Ask for a new one.',
        'Ce lien est invalide, expiré ou déjà utilisé. Demandez-en un nouveau.',
      ));
    } finally { setEnCours(false); }
  };

  return (
    <div className="min-h-screen bg-ink text-bone flex flex-col">
      <div className="flex justify-end p-6"><LangToggle /></div>
      <main className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-md">
          <p className="font-mono text-[11px] tracking-eyebrow uppercase text-bone-3">
            {jeton ? t('New password', 'Nouveau mot de passe') : t('Forgot password', 'Mot de passe oublié')}
          </p>
          <h1 className="mt-3 font-serif italic text-3xl text-bone leading-tight">Digital · Humans</h1>

          {!jeton && (
            <form className="mt-8 space-y-5" onSubmit={demander} noValidate>
              {erreur && <Alerte texte={erreur} />}
              {fait ? (
                <Succes texte={t(
                  'If an account exists for this address, a link valid for 30 minutes is on its way.',
                  'Si un compte existe pour cette adresse, un lien valable 30 minutes vient de partir.',
                )} />
              ) : (
                <>
                  <div>
                    <label htmlFor="email" className={etiquette}>{t('Email', 'Adresse e-mail')}</label>
                    <input id="email" type="email" autoComplete="email" required value={email}
                      onChange={(e) => setEmail(e.target.value)} className={champ} placeholder="you@studio.com" />
                  </div>
                  <button type="submit" disabled={enCours || !email.includes('@')} className={bouton}>
                    {enCours ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                    {t('Send me a link', 'Recevoir un lien')}
                  </button>
                </>
              )}
            </form>
          )}

          {jeton && (
            <form className="mt-8 space-y-5" onSubmit={confirmer} noValidate>
              {erreur && <Alerte texte={erreur} />}
              {fait ? (
                <Succes texte={t('Password changed. Redirecting to sign in…', 'Mot de passe changé. Retour à la connexion…')} />
              ) : (
                <>
                  <div>
                    <label htmlFor="password" className={etiquette}>{t('New password', 'Nouveau mot de passe')}</label>
                    <input id="password" type="password" autoComplete="new-password" required minLength={8}
                      aria-describedby="password-regle" value={motDePasse}
                      onChange={(e) => setMotDePasse(e.target.value)} className={champ} />
                    <p id="password-regle" className={`mt-2 font-mono text-[10px] tracking-[0.04em] uppercase ${tropCourt ? 'text-error' : 'text-bone-4'}`}>
                      {t('8 characters minimum', 'Minimum 8 caractères')}
                    </p>
                  </div>
                  <div>
                    <label htmlFor="confirm" className={etiquette}>{t('Confirm', 'Confirmer')}</label>
                    <input id="confirm" type="password" autoComplete="new-password" required value={confirmation}
                      onChange={(e) => setConfirmation(e.target.value)} className={champ} />
                    {different && (
                      <p className="mt-2 font-mono text-[10px] tracking-[0.04em] uppercase text-error">
                        {t('Passwords do not match', 'Les mots de passe ne correspondent pas')}
                      </p>
                    )}
                  </div>
                  <button type="submit" disabled={enCours || tropCourt || different || motDePasse.length < 8} className={bouton}>
                    {enCours ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                    {t('Change my password', 'Changer mon mot de passe')}
                  </button>
                </>
              )}
            </form>
          )}

          <div className="mt-8 pt-6 border-t border-bone/5">
            <Link to="/login" className="block font-mono text-[11px] tracking-[0.04em] uppercase text-bone-3 hover:text-brass transition-colors">
              {t('← Back to sign in', '← Retour à la connexion')}
            </Link>
            {jeton && (
              <Link to="/forgot-password" className="block mt-3 font-mono text-[10px] tracking-[0.04em] uppercase text-bone-4 hover:text-bone-3 transition-colors">
                {t('Ask for a new link', 'Demander un nouveau lien')}
              </Link>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <LangProvider>
      <ResetInner />
    </LangProvider>
  );
}
